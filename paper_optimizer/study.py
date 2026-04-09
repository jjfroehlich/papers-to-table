from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .acceptance import evaluate_promotion
from .benchmarks import Benchmarks, benchmark_id_for_split
from .bundle import build_candidate_from_dict
from .contracts import Candidate, CandidateResult, RoundSummary
from .pipeline import evaluate_candidate_once
from .plotting import generate_compare_plots, generate_optimize_plots
from .propose import propose_candidates
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


def _result_summary_row(result: CandidateResult, primary_metric: str) -> dict[str, Any]:
    return {
        "candidate_id": result.candidate_id,
        "candidate_status": result.candidate_status,
        "text_model_id": result.text_model_id,
        "prompt_bundle_id": result.prompt_bundle_id,
        "primary_metric_value": result.primary_metrics.get(primary_metric),
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
        "text_model_id": result.text_model_id,
        "prompt_bundle_id": result.prompt_bundle_id,
        "runtime_seconds": result.runtime_seconds,
        "primary_metric_value": score,
        "score_available": score is not None,
        "score_status": "scored" if score is not None else ("failed" if result.candidate_status != "completed" else "unscored"),
        "score_explanation": _candidate_score_explanation(result, primary_metric, eval_metrics, reviewer_summary),
        "scored_cell_count": eval_metrics.get("scored_cell_count"),
        "text_scored_cell_count": eval_metrics.get("text_scored_cell_count"),
        "judge_text_scored_cell_count": eval_metrics.get("judge_text_scored_cell_count"),
        "unscored_text_cell_count": eval_metrics.get("unscored_text_cell_count"),
        "judge_request_failed_count": eval_metrics.get("judge_request_failed_count"),
        "judge_unclear_text_cell_count": eval_metrics.get("judge_unclear_text_cell_count"),
        "filled_on_gold_empty_count": eval_metrics.get("filled_on_gold_empty_count"),
        "missing_proposal_count": eval_metrics.get("missing_proposal_count"),
        "main_structured_output_mode": reviewer_summary.get("structured_output_mode"),
        "main_structured_output_reason": reviewer_summary.get("structured_output_reason"),
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
    payload["holdout_validation"] = {
        "ran": True,
        "benchmark_id": benchmark_id,
        "candidate_ids": candidate_ids,
        "output_dir": str(holdout_dir.resolve()),
    }
    write_json(summary_path, payload)


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
    winner = ranked_results[0] if ranked_results and ranked_results[0].candidate_status == "completed" else None
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
        writer.write_no_winner(
            {
                "study_type": "compare",
                "benchmark_id": benchmark_id,
                "reason": "no_completed_candidates",
                "candidate_count": len(results),
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
            "rejection_reason_counts": _aggregate_reason_counts(results),
            "model_rollup": _aggregate_best_by_field(results, primary_metric, "text_model_id"),
            "prompt_rollup": _aggregate_best_by_field(results, primary_metric, "prompt_bundle_id"),
            "holdout_validation": {
                "ran": False,
                "configured_top_k": int(config.get("compare", {}).get("holdout_top_k", 0)),
            },
            "ranked_candidates": [_result_summary_row(result, primary_metric) for result in ranked_results],
        }
    )
    _write_candidate_diagnostics(experiment_dir, ranked_results, primary_metric)
    _write_compare_summary(
        experiment_dir,
        benchmark_id=benchmark_id,
        primary_metric=primary_metric,
        ranked_results=ranked_results,
        winner=winner,
    )

    generate_compare_plots(experiment_dir, primary_metric)


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
                "holdout_validation": {"ran": False},
                "fatal_error": "baseline candidate failed before optimization rounds could start",
                "no_winner_reason": "baseline_candidate_failed",
            }
        )
        raise RuntimeError("Baseline candidate failed before optimization rounds could start")

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
        decision_notes: list[str] = []

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
                    challenger_result.primary_metrics.get(config["acceptance"]["primary_metric"], float("-inf"))
                    > best_accepted_result.primary_metrics.get(config["acceptance"]["primary_metric"], float("-inf"))
                ):
                    best_accepted_result = challenger_result
                    promoted_id = candidate.candidate_id
            else:
                challenger_result.promotion_decision = "rejected"
                challenger_result.decision_reason = reason
                decision_notes.append(f"{candidate.candidate_id}:{reason}")

            writer.append_result(challenger_result)
            all_results.append(challenger_result)

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
            "rejection_reason_counts": _aggregate_reason_counts(all_results),
            "promotion_history": [summary.to_dict() for summary in round_summaries],
            "incumbent_lineage": _incumbent_lineage(all_results, incumbent_result.candidate_id),
            "top_candidates": [
                _result_summary_row(result, config["acceptance"]["primary_metric"])
                for result in _rank_compare_results(all_results, config["acceptance"]["primary_metric"])[:5]
            ],
            "holdout_validation": {"ran": False},
        }
    )

    generate_optimize_plots(experiment_dir, config["acceptance"]["primary_metric"])


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


def summarize(config: dict[str, Any], experiment_dir: Path) -> None:
    manifest = read_json(experiment_dir / "experiment.json")
    study_type = manifest.get("study_type", "optimize")
    primary_metric = config["acceptance"]["primary_metric"]
    if study_type == "compare":
        generate_compare_plots(experiment_dir, primary_metric)
    else:
        generate_optimize_plots(experiment_dir, primary_metric)
