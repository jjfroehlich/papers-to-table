from __future__ import annotations

import csv
import json
import asyncio
import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .acceptance import degraded_score_policy, evaluate_promotion, is_degraded_score
from .benchmarks import Benchmarks
from .bundle import build_candidate_from_dict, candidate_hash
from .contracts import Candidate, CandidateResult, RoundSummary
from .pipeline import evaluate_candidate_once, evaluate_external_result_once
from .plotting import generate_compare_plots, generate_optimize_plots, generate_suite_plots
from .proposal_tables import write_proposal_tables
from .report import generate_experiment_report
from .propose import propose_candidates
from .proposer import collect_proposer_candidates
from .results import ResultsWriter, load_results_jsonl
from .settings import normalize_config
from .utils import read_json, write_json


@dataclass(frozen=True)
class SuiteExecutionPlan:
    suite_id: str
    benchmark_ids: list[str]
    primary_metric: str
    weights: dict[str, float]
    replicate_count: int
    continue_on_failure: bool


def _primary_metric_value(result: CandidateResult, metric_name: str) -> float:
    return float(result.primary_metrics.get(metric_name, float("-inf")))


def _ranking_penalty(result: CandidateResult) -> tuple[float, ...]:
    eval_summary = result.metadata.get("eval_summary", {}) if isinstance(result.metadata.get("eval_summary"), dict) else {}
    metrics = eval_summary.get("metrics", {}) if isinstance(eval_summary.get("metrics"), dict) else {}
    disagreement = float(metrics.get("judge_disagreement_rate") or 0.0)
    judge_failures = float(metrics.get("judge_request_failed_count") or 0.0)
    missing_evidence = float(metrics.get("missing_evidence_count") or 0.0)
    suite_summary = result.metadata.get("suite_summary", {}) if isinstance(result.metadata.get("suite_summary"), dict) else {}
    benchmark_summary = result.metadata.get("benchmark_summary", {}) if isinstance(result.metadata.get("benchmark_summary"), dict) else {}
    failed = float(suite_summary.get("failed_replicate_count") or benchmark_summary.get("n_failed") or 0.0)
    unscored = float(suite_summary.get("unscored_replicate_count") or benchmark_summary.get("n_unscored") or 0.0)
    degraded = float(suite_summary.get("degraded_replicate_count") or benchmark_summary.get("n_degraded") or 0.0)
    coverage_loss = 1.0 - float(suite_summary.get("benchmark_coverage", 1.0) or 0.0)
    caveat_count = float(len(suite_summary.get("trust_caveats") or benchmark_summary.get("trust_caveats") or []))
    return (-failed, -unscored, -degraded, -coverage_loss, -caveat_count, -disagreement, -judge_failures, -missing_evidence)


def _rank_compare_results(results: list[CandidateResult], primary_metric: str) -> list[CandidateResult]:
    return sorted(
        results,
        key=lambda item: (
            item.candidate_status == "completed",
            _primary_metric_value(item, primary_metric),
            *_ranking_penalty(item),
            -(item.runtime_seconds or float("inf")),
        ),
        reverse=True,
    )


def _replicate_count(config: dict[str, Any]) -> int:
    replicates = config.get("replicates") if isinstance(config.get("replicates"), dict) else {}
    return int(replicates.get("count", 1) or 1)


def _continue_on_replicate_failure(config: dict[str, Any]) -> bool:
    replicates = config.get("replicates") if isinstance(config.get("replicates"), dict) else {}
    return bool(replicates.get("continue_on_failure", True))


def _suite_config(config: dict[str, Any], suite_id: str) -> dict[str, Any]:
    suites = config.get("benchmark_suites") if isinstance(config.get("benchmark_suites"), dict) else {}
    suite = suites.get(suite_id)
    if not isinstance(suite, dict):
        raise ValueError(f"Unknown benchmark suite: {suite_id}")
    return suite


def _suite_plan(config: dict[str, Any], suite_id: str) -> SuiteExecutionPlan:
    suite = _suite_config(config, suite_id)
    aggregation = suite.get("aggregation") if isinstance(suite.get("aggregation"), dict) else {}
    weights = {
        str(benchmark_id): float(weight)
        for benchmark_id, weight in dict(aggregation.get("weights") or {}).items()
    }
    benchmark_ids = list(suite["benchmark_ids"])
    for benchmark_id in benchmark_ids:
        weights.setdefault(benchmark_id, 1.0)
    return SuiteExecutionPlan(
        suite_id=suite_id,
        benchmark_ids=benchmark_ids,
        primary_metric=str(aggregation.get("primary_metric") or config["acceptance"]["primary_metric"]),
        weights=weights,
        replicate_count=_replicate_count(config),
        continue_on_failure=_continue_on_replicate_failure(config),
    )


def _suite_id_for_study(config: dict[str, Any], study_type: str, override: str | None) -> str:
    if override:
        return override
    section = config.get(study_type) if isinstance(config.get(study_type), dict) else {}
    suite_id = section.get("suite_id")
    if not isinstance(suite_id, str) or not suite_id.strip():
        raise ValueError(f"{study_type}.suite_id must name a benchmark suite")
    return suite_id


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _sd(values: list[float]) -> float | None:
    if len(values) <= 1:
        return None
    mean_value = sum(values) / len(values)
    return math.sqrt(sum((value - mean_value) ** 2 for value in values) / (len(values) - 1))


def _sem(values: list[float]) -> float | None:
    sd_value = _sd(values)
    return sd_value / math.sqrt(len(values)) if sd_value is not None and values else None


def _metric_float(result: CandidateResult, *names: str) -> float | None:
    for name in names:
        value = result.diagnostic_metrics.get(name)
        if value is None:
            eval_summary = result.metadata.get("eval_summary", {}) if isinstance(result.metadata.get("eval_summary"), dict) else {}
            metrics = eval_summary.get("metrics", {}) if isinstance(eval_summary.get("metrics"), dict) else {}
            value = metrics.get(name)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _trust_caveats_for_results(results: list[CandidateResult], *, planned_replicates: int) -> list[str]:
    caveats: list[str] = []
    if planned_replicates == 1:
        caveats.append("single_replicate_no_variance_estimate")
    if any(result.score_status == "failed" or result.candidate_status != "completed" for result in results):
        caveats.append("failed_replicates_visible")
    if any(result.score_status == "unscored" or not result.scored for result in results):
        caveats.append("unscored_replicates_visible")
    if any(result.score_status == "scored_degraded" or result.prompt_only_degraded_mode_used for result in results):
        caveats.append("degraded_replicates_visible")
    if any(result.extraction_contract_valid is False for result in results):
        caveats.append("invalid_contract_observed")
    for result in results:
        eval_summary = result.metadata.get("eval_summary", {}) if isinstance(result.metadata.get("eval_summary"), dict) else {}
        metrics = eval_summary.get("metrics", {}) if isinstance(eval_summary.get("metrics"), dict) else {}
        if (metrics.get("judge_disagreement_rate") or 0) and float(metrics.get("judge_disagreement_rate") or 0) > 0:
            caveats.append("judge_instability_observed")
            break
        if (metrics.get("missing_evidence_count") or 0) and float(metrics.get("missing_evidence_count") or 0) > 0:
            caveats.append("missing_evidence_observed")
            break
    return sorted(set(caveats))


def _benchmark_summary_row(
    *,
    candidate: Candidate,
    suite_id: str | None,
    benchmark_id: str,
    primary_metric: str,
    replicate_results: list[CandidateResult],
    planned_replicates: int,
) -> dict[str, Any]:
    scored_values = [
        float(result.primary_metrics[primary_metric])
        for result in replicate_results
        if result.scored and result.primary_metrics.get(primary_metric) is not None
    ]
    runtimes = [float(result.runtime_seconds) for result in replicate_results if result.runtime_seconds is not None]
    runtime_total = sum(runtimes) if runtimes else None
    scored_cell_counts = [
        value
        for result in replicate_results
        for value in [_metric_float(result, "scored_cell_count")]
        if value is not None and value > 0
    ]
    gold_present_cell_counts = [
        value
        for result in replicate_results
        for value in [_metric_float(result, "content_gold_present_cell_count", "gold_present_cell_count")]
        if value is not None and value > 0
    ]
    n_degraded = sum(
        1
        for result in replicate_results
        if result.score_status == "scored_degraded" or result.prompt_only_degraded_mode_used
    )
    return {
        "candidate_id": candidate.candidate_id,
        "suite_id": suite_id,
        "benchmark_id": benchmark_id,
        "primary_metric": primary_metric,
        "primary_metric_mean": _mean(scored_values),
        "primary_metric_sd": _sd(scored_values),
        "primary_metric_sem": _sem(scored_values),
        "n_total": len(replicate_results),
        "n_scored": len(scored_values),
        "n_failed": sum(1 for result in replicate_results if result.score_status == "failed" or result.candidate_status != "completed"),
        "n_unscored": sum(1 for result in replicate_results if result.score_status == "unscored" or not result.scored),
        "n_degraded": n_degraded,
        "runtime_mean_seconds": _mean(runtimes),
        "runtime_sd_seconds": _sd(runtimes),
        "runtime_total_seconds": runtime_total,
        "scored_cell_count_total": sum(scored_cell_counts) if scored_cell_counts else None,
        "gold_present_cell_count_total": sum(gold_present_cell_counts) if gold_present_cell_counts else None,
        "runtime_mean_per_scored_cell_seconds": (
            runtime_total / sum(scored_cell_counts)
            if runtime_total is not None and scored_cell_counts and sum(scored_cell_counts) > 0
            else None
        ),
        "runtime_mean_per_gold_present_cell_seconds": (
            runtime_total / sum(gold_present_cell_counts)
            if runtime_total is not None and gold_present_cell_counts and sum(gold_present_cell_counts) > 0
            else None
        ),
        "trust_caveats": _trust_caveats_for_results(replicate_results, planned_replicates=planned_replicates),
    }


def _suite_summary_row(
    *,
    candidate: Candidate,
    plan: SuiteExecutionPlan,
    benchmark_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    weighted_values: list[tuple[float, float]] = []
    for benchmark_id in plan.benchmark_ids:
        row = next((item for item in benchmark_rows if item["benchmark_id"] == benchmark_id), None)
        if row is None or row.get("primary_metric_mean") is None:
            continue
        weighted_values.append((float(row["primary_metric_mean"]), float(plan.weights.get(benchmark_id, 1.0))))
    weight_total = sum(weight for _, weight in weighted_values)
    weighted_mean = (
        sum(value * weight for value, weight in weighted_values) / weight_total
        if weighted_values and weight_total > 0
        else None
    )
    failed_benchmarks = sum(1 for row in benchmark_rows if row.get("n_scored", 0) == 0 or row.get("n_failed", 0) > 0)
    degraded_benchmarks = sum(1 for row in benchmark_rows if row.get("n_degraded", 0) > 0)
    total_runtime_values = [float(row["runtime_total_seconds"]) for row in benchmark_rows if row.get("runtime_total_seconds") is not None]
    scored_cell_total = sum(float(row.get("scored_cell_count_total") or 0.0) for row in benchmark_rows)
    gold_present_cell_total = sum(float(row.get("gold_present_cell_count_total") or 0.0) for row in benchmark_rows)
    runtime_total = sum(total_runtime_values) if total_runtime_values else None
    caveats = sorted(
        {
            caveat
            for row in benchmark_rows
            for caveat in (row.get("trust_caveats") or [])
        }
        | ({"benchmark_coverage_loss"} if len(weighted_values) < len(plan.benchmark_ids) else set())
    )
    return {
        "candidate_id": candidate.candidate_id,
        "suite_id": plan.suite_id,
        "benchmark_ids": list(plan.benchmark_ids),
        "replicate_count": plan.replicate_count,
        "primary_metric": plan.primary_metric,
        "suite_primary_metric_weighted_mean": weighted_mean,
        "benchmark_coverage": len(weighted_values) / len(plan.benchmark_ids) if plan.benchmark_ids else 0.0,
        "benchmarks_total": len(plan.benchmark_ids),
        "benchmarks_scored": len(weighted_values),
        "failed_benchmark_count": failed_benchmarks,
        "failed_replicate_count": sum(int(row.get("n_failed", 0)) for row in benchmark_rows),
        "unscored_replicate_count": sum(int(row.get("n_unscored", 0)) for row in benchmark_rows),
        "degraded_benchmark_count": degraded_benchmarks,
        "degraded_replicate_count": sum(int(row.get("n_degraded", 0)) for row in benchmark_rows),
        "runtime_total_seconds": runtime_total,
        "runtime_mean_per_benchmark_seconds": (
            runtime_total / len(plan.benchmark_ids)
            if runtime_total is not None and plan.benchmark_ids
            else None
        ),
        "runtime_mean_per_scored_cell_seconds": (
            runtime_total / scored_cell_total
            if runtime_total is not None and scored_cell_total > 0
            else None
        ),
        "runtime_mean_per_gold_present_cell_seconds": (
            runtime_total / gold_present_cell_total
            if runtime_total is not None and gold_present_cell_total > 0
            else None
        ),
        "scored_cell_count_total": scored_cell_total or None,
        "gold_present_cell_count_total": gold_present_cell_total or None,
        "trust_caveats": caveats,
    }


def _summary_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    caveats = set(row.get("trust_caveats") or [])
    score = row.get("suite_primary_metric_weighted_mean")
    if score is None:
        score = row.get("primary_metric_mean")
    return (
        row.get("benchmark_coverage", 1.0),
        -(int(row.get("failed_benchmark_count", 0)) + int(row.get("failed_replicate_count", 0))),
        -(int(row.get("unscored_replicate_count", 0))),
        -(int(row.get("degraded_benchmark_count", 0)) + int(row.get("degraded_replicate_count", 0))),
        -len(caveats),
        float(score) if score is not None else float("-inf"),
    )


def _aggregate_result_from_summary(
    template: CandidateResult,
    *,
    suite_id: str | None,
    benchmark_id: str,
    primary_metric: str,
    score: float | None,
    runtime_seconds: float | None,
    score_status: str,
    metadata: dict[str, Any],
) -> CandidateResult:
    scored = score is not None
    return replace(
        template,
        suite_id=suite_id,
        benchmark_id=benchmark_id,
        replicate_index=None,
        replicate_id=None,
        primary_metrics={primary_metric: float(score)} if scored else {},
        scored=scored,
        score_status=score_status if scored else "unscored",
        unscored_reason=None if scored else "aggregate_missing_scored_replicates",
        runtime_seconds=runtime_seconds,
        runtime_metadata={
            **template.runtime_metadata,
            "suite_total_runtime_seconds": metadata.get("suite_summary", {}).get("runtime_total_seconds")
            if isinstance(metadata.get("suite_summary"), dict)
            else None,
            "suite_mean_runtime_per_benchmark_seconds": metadata.get("suite_summary", {}).get("runtime_mean_per_benchmark_seconds")
            if isinstance(metadata.get("suite_summary"), dict)
            else None,
            "suite_mean_runtime_per_scored_cell_seconds": metadata.get("suite_summary", {}).get("runtime_mean_per_scored_cell_seconds")
            if isinstance(metadata.get("suite_summary"), dict)
            else None,
        },
        candidate_status="completed" if scored else "failed",
        metadata={**template.metadata, **metadata},
    )


def _evaluate_candidate_with_suite_and_replicates(
    config: dict[str, Any],
    writer: ResultsWriter,
    *,
    experiment_dir: Path,
    candidate: Candidate,
    plan: SuiteExecutionPlan,
    study_type: str,
    decision: str,
    reason: str,
) -> CandidateResult:
    all_replicates: list[CandidateResult] = []
    benchmark_rows: list[dict[str, Any]] = []

    for planned_benchmark_id in plan.benchmark_ids:
        per_benchmark: list[CandidateResult] = []
        for replicate_index in range(1, plan.replicate_count + 1):
            result = evaluate_candidate_once(
                config,
                experiment_dir=experiment_dir,
                candidate=candidate,
                benchmark_id=planned_benchmark_id,
                study_type=study_type,
                decision=decision,
                reason=reason,
            )
            result.suite_id = plan.suite_id
            result.replicate_index = replicate_index
            result.replicate_id = f"{candidate.candidate_id}:{plan.suite_id}:{planned_benchmark_id}:r{replicate_index:03d}"
            result.metadata["replicate"] = {
                "suite_id": plan.suite_id,
                "benchmark_id": planned_benchmark_id,
                "replicate_index": replicate_index,
                "replicate_id": result.replicate_id,
            }
            per_benchmark.append(result)
            all_replicates.append(result)
            if result.score_status == "failed" and not plan.continue_on_failure:
                break
        benchmark_rows.append(
            _benchmark_summary_row(
                candidate=candidate,
                suite_id=plan.suite_id,
                benchmark_id=planned_benchmark_id,
                primary_metric=plan.primary_metric,
                replicate_results=per_benchmark,
                planned_replicates=plan.replicate_count,
            )
        )

    existing_replicates: list[CandidateResult] = []
    replicate_jsonl = experiment_dir / "results" / "replicate_results.jsonl"
    if replicate_jsonl.exists():
        for line in replicate_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            existing_replicates.append(CandidateResult(**payload))
    writer.write_replicate_results(existing_replicates + all_replicates)

    benchmark_summary_path = experiment_dir / "results" / "benchmark_summary.json"
    prior_benchmark_rows: list[dict[str, Any]] = []
    if benchmark_summary_path.exists():
        existing = read_json(benchmark_summary_path)
        prior_benchmark_rows = list(existing.get("rows", [])) if isinstance(existing, dict) else []
    benchmark_rows_all = [
        row for row in prior_benchmark_rows if row.get("candidate_id") != candidate.candidate_id
    ] + benchmark_rows
    writer.write_table_artifacts(
        "benchmark_summary",
        benchmark_rows_all,
        {"primary_metric": plan.primary_metric, "rows": benchmark_rows_all},
    )

    suite_row = _suite_summary_row(
        candidate=candidate,
        plan=plan,
        benchmark_rows=benchmark_rows,
    )
    prior_rows = []
    suite_summary_path = experiment_dir / "results" / "suite_summary.json"
    if suite_summary_path.exists():
        existing = read_json(suite_summary_path)
        prior_rows = list(existing.get("rows", [])) if isinstance(existing, dict) else []
    suite_rows = [row for row in prior_rows if row.get("candidate_id") != candidate.candidate_id]
    suite_rows.append(suite_row)
    suite_rows = sorted(suite_rows, key=_summary_sort_key, reverse=True)
    writer.write_table_artifacts("suite_summary", suite_rows, {"primary_metric": plan.primary_metric, "rows": suite_rows})
    return _aggregate_result_from_summary(
        all_replicates[0],
        suite_id=plan.suite_id,
        benchmark_id=f"suite:{plan.suite_id}",
        primary_metric=plan.primary_metric,
        score=suite_row.get("suite_primary_metric_weighted_mean"),
        runtime_seconds=suite_row.get("runtime_total_seconds"),
        score_status=(
            "scored_degraded"
            if int(suite_row.get("degraded_replicate_count", 0) or 0) > 0
            else "scored"
        ),
        metadata={"suite_summary": suite_row, "benchmark_summaries": benchmark_rows, "replicate_count": plan.replicate_count},
    )


def evaluate_candidate_suite(
    config: dict[str, Any],
    *,
    experiment_dir: Path,
    candidate: Candidate,
    suite_id: str,
    study_type: str,
    decision: str,
    reason: str,
    writer: ResultsWriter | None = None,
) -> CandidateResult:
    config = normalize_config(config)
    plan = _suite_plan(config, suite_id)
    writer = writer or ResultsWriter(experiment_dir)
    return _evaluate_candidate_with_suite_and_replicates(
        config,
        writer,
        experiment_dir=experiment_dir,
        candidate=candidate,
        plan=plan,
        study_type=study_type,
        decision=decision,
        reason=reason,
    )


def _winner_eligible(result: CandidateResult, acceptance_cfg: dict[str, Any]) -> bool:
    if result.candidate_status != "completed" or not result.scored:
        return False
    if degraded_score_policy(acceptance_cfg) == "disallow" and is_degraded_score(result):
        return False
    return True


def _result_summary_row(result: CandidateResult, primary_metric: str) -> dict[str, Any]:
    reviewer_summary = _load_candidate_reviewer_summary(result)
    provider_diag = _load_candidate_provider_diagnostics(result)
    provider_counts = _provider_failure_counters(provider_diag)
    reliability_label = _reliability_label(result, reviewer_summary, provider_counts)
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
        "main_structured_output_mode": result.structured_output_mode or reviewer_summary.get("structured_output_mode"),
        "main_structured_output_reason": result.structured_output_reason or reviewer_summary.get("structured_output_reason"),
        "prompt_only_degraded_mode_used": bool(result.prompt_only_degraded_mode_used),
        "parse_repair_used": bool(result.parse_repair_used),
        "extraction_contract_valid": result.extraction_contract_valid,
        "retrieval_mode": result.retrieval_mode,
        "retrieval_top_k": result.retrieval_top_k,
        "provider_retry_count": provider_counts["retry_count"],
        "provider_malformed_json_count": provider_counts["malformed_json_count"],
        "provider_structured_error_count": provider_counts["structured_output_error_count"],
        "provider_failed_structured_elapsed_ms": provider_counts["failed_structured_elapsed_ms"],
        "reliability_label": reliability_label,
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
    if reviewer_summary.get("extraction_contract_valid") is False:
        reasons.append("extraction contract invalid")
    anchor_valid_rate = eval_metrics.get("anchor_valid_rate")
    if anchor_valid_rate is not None and anchor_valid_rate <= 0.0 and (eval_metrics.get("evidence_item_count") or 0) > 0:
        reasons.append("zero evidence anchors validated")
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
    reviewer_summary = _load_candidate_reviewer_summary(result)
    provider_diag = _load_candidate_provider_diagnostics(result)
    provider_counts = _provider_failure_counters(provider_diag)
    reliability_label = _reliability_label(result, reviewer_summary, provider_counts)
    score = result.primary_metrics.get(primary_metric)
    disagreement_rate = eval_metrics.get("judge_disagreement_rate")
    correctness_a = eval_metrics.get("correctness_judge_a")
    correctness_b = eval_metrics.get("correctness_judge_b")
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
        "content_correctness": eval_metrics.get("content_correctness"),
        "content_correctness_scored_only": eval_metrics.get("content_correctness_scored_only"),
        "overall_correctness": eval_metrics.get("overall_correctness"),
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
        "judge_a_request_failed_count": eval_metrics.get("judge_a_request_failed_count"),
        "judge_b_request_failed_count": eval_metrics.get("judge_b_request_failed_count"),
        "judge_a_unclear_text_cell_count": eval_metrics.get("judge_a_unclear_text_cell_count"),
        "judge_b_unclear_text_cell_count": eval_metrics.get("judge_b_unclear_text_cell_count"),
        "dual_judge_completed": eval_metrics.get("dual_judge_completed"),
        "judge_disagreement_count": eval_metrics.get("judge_disagreement_count"),
        "judge_disagreement_rate": eval_metrics.get("judge_disagreement_rate"),
        "judge_disagreement_warning": bool(disagreement_rate is not None and float(disagreement_rate) >= 0.2),
        "judge_correctness_delta": (
            abs(float(correctness_a) - float(correctness_b))
            if correctness_a is not None and correctness_b is not None
            else None
        ),
        "anchor_valid_rate": eval_metrics.get("anchor_valid_rate"),
        "evidence_item_count": eval_metrics.get("evidence_item_count"),
        "missing_evidence_count": eval_metrics.get("missing_evidence_count"),
        "validated_evidence_item_count": eval_metrics.get("validated_evidence_item_count"),
        "anchor_invalid_count": eval_metrics.get("anchor_invalid_count"),
        "evidence_present_but_unvalidated_count": eval_metrics.get("evidence_present_but_unvalidated_count"),
        "evidence_anchor_reason_counts": eval_metrics.get("evidence_anchor_reason_counts"),
        "evidence_anchor_outcome_counts": eval_metrics.get("evidence_anchor_outcome_counts"),
        "judge_execution_summary": eval_metrics.get("judge_execution_summary"),
        "metadata_summary": eval_metrics.get("metadata_summary"),
        "judge_summary": eval_metrics.get("judge_summary"),
        "proposal_coverage_on_content_gold_present": eval_metrics.get("proposal_coverage_on_content_gold_present"),
        "proposal_coverage_on_all_gold_present": eval_metrics.get("proposal_coverage_on_all_gold_present"),
        "filled_on_gold_empty_count": eval_metrics.get("filled_on_gold_empty_count"),
        "missing_proposal_count": eval_metrics.get("missing_proposal_count"),
        "join_failure_count": eval_metrics.get("join_failure_count"),
        "parser_gap_count": eval_metrics.get("parser_gap_count"),
        "retrieval_miss_count": eval_metrics.get("retrieval_miss_count"),
        "extraction_miss_count": eval_metrics.get("extraction_miss_count"),
        "evidence_ambiguity_count": eval_metrics.get("evidence_ambiguity_count"),
        "judge_failure_count": eval_metrics.get("judge_failure_count"),
        "judge_unclear_count": eval_metrics.get("judge_unclear_count"),
        "main_structured_output_mode": result.structured_output_mode or reviewer_summary.get("structured_output_mode"),
        "main_structured_output_reason": result.structured_output_reason or reviewer_summary.get("structured_output_reason"),
        "prompt_only_degraded_mode_used": result.prompt_only_degraded_mode_used,
        "parse_repair_used": result.parse_repair_used,
        "provider_retry_count": provider_counts["retry_count"],
        "provider_malformed_json_count": provider_counts["malformed_json_count"],
        "provider_structured_error_count": provider_counts["structured_output_error_count"],
        "provider_failed_structured_elapsed_ms": provider_counts["failed_structured_elapsed_ms"],
        "reliability_label": reliability_label,
        "extraction_contract_valid": result.extraction_contract_valid,
        "extraction_contract_warnings": "|".join(result.extraction_contract_warnings),
        "extraction_contract_warning_count": len(result.extraction_contract_warnings),
        "retrieval_mode": result.retrieval_mode,
        "retrieval_top_k": result.retrieval_top_k,
        "recall_rescue_enabled": result.recall_rescue_enabled,
        "whole_document_mode": result.whole_document_mode,
        "whole_document_max_chars": result.whole_document_max_chars,
        "recall_rescue_used": result.recall_rescue_used,
        "recall_rescue_invocation_count": result.recall_rescue_invocation_count,
        "whole_document_used_count": result.whole_document_used_count,
        "runtime_total_duration_seconds": result.runtime_metadata.get("total_duration_seconds"),
        "runtime_main_app_duration_seconds": result.runtime_metadata.get("main_app_duration_seconds"),
        "runtime_eval_duration_seconds": result.runtime_metadata.get("eval_duration_seconds"),
        "provider_request_counts": result.runtime_metadata.get("provider_request_counts"),
        "run_stats_counters": result.runtime_metadata.get("run_stats_counters"),
        "main_total_proposals": reviewer_summary.get("total_proposals"),
        "main_pending_proposals": reviewer_summary.get("pending"),
}


def _load_candidate_reviewer_summary(result: CandidateResult) -> dict[str, Any]:
    run_path_value = result.main_app_run_ref.get("run_path")
    reviewer_summary_path = Path(run_path_value) / "summaries" / "reviewer_summary.json" if isinstance(run_path_value, str) else None
    return _load_json_if_exists(reviewer_summary_path)


def _load_candidate_provider_diagnostics(result: CandidateResult) -> dict[str, Any]:
    run_path_value = result.main_app_run_ref.get("run_path")
    if not isinstance(run_path_value, str):
        return {}
    return _load_json_if_exists(Path(run_path_value) / "diagnostics" / "provider_diagnostics.json")


def _provider_failure_counters(provider_diag: dict[str, Any]) -> dict[str, Any]:
    attempts = provider_diag.get("attempts") if isinstance(provider_diag.get("attempts"), list) else []
    retry_count = 0
    malformed_json_count = 0
    structured_output_error_count = 0
    failed_structured_elapsed_ms = 0.0
    for attempt in attempts:
        if not isinstance(attempt, dict):
            continue
        if attempt.get("phase") == "retry":
            retry_count += 1
        outcome = str(attempt.get("outcome") or "")
        if outcome == "structured_output_error":
            structured_output_error_count += 1
        if str(attempt.get("error_reason") or "") == "malformed_json":
            malformed_json_count += 1
        if attempt.get("structured_mode") in {"json_schema", "json_object", "none"} and outcome != "success":
            failed_structured_elapsed_ms += float(attempt.get("duration_ms", 0.0) or 0.0)
    return {
        "retry_count": retry_count,
        "malformed_json_count": malformed_json_count,
        "structured_output_error_count": structured_output_error_count,
        "failed_structured_elapsed_ms": round(failed_structured_elapsed_ms, 3),
    }


def _reliability_label(
    result: CandidateResult,
    reviewer_summary: dict[str, Any],
    provider_counts: dict[str, Any],
) -> str:
    if result.candidate_status == "ineligible":
        return "ineligible"
    structured_mode = result.structured_output_mode or reviewer_summary.get("structured_output_mode")
    degraded = bool(result.prompt_only_degraded_mode_used) or structured_mode == "none"
    contract_invalid = reviewer_summary.get("extraction_contract_valid") is False or result.extraction_contract_valid is False
    unstable = (
        provider_counts["structured_output_error_count"] > 0
        or provider_counts["malformed_json_count"] > 0
        or provider_counts["retry_count"] > 0
    )
    eval_summary = result.metadata.get("eval_summary", {}) if isinstance(result.metadata.get("eval_summary"), dict) else {}
    eval_metrics = eval_summary.get("metrics", {}) if isinstance(eval_summary.get("metrics"), dict) else {}
    high_disagreement = float(eval_metrics.get("judge_disagreement_rate") or 0.0) >= 0.2
    weak_evidence = (
        int(eval_metrics.get("missing_evidence_count") or 0) > 0
        or int(eval_metrics.get("evidence_present_but_unvalidated_count") or 0) > 0
    )
    if contract_invalid or degraded:
        return "degraded"
    if unstable or high_disagreement or weak_evidence:
        return "unstable"
    return "healthy"


def _compare_policy(config: dict[str, Any]) -> dict[str, bool]:
    compare_cfg = config.get("compare", {})
    require_structured = bool(compare_cfg.get("require_structured_output_for_extraction", True))
    allow_degraded = bool(compare_cfg.get("allow_degraded_candidates", False))
    return {
        "require_structured_output_for_extraction": require_structured,
        "allow_degraded_candidates": allow_degraded,
    }


def _probe_candidate_structured_output_mode(
    config: dict[str, Any],
    *,
    candidate: Candidate,
    benchmark_id: str,
) -> dict[str, Any]:
    try:
        from .launch_main import build_resolved_main_config
        from .benchmarks import load_benchmarks
    except Exception as exc:
        return {"probe_status": "error", "error": str(exc)}
    try:
        bench = load_benchmarks(config).manifests[benchmark_id]
        _, resolved = build_resolved_main_config(
            config,
            candidate=candidate,
            benchmark=bench,
            run_output_dir=Path("/tmp/papers_to_table_probe"),
        )
        provider_cfg = resolved.get("provider") if isinstance(resolved.get("provider"), dict) else {}
        text_cfg = provider_cfg.get("text_model") if isinstance(provider_cfg.get("text_model"), dict) else {}
        vision_cfg = provider_cfg.get("vision_model") if isinstance(provider_cfg.get("vision_model"), dict) else None
        token = str(provider_cfg.get("token", "lm_studio"))
        base_url = str(provider_cfg.get("base_url", "http://localhost:1234"))
        backend_src = Path(config["main_app"]["repo_root"]).resolve() / "backend" / "src"
        if str(backend_src) not in sys.path:
            sys.path.insert(0, str(backend_src))
        from backend.app.provider import initialize_provider  # type: ignore

        class _ModelCfg:
            def __init__(self, payload: dict[str, Any]):
                self.model_id = payload.get("model_id")
                self.temperature = payload.get("temperature", 0.0)
                self.top_p = payload.get("top_p")
                self.top_k = payload.get("top_k")
                self.min_p = payload.get("min_p")
                self.presence_penalty = payload.get("presence_penalty")
                self.repetition_penalty = payload.get("repetition_penalty")
                self.extra_body = dict(payload.get("extra_body") or {})
                self.chat_template_kwargs = dict(payload.get("chat_template_kwargs") or {})
                self.working_context_budget = payload.get("working_context_budget")
                self.required_load_context_length = (
                    payload.get("required_load_context_length")
                    or payload.get("load_context_length")
                    or payload.get("working_context_budget")
                )
                self.load_context_is_derived = payload.get("load_context_is_derived", False)
                self.load_context_length = payload.get("load_context_length")
                self.model_fields_set = set(payload)

        class _ProviderCfg:
            def __init__(self) -> None:
                self.token = token
                self.base_url = base_url
                self.text_model = _ModelCfg(text_cfg)
                self.vision_model = _ModelCfg(vision_cfg) if isinstance(vision_cfg, dict) else None

        provider, provider_mode = asyncio.run(
            initialize_provider(
                _ProviderCfg(),
                text_model_id=candidate.text_model_id,
                vision_model_id=candidate.vision_model_id,
                diagnostics_config=None,
            )
        )
        return {
            "probe_status": "ok",
            "structured_output_mode": provider_mode.structured_output_mode,
            "structured_output_reason": provider_mode.structured_output_reason,
            "model_request_profiles": (
                provider.get_model_request_profile_report()
                if hasattr(provider, "get_model_request_profile_report")
                else {}
            ),
            "provider_probe": (
                provider.get_probe_report()
                if hasattr(provider, "get_probe_report")
                else {}
            ),
        }
    except Exception as exc:
        return {"probe_status": "error", "error": str(exc)}


def _ineligible_result(
    config: dict[str, Any],
    *,
    candidate: Candidate,
    benchmark_id: str,
    reason: str,
    detail: str,
    gate_details: dict[str, Any],
) -> CandidateResult:
    return CandidateResult(
        schema_version=str(config["schema_version"]),
        experiment_id=str(config["experiment_id"]),
        study_type="compare",
        benchmark_id=benchmark_id,
        candidate_id=candidate.candidate_id,
        parent_candidate_id=candidate.parent_candidate_id,
        round_index=candidate.round_index,
        candidate_hash=candidate_hash(candidate),
        candidate_manifest_path="",
        candidate_bundle_dir="",
        prompt_bundle_id=candidate.prompt_bundle_id,
        text_model_id=candidate.text_model_id,
        vision_model_id=candidate.vision_model_id,
        optimizer_knobs_flat={f"knob.{key}": value for key, value in candidate.optimizer_knobs.items()},
        primary_metrics={},
        guardrail_metrics={},
        diagnostic_metrics={},
        scored=False,
        score_status="unscored",
        unscored_reason=reason,
        unscored_reason_detail=detail,
        runtime_seconds=0.0,
        runtime_metadata={},
        started_at="",
        ended_at="",
        candidate_status="ineligible",
        promotion_decision="not_promoted",
        decision_reason=reason,
        structured_output_mode=gate_details.get("structured_output_mode"),
        structured_output_reason=gate_details.get("structured_output_reason"),
        prompt_only_degraded_mode_used=True,
        metadata={"eligibility_gate": gate_details},
    )


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


def _best_completed_result(results: list[CandidateResult], primary_metric: str) -> CandidateResult | None:
    completed = [result for result in results if result.candidate_status == "completed"]
    if not completed:
        return None
    ranked = _rank_compare_results(completed, primary_metric)
    return ranked[0] if ranked else None


def _write_compare_progress(
    writer: ResultsWriter,
    *,
    config: dict[str, Any],
    benchmark_id: str,
    primary_metric: str,
    results: list[CandidateResult],
    progress_state: str,
) -> None:
    ranked_results = _rank_compare_results(results, primary_metric)
    active_suite_id = next((result.suite_id for result in results if result.suite_id), None)
    best_raw = _best_completed_result(results, primary_metric)
    eligible_winner = next(
        (result for result in ranked_results if _winner_eligible(result, config["acceptance"])),
        None,
    )
    provisional_winner = best_raw if best_raw is not None and eligible_winner is None else None

    if eligible_winner is not None:
        writer.write_best_candidate(
            {
                "candidate_id": eligible_winner.candidate_id,
                "benchmark_id": benchmark_id,
                "suite_id": active_suite_id,
                "study_type": "compare",
                "primary_metric": primary_metric,
                "primary_metric_value": eligible_winner.primary_metrics.get(primary_metric),
                "candidate_hash": eligible_winner.candidate_hash,
                "text_model_id": eligible_winner.text_model_id,
                "prompt_bundle_id": eligible_winner.prompt_bundle_id,
                "vision_model_id": eligible_winner.vision_model_id,
                "optimizer_knobs_flat": eligible_winner.optimizer_knobs_flat,
                "score_status": eligible_winner.score_status,
                "progress_state": progress_state,
            }
        )
        writer.clear_no_winner()
    else:
        writer.clear_best_candidate()
        writer.write_no_winner(
            {
                "study_type": "compare",
                "benchmark_id": benchmark_id,
                "suite_id": active_suite_id,
                "reason": "no_eligible_winner" if any(result.candidate_status == "completed" for result in results) else "no_completed_candidates",
                "candidate_count": len(results),
                "degraded_score_policy": degraded_score_policy(config["acceptance"]),
                "best_raw_candidate_id": best_raw.candidate_id if best_raw is not None else None,
                "best_raw_score_status": best_raw.score_status if best_raw is not None else None,
                "progress_state": progress_state,
            }
        )

    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": "compare",
            "benchmark_id": benchmark_id,
            "primary_metric": primary_metric,
            "progress_state": progress_state,
            "winner_candidate_id": eligible_winner.candidate_id if eligible_winner is not None else None,
            "winner_text_model_id": eligible_winner.text_model_id if eligible_winner is not None else None,
            "winner_prompt_bundle_id": eligible_winner.prompt_bundle_id if eligible_winner is not None else None,
            "best_raw_candidate_id": best_raw.candidate_id if best_raw is not None else None,
            "best_raw_score": best_raw.primary_metrics.get(primary_metric) if best_raw is not None else None,
            "best_raw_score_status": best_raw.score_status if best_raw is not None else None,
            "eligible_winner_candidate_id": eligible_winner.candidate_id if eligible_winner is not None else None,
            "eligible_winner_score": eligible_winner.primary_metrics.get(primary_metric) if eligible_winner is not None else None,
            "eligible_winner_score_status": eligible_winner.score_status if eligible_winner is not None else None,
            "provisional_winner_candidate_id": provisional_winner.candidate_id if provisional_winner is not None else None,
            "provisional_winner_score_status": provisional_winner.score_status if provisional_winner is not None else None,
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
            "ranked_candidates": [_result_summary_row(result, primary_metric) for result in ranked_results],
        }
    )


def _write_optimize_progress(
    writer: ResultsWriter,
    *,
    config: dict[str, Any],
    benchmark_id: str,
    all_results: list[CandidateResult],
    incumbent_result: CandidateResult,
    round_summaries: list[RoundSummary],
    proposer_enabled: bool,
    proposer_suggestion_count: int,
    progress_state: str,
    fatal_error: str | None = None,
) -> None:
    primary_metric = config["acceptance"]["primary_metric"]
    ranked_results = _rank_compare_results(all_results, primary_metric)
    best_raw = _best_completed_result(all_results, primary_metric)
    eligible_winner = incumbent_result if _winner_eligible(incumbent_result, config["acceptance"]) else None
    provisional_winner = best_raw if best_raw is not None and eligible_winner is None else None

    if eligible_winner is not None:
        writer.write_best_candidate(
            {
                "candidate_id": eligible_winner.candidate_id,
                "round_index": eligible_winner.round_index,
                "reason": "promoted" if eligible_winner.candidate_id != "cand_0000" else "baseline",
                "benchmark_id": benchmark_id,
                "primary_metric": primary_metric,
                "primary_metric_value": eligible_winner.primary_metrics.get(primary_metric),
                "text_model_id": eligible_winner.text_model_id,
                "prompt_bundle_id": eligible_winner.prompt_bundle_id,
                "score_status": eligible_winner.score_status,
                "progress_state": progress_state,
            }
        )
        writer.clear_no_winner()
    else:
        writer.clear_best_candidate()
        writer.write_no_winner(
            {
                "study_type": "optimize",
                "benchmark_id": benchmark_id,
                "reason": "no_eligible_winner" if any(result.candidate_status == "completed" for result in all_results) else "no_completed_candidates",
                "candidate_id": incumbent_result.candidate_id,
                "degraded_score_policy": degraded_score_policy(config["acceptance"]),
                "score_status": incumbent_result.score_status,
                "best_raw_candidate_id": best_raw.candidate_id if best_raw is not None else None,
                "best_raw_score_status": best_raw.score_status if best_raw is not None else None,
                "progress_state": progress_state,
            }
        )

    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": "optimize",
            "benchmark_id": benchmark_id,
            "primary_metric": primary_metric,
            "progress_state": progress_state,
            "current_best_candidate_id": incumbent_result.candidate_id,
            "current_best_score": incumbent_result.primary_metrics.get(primary_metric),
            "current_best_score_status": incumbent_result.score_status,
            "current_best_text_model_id": incumbent_result.text_model_id,
            "current_best_prompt_bundle_id": incumbent_result.prompt_bundle_id,
            "best_raw_candidate_id": best_raw.candidate_id if best_raw is not None else None,
            "best_raw_score": best_raw.primary_metrics.get(primary_metric) if best_raw is not None else None,
            "best_raw_score_status": best_raw.score_status if best_raw is not None else None,
            "eligible_winner_candidate_id": eligible_winner.candidate_id if eligible_winner is not None else None,
            "eligible_winner_score": eligible_winner.primary_metrics.get(primary_metric) if eligible_winner is not None else None,
            "eligible_winner_score_status": eligible_winner.score_status if eligible_winner is not None else None,
            "provisional_winner_candidate_id": provisional_winner.candidate_id if provisional_winner is not None else None,
            "provisional_winner_score_status": provisional_winner.score_status if provisional_winner is not None else None,
            "rounds_configured": int(config.get("optimize", {}).get("rounds", 0)),
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
                _result_summary_row(result, primary_metric)
                for result in ranked_results[:5]
            ],
            "winner_eligible": _winner_eligible(incumbent_result, config["acceptance"]),
            "fatal_error": fatal_error,
            "no_winner_reason": None if eligible_winner is not None else ("baseline_candidate_failed" if fatal_error else "no_eligible_winner"),
        }
    )


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
    plan: SuiteExecutionPlan,
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
        "suite_id": plan.suite_id,
        "benchmark_ids": plan.benchmark_ids,
        "runs": [],
        "confirmed": True,
    }
    if not enabled or count <= 0:
        return True, payload

    confirmation_writer = ResultsWriter(experiment_dir / "confirmation_runs")
    for attempt_index in range(1, count + 1):
        rerun_result = _evaluate_candidate_with_suite_and_replicates(
            config,
            confirmation_writer,
            experiment_dir=experiment_dir / "confirmation_runs",
            candidate=candidate,
            plan=plan,
            study_type=study_type,
            decision="confirmation_rerun",
            reason="confirmation_rerun",
        )
        ok, reason = evaluate_promotion(incumbent_result, rerun_result, config["acceptance"])
        incumbent_score = _candidate_score(incumbent_result, config["acceptance"]["primary_metric"])
        rerun_score = _candidate_score(rerun_result, config["acceptance"]["primary_metric"])
        if rerun_score <= incumbent_score:
            ok = False
            reason = "confirmation_primary_not_improved"
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


def run_compare_mode(config: dict[str, Any], benchmarks: Benchmarks, experiment_dir: Path, suite_id: str | None = None) -> None:
    config = normalize_config(config)
    writer = ResultsWriter(experiment_dir)
    plan = _suite_plan(config, _suite_id_for_study(config, "compare", suite_id))
    benchmark_id = plan.benchmark_ids[0]
    primary_metric = plan.primary_metric
    config = {
        **config,
        "acceptance": {
            **config["acceptance"],
            "primary_metric": primary_metric,
        },
    }
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": "compare",
            "benchmark_id": benchmark_id,
            "suite_id": plan.suite_id,
            "benchmark_ids": plan.benchmark_ids,
            "replicates": {"count": plan.replicate_count, "continue_on_failure": plan.continue_on_failure},
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
    compare_policy = _compare_policy(config)

    for planned_benchmark_id in plan.benchmark_ids:
        benchmark = benchmarks.manifests[planned_benchmark_id]
        for external_result in benchmark.external_results or []:
            result = evaluate_external_result_once(
                config,
                experiment_dir=experiment_dir,
                benchmark_id=planned_benchmark_id,
                external_result=external_result,
                study_type="compare",
            )
            result.suite_id = plan.suite_id
            writer.append_result(result)
            results.append(result)

    for candidate in candidates:
        gate_probe = _probe_candidate_structured_output_mode(
            config,
            candidate=candidate,
            benchmark_id=benchmark_id,
        )
        gate_mode = gate_probe.get("structured_output_mode")
        gate_ineligible = (
            compare_policy["require_structured_output_for_extraction"]
            and gate_probe.get("probe_status") == "ok"
            and gate_mode == "none"
            and not compare_policy["allow_degraded_candidates"]
        )
        if gate_ineligible:
            result = _ineligible_result(
                config,
                candidate=candidate,
                benchmark_id=benchmark_id,
                reason="ineligible_structured_output_none",
                detail=(
                    "compare policy requires structured output for extraction and provider probing "
                    "returned structured_output_mode='none'"
                ),
                gate_details={
                    **gate_probe,
                    "policy": compare_policy,
                    "degraded_experimental": False,
                },
            )
            result.suite_id = plan.suite_id
            result.metadata["suite_execution"] = {
                "suite_id": plan.suite_id,
                "benchmark_ids": plan.benchmark_ids,
                "replicate_count": plan.replicate_count,
            }
            writer.append_result(result)
            results.append(result)
            _write_compare_progress(
                writer,
                config=config,
                benchmark_id=benchmark_id,
                primary_metric=primary_metric,
                results=results,
                progress_state="running",
            )
            continue

        result = _evaluate_candidate_with_suite_and_replicates(
            config,
            writer,
            experiment_dir=experiment_dir,
            candidate=candidate,
            plan=plan,
            study_type="compare",
            decision="not_promoted",
            reason="compare_mode_fixed_comparison",
        )
        if (
            compare_policy["require_structured_output_for_extraction"]
            and compare_policy["allow_degraded_candidates"]
            and gate_probe.get("probe_status") == "ok"
            and gate_mode == "none"
        ):
            result.metadata["eligibility_gate"] = {
                **gate_probe,
                "policy": compare_policy,
                "degraded_experimental": True,
            }
            result.decision_reason = "compare_mode_degraded_experimental"
        writer.append_result(result)
        results.append(result)
        _write_compare_progress(
            writer,
            config=config,
            benchmark_id=benchmark_id,
            primary_metric=primary_metric,
            results=results,
            progress_state="running",
        )

    ranked_results = _rank_compare_results(results, primary_metric)
    winner = next((result for result in ranked_results if _winner_eligible(result, config["acceptance"])), None)
    _write_compare_progress(
        writer,
        config=config,
        benchmark_id=benchmark_id,
        primary_metric=primary_metric,
        results=results,
        progress_state="completed",
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

    write_proposal_tables(experiment_dir)
    generate_compare_plots(experiment_dir, primary_metric)
    generate_suite_plots(experiment_dir, primary_metric)
    generate_experiment_report(experiment_dir)


def run_optimize_mode(config: dict[str, Any], benchmarks: Benchmarks, search_space: Any, experiment_dir: Path, suite_id: str | None = None) -> None:
    config = normalize_config(config)
    writer = ResultsWriter(experiment_dir)
    plan = _suite_plan(config, _suite_id_for_study(config, "optimize", suite_id))
    benchmark_id = plan.benchmark_ids[0]
    config = {
        **config,
        "acceptance": {
            **config["acceptance"],
            "primary_metric": plan.primary_metric,
        },
    }

    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": "optimize",
            "benchmark_id": benchmark_id,
            "suite_id": plan.suite_id,
            "benchmark_ids": plan.benchmark_ids,
            "replicates": {"count": plan.replicate_count, "continue_on_failure": plan.continue_on_failure},
            "rounds": config.get("optimize", {}).get("rounds", 0),
            "batch_size": config.get("optimize", {}).get("batch_size", 1),
        }
    )

    incumbent_candidate = _baseline_candidate(config)
    incumbent_result = _evaluate_candidate_with_suite_and_replicates(
        config,
        writer,
        experiment_dir=experiment_dir,
        candidate=incumbent_candidate,
        plan=plan,
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
        _write_optimize_progress(
            writer,
            config=config,
            benchmark_id=benchmark_id,
            all_results=[incumbent_result],
            incumbent_result=incumbent_result,
            round_summaries=[],
            proposer_enabled=bool(config.get("proposer", {}).get("enabled", False)),
            proposer_suggestion_count=0,
            progress_state="failed",
            fatal_error="baseline candidate failed before optimization rounds could start",
        )
        raise RuntimeError("Baseline candidate failed before optimization rounds could start")

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
    _write_optimize_progress(
        writer,
        config=config,
        benchmark_id=benchmark_id,
        all_results=all_results,
        incumbent_result=incumbent_result,
        round_summaries=round_summaries,
        proposer_enabled=proposer_enabled,
        proposer_suggestion_count=proposer_suggestion_count,
        progress_state="running",
    )

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
            _write_optimize_progress(
                writer,
                config=config,
                benchmark_id=benchmark_id,
                all_results=all_results,
                incumbent_result=incumbent_result,
                round_summaries=round_summaries,
                proposer_enabled=proposer_enabled,
                proposer_suggestion_count=proposer_suggestion_count,
                progress_state="running",
            )
            continue

        next_candidate_number += len(filtered)

        promoted_id: str | None = None
        best_accepted_result = incumbent_result
        best_accepted_candidate: Candidate | None = None
        decision_notes: list[str] = []
        challenger_results: list[tuple[Candidate, CandidateResult, bool, str]] = []

        for candidate in filtered:
            challenger_result = _evaluate_candidate_with_suite_and_replicates(
                config,
                writer,
                experiment_dir=experiment_dir,
                candidate=candidate,
                plan=plan,
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
                plan=plan,
                incumbent_result=incumbent_result,
                study_type="optimize",
            )
            best_accepted_result.metadata["confirmation_reruns"] = confirmation_payload
            if not confirmed:
                promoted_id = None
                best_accepted_result.promotion_decision = "rejected"
                best_accepted_result.decision_reason = "confirmation_rerun_failed"
                decision_notes.append(f"{best_accepted_candidate.candidate_id}:confirmation_rerun_failed")
                best_accepted_result = incumbent_result
                best_accepted_candidate = None

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
        _write_optimize_progress(
            writer,
            config=config,
            benchmark_id=benchmark_id,
            all_results=all_results,
            incumbent_result=incumbent_result,
            round_summaries=round_summaries,
            proposer_enabled=proposer_enabled,
            proposer_suggestion_count=proposer_suggestion_count,
            progress_state="running",
        )

    _write_optimize_progress(
        writer,
        config=config,
        benchmark_id=benchmark_id,
        all_results=all_results,
        incumbent_result=incumbent_result,
        round_summaries=round_summaries,
        proposer_enabled=proposer_enabled,
        proposer_suggestion_count=proposer_suggestion_count,
        progress_state="completed",
    )

    write_proposal_tables(experiment_dir)
    generate_optimize_plots(experiment_dir, config["acceptance"]["primary_metric"])
    generate_suite_plots(experiment_dir, config["acceptance"]["primary_metric"])
    generate_experiment_report(experiment_dir)


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
    primary_metric = payload.get("primary_metric")
    holdout_records = load_results_jsonl(holdout_dir)
    holdout_scores = [
        float(record.get("primary_metrics", {}).get(primary_metric, float("-inf")))
        for record in holdout_records
        if isinstance(record.get("primary_metrics"), dict)
        and record.get("primary_metrics", {}).get(primary_metric) is not None
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


def validate_best(config: dict[str, Any], benchmarks: Benchmarks, experiment_dir: Path, out_dir: Path) -> None:
    config = normalize_config(config)
    records = load_results_jsonl(experiment_dir)
    if not records:
        raise ValueError("No experiment records found")

    study_type = str(records[0].get("study_type", "optimize"))
    section = config.get(study_type) if isinstance(config.get(study_type), dict) else {}
    holdout_suite_id = str(section.get("holdout_suite_id") or "holdout_suite")
    plan = _suite_plan(config, holdout_suite_id)
    config = {
        **config,
        "acceptance": {
            **config["acceptance"],
            "primary_metric": plan.primary_metric,
        },
    }
    primary_metric = plan.primary_metric

    if study_type == "optimize":
        best_candidate_path = experiment_dir / "best_candidate.json"
        if not best_candidate_path.exists():
            raise ValueError("No best_candidate.json found for optimize holdout validation")
        best_candidate_payload = read_json(best_candidate_path)
        best_candidate_id = best_candidate_payload.get("candidate_id")
        selected = [record for record in records if record.get("candidate_id") == best_candidate_id]
        if not selected:
            raise ValueError("Configured optimize incumbent was not found in experiment results")
    else:
        top_k = int(config.get("compare", {}).get("holdout_top_k", 0) or 0)
        if top_k <= 0:
            return
        selected = sorted(
            records,
            key=lambda record: float(record.get("primary_metrics", {}).get(primary_metric, float("-inf"))),
            reverse=True,
        )[:top_k]

    writer = ResultsWriter(out_dir)
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": study_type,
            "benchmark_id": plan.benchmark_ids[0],
            "suite_id": plan.suite_id,
            "benchmark_ids": plan.benchmark_ids,
            "validation": True,
        }
    )

    for item in selected:
        candidate = Candidate(
            candidate_id=str(item["candidate_id"]),
            prompt_bundle_id=str(item["prompt_bundle_id"]),
            text_model_id=str(item["text_model_id"]),
            vision_model_id=item.get("vision_model_id"),
            optimizer_knobs=dict(item.get("optimizer_knobs_flat", {})),
            parent_candidate_id=item.get("parent_candidate_id"),
            round_index=None,
        )
        result = _evaluate_candidate_with_suite_and_replicates(
            config,
            writer,
            experiment_dir=out_dir,
            candidate=candidate,
            plan=plan,
            study_type=study_type,
            decision="validated",
            reason="holdout_validation",
        )
        writer.append_result(result)

    candidate_ids = [str(item["candidate_id"]) for item in selected]
    writer.write_experiment_summary(
        {
            "experiment_id": config["experiment_id"],
            "study_type": study_type,
            "benchmark_id": plan.benchmark_ids[0],
            "suite_id": plan.suite_id,
            "benchmark_ids": plan.benchmark_ids,
            "primary_metric": primary_metric,
            "validated_candidate_ids": candidate_ids,
            "candidate_count": len(candidate_ids),
            "completed_candidate_count": len(candidate_ids),
        }
    )
    _write_holdout_status(
        experiment_dir,
        holdout_dir=out_dir,
        candidate_ids=candidate_ids,
        benchmark_id=plan.benchmark_ids[0],
    )
    write_proposal_tables(experiment_dir)
    generate_experiment_report(experiment_dir)


def summarize(config: dict[str, Any], experiment_dir: Path) -> None:
    manifest = read_json(experiment_dir / "experiment.json")
    study_type = manifest.get("study_type", "optimize")
    primary_metric = config["acceptance"]["primary_metric"]
    if study_type == "compare":
        generate_compare_plots(experiment_dir, primary_metric)
    else:
        generate_optimize_plots(experiment_dir, primary_metric)
    write_proposal_tables(experiment_dir)
    generate_experiment_report(experiment_dir)
