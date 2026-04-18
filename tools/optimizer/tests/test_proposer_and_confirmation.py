from __future__ import annotations

import json
from pathlib import Path

from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.contracts import Candidate, CandidateResult, ProposerResponse
from paper_optimizer.proposer import build_proposer_request, collect_proposer_candidates
from paper_optimizer.search_space import load_search_space
from paper_optimizer.study import run_optimize_mode


def _result_for_candidate(
    base_config: dict,
    candidate: Candidate,
    *,
    score: float,
    decision: str,
    reason: str,
) -> CandidateResult:
    return CandidateResult(
        schema_version=str(base_config["schema_version"]),
        experiment_id=str(base_config["experiment_id"]),
        study_type="optimize",
        benchmark_id="bench_dev",
        candidate_id=candidate.candidate_id,
        parent_candidate_id=candidate.parent_candidate_id,
        round_index=candidate.round_index,
        candidate_hash=f"hash-{candidate.candidate_id}",
        candidate_manifest_path=f"/tmp/{candidate.candidate_id}.json",
        candidate_bundle_dir=f"/tmp/{candidate.candidate_id}",
        prompt_bundle_id=candidate.prompt_bundle_id,
        text_model_id=candidate.text_model_id,
        vision_model_id=candidate.vision_model_id,
        optimizer_knobs_flat=dict(candidate.optimizer_knobs),
        primary_metrics={"correctness": score},
        guardrail_metrics={"evidence_quality": 0.9, "null_count": 0.0, "failure_count": 0.0, "runtime_seconds": 10.0},
        diagnostic_metrics={},
        scored=True,
        score_status="scored",
        runtime_seconds=10.0,
        runtime_metadata={"main_app_duration_seconds": 5.0, "eval_duration_seconds": 5.0, "total_duration_seconds": 10.0},
        started_at="",
        ended_at="",
        candidate_status="completed",
        promotion_decision=decision,
        decision_reason=reason,
        main_app_run_ref={},
        eval_output_ref={},
        metadata={"deterministic_gate": {"stage": "acceptance", "passed": True, "failures": []}},
    )


def test_build_proposer_request_stays_within_search_surface(base_config: dict) -> None:
    incumbent = Candidate(
        candidate_id="cand_0000",
        prompt_bundle_id=base_config["baseline_candidate"]["prompt_bundle_id"],
        text_model_id=base_config["baseline_candidate"]["text_model_id"],
        vision_model_id=base_config["baseline_candidate"]["vision_model_id"],
        optimizer_knobs=dict(base_config["baseline_candidate"]["optimizer_knobs"]),
    )
    search_space = load_search_space(base_config)

    request_payload = build_proposer_request(
        incumbent,
        search_space=search_space,
        round_index=1,
        max_candidates=2,
    ).to_dict()

    assert request_payload["max_candidates"] == 2
    assert request_payload["incumbent"]["text_model_id"] == "text-model-a"
    assert "default" in request_payload["allowed_prompt_bundle_ids"]
    assert "text-model-b" in request_payload["allowed_text_model_ids"]
    assert request_payload["allowed_numeric_knobs"]["retrieval_top_k"] == [6]


def test_collect_proposer_candidates_rejects_invalid_and_duplicate_outputs(
    base_config: dict,
    tmp_path: Path,
    monkeypatch,
) -> None:
    base_config["proposer"] = {
        "enabled": True,
        "provider": "lm_studio",
        "model_id": "qwen/qwen3.5-35b-a3b",
        "api_base": "http://127.0.0.1:1234/v1",
        "max_candidates": 3,
    }
    base_config["search_space"]["numeric_knobs"]["retrieval_top_k"] = {"values": [6, 8]}
    incumbent = Candidate(
        candidate_id="cand_0000",
        prompt_bundle_id=base_config["baseline_candidate"]["prompt_bundle_id"],
        text_model_id=base_config["baseline_candidate"]["text_model_id"],
        vision_model_id=base_config["baseline_candidate"]["vision_model_id"],
        optimizer_knobs=dict(base_config["baseline_candidate"]["optimizer_knobs"]),
    )
    search_space = load_search_space(base_config)

    def _fake_call(*args, **kwargs):
        return (
            ProposerResponse(
                response_mode="json_object",
                raw_response={
                    "candidates": [
                        {"text_model_id": "text-model-b", "optimizer_knobs": {"retrieval_top_k": 8}},
                        {"text_model_id": "not-allowed"},
                        {"text_model_id": "text-model-b", "optimizer_knobs": {"retrieval_top_k": 8}},
                    ]
                },
            ),
            None,
        )

    monkeypatch.setattr("paper_optimizer.proposer._call_lm_studio_proposer", _fake_call)

    candidates = collect_proposer_candidates(
        base_config,
        incumbent=incumbent,
        search_space=search_space,
        round_index=1,
        batch_size=3,
        next_candidate_number_start=10,
        experiment_dir=tmp_path / "exp",
    )

    assert [candidate.candidate_id for candidate in candidates] == ["cand_0010"]
    assert candidates[0].text_model_id == "text-model-b"
    assert candidates[0].optimizer_knobs["retrieval_top_k"] == 8

    audit = json.loads((tmp_path / "exp" / "proposer" / "round_0001.json").read_text(encoding="utf-8"))
    assert len(audit["accepted_candidates"]) == 1
    rejection_reasons = {item["reason"] for item in audit["rejected_candidates"]}
    assert "invalid_text_model_id" in rejection_reasons
    assert "duplicate_candidate" in rejection_reasons


def test_confirmation_rerun_can_block_promotion(base_config: dict, tmp_path: Path, monkeypatch) -> None:
    base_config["optimize"] = {
        "rounds": 1,
        "batch_size": 1,
        "confirmation_reruns": {"enabled": True, "count": 1},
    }
    benches = load_benchmarks(base_config)
    search_space = load_search_space(base_config)

    challenger = Candidate(
        candidate_id="cand_0001",
        prompt_bundle_id="default",
        text_model_id="text-model-b",
        vision_model_id=None,
        optimizer_knobs={"retrieval_top_k": 6, "recall_rescue_enabled": True, "whole_document_mode": False},
        parent_candidate_id="cand_0000",
        round_index=1,
    )

    monkeypatch.setattr("paper_optimizer.study.propose_candidates", lambda *args, **kwargs: [challenger])
    monkeypatch.setattr("paper_optimizer.study.collect_proposer_candidates", lambda *args, **kwargs: [])
    monkeypatch.setattr("paper_optimizer.study.generate_optimize_plots", lambda *args, **kwargs: None)

    call_counts: dict[str, int] = {"cand_0000": 0, "cand_0001": 0}

    def _fake_evaluate(*args, **kwargs):
        candidate = kwargs["candidate"]
        call_counts[candidate.candidate_id] = call_counts.get(candidate.candidate_id, 0) + 1
        if candidate.candidate_id == "cand_0000":
            return _result_for_candidate(base_config, candidate, score=0.70, decision="incumbent", reason="baseline")
        if call_counts[candidate.candidate_id] == 1:
            return _result_for_candidate(base_config, candidate, score=0.90, decision="promoted", reason="primary_metric_improved")
        return _result_for_candidate(base_config, candidate, score=0.69, decision="confirmation_rerun", reason="confirmation_rerun")

    monkeypatch.setattr("paper_optimizer.study.evaluate_candidate_once", _fake_evaluate)

    out = tmp_path / "optimize_exp"
    run_optimize_mode(base_config, benches, search_space, out)

    best_candidate = json.loads((out / "best_candidate.json").read_text(encoding="utf-8"))
    round_summary = json.loads((out / "rounds" / "round_0001.json").read_text(encoding="utf-8"))
    confirmation = json.loads((out / "confirmation" / "round_0001_cand_0001.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))

    assert best_candidate["candidate_id"] == "cand_0000"
    assert round_summary["promoted_candidate_id"] is None
    assert confirmation["confirmed"] is False
    assert summary["confirmation_reruns"]["enabled"] is True