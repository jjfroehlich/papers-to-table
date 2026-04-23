from __future__ import annotations

import json
from pathlib import Path

import pytest

from paper_optimizer.contracts import Candidate
from paper_optimizer.propose import propose_candidates
from paper_optimizer.search_space import load_search_space
from paper_optimizer.settings import ConfigError, load_config


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
        "compare_models_smoke.json",
        "compare_models_dev.json",
        "compare_models_overnight.json",
        "compare_prompts_dev.json",
        "compare_retrieval_dev.json",
        "compare_retrieval_modes_dev.json",
        "optimize_overnight.json",
    ]

    for config_name in config_names:
        payload = json.loads((repo_root / "configs" / config_name).read_text(encoding="utf-8"))
        assert payload["acceptance"]["degraded_score_policy"] == "disallow"
        if "compare_candidates" in payload:
            assert payload["compare"]["require_structured_output_for_extraction"] is True
            assert payload["compare"]["allow_degraded_candidates"] is False


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
            assert judge_b == "mistralai/ministral-3-14b-reasoning"


def test_compare_models_smoke_is_tiny_and_fast_by_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = json.loads((repo_root / "configs" / "compare_models_smoke.json").read_text(encoding="utf-8"))
    bench = payload["benchmarks"]["manifests"][payload["benchmarks"]["smoke"]]

    assert len(payload["compare_candidates"]) == 2
    assert bench["expected_items"] == 3
    assert bench["table_path"] == "benchmarks/smoke_fixture_table.csv"
    assert bench["gold_path"] == "benchmarks/smoke_fixture_table.csv"
    assert bench["schema_path"] == "benchmarks/smoke_fixture_schema.csv"


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
