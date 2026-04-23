from __future__ import annotations

import csv
import json
from pathlib import Path

from paper_optimizer.plotting import generate_compare_plots
from paper_optimizer.benchmarks import load_benchmarks
from paper_optimizer.contracts import CandidateResult
from paper_optimizer.study import run_compare_mode


def test_compare_mode_outputs(base_config: dict, tmp_path: Path) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"
    run_compare_mode(base_config, benches, out)

    assert (out / "best_candidate.json").exists()
    assert (out / "compare_summary.json").exists()
    assert (out / "summary.json").exists()
    assert (out / "results" / "results.csv").exists()
    assert (out / "results" / "results.jsonl").exists()
    assert (out / "results" / "candidate_diagnostics.csv").exists()
    assert (out / "candidate_diagnostics.json").exists()
    assert (out / "plots" / "compare_primary_by_candidate.png").exists()
    assert (out / "plots" / "compare_correctness_vs_runtime.png").exists()
    assert (out / "plots" / "compare_primary_by_text_model.png").exists()
    assert (out / "plots" / "compare_primary_by_knob_retrieval_top_k.png").exists()

    best_candidate = json.loads((out / "best_candidate.json").read_text(encoding="utf-8"))
    compare_summary = json.loads((out / "compare_summary.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert best_candidate["candidate_id"]
    assert best_candidate["text_model_id"]
    assert best_candidate["prompt_bundle_id"]
    assert isinstance(best_candidate["optimizer_knobs_flat"], dict)
    assert compare_summary["winner"]["candidate_id"] == best_candidate["candidate_id"]
    assert compare_summary["candidate_count"] == 3
    assert best_candidate["progress_state"] == "completed"
    assert summary["progress_state"] == "completed"
    assert summary["eligible_winner_candidate_id"] == best_candidate["candidate_id"]
    assert summary["best_raw_candidate_id"] == best_candidate["candidate_id"]
    assert summary["provisional_winner_candidate_id"] is None

    report_html = (out / "report.html").read_text(encoding="utf-8")
    assert "Winner" in report_html
    assert "Why This Candidate Won" in report_html
    assert "Compare Semantics" in report_html
    assert "What This Shows" in report_html
    assert "How To Read It" in report_html
    assert "What To Watch For" in report_html
    assert "top_k=6" in report_html
    assert "Benchmark Winner" in report_html
    assert "Recommended Default" in report_html
    assert "Baseline" not in report_html
    assert "Promoted" not in report_html


def test_compare_report_surfaces_retrieval_settings(base_config: dict, tmp_path: Path) -> None:
    for candidate, top_k in zip(base_config["compare_candidates"], [6, 8, 10], strict=True):
        candidate["text_model_id"] = "text-model-b"
        candidate["optimizer_knobs"]["retrieval_top_k"] = top_k

    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_retrieval_exp"
    run_compare_mode(base_config, benches, out)

    report_html = (out / "report.html").read_text(encoding="utf-8")
    assert "retrieval compare" in report_html.lower()
    assert "Retrieval Signals" in report_html
    assert "Winner retrieval mode" in report_html
    assert "top_k=10" in report_html or "top_k=8" in report_html or "top_k=6" in report_html
    assert "not configured" not in report_html.split("Retrieval Signals", 1)[1].split("</article>", 1)[0]


def test_compare_plots_keep_unscored_candidates(tmp_path: Path) -> None:
    experiment_dir = tmp_path / "compare_exp"
    results_dir = experiment_dir / "results"
    results_dir.mkdir(parents=True)
    results_csv = results_dir / "results.csv"

    fieldnames = [
        "candidate_id",
        "candidate_status",
        "text_model_id",
        "prompt_bundle_id",
        "primary.correctness",
        "runtime_seconds",
        "guardrail.evidence_quality",
        "guardrail.null_count",
        "guardrail.failure_count",
    ]
    rows = [
        {
            "candidate_id": "cand_0001",
            "candidate_status": "completed",
            "text_model_id": "qwen/qwen3.5-9b",
            "prompt_bundle_id": "default",
            "primary.correctness": "",
            "runtime_seconds": "4905.39",
            "guardrail.evidence_quality": "",
            "guardrail.null_count": "9",
            "guardrail.failure_count": "9",
        },
        {
            "candidate_id": "cand_0002",
            "candidate_status": "completed",
            "text_model_id": "google/gemma-4-26b-a4b",
            "prompt_bundle_id": "default",
            "primary.correctness": "0.8333333333333334",
            "runtime_seconds": "843.5469",
            "guardrail.evidence_quality": "0.0",
            "guardrail.null_count": "9",
            "guardrail.failure_count": "9",
        },
    ]

    with results_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    generate_compare_plots(experiment_dir, "correctness")

    candidate_rows = list(
        csv.DictReader((experiment_dir / "plots" / "compare_primary_by_candidate.csv").open("r", encoding="utf-8", newline=""))
    )
    assert [row["candidate_id"] for row in candidate_rows] == ["cand_0001", "cand_0002"]
    assert candidate_rows[0]["candidate_label"] == "qwen/qwen3.5-9b"
    assert candidate_rows[0]["primary_score_display"] == "NA"
    assert candidate_rows[0]["score_available"] == "False"
    assert candidate_rows[1]["candidate_label"] == "google/gemma-4-26b-a4b"

    model_rows = list(
        csv.DictReader((experiment_dir / "plots" / "compare_primary_by_text_model.csv").open("r", encoding="utf-8", newline=""))
    )
    assert [row["text_model_id"] for row in model_rows] == ["google/gemma-4-26b-a4b", "qwen/qwen3.5-9b"]
    assert model_rows[1]["best_primary_score"] == ""


def test_compare_mode_writes_no_winner_artifact_when_all_candidates_fail(
    base_config: dict,
    tmp_path: Path,
    monkeypatch,
) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"

    def _failed_result(*args, **kwargs) -> CandidateResult:
        candidate = kwargs["candidate"]
        return CandidateResult(
            schema_version="1.0",
            experiment_id=base_config["experiment_id"],
            study_type="compare",
            benchmark_id="bench_dev",
            candidate_id=candidate.candidate_id,
            parent_candidate_id=candidate.parent_candidate_id,
            round_index=candidate.round_index,
            candidate_hash=f"hash-{candidate.candidate_id}",
            candidate_manifest_path=str(out / f"{candidate.candidate_id}.json"),
            candidate_bundle_dir=str(out / candidate.candidate_id),
            prompt_bundle_id=candidate.prompt_bundle_id,
            text_model_id=candidate.text_model_id,
            vision_model_id=candidate.vision_model_id,
            optimizer_knobs_flat=dict(candidate.optimizer_knobs),
            primary_metrics={},
            guardrail_metrics={},
            diagnostic_metrics={},
            runtime_seconds=None,
            runtime_metadata={},
            started_at="",
            ended_at="",
            candidate_status="failed",
            promotion_decision="rejected",
            decision_reason="simulated_failure",
            main_app_run_ref={},
            eval_output_ref={},
            metadata={},
        )

    monkeypatch.setattr("paper_optimizer.study.evaluate_candidate_once", _failed_result)
    monkeypatch.setattr("paper_optimizer.study.generate_compare_plots", lambda *args, **kwargs: None)

    run_compare_mode(base_config, benches, out)

    assert (out / "no_winner.json").exists()
    payload = json.loads((out / "no_winner.json").read_text(encoding="utf-8"))
    assert payload["reason"] == "no_completed_candidates"
    report_html = (out / "report.html").read_text(encoding="utf-8")
    assert "No winner was materialized" in report_html
    assert "not configured" in report_html or "not recorded" in report_html


def test_compare_mode_writes_progressive_summary_states(
    base_config: dict,
    tmp_path: Path,
    monkeypatch,
) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"
    progress_states: list[str] = []

    from paper_optimizer.study import ResultsWriter

    original_write = ResultsWriter.write_experiment_summary

    def _record_progress(self, payload):
        progress_states.append(str(payload.get("progress_state")))
        return original_write(self, payload)

    monkeypatch.setattr(ResultsWriter, "write_experiment_summary", _record_progress)

    run_compare_mode(base_config, benches, out)

    assert progress_states
    assert progress_states[0] == "running"
    assert progress_states[-1] == "completed"


def test_compare_mode_writes_no_eligible_winner_when_degraded_scores_are_disallowed(
    base_config: dict,
    tmp_path: Path,
    monkeypatch,
) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"
    base_config["acceptance"]["degraded_score_policy"] = "disallow"

    def _degraded_result(*args, **kwargs) -> CandidateResult:
        candidate = kwargs["candidate"]
        return CandidateResult(
            schema_version="1.0",
            experiment_id=base_config["experiment_id"],
            study_type="compare",
            benchmark_id="bench_dev",
            candidate_id=candidate.candidate_id,
            parent_candidate_id=candidate.parent_candidate_id,
            round_index=candidate.round_index,
            candidate_hash=f"hash-{candidate.candidate_id}",
            candidate_manifest_path=str(out / f"{candidate.candidate_id}.json"),
            candidate_bundle_dir=str(out / candidate.candidate_id),
            prompt_bundle_id=candidate.prompt_bundle_id,
            text_model_id=candidate.text_model_id,
            vision_model_id=candidate.vision_model_id,
            optimizer_knobs_flat=dict(candidate.optimizer_knobs),
            primary_metrics={"correctness": 0.75},
            guardrail_metrics={"evidence_quality": 0.9, "null_count": 0.0, "failure_count": 0.0},
            diagnostic_metrics={},
            scored=True,
            score_status="scored_degraded",
            unscored_reason=None,
            unscored_reason_detail=None,
            runtime_seconds=1.0,
            runtime_metadata={},
            started_at="",
            ended_at="",
            candidate_status="completed",
            promotion_decision="rejected",
            decision_reason="completed",
            main_app_run_ref={},
            eval_output_ref={},
            metadata={"deterministic_gate": {"passed": True, "failures": []}},
        )

    monkeypatch.setattr("paper_optimizer.study.evaluate_candidate_once", _degraded_result)
    monkeypatch.setattr("paper_optimizer.study.generate_compare_plots", lambda *args, **kwargs: None)

    run_compare_mode(base_config, benches, out)

    payload = json.loads((out / "no_winner.json").read_text(encoding="utf-8"))
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert payload["reason"] == "no_eligible_winner"
    assert payload["degraded_score_policy"] == "disallow"
    assert payload["progress_state"] == "completed"
    assert payload["best_raw_candidate_id"] == summary["best_raw_candidate_id"]
    assert summary["winner_candidate_id"] is None
    assert summary["eligible_winner_candidate_id"] is None
    assert summary["provisional_winner_candidate_id"] == summary["best_raw_candidate_id"]
    assert summary["progress_state"] == "completed"
    assert summary["scored_degraded_candidate_count"] == len(base_config["compare_candidates"])


def test_compare_report_surfaces_trust_notes_for_degraded_candidates(base_config: dict, tmp_path: Path, monkeypatch) -> None:
    benches = load_benchmarks(base_config)
    out = tmp_path / "compare_exp"

    def _mixed_result(*args, **kwargs) -> CandidateResult:
        candidate = kwargs["candidate"]
        degraded = candidate.text_model_id == "text-model-a"
        return CandidateResult(
            schema_version="1.0",
            experiment_id=base_config["experiment_id"],
            study_type="compare",
            benchmark_id="bench_dev",
            candidate_id=candidate.candidate_id,
            parent_candidate_id=candidate.parent_candidate_id,
            round_index=candidate.round_index,
            candidate_hash=f"hash-{candidate.candidate_id}",
            candidate_manifest_path=str(out / f"{candidate.candidate_id}.json"),
            candidate_bundle_dir=str(out / candidate.candidate_id),
            prompt_bundle_id=candidate.prompt_bundle_id,
            text_model_id=candidate.text_model_id,
            vision_model_id=candidate.vision_model_id,
            optimizer_knobs_flat=dict(candidate.optimizer_knobs),
            primary_metrics={"correctness": 0.75 if degraded else 0.8},
            guardrail_metrics={"evidence_quality": 0.0 if degraded else 0.9, "null_count": 0.0, "failure_count": 0.0},
            diagnostic_metrics={
                "dual_judge_completed": 1.0,
                "judge_disagreement_rate": 0.25,
                "anchor_valid_rate": 0.0 if degraded else 1.0,
                "evidence_item_count": 2.0,
            },
            scored=True,
            score_status="scored_degraded" if degraded else "scored",
            runtime_seconds=1.0,
            runtime_metadata={},
            started_at="",
            ended_at="",
            candidate_status="completed",
            promotion_decision="rejected",
            decision_reason="completed",
            structured_output_mode="none" if degraded else "json_schema",
            prompt_only_degraded_mode_used=degraded,
            extraction_contract_valid=not degraded,
            extraction_contract_warnings=["missing_proposals_jsonl"] if degraded else [],
            main_app_run_ref={},
            eval_output_ref={},
            metadata={
                "deterministic_gate": {"passed": True, "failures": []},
                "eval_summary": {
                    "metrics": {
                        "anchor_valid_rate": 0.0 if degraded else 1.0,
                        "evidence_item_count": 2,
                        "dual_judge_completed": True,
                        "judge_disagreement_rate": 0.25,
                    }
                },
            },
        )

    monkeypatch.setattr("paper_optimizer.study.evaluate_candidate_once", _mixed_result)
    monkeypatch.setattr("paper_optimizer.study.generate_compare_plots", lambda *args, **kwargs: None)

    run_compare_mode(base_config, benches, out)

    report_html = (out / "report.html").read_text(encoding="utf-8")
    assert "prompt-only degraded" in report_html
    assert "zero grounded evidence" in report_html
