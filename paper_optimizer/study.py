from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .acceptance import degraded_score_policy, evaluate_promotion, is_degraded_score
from .benchmarks import Benchmarks, benchmark_id_for_split
from .bundle import build_candidate_from_dict
from .contracts import Candidate, CandidateResult, RoundSummary
from .pipeline import evaluate_candidate_once
from .plotting import generate_compare_plots, generate_optimize_plots
from .report import generate_experiment_report
from .propose import propose_candidates
from .proposer import collect_proposer_candidates
from .results import ResultsWriter, load_results_jsonl
from .utils import read_json, write_json


def _primary_metric_value(result: CandidateResult, metric_name: str) -> float:
    return float(result.primary_metrics.get(metric_name, float("-inf")))


def _rank_compare_results(results: list[CandidateResult], primary_metric: str) -> list[CandidateResult]:
    return sorted(
        results,
        key=lambda item: (
            item.candidate_status == "completed",
            _primary_metric_value(item, primary_metric),
            -(item.runtime_seconds or float("inf")),
        ),
        reverse=True,
    )


def _winner_eligible(result: CandidateResult, acceptance_cfg: dict[str, Any]) -> bool:
    if result.candidate_status != "completed" or not result.scored:
        return False
    if degraded_score_policy(acceptance_cfg) == "disallow" and is_degraded_score(result):
        return False
    return True


def _result_summary_row(result: CandidateResult, primary_metric: str) -> dict[str, Any]:
    return {
        "candidate_id": result.candidate_id,
        "candidate_status": result.candidate_status,
        "scored": result.scored,
        "score_status": result.score_status,
        "unscored_reason": result.unscored_reason,
        "unscored_reason_detail": result.unscored_reason_detail,
        "text_model_id": result.text_model_id,
        "prompt_bundle_id": result.prompt_bundle_id,
        "primary_metric_value": result.primary_metrics.get(primary_metric),
        "structured_output_mode": result.structured_output_mode,
        "structured_output_reason": result.structured_output_reason,
        "extraction_contract_valid": result.extraction_contract_valid,
        "retrieval_mode": result.retrieval_mode,
        "retrieval_top_k": result.retrieval_top_k,
        "whole_document_max_chars": result.whole_document_max_chars,
        "runtime_seconds": result.runtime_seconds,
        "promotion_decision": result.promotion_decision,
        "decision_reason": result.decision_reason,
    }


def _load_json_if_exists(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return read_json(path)
    except Exception:
        return {}


def _candidate_score_explanation(result: CandidateResult, primary_metric: str, eval_metrics: dict[str, Any], reviewer_summary: dict[str, Any]) -> str:
    score = result.primary_metrics.get(primary_metric)
    if result.candidate_status != "completed":
        return f"candidate failed before scoring: {result.decision_reason}"
    if not result.scored:
        detail = result.unscored_reason_detail or ""
        return result.unscored_reason + (f": {detail}" if result.unscored_reason and detail else "") if result.unscored_reason else (detail or "primary metric unavailable")
    reasons: list[str] = []
    if score is None:
        reasons.append("primary metric unavailable")
    if eval_metrics.get("scored_cell_count") == 0:
        reasons.append("no scored cells")
    if eval_metrics.get("judge_text_scored_cell_count") == 0 and (eval_metrics.get("unscored_text_cell_count") or 0) > 0:
        reasons.append("no text cells were successfully judge-scored")
    if (eval_metrics.get("judge_request_failed_count") or 0) > 0:
        reasons.append(f"{int(eval_metrics['judge_request_failed_count'])} judge request failures")
    structured_output_mode = reviewer_summary.get("structured_output_mode")
    if structured_output_mode == "none":
        reasons.append("main extraction ran in prompt-only mode")
    if score is not None and not reasons:
        return "primary metric computed"
    if score is not None:
        return "primary metric computed with partial diagnostics: " + "; ".join(reasons)
    if reasons:
        return "; ".join(reasons)
    return "primary metric unavailable"


def _candidate_diagnostic_row(result: CandidateResult, primary_metric: str) -> dict[str, Any]:
    eval_summary = result.metadata.get("eval_summary", {}) if isinstance(result.metadata.get("eval_summary"), dict) else {}
    eval_metrics = eval_summary.get("metrics", {}) if isinstance(eval_summary.get("metrics"), dict) else {}
    run_path_value = result.main_app_run_ref.get("run_path")
    reviewer_summary_path = Path(run_path_value) / "summaries" / "reviewer_summary.json" if isinstance(run_path_value, str) else None
    reviewer_summary = _load_json_if_exists(reviewer_summary_path)
    score = result.primary_metrics.get(primary_metric)
    return {
        "candidate_id": result.candidate_id,
        "candidate_status": result.candidate_status,
        "scored": result.scored,
        "score_status": result.score_status,
        "unscored_reason": result.unscored_reason,
        "unscored_reason_detail": result.unscored_reason_detail,
        "text_model_id": result.text_model_id,
        "prompt_bundle_id": result.prompt_bundle_id,
        "runtime_seconds": result.runtime_seconds,
        "primary_metric_value": score,
        "score_available": score is not None,
        "score_explanation": _candidate_score_explanation(result, primary_metric, eval_metrics, reviewer_summary),
        "scored_cell_count": eval_metrics.get("scored_cell_count"),
        "correctness": eval_metrics.get("correctness"),
        "correctness_mean": eval_metrics.get("correctness_mean"),
        "correctness_judge_a": eval_metrics.get("correctness_judge_a"),
        "correctness_judge_b": eval_metrics.get("correctness_judge_b"),
        "judge_disagreement": eval_metrics.get("judge_disagreement"),
        "text_scored_cell_count": eval_metrics.get("text_scored_cell_count"),
        "judge_text_scored_cell_count": eval_metrics.get("judge_text_scored_cell_count"),
        "unscored_text_cell_count": eval_metrics.get("unscored_text_cell_count"),
        "judge_request_failed_count": eval_metrics.get("judge_request_failed_count"),
        "judge_unclear_text_cell_count": eval_metrics.get("judge_unclear_text_cell_count"),
        "filled_on_gold_empty_count": eval_metrics.get("filled_on_gold_empty_count"),
        "missing_proposal_count": eval_metrics.get("missing_proposal_count"),
        "main_structured_output_mode": result.structured_output_mode or reviewer_summary.get("structured_output_mode"),
        "main_structured_output_reason": result.structured_output_reason or reviewer_summary.get("structured_output_reason"),
        "prompt_only_degraded_mode_used": result.prompt_only_degraded_mode_used,
        "parse_repair_used": result.parse_repair_used,
        "extraction_contract_valid": result.extraction_contract_valid,
        "extraction_contract_warnings": "|".join(result.extraction_contract_warnings),
        "retrieval_mode": result.retrieval_mode,
        "retrieval_top_k": result.retrieval_top_k,
        "recall_rescue_enabled": result.recall_rescue_enabled,
        "whole_document_mode": result.whole_document_mode,
        "whole_document_max_chars": result.whole_document_max_chars,
        "recall_rescue_used": result.recall_rescue_used,
        "recall_rescue_invocation_count": result.recall_rescue_invocation_count,
        "main_total_proposals": reviewer_summary.get("total_proposals"),
        "main_pending_proposals": reviewer_summary.get("pending"),
    }


def _write_candidate_diagnostics(experiment_dir: Path, results: list[CandidateResult], primary_metric: str) -> None:
    rows = [_candidate_diagnostic_row(result, primary_metric) for result in results]
    write_json(experiment_dir / "candidate_diagnostics.json", {"primary_metric": primary_metric, "rows": rows})
    results_dir = experiment_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / "candidate_diagnostics.csv"
    if not rows:
        csv_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_compare_summary(
    experiment_dir: Path,
    *,
    acceptance_cfg: dict[str, Any],
    benchmark_id: str,
    primary_metric: str,
    ranked_results: list[CandidateResult],
    winner: CandidateResult | None,
) -> None:
    candidate_rows = [_candidate_diagnostic_row(result, primary_metric) for result in ranked_results]
    payload = {
        "study_type": "compare",
        "benchmark_id": benchmark_id,
        "primary_metric": primary_metric,
        "candidate_count": len(candidate_rows),
        "scored_candidate_count": sum(1 for row in candidate_rows if row.get("score_status") == "scored"),
        "scored_degraded_candidate_count": sum(1 for row in candidate_rows if row.get("score_status") == "scored_degraded"),
        "unscored_candidate_count": sum(1 for row in candidate_rows if row.get("score_status") == "unscored"),
        "failed_candidate_count": sum(1 for row in candidate_rows if row.get("score_status") == "failed"),
        "winner": None,
        "candidates": candidate_rows,
    }
    if winner is not None:
        payload["winner"] = next(
            (row for row in candidate_rows if row.get("candidate_id") == winner.candidate_id),
            None,
        )
    payload["degraded_score_policy"] = degraded_score_policy(acceptance_cfg)
    write_json(experiment_dir / "compare_summary.json", payload)


def _aggregate_reason_counts(results: list[CandidateResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        reason = result.decision_reason or "unspecified"
        counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _aggregate_best_by_field(results: list[CandidateResult], primary_metric: str, field_name: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[CandidateResult]] = {}
    for result in results:
        key = str(getattr(result, field_name) or "")
        grouped.setdefault(key, []).append(result)

    rows: list[dict[str, Any]] = []
    for key, items in sorted(grouped.items()):
        completed_scores = [r.primary_metrics.get(primary_metric) for r in items if r.candidate_status == "completed"]
        numeric_scores = [float(score) for score in completed_scores if score is not None]
        rows.append(
            {
                field_name: key,
                "candidate_count": len(items),
                "completed_candidate_count": sum(1 for r in items if r.candidate_status == "completed"),
                "best_primary_metric_value": max(numeric_scores) if numeric_scores else None,
            }
        )
    return rows


def _incumbent_lineage(results: list[CandidateResult], incumbent_id: str | None) -> list[str]:
    if incumbent_id is None:
        return []
    by_id = {result.candidate_id: result for result in results}
    lineage: list[str] = []
    current_id = incumbent_id
    while current_id:
        lineage.append(current_id)
        current = by_id.get(current_id)
        if current is None:
            break
        current_id = current.parent_candidate_id
    lineage.reverse()
    return lineage


def _write_holdout_status(
    experiment_dir: Path,
    *,
    holdout_dir: Path,
    candidate_ids: list[str],
    benchmark_id: str,
) -> None:
    summary_path = experiment_dir / "summary.json"
    if not summary_path.exists():
        return
    payload = read_json(summary_path)
    holdout_records = load_results_jsonl(holdout_dir)
    holdout_scores = [
        float(record.get("primary_metrics", {}).get(payload.get("primary_metric"), float("-inf")))
        for record in holdout_records
        if isinstance(record.get("primary_metrics"), dict) and record.get("primary_metrics", {}).get(payload.get("primary_metric")) is not None
    ]
    payload["holdout_validation"] = {
        "configured": True,
        "status": "completed",
        "ran": True,
        "benchmark_id": benchmark_id,
        "candidate_ids": candidate_ids,
        "output_dir": str(holdout_dir.resolve()),
        "score": max(holdout_scores) if holdout_scores else None,
        "score_statuses": [record.get("score_status") for record in holdout_records],
    }
    write_json(summary_path, payload)


def _initial_holdout_validation_summary(config: dict[str, Any], *, study_type: str) -> dict[str, Any]:
    configured = "holdout" in config.get("benchmarks", {})
    configured_top_k = int(config.get("compare", {}).get("holdout_top_k", 0) or 0) if study_type == "compare" else 1
    return {
        "configured": configured,
        "configured_top_k": configured_top_k,
        "status": "not_run",
        "ran": False,
        "skip_reason": None,
    }


def _baseline_candidate(config: dict[str, Any]) -> Candidate:
    baseline = config["baseline_candidate"]
    return build_candidate_from_dict(
        "cand_0000",
        baseline,
        parent_candidate_id=None,
        round_index=0,
    )


def _candidate_from_dict_with_id(index: int, payload: dict[str, Any], round_index: int | None, parent_id: str | None) -> Candidate:
    return build_candidate_from_dict(
        f"cand_{index:04d}",
        payload,
        parent_candidate_id=parent_id,
        round_index=round_index,
    )


def _candidate_score(result: CandidateResult, primary_metric: str) -> float:
    return float(result.primary_metrics.get(primary_metric, float("-inf")))


def _write_confirmation_audit(
    experiment_dir: Path,
    *,
    round_index: int,
    candidate_id: str,
    payload: dict[str, Any],
) -> None:
    confirmation_dir = experiment_dir / "confirmation"
    confirmation_dir.mkdir(parents=True, exist_ok=True)
    write_json(confirmation_dir / f"round_{round_index:04d}_{candidate_id}.json", payload)


def _run_confirmation_reruns(
    config: dict[str, Any],
    *,
    experiment_dir: Path,
    candidate: Candidate,
    benchmark_id: str,
    incumbent_result: CandidateResult,
    study_type: str,
) -> tuple[bool, dict[str, Any]]:
    confirmation_config = config.get("optimize", {}).get("confirmation_reruns", {}) or {}
    enabled = bool(confirmation_config.get("enabled", False))
    count = int(confirmation_config.get("count", 0) or 0)
    payload: dict[str, Any] = {
        "enabled": enabled,
        "count": count,
        "candidate_id": candidate.candidate_id,
        "benchmark_id": benchmark_id,
        "runs": [],
        "confirmed": True,
    }
    if not enabled or count <= 0:
        return True, payload

    for attempt_index in range(1, count + 1):
        rerun_result = evaluate_candidate_once(
            config,
            experiment_dir=experiment_dir / "confirmation_runs",
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type=study_type,
            decision="confirmation_rerun",
            reason="confirmation_rerun",
        )
        ok, reason = evaluate_promotion(incumbent_result, rerun_result, config["acceptance"])
        payload["runs"].append(
            {
                "attempt_index": attempt_index,
                "candidate_status": rerun_result.candidate_status,
                "primary_metric_value": rerun_result.primary_metrics.get(config["acceptance"]["primary_metric"]),
                "ok": ok,
                "reason": reason,
            }
        )
        if not ok:
            payload["confirmed"] = False

    _write_confirmation_audit(
        experiment_dir,
        round_index=int(candidate.round_index or 0),
        candidate_id=candidate.candidate_id,
        payload=payload,
    )
    return bool(payload["confirmed"]), payload


def run_compare_mode(config: dict[str, Any], benchmarks: Benchmarks, experiment_dir: Path) -> None:
    writer = ResultsWriter(experiment_dir)
    benchmark_id = benchmark_id_for_split(benchmarks, "dev")
    primary_metric = config["acceptance"]["primary_metric"]
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": "compare",
            "benchmark_id": benchmark_id,
        }
    )

    candidates_raw = list(config.get("compare_candidates", []))
    if not candidates_raw:
        candidates_raw = [config["baseline_candidate"]]

    candidates = [
        _candidate_from_dict_with_id(index=i + 1, payload=row, round_index=None, parent_id=None)
        for i, row in enumerate(candidates_raw)
    ]

    results: list[CandidateResult] = []

    for candidate in candidates:
        result = evaluate_candidate_once(
            config,
            experiment_dir=experiment_dir,
            candidate=candidate,
            benchmark_id=benchmark_id,
            study_type="compare",
            decision="not_promoted",
            reason="compare_mode_fixed_comparison",
        )
        writer.append_result(result)
        results.append(result)

    ranked_results = _rank_compare_results(results, primary_metric)
    winner = next((result for result in ranked_results if _winner_eligible(result, config["acceptance"])), None)
    if winner is not None:
        writer.write_best_candidate(
            {
                "candidate_id": winner.candidate_id,
                "benchmark_id": benchmark_id,
                "study_type": "compare",
                "primary_metric": primary_metric,
                "primary_metric_value": winner.primary_metrics.get(primary_metric),
                "candidate_hash": winner.candidate_hash,
                "text_model_id": winner.text_model_id,
                "prompt_bundle_id": winner.prompt_bundle_id,
                "vision_model_id": winner.vision_model_id,
                "optimizer_knobs_flat": winner.optimizer_knobs_flat,
            }
        )
    else:
        no_winner_reason = "no_eligible_winner" if any(result.candidate_status == "completed" for result in results) else "no_completed_candidates"
        writer.write_no_winner(
            {
                "study_type": "compare",
                "benchmark_id": benchmark_id,
                "reason": no_winner_reason,
                "candidate_count": len(results),
                "degraded_score_policy": degraded_score_policy(config["acceptance"]),
            }
        )
    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": "compare",
            "benchmark_id": benchmark_id,
            "primary_metric": primary_metric,
            "winner_candidate_id": winner.candidate_id if winner is not None else None,
            "winner_text_model_id": winner.text_model_id if winner is not None else None,
            "winner_prompt_bundle_id": winner.prompt_bundle_id if winner is not None else None,
            "candidate_count": len(results),
            "completed_candidate_count": sum(1 for result in results if result.candidate_status == "completed"),
            "failed_candidate_count": sum(1 for result in results if result.candidate_status != "completed"),
            "scored_candidate_count": sum(1 for result in results if result.score_status == "scored"),
            "scored_degraded_candidate_count": sum(1 for result in results if result.score_status == "scored_degraded"),
            "unscored_candidate_count": sum(1 for result in results if result.score_status == "unscored"),
            "degraded_score_policy": degraded_score_policy(config["acceptance"]),
            "rejection_reason_counts": _aggregate_reason_counts(results),
            "model_rollup": _aggregate_best_by_field(results, primary_metric, "text_model_id"),
            "prompt_rollup": _aggregate_best_by_field(results, primary_metric, "prompt_bundle_id"),
            "holdout_validation": {
                **_initial_holdout_validation_summary(config, study_type="compare"),
            },
            "ranked_candidates": [_result_summary_row(result, primary_metric) for result in ranked_results],
        }
    )
    _write_candidate_diagnostics(experiment_dir, ranked_results, primary_metric)
    _write_compare_summary(
        experiment_dir,
        acceptance_cfg=config["acceptance"],
        benchmark_id=benchmark_id,
        primary_metric=primary_metric,
        ranked_results=ranked_results,
        winner=winner,
    )

    generate_compare_plots(experiment_dir, primary_metric)
    generate_experiment_report(experiment_dir)


def run_optimize_mode(config: dict[str, Any], benchmarks: Benchmarks, search_space: Any, experiment_dir: Path) -> None:
    writer = ResultsWriter(experiment_dir)
    benchmark_id = benchmark_id_for_split(benchmarks, "dev")

    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": "optimize",
            "benchmark_id": benchmark_id,
            "rounds": config.get("optimize", {}).get("rounds", 0),
            "batch_size": config.get("optimize", {}).get("batch_size", 1),
        }
    )

    incumbent_candidate = _baseline_candidate(config)
    incumbent_result = evaluate_candidate_once(
        config,
        experiment_dir=experiment_dir,
        candidate=incumbent_candidate,
        benchmark_id=benchmark_id,
        study_type="optimize",
        decision="incumbent",
        reason="baseline",
    )
    writer.append_result(incumbent_result)
    if incumbent_result.candidate_status != "completed":
        writer.write_no_winner(
            {
                "study_type": "optimize",
                "benchmark_id": benchmark_id,
                "reason": "baseline_candidate_failed",
                "candidate_id": incumbent_candidate.candidate_id,
            }
        )
        writer.write_experiment_summary(
            {
                "experiment_id": config["experiment_id"],
                "study_type": "optimize",
                "benchmark_id": benchmark_id,
                "primary_metric": config["acceptance"]["primary_metric"],
                "current_best_candidate_id": None,
                "candidate_count": 1,
                "completed_candidate_count": 0,
                "failed_candidate_count": 1,
                "rejection_reason_counts": {incumbent_result.decision_reason: 1},
                "holdout_validation": _initial_holdout_validation_summary(config, study_type="optimize"),
                "fatal_error": "baseline candidate failed before optimization rounds could start",
                "no_winner_reason": "baseline_candidate_failed",
            }
        )
        raise RuntimeError("Baseline candidate failed before optimization rounds could start")

    if _winner_eligible(incumbent_result, config["acceptance"]):
        writer.write_best_candidate({
            "candidate_id": incumbent_candidate.candidate_id,
            "reason": "baseline",
            "benchmark_id": benchmark_id,
            "primary_metric": config["acceptance"]["primary_metric"],
            "primary_metric_value": incumbent_result.primary_metrics.get(config["acceptance"]["primary_metric"]),
            "text_model_id": incumbent_result.text_model_id,
            "prompt_bundle_id": incumbent_result.prompt_bundle_id,
        })

    rounds = int(config.get("optimize", {}).get("rounds", 0))
    batch_size = int(config.get("optimize", {}).get("batch_size", 1))
    next_candidate_number = 1
    proposer_suggestion_count = 0
    proposer_enabled = bool(config.get("proposer", {}).get("enabled", False))
    seen_signatures: set[tuple[str, str, str | None, str]] = {
        (
            incumbent_candidate.prompt_bundle_id,
            incumbent_candidate.text_model_id,
            incumbent_candidate.vision_model_id,
            str(sorted(incumbent_candidate.optimizer_knobs.items())),
        )
    }
    all_results: list[CandidateResult] = [incumbent_result]
    round_summaries: list[RoundSummary] = []

    for round_index in range(1, rounds + 1):
        proposals = propose_candidates(
            incumbent_candidate,
            search_space=search_space,
            round_index=round_index,
            batch_size=batch_size,
            next_candidate_number_start=next_candidate_number,
        )
        proposer_candidates = collect_proposer_candidates(
            config,
            incumbent=incumbent_candidate,
            search_space=search_space,
            round_index=round_index,
            batch_size=batch_size,
            next_candidate_number_start=next_candidate_number + len(proposals),
            experiment_dir=experiment_dir,
        )
        proposer_suggestion_count += len(proposer_candidates)
        proposals.extend(proposer_candidates)

        filtered: list[Candidate] = []
        for candidate in proposals:
            signature = (
                candidate.prompt_bundle_id,
                candidate.text_model_id,
                candidate.vision_model_id,
                str(sorted(candidate.optimizer_knobs.items())),
            )
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            filtered.append(candidate)

        if not filtered:
            summary = RoundSummary(
                round_index=round_index,
                incumbent_id_before=incumbent_candidate.candidate_id,
                promoted_candidate_id=None,
                incumbent_id_after=incumbent_candidate.candidate_id,
                challenger_ids=[],
                decision_notes=["no_unique_candidates"],
            )
            writer.write_round_summary(summary)
            round_summaries.append(summary)
            continue

        next_candidate_number += len(filtered)

        promoted_id: str | None = None
        best_accepted_result = incumbent_result
        best_accepted_candidate: Candidate | None = None
        decision_notes: list[str] = []
        challenger_results: list[tuple[Candidate, CandidateResult, bool, str]] = []

        for candidate in filtered:
            challenger_result = evaluate_candidate_once(
                config,
                experiment_dir=experiment_dir,
                candidate=candidate,
                benchmark_id=benchmark_id,
                study_type="optimize",
                decision="rejected",
                reason="not_evaluated",
            )

            ok, reason = evaluate_promotion(incumbent_result, challenger_result, config["acceptance"])
            if ok:
                challenger_result.promotion_decision = "promoted"
                challenger_result.decision_reason = reason
                if (
                    _candidate_score(challenger_result, config["acceptance"]["primary_metric"])
                    > _candidate_score(best_accepted_result, config["acceptance"]["primary_metric"])
                ):
                    best_accepted_result = challenger_result
                    best_accepted_candidate = candidate
                    promoted_id = candidate.candidate_id
            else:
                challenger_result.promotion_decision = "rejected"
                challenger_result.decision_reason = reason
                decision_notes.append(f"{candidate.candidate_id}:{reason}")

            challenger_results.append((candidate, challenger_result, ok, reason))
            all_results.append(challenger_result)

        if best_accepted_candidate is not None:
            confirmed, confirmation_payload = _run_confirmation_reruns(
                config,
                experiment_dir=experiment_dir,
                candidate=best_accepted_candidate,
                benchmark_id=benchmark_id,
                incumbent_result=incumbent_result,
                study_type="optimize",
            )
            best_accepted_result.metadata["confirmation_reruns"] = confirmation_payload
            if not confirmed:
                promoted_id = None
                best_accepted_result.promotion_decision = "rejected"
                best_accepted_result.decision_reason = "confirmation_rerun_failed"
                decision_notes.append(f"{best_accepted_candidate.candidate_id}:confirmation_rerun_failed")

        for _, challenger_result, _, _ in challenger_results:
            writer.append_result(challenger_result)

        incumbent_before = incumbent_candidate.candidate_id
        if promoted_id is not None:
            incumbent_result = best_accepted_result
            incumbent_candidate = Candidate(
                candidate_id=incumbent_result.candidate_id,
                prompt_bundle_id=incumbent_result.prompt_bundle_id,
                text_model_id=incumbent_result.text_model_id,
                vision_model_id=incumbent_result.vision_model_id,
                optimizer_knobs=incumbent_result.optimizer_knobs_flat,
                parent_candidate_id=incumbent_result.parent_candidate_id,
                round_index=round_index,
            )
            if _winner_eligible(incumbent_result, config["acceptance"]):
                writer.write_best_candidate(
                    {
                        "candidate_id": incumbent_result.candidate_id,
                        "round_index": round_index,
                        "reason": "promoted",
                        "benchmark_id": benchmark_id,
                        "primary_metric": config["acceptance"]["primary_metric"],
                        "primary_metric_value": incumbent_result.primary_metrics.get(config["acceptance"]["primary_metric"]),
                        "text_model_id": incumbent_result.text_model_id,
                        "prompt_bundle_id": incumbent_result.prompt_bundle_id,
                    }
                )

        summary = RoundSummary(
            round_index=round_index,
            incumbent_id_before=incumbent_before,
            promoted_candidate_id=promoted_id,
            incumbent_id_after=incumbent_candidate.candidate_id,
            challenger_ids=[candidate.candidate_id for candidate in filtered],
            decision_notes=decision_notes,
        )
        writer.write_round_summary(summary)
        round_summaries.append(summary)

    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": "optimize",
            "benchmark_id": benchmark_id,
            "primary_metric": config["acceptance"]["primary_metric"],
            "current_best_candidate_id": incumbent_result.candidate_id,
            "current_best_score": incumbent_result.primary_metrics.get(config["acceptance"]["primary_metric"]),
            "current_best_text_model_id": incumbent_result.text_model_id,
            "current_best_prompt_bundle_id": incumbent_result.prompt_bundle_id,
            "rounds_configured": rounds,
            "rounds_completed": len(round_summaries),
            "candidate_count": len(all_results),
            "completed_candidate_count": sum(1 for result in all_results if result.candidate_status == "completed"),
            "failed_candidate_count": sum(1 for result in all_results if result.candidate_status != "completed"),
            "scored_candidate_count": sum(1 for result in all_results if result.score_status == "scored"),
            "scored_degraded_candidate_count": sum(1 for result in all_results if result.score_status == "scored_degraded"),
            "unscored_candidate_count": sum(1 for result in all_results if result.score_status == "unscored"),
            "degraded_score_policy": degraded_score_policy(config["acceptance"]),
            "rejection_reason_counts": _aggregate_reason_counts(all_results),
            "promotion_history": [summary.to_dict() for summary in round_summaries],
            "incumbent_lineage": _incumbent_lineage(all_results, incumbent_result.candidate_id),
            "proposer": {
                "enabled": proposer_enabled,
                "suggested_candidate_count": proposer_suggestion_count,
            },
            "confirmation_reruns": {
                "enabled": bool(config.get("optimize", {}).get("confirmation_reruns", {}).get("enabled", False)),
                "count": int(config.get("optimize", {}).get("confirmation_reruns", {}).get("count", 0) or 0),
            },
            "top_candidates": [
                _result_summary_row(result, config["acceptance"]["primary_metric"])
                for result in _rank_compare_results(all_results, config["acceptance"]["primary_metric"])[:5]
            ],
            "holdout_validation": _initial_holdout_validation_summary(config, study_type="optimize"),
            "winner_eligible": _winner_eligible(incumbent_result, config["acceptance"]),
        }
    )
    if not _winner_eligible(incumbent_result, config["acceptance"]):
        writer.write_no_winner(
            {
                "study_type": "optimize",
                "benchmark_id": benchmark_id,
                "reason": "no_eligible_winner",
                "candidate_id": incumbent_result.candidate_id,
                "degraded_score_policy": degraded_score_policy(config["acceptance"]),
                "score_status": incumbent_result.score_status,
            }
        )

    generate_optimize_plots(experiment_dir, config["acceptance"]["primary_metric"])
    generate_experiment_report(experiment_dir)


def validate_best(config: dict[str, Any], benchmarks: Benchmarks, experiment_dir: Path, out_dir: Path) -> None:
    holdout_id = benchmark_id_for_split(benchmarks, "holdout")
    records = load_results_jsonl(experiment_dir)
    if not records:
        raise ValueError("No experiment records found")

    study_type = records[0].get("study_type", "optimize")
    primary_metric = config["acceptance"]["primary_metric"]

    if study_type == "optimize":
        best_candidate_path = experiment_dir / "best_candidate.json"
        if not best_candidate_path.exists():
            raise ValueError("No best_candidate.json found for optimize holdout validation")
        best_candidate_payload = read_json(best_candidate_path)
        best_candidate_id = best_candidate_payload.get("candidate_id")
        top = [record for record in records if record.get("candidate_id") == best_candidate_id]
        if not top:
            raise ValueError("Configured optimize incumbent was not found in experiment results")
    else:
        top_k = int(config.get("compare", {}).get("holdout_top_k", 0))
        if top_k <= 0:
            return
        ranked = sorted(records, key=lambda r: float(r.get("primary_metrics", {}).get(primary_metric, float("-inf"))), reverse=True)
        top = ranked[:top_k]

    writer = ResultsWriter(out_dir)
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": study_type,
            "benchmark_id": holdout_id,
            "validation": True,
        }
    )

    for item in top:
        candidate = Candidate(
            candidate_id=str(item["candidate_id"]),
            prompt_bundle_id=str(item["prompt_bundle_id"]),
            text_model_id=str(item["text_model_id"]),
            vision_model_id=item.get("vision_model_id"),
            optimizer_knobs=dict(item.get("optimizer_knobs_flat", {})),
            parent_candidate_id=item.get("parent_candidate_id"),
            round_index=None,
        )
        result = evaluate_candidate_once(
            config,
            experiment_dir=out_dir,
            candidate=candidate,
            benchmark_id=holdout_id,
            study_type=study_type,
            decision="validated",
            reason="holdout_validation",
        )
        writer.append_result(result)

    candidate_ids = [str(item["candidate_id"]) for item in top]
    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": study_type,
            "benchmark_id": holdout_id,
            "primary_metric": primary_metric,
            "validated_candidate_ids": candidate_ids,
            "candidate_count": len(candidate_ids),
            "completed_candidate_count": len(candidate_ids),
        }
    )
    _write_holdout_status(experiment_dir, holdout_dir=out_dir, candidate_ids=candidate_ids, benchmark_id=holdout_id)
    generate_experiment_report(experiment_dir)


def summarize(config: dict[str, Any], experiment_dir: Path) -> None:
    manifest = read_json(experiment_dir / "experiment.json")
    study_type = manifest.get("study_type", "optimize")
    primary_metric = config["acceptance"]["primary_metric"]
    if study_type == "compare":
        generate_compare_plots(experiment_dir, primary_metric)
    else:
        generate_optimize_plots(experiment_dir, primary_metric)
    generate_experiment_report(experiment_dir)
