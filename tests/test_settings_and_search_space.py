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
