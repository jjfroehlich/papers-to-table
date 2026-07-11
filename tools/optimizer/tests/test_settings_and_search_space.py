from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_optimizer.contracts import Candidate
from paper_optimizer.propose import propose_candidates
from paper_optimizer.search_space import load_search_space
from paper_optimizer.settings import ConfigError, load_config, validate_config
from paper_optimizer.utils import EXTERNAL_CANDIDATE_ID_MAX_LENGTH, SAFE_IDENTIFIER_RE

REQUIRED_COMPARE_MODELS = {
    "openai/gpt-oss-20b",
    "google/gemma-4-e4b",
    "google/gemma-4-12b",
    "google/gemma-4-12b-qat",
    "google/gemma-4-26b-a4b",
    "mistralai/ministral-3-14b-reasoning",
    "nvidia/nemotron-3-nano-omni",
    "nuextract3",
    "qwen/qwen3.6-27b",
    "qwen3.6-27b-mtp",
    "zai-org/glm-4.6v-flash",
}

MODEL_PROFILE_MANAGED_KNOBS = {
    "text_temperature",
    "text_max_tokens",
    "text_top_p",
    "text_top_k",
    "text_min_p",
    "text_presence_penalty",
    "text_repetition_penalty",
    "text_extra_body",
    "text_chat_template_kwargs",
    "vision_temperature",
    "vision_max_tokens",
    "vision_top_p",
    "vision_top_k",
    "vision_min_p",
    "vision_presence_penalty",
    "vision_repetition_penalty",
    "vision_extra_body",
    "vision_chat_template_kwargs",
}


def test_load_config_success(config_path: Path) -> None:
    cfg = load_config(config_path)
    assert cfg["schema_version"] == "1.0"
    assert cfg["experiment_id"] == "exp_test"


def test_load_config_missing_required(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad)


def test_load_config_rejects_invalid_degraded_score_policy(config_path: Path) -> None:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    payload["acceptance"]["degraded_score_policy"] = "maybe"
    config_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_load_search_space_success(base_config: dict) -> None:
    ss = load_search_space(base_config)
    assert "retrieval_top_k" in ss.numeric_knobs
    assert ss.numeric_knobs["retrieval_top_k"] == [6]


def test_checked_in_planned_configs_disallow_degraded_scores() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_names = [
        "compare_models_contract_smoke.json",
        "compare_models.json",
        "compare_prompts.json",
        "compare_retrieval_parameters.json",
        "compare_extraction_features.json",
    ]

    for config_name in config_names:
        payload = json.loads((repo_root / "configs" / config_name).read_text(encoding="utf-8"))
        assert payload["acceptance"]["degraded_score_policy"] == "disallow"
        if "compare_candidates" in payload:
            assert payload["compare"]["require_structured_output_for_extraction"] is True
            assert payload["compare"]["allow_degraded_candidates"] is False


def test_checked_in_configs_use_explicit_suites_and_replicates() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for path in (repo_root / "configs").glob("*.json"):
        cfg = load_config(path)
        suites = cfg["benchmark_suites"]
        assert suites
        assert cfg["replicates"]["count"] >= 1
        assert isinstance(cfg["replicates"]["continue_on_failure"], bool)
        for suite_id, suite in suites.items():
            assert suite["benchmark_ids"]
            assert suite["aggregation"]["method"] == "weighted_mean"
            assert suite["aggregation"]["primary_metric"] == cfg["acceptance"]["primary_metric"]
            assert set(suite["aggregation"]["weights"]).issubset(set(suite["benchmark_ids"]))
        assert cfg["compare"]["suite_id"] in suites
        if "holdout_suite_id" in cfg["compare"]:
            assert cfg["compare"]["holdout_suite_id"] in suites


def test_checked_in_planned_configs_pin_non_gemma_non_qwen_judge_b() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for path in (repo_root / "configs").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifests = (payload.get("benchmarks") or {}).get("manifests") or {}
        for manifest in manifests.values():
            eval_args = manifest.get("eval_args")
            if not isinstance(eval_args, list) or "--judge-model-b" not in eval_args:
                continue
            judge_b = eval_args[eval_args.index("--judge-model-b") + 1]
            assert judge_b == "openai/gpt-oss-20b"


def test_compare_models_contract_smoke_is_tiny_and_fast_by_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_models_contract_smoke.json").read_text(encoding="utf-8"))
    bench = payload["benchmarks"]["manifests"][payload["benchmarks"]["smoke"]]

    assert len(payload["compare_candidates"]) == 2
    assert bench["expected_items"] == 3
    assert bench["table_path"] == "benchmarks/smoke_fixture_table.csv"
    assert bench["gold_path"] == "benchmarks/smoke_fixture_table.csv"
    assert bench["schema_path"] == "benchmarks/smoke_fixture_schema.csv"


def test_real_benchmark_configs_use_real_inputs_and_dual_judges() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_names = ["compare_models.json"]

    for config_name in config_names:
        payload = json.loads((repo_root / "configs" / config_name).read_text(encoding="utf-8"))
        dev_ids = payload["benchmark_suites"]["dev_suite"]["benchmark_ids"]
        assert dev_ids == [
            "bench_massively_parallel_reporter_assays",
            "bench_genome_editing",
            "bench_spatial_transcriptomics",
        ]

        for benchmark_id in dev_ids:
            dev_manifest = payload["benchmarks"]["manifests"][benchmark_id]
            assert dev_manifest["require_non_fixture_inputs"] is True
            assert dev_manifest["benchmark_kind"].startswith("real_external")
            assert "app/tests/fixtures" not in dev_manifest["table_path"].replace("\\", "/")
            assert "benchmarks/smoke_fixture" not in dev_manifest["table_path"].replace("\\", "/")
            assert dev_manifest["expected_items"] == 5
            assert {"judge_a", "judge_b"}.issubset(set(dev_manifest["required_judges"]))
            assert "--judge-model" in dev_manifest["eval_args"]
            assert "--judge-model-b" in dev_manifest["eval_args"]


def test_compare_models_external_results_use_path_safe_candidate_ids() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_path = repo_root / "configs" / "compare_models.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    dev_ids = payload["benchmark_suites"]["dev_suite"]["benchmark_ids"]
    ids_by_label: dict[str, str] = {}

    for benchmark_id in dev_ids:
        external_results = payload["benchmarks"]["manifests"][benchmark_id]["external_results"]
        for result in external_results:
            candidate_id = result.get("candidate_id")
            assert isinstance(candidate_id, str)
            assert len(candidate_id) <= EXTERNAL_CANDIDATE_ID_MAX_LENGTH
            assert SAFE_IDENTIFIER_RE.fullmatch(candidate_id)
            prior = ids_by_label.setdefault(result["label"], candidate_id)
            assert prior == candidate_id
            for replicate in result["replicates"]:
                assert (config_path.parent / replicate["path"]).resolve().exists()

    assert ids_by_label == {
        "codex_gpt_pro_5_5_extra_high": "ext_codex",
        "codex_gpt_pro_5_5_extra_high_jjfroehlich_papers_to_table_agent_kit": "ext_agentkit",
        "codex_gpt_pro_5_5_extra_high_jkitchin_scientific_data_extraction": "ext_kitchin",
        "gold_cross_field_negative_control": "ext_gold_cross_field",
        "gold_positive_control": "ext_gold",
        "gold_word_shuffle_negative_control": "ext_gold_word_shuffle",
    }


def test_external_result_candidate_id_must_be_path_safe() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_models.json").read_text(encoding="utf-8"))
    payload["benchmarks"]["manifests"]["bench_massively_parallel_reporter_assays"]["external_results"][0][
        "candidate_id"
    ] = "not path safe"

    with pytest.raises(ConfigError, match="path-safe"):
        validate_config(payload)


def test_external_result_candidate_id_length_is_bounded() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_models.json").read_text(encoding="utf-8"))
    payload["benchmarks"]["manifests"]["bench_massively_parallel_reporter_assays"]["external_results"][0][
        "candidate_id"
    ] = "x" * (EXTERNAL_CANDIDATE_ID_MAX_LENGTH + 1)

    with pytest.raises(ConfigError, match="at most"):
        validate_config(payload)


def test_compare_models_tracks_requested_model_set() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_models.json").read_text(encoding="utf-8"))

    all_models = {payload["baseline_candidate"]["text_model_id"]} | {
        candidate["text_model_id"] for candidate in payload["compare_candidates"]
    }
    compared_models = {candidate["text_model_id"] for candidate in payload["compare_candidates"]}
    search_models = set(payload["search_space"]["text_model_ids"])

    assert all_models == REQUIRED_COMPARE_MODELS
    assert compared_models == REQUIRED_COMPARE_MODELS
    assert search_models == REQUIRED_COMPARE_MODELS
    assert "nvidia/nemotron-3-nano-4b" not in all_models
    assert "qwen/qwen3.5-9b" not in all_models
    assert "unsloth/gemma-4-26b-a4b-it" not in all_models
    assert "unsloth/qwen3.6-27b" not in all_models
    assert "qwen/qwen3.6-35b-a3b" not in all_models
    assert "unsloth/qwen3.6-35b-a3b" not in all_models
    assert "qwen/qwen3.6-27b" in all_models
    assert "google/gemma-4-12b" in all_models
    assert "google/gemma-4-12b-qat" in all_models
    assert "google/gemma-4-26b-a4b" in all_models
    assert "nvidia/nemotron-3-nano-omni" in all_models
    assert "nuextract3" in all_models
    assert "qwen3.6-27b-mtp" in all_models
    assert payload["baseline_candidate"]["text_model_id"] == "google/gemma-4-e4b"
    assert payload["baseline_candidate"]["vision_model_id"] == "google/gemma-4-e4b"
    for candidate in [payload["baseline_candidate"], *payload["compare_candidates"]]:
        knobs = candidate["optimizer_knobs"]
        assert knobs["retrieval_mode"] == "hybrid_experimental"
        assert knobs["retrieval_top_k"] == 12
        assert knobs["recall_rescue_enabled"] is False
        assert knobs["whole_document_mode"] is False
        assert MODEL_PROFILE_MANAGED_KNOBS.isdisjoint(knobs)

        if candidate["text_model_id"] == "openai/gpt-oss-20b":
            assert candidate["vision_model_id"] == "google/gemma-4-e4b"
        else:
            assert candidate["vision_model_id"] == candidate["text_model_id"]


def test_compare_models_config_runs_triplicate() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_models.json").read_text(encoding="utf-8"))

    assert payload["replicates"]["count"] == 3


def test_compare_prompts_tracks_bounded_prompt_bundles() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_prompts.json").read_text(encoding="utf-8"))

    prompt_ids = {candidate["prompt_bundle_id"] for candidate in payload["compare_candidates"]}
    assert prompt_ids == {"default", "checklist_guided"}
    assert set(payload["search_space"]["prompt_bundle_ids"]) == prompt_ids


def test_compare_retrieval_parameters_tracks_bounded_retrieval_candidates() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_retrieval_parameters.json").read_text(encoding="utf-8"))

    retrieval_pairs = {
        (candidate["optimizer_knobs"]["retrieval_mode"], candidate["optimizer_knobs"]["retrieval_top_k"])
        for candidate in payload["compare_candidates"]
    }
    assert retrieval_pairs == {("hybrid_experimental", 8), ("lexical", 12)}
    assert payload["search_space"]["numeric_knobs"]["retrieval_top_k"]["values"] == [8, 12]


def test_full_benchmark_compare_phases_run_triplicate_with_bounded_vision_cost() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    model_payload = json.loads((repo_root / "configs" / "compare_models.json").read_text(encoding="utf-8"))
    assert model_payload["replicates"]["count"] == 3
    for candidate in [model_payload["baseline_candidate"], *model_payload.get("compare_candidates", [])]:
        assert candidate["optimizer_knobs"]["figure_review_enabled"] is True

    for config_name in ["compare_prompts.json", "compare_retrieval_parameters.json"]:
        payload = json.loads((repo_root / "configs" / config_name).read_text(encoding="utf-8"))
        assert payload["replicates"]["count"] == 3
        for candidate in [payload["baseline_candidate"], *payload.get("compare_candidates", [])]:
            assert candidate["optimizer_knobs"]["figure_review_enabled"] is False


def test_extraction_feature_config_runs_triplicate_bounded_feature_comparison() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_extraction_features.json").read_text(encoding="utf-8"))

    assert payload["experiment_id"] == "compare_extraction_features"
    assert payload["replicates"]["count"] == 3
    feature_sets = {
        (
            candidate["optimizer_knobs"]["recall_rescue_enabled"],
            candidate["optimizer_knobs"]["whole_document_mode"],
            candidate["optimizer_knobs"]["figure_review_enabled"],
        )
        for candidate in payload["compare_candidates"]
    }
    assert feature_sets == {
        (True, False, False),
        (True, True, False),
        (True, False, True),
    }


def test_full_benchmark_stage_run_names_are_path_length_safe() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "full_benchmark.sh").read_text(encoding="utf-8")

    assert 'compare_run_name="${session_id}_fb_model"' in script
    assert 'prompt_run_name="${session_id}_fb_prompt"' in script
    assert 'retrieval_parameter_run_name="${session_id}_fb_retrieval"' in script
    assert 'extraction_feature_run_name="${session_id}_fb_features"' in script
    assert 'materialize_extraction_feature_config "$extraction_feature_config" "$(resolve_results_jsonl "$retrieval_parameter_run_name")" "$extraction_feature_config_materialized" 1' in script
    assert "fb_optimize" not in script
    assert "compare_retrieval_parameters_${safe_label}" not in script


def test_full_benchmark_supports_run_local_initial_model_filter() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "full_benchmark.sh").read_text(encoding="utf-8")
    wrapper = (repo_root.parents[1] / "scripts" / "papers_to_table.py").read_text(encoding="utf-8")

    assert "--initial-model" in script
    assert "materialize_initial_model_config" in script
    assert "resolve_path_fields(config)" in script
    assert 'compare_config_materialized="$tmp_dir/compare_models.json"' in script
    assert 'config["compare_candidates"] = [deepcopy(selected)]' in script
    assert 'payload["initial_model_filter"] = {"text_model_id": initial_model}' in script
    assert "full_benchmark.add_argument(" in wrapper
    assert "--initial-model" in wrapper


def test_compare_models_supports_run_local_initial_model_filter() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "compare_models.sh").read_text(encoding="utf-8")
    wrapper = (repo_root.parents[1] / "scripts" / "papers_to_table.py").read_text(encoding="utf-8")

    assert "--initial-model" in script
    assert "materialize_initial_model_config" in script
    assert "resolve_path_fields(config)" in script
    assert 'materialized_dir="$overnight_dir/materialized_configs"' in script
    assert 'compare_config="$materialized_dir/compare_models.json"' in script
    assert 'config["compare_candidates"] = [deepcopy(selected)]' in script
    assert 'payload["initial_model_filter"] = {"text_model_id": initial_model}' in script
    assert 'optimizer_sub.add_parser("compare-models"' in wrapper
    assert "--initial-model" in wrapper


def test_wrapper_exposes_optimizer_dev_check_shortcut() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    wrapper = (repo_root.parents[1] / "scripts" / "papers_to_table.py").read_text(encoding="utf-8")
    docs = (repo_root.parents[1] / "docs" / "tools" / "optimizer.md").read_text(encoding="utf-8")

    assert 'optimizer_sub.add_parser(\n        "dev-check"' in wrapper
    assert 'default="google/gemma-4-e4b"' in wrapper
    assert 'default="bench_genome_editing"' in wrapper
    assert '"aggregation": {' in wrapper
    assert '"primary_metric": "content_correctness"' in wrapper
    assert "_resolve_optimizer_config_paths(config, source_config=source_config)" in wrapper
    assert "_remove_external_results(config)" in wrapper
    assert "dev-check" in docs
    assert "bench_genome_editing" in docs


def test_propose_candidates_covers_multi_knob_combinations() -> None:
    incumbent = Candidate(
        candidate_id="cand_0000",
        prompt_bundle_id="default",
        text_model_id="text-model-a",
        vision_model_id=None,
        optimizer_knobs={"retrieval_top_k": 6, "temperature": 0.0},
        parent_candidate_id=None,
        round_index=0,
    )
    search_space = load_search_space(
        {
            "search_space": {
                "prompt_bundle_ids": [],
                "text_model_ids": [],
                "vision_model_ids": [],
                "numeric_knobs": {
                    "retrieval_top_k": {"values": [6, 8]},
                    "temperature": {"values": [0.0, 0.2]},
                },
            }
        }
    )

    proposals = propose_candidates(
        incumbent,
        search_space=search_space,
        round_index=1,
        batch_size=10,
        next_candidate_number_start=1,
    )

    knob_pairs = {(item.optimizer_knobs["retrieval_top_k"], item.optimizer_knobs["temperature"]) for item in proposals}
    assert (8, 0.2) in knob_pairs
