from __future__ import annotations

from pathlib import Path

from paper_optimizer.bundle import build_candidate_from_dict
from paper_optimizer.pipeline import evaluate_candidate_once


def test_single_candidate_pipeline(base_config: dict, tmp_path: Path) -> None:
    candidate = build_candidate_from_dict(
        "cand_0001",
        {
            "prompt_bundle_id": "prompt_a",
            "text_model_id": "text-model-a",
            "vision_model_id": None,
            "optimizer_knobs": {"retrieval_top_k": 5},
        },
        parent_candidate_id=None,
        round_index=None,
    )

    result = evaluate_candidate_once(
        base_config,
        experiment_dir=tmp_path / "exp",
        candidate=candidate,
        benchmark_id="bench_dev",
        study_type="compare",
        decision="not_promoted",
        reason="test",
    )

    assert result.candidate_id == "cand_0001"
    assert "correctness" in result.primary_metrics
    assert result.main_app_run_ref.get("run_id") == "run_cand_0001"
