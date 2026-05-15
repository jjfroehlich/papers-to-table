from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_optimizer.contracts import Candidate
from paper_optimizer.propose import propose_candidates
from paper_optimizer.search_space import load_search_space
from paper_optimizer.settings import ConfigError, load_config

REQUIRED_COMPARE_MODELS = {
    "unsloth/gemma-4-26b-a4b-it",
    "openai/gpt-oss-20b",
    "google/gemma-4-e4b",
    "mistralai/ministral-3-14b-reasoning",
    "unsloth/qwen3.6-27b",
    "unsloth/qwen3.6-35b-a3b",
    "qwen/qwen3.6-35b-a3b",
    "qwen/qwen3.6-27b",
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
        "optimize_parameter_sweeps.json",
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
        assert cfg["optimize"]["suite_id"] in suites
        if "holdout_suite_id" in cfg["compare"]:
            assert cfg["compare"]["holdout_suite_id"] in suites
        if "holdout_suite_id" in cfg["optimize"]:
            assert cfg["optimize"]["holdout_suite_id"] in suites


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
    config_names = [
        "compare_models.json",
        "optimize_parameter_sweeps.json",
    ]

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
    assert "google/gemma-4-26b-a4b" not in all_models
    assert "nvidia/nemotron-3-nano-4b" not in all_models
    assert "nvidia/nemotron-3-nano-omni" not in all_models
    assert "qwen/qwen3.5-9b" not in all_models
    assert "qwen/qwen3.6-35b-a3b" in all_models
    assert "qwen/qwen3.6-27b" in all_models
    assert "unsloth/qwen3.6-35b-a3b" in all_models
    assert payload["baseline_candidate"]["text_model_id"] == "unsloth/gemma-4-26b-a4b-it"
    for candidate in [payload["baseline_candidate"], *payload["compare_candidates"]]:
        knobs = candidate["optimizer_knobs"]
        assert knobs["retrieval_mode"] == "hybrid_experimental"
        assert knobs["retrieval_top_k"] == 12
        assert knobs["recall_rescue_enabled"] is False
        assert knobs["whole_document_mode"] is False
        assert MODEL_PROFILE_MANAGED_KNOBS.isdisjoint(knobs)


def test_compare_models_config_runs_triplicate() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_models.json").read_text(encoding="utf-8"))

    assert payload["replicates"]["count"] == 3


def test_compare_prompts_tracks_three_prompt_bundles() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_prompts.json").read_text(encoding="utf-8"))

    prompt_ids = {candidate["prompt_bundle_id"] for candidate in payload["compare_candidates"]}
    assert prompt_ids == {"default", "context_balanced", "checklist_guided"}
    assert set(payload["search_space"]["prompt_bundle_ids"]) == prompt_ids


def test_full_benchmark_compare_phases_run_triplicate_with_figure_review() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for config_name in ["compare_models.json", "compare_prompts.json", "compare_retrieval_parameters.json"]:
        payload = json.loads((repo_root / "configs" / config_name).read_text(encoding="utf-8"))
        assert payload["replicates"]["count"] == 3
        for candidate in [payload["baseline_candidate"], *payload.get("compare_candidates", [])]:
            assert candidate["optimizer_knobs"]["figure_review_enabled"] is True


def test_extraction_feature_config_runs_triplicate_factorial() -> None:
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
    assert len(feature_sets) == 8


def test_full_benchmark_optimize_stage_is_top_k_focused_on_gemma_26b() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "optimize_parameter_sweeps.json").read_text(encoding="utf-8"))
    knobs = payload["baseline_candidate"]["optimizer_knobs"]

    assert payload["baseline_candidate"]["text_model_id"] == "google/gemma-4-26b-a4b"
    assert payload["search_space"]["text_model_ids"] == ["google/gemma-4-26b-a4b"]
    assert set(payload["search_space"]["numeric_knobs"]) == {"retrieval_top_k"}
    assert payload["search_space"]["numeric_knobs"]["retrieval_top_k"]["values"] == [12, 14]
    assert payload["optimize"]["rounds"] == 1
    assert payload["optimize"]["batch_size"] == 2
    assert payload["replicates"]["count"] == 3
    assert knobs["retrieval_mode"] == "hybrid_experimental"
    assert knobs["retrieval_top_k"] == 12
    assert knobs["recall_rescue_enabled"] is False
    assert knobs["whole_document_mode"] is False


def test_full_benchmark_stage_run_names_are_path_length_safe() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = (repo_root / "scripts" / "full_benchmark.sh").read_text(encoding="utf-8")

    assert 'compare_run_name="${session_id}_fb_model"' in script
    assert 'prompt_run_name="${session_id}_fb_prompt"' in script
    assert 'retrieval_parameter_run_name="${session_id}_fb_retrieval"' in script
    assert 'extraction_feature_run_name="${session_id}_fb_features"' in script
    assert 'optimize_run_name="${session_id}_fb_optimize"' in script
    assert "compare_retrieval_parameters_${safe_label}" not in script


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
