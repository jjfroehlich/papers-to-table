from __future__ import annotations

import json
from typing import Iterable

from paper_eval.contracts import GoldDataset, LoadedRun, RunSummary, ScoredCell


def _checked_ratio(numerator: int, denominator: int, *, metric_name: str) -> float | None:
    value = _ratio(numerator, denominator)
    if value is None:
        return None
    if value < 0.0 or value > 1.0:
        raise ValueError(
            f"{metric_name} must be within [0, 1], got {value} from {numerator}/{denominator}."
        )
    return value


def build_run_summary(
    loaded_run: LoadedRun,
    gold_dataset: GoldDataset,
    scored_cells: Iterable[ScoredCell],
    *,
    judge_execution_summary: dict[str, object] | None = None,
) -> RunSummary:
    scored_cells = list(scored_cells)
    gold_cell_records = [cell for cell in scored_cells if cell.record_kind == "gold_cell"]
    gold_present_records = [cell for cell in gold_cell_records if cell.is_gold_present]
    gold_empty_records = [cell for cell in gold_cell_records if cell.is_gold_empty]
    metadata_gold_present_records = [cell for cell in gold_present_records if _is_metadata_record(cell)]
    content_gold_present_records = [cell for cell in gold_present_records if not _is_metadata_record(cell)]
    scored_records = [cell for cell in gold_cell_records if cell.was_scored]
    metadata_scored_records = [cell for cell in scored_records if _is_metadata_record(cell)]
    content_scored_records = [cell for cell in scored_records if not _is_metadata_record(cell)]
    structured_records = [cell for cell in scored_records if cell.field_type in {"boolean", "categorical", "numeric"}]
    boolean_records = [cell for cell in structured_records if cell.field_type == "boolean"]
    categorical_records = [cell for cell in structured_records if cell.field_type == "categorical"]
    numeric_records = [cell for cell in structured_records if cell.field_type == "numeric"]
    text_records = [cell for cell in scored_records if cell.field_type == "text"]
    judge_text_records = [cell for cell in text_records if cell.scoring_policy == "judge"]
    deterministic_text_records = [cell for cell in text_records if cell.scoring_policy == "deterministic"]
    judge_unclear_records = [cell for cell in gold_present_records if cell.field_type == "text" and cell.judge_verdict == "unclear"]
    judge_request_failed_records = [
        cell for cell in gold_present_records if "judge_request_failed" in cell.diagnostic_flags
    ]
    judge_json_schema_records = [cell for cell in gold_present_records if cell.judge_response_mode == "json_schema"]
    judge_json_object_records = [cell for cell in gold_present_records if cell.judge_response_mode == "json_object"]
    judge_prompt_only_records = [cell for cell in gold_present_records if cell.judge_response_mode == "none"]
    dual_judge_evaluable_records = [
        cell
        for cell in content_gold_present_records
        if {"judge_a", "judge_b"}.issubset(set((cell.judge_results or {}).keys()))
    ]
    anchor_valid_records = [cell for cell in scored_records if cell.anchor_valid]
    evidence_unvalidated_records = [
        cell for cell in scored_records if cell.evidence_present_but_unvalidated
    ]
    correct_and_anchored_records = [
        cell for cell in scored_records if cell.is_correct and cell.anchor_valid
    ]
    content_correct_and_anchored_records = [
        cell for cell in content_scored_records if cell.is_correct and cell.anchor_valid
    ]
    structured_support_supported_records = [
        cell
        for cell in structured_records
        if cell.diagnostics.get("structured_support_proxy", {}).get("status") == "supported"
    ]
    structured_support_unsupported_records = [
        cell
        for cell in structured_records
        if cell.diagnostics.get("structured_support_proxy", {}).get("status") == "unsupported"
    ]
    structured_support_unvalidated_records = [
        cell
        for cell in structured_records
        if cell.diagnostics.get("structured_support_proxy", {}).get("status") == "unvalidated"
    ]
    structured_support_evaluated_records = [
        *structured_support_supported_records,
        *structured_support_unsupported_records,
    ]
    covered_gold_present = [
        cell
        for cell in gold_present_records
        if cell.join_status == "matched" and cell.proposal_count == 1
    ]
    covered_content_gold_present = [
        cell
        for cell in content_gold_present_records
        if cell.join_status == "matched" and cell.proposal_count == 1
    ]
    join_problem_records = [
        cell
        for cell in scored_cells
        if cell.join_status in {"missing_proposal", "duplicate_proposals", "cell_id_mismatch", "unmatched_proposal"}
    ]
    judge_labels = sorted(
        {
            label
            for cell in gold_present_records
            for label in (cell.judge_results or {}).keys()
        }
    )
    correctness_by_judge = {
        label: _correctness_for_judge(content_gold_present_records, label)
        for label in judge_labels
    }
    available_correctness = [value for value in correctness_by_judge.values() if value is not None]
    content_correctness_scored_only = (
        sum(available_correctness) / len(available_correctness)
        if available_correctness
        else _accuracy(content_scored_records)
    )
    content_correctness_on_gold_present = _accuracy_with_unscored_as_incorrect(content_gold_present_records)
    overall_correctness_on_gold_present = _accuracy_with_unscored_as_incorrect(gold_present_records)
    overall_correctness_mean = _accuracy(scored_records)
    content_proposal_coverage_on_gold_present = _checked_ratio(
        len(covered_content_gold_present),
        len(content_gold_present_records),
        metric_name="proposal_coverage_on_content_gold_present",
    )
    overall_proposal_coverage_on_gold_present = _checked_ratio(
        len(covered_gold_present),
        len(gold_present_records),
        metric_name="proposal_coverage_on_all_gold_present",
    )
    judge_disagreement_records = [
        cell
        for cell in content_gold_present_records
        if bool(cell.judge_disagreement)
    ]
    judge_disagreement_evaluable = [
        cell
        for cell in content_gold_present_records
        if len(
            [
                result
                for result in (cell.judge_results or {}).values()
                if result.get("verdict") in {"correct", "incorrect"}
            ]
        ) >= 2
    ]
    correctness_abs_delta = _judge_abs_delta(correctness_by_judge.get("judge_a"), correctness_by_judge.get("judge_b"))
    evidence_audit = _build_evidence_audit(scored_records)
    metadata_summary = _build_metadata_summary(metadata_gold_present_records)
    judge_summary = _build_judge_summary(gold_present_records)

    metrics = {
        "content_correctness": content_correctness_on_gold_present,
        "content_correctness_on_gold_present": content_correctness_on_gold_present,
        "content_correctness_mean": content_correctness_scored_only,
        "content_correctness_scored_only": content_correctness_scored_only,
        "correctness": content_correctness_on_gold_present,
        "correctness_on_gold_present": content_correctness_on_gold_present,
        "correctness_mean": content_correctness_scored_only,
        "correctness_scored_only": content_correctness_scored_only,
        "overall_correctness": overall_correctness_on_gold_present,
        "overall_correctness_on_gold_present": overall_correctness_on_gold_present,
        "overall_correctness_mean": overall_correctness_mean,
        "overall_correctness_scored_only": overall_correctness_mean,
        "metadata_correctness": _accuracy_with_unscored_as_incorrect(metadata_gold_present_records),
        "metadata_correctness_mean": _accuracy(metadata_scored_records),
        "correctness_judge_a": correctness_by_judge.get("judge_a"),
        "correctness_judge_b": correctness_by_judge.get("judge_b"),
        "correctness_abs_delta": correctness_abs_delta,
        "judge_disagreement": correctness_abs_delta,
        "judge_disagreement_count": len(judge_disagreement_records),
        "judge_disagreement_rate": _ratio(len(judge_disagreement_records), len(judge_disagreement_evaluable)),
        "dual_judge_cell_count": len(dual_judge_evaluable_records),
        "dual_judge_completed": len(dual_judge_evaluable_records) > 0,
        "structured_accuracy": _accuracy(structured_records),
        "boolean_accuracy": _accuracy(boolean_records),
        "categorical_accuracy": _accuracy(categorical_records),
        "numeric_accuracy": _accuracy(numeric_records),
        "text_accuracy": _accuracy(text_records),
        "proposal_coverage_on_content_gold_present": content_proposal_coverage_on_gold_present,
        "proposal_coverage_on_all_gold_present": overall_proposal_coverage_on_gold_present,
        "proposal_coverage_on_gold_present": content_proposal_coverage_on_gold_present,
        "anchor_valid_rate": _ratio(len(anchor_valid_records), len(scored_records)),
        "content_anchor_valid_rate": _ratio(
            sum(1 for cell in content_scored_records if cell.anchor_valid),
            len(content_scored_records),
        ),
        "correct_and_anchored_rate": _ratio(len(correct_and_anchored_records), len(scored_records)),
        "evidence_grounded_correctness": _ratio(
            len(content_correct_and_anchored_records), len(content_gold_present_records)
        ),
        "content_correct_and_anchored_rate": _ratio(
            len(content_correct_and_anchored_records), len(content_scored_records)
        ),
        "structured_support_proxy_supported_rate": _ratio(
            len(structured_support_supported_records), len(structured_support_evaluated_records)
        ),
        "gold_present_cell_count": len(gold_present_records),
        "content_gold_present_cell_count": len(content_gold_present_records),
        "metadata_gold_present_cell_count": len(metadata_gold_present_records),
        "gold_empty_cell_count": len(gold_empty_records),
        "filled_on_gold_empty_count": sum(1 for cell in gold_empty_records if cell.proposal_count > 0),
        "structured_scored_cell_count": len(structured_records),
        "structured_support_proxy_evaluated_count": len(structured_support_evaluated_records),
        "structured_support_proxy_supported_count": len(structured_support_supported_records),
        "structured_support_proxy_unsupported_count": len(structured_support_unsupported_records),
        "structured_support_proxy_unvalidated_count": len(structured_support_unvalidated_records),
        "scored_cell_count": len(scored_records),
        "boolean_scored_cell_count": len(boolean_records),
        "categorical_scored_cell_count": len(categorical_records),
        "numeric_scored_cell_count": len(numeric_records),
        "text_scored_cell_count": len(text_records),
        "judge_text_scored_cell_count": len(judge_text_records),
        "deterministic_text_scored_cell_count": len(deterministic_text_records),
        "judge_unclear_text_cell_count": len(judge_unclear_records),
        "judge_request_failed_count": len(judge_request_failed_records),
        "judge_json_schema_text_cell_count": len(judge_json_schema_records),
        "judge_json_object_text_cell_count": len(judge_json_object_records),
        "judge_prompt_only_text_cell_count": len(judge_prompt_only_records),
        "judge_a_request_failed_count": _judge_flag_count(gold_present_records, "judge_a", "error_message"),
        "judge_b_request_failed_count": _judge_flag_count(gold_present_records, "judge_b", "error_message"),
        "judge_a_unclear_text_cell_count": _judge_verdict_count(gold_present_records, "judge_a", "unclear"),
        "judge_b_unclear_text_cell_count": _judge_verdict_count(gold_present_records, "judge_b", "unclear"),
        "anchor_valid_count": len(anchor_valid_records),
        "evidence_present_but_unvalidated_count": len(evidence_unvalidated_records),
        "evidence_item_count": evidence_audit["evidence_item_count"],
        "missing_evidence_count": evidence_audit["missing_evidence_count"],
        "validated_evidence_item_count": evidence_audit["validated_evidence_item_count"],
        "anchor_invalid_count": evidence_audit["anchor_invalid_count"],
        "evidence_anchor_reason_counts": evidence_audit["reason_counts"],
        "evidence_anchor_outcome_counts": evidence_audit["outcome_counts"],
        "evidence_anchor_audit": evidence_audit,
        "unscored_text_cell_count": sum(1 for cell in gold_present_records if cell.field_type == "text" and not cell.was_scored),
        "missing_proposal_count": sum(1 for cell in gold_present_records if cell.join_status == "missing_proposal"),
        "duplicate_proposal_join_count": sum(
            1 for cell in gold_present_records if cell.join_status == "duplicate_proposals"
        ),
        "cell_id_mismatch_count": sum(1 for cell in gold_present_records if cell.join_status == "cell_id_mismatch"),
        "unmatched_proposal_count": sum(
            1 for cell in scored_cells if cell.join_status == "unmatched_proposal"
        ),
        "join_failure_count": len(join_problem_records),
        "contract_warning_count": len(loaded_run.contract_warnings),
        "extraction_contract_valid": loaded_run.metadata.extraction_contract_valid,
        "parser_gap_count": _failure_attribution_count(scored_cells, "parser_gap"),
        "retrieval_miss_count": _failure_attribution_count(scored_cells, "retrieval_miss"),
        "extraction_miss_count": _failure_attribution_count(scored_cells, "extraction_miss"),
        "evidence_ambiguity_count": _failure_attribution_count(scored_cells, "evidence_ambiguity"),
        "judge_failure_count": _failure_attribution_count(scored_cells, "judge_failure"),
        "judge_unclear_count": _failure_attribution_count(scored_cells, "judge_unclear"),
        "degraded_run_count": 1 if loaded_run.metadata.prompt_only_degraded_mode_used else 0,
        "contract_invalid_count": 0 if loaded_run.metadata.extraction_contract_valid is not False else 1,
        "benchmark_style_profile_mode": loaded_run.metadata.style_profile_mode,
        "metadata_summary": metadata_summary,
        "judge_summary": judge_summary,
        "judge_execution_summary": judge_execution_summary or {},
    }

    scored = content_correctness_scored_only is not None
    unscored_reason = _determine_unscored_reason(
        loaded_run=loaded_run,
        metrics=metrics,
        gold_present_records=gold_present_records,
        join_problem_records=join_problem_records,
    )
    unscored_reason_detail = _determine_unscored_reason_detail(
        loaded_run=loaded_run,
        metrics=metrics,
        gold_present_records=gold_present_records,
        join_problem_records=join_problem_records,
    )
    metrics["scored"] = scored
    metrics["unscored_reason"] = unscored_reason
    metrics["unscored_reason_detail"] = unscored_reason_detail

    join_diagnostics = [
        f"{cell.join_status}:{cell.row_id}:{cell.column_name}:{cell.cell_id}"
        for cell in join_problem_records
    ]
    return RunSummary(
        run_id=loaded_run.metadata.run_id,
        run_dir=loaded_run.run_dir,
        gold_source=gold_dataset.source_path,
        gold_sheet=gold_dataset.sheet_name,
        metrics=metrics,
        metadata=loaded_run.metadata.flat_metadata(),
        scored=scored,
        unscored_reason=unscored_reason,
        unscored_reason_detail=unscored_reason_detail,
        contract_warnings=list(loaded_run.contract_warnings),
        join_diagnostics=join_diagnostics,
    )


def comparison_row_from_summary(summary: RunSummary) -> dict[str, object]:
    row: dict[str, object] = {
        "run_id": summary.run_id,
        "run_dir": str(summary.run_dir),
        "gold_source": str(summary.gold_source),
        "gold_sheet": summary.gold_sheet,
        "scored": summary.scored,
        "unscored_reason": summary.unscored_reason,
        "unscored_reason_detail": summary.unscored_reason_detail,
        "contract_warning_count": len(summary.contract_warnings),
        "join_diagnostic_count": len(summary.join_diagnostics),
        "contract_warnings": json.dumps(summary.contract_warnings),
        "join_diagnostics": json.dumps(summary.join_diagnostics),
    }
    row.update(summary.metadata)
    row.update(summary.metrics)
    return row


def _accuracy(records: list[ScoredCell]) -> float | None:
    if not records:
        return None
    correct = sum(1 for record in records if record.is_correct)
    return correct / len(records)


def _accuracy_with_unscored_as_incorrect(records: list[ScoredCell]) -> float | None:
    if not records:
        return None
    correct = sum(1 for record in records if record.is_correct is True)
    return correct / len(records)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator


def _correctness_for_judge(records: list[ScoredCell], judge_label: str) -> float | None:
    values: list[float] = []
    for record in records:
        if record.field_type != "text" or record.scoring_policy != "judge":
            if record.was_scored and record.is_correct is not None:
                values.append(1.0 if record.is_correct else 0.0)
            continue
        judge_result = (record.judge_results or {}).get(judge_label, {})
        verdict = judge_result.get("verdict")
        if verdict == "correct":
            values.append(1.0)
        elif verdict == "incorrect":
            values.append(0.0)
    if not values:
        return None
    return sum(values) / len(values)


def _judge_verdict_count(records: list[ScoredCell], judge_label: str, verdict: str) -> int:
    return sum(
        1
        for record in records
        if (record.judge_results or {}).get(judge_label, {}).get("verdict") == verdict
    )


def _judge_flag_count(records: list[ScoredCell], judge_label: str, key: str) -> int:
    return sum(
        1
        for record in records
        if bool((record.judge_results or {}).get(judge_label, {}).get(key))
    )


def _judge_abs_delta(first: float | None, second: float | None) -> float | None:
    if first is None or second is None:
        return None
    return abs(first - second)


def _build_evidence_audit(records: Iterable[ScoredCell]) -> dict[str, object]:
    evidence_item_count = 0
    validated_evidence_item_count = 0
    anchor_invalid_count = 0
    evidence_present_but_unvalidated_count = 0
    reason_counts: dict[str, int] = {}
    outcome_counts: dict[str, int] = {}

    for record in records:
        evidence = record.diagnostics.get("evidence", {}) if isinstance(record.diagnostics, dict) else {}
        evidence_item_count += int(evidence.get("evidence_item_count") or 0)
        validated_evidence_item_count += int(evidence.get("validated_evidence_item_count") or 0)
        anchor_invalid_count += int(evidence.get("anchor_invalid_count") or 0)
        evidence_present_but_unvalidated_count += int(evidence.get("evidence_present_but_unvalidated_count") or 0)
        for key, value in (evidence.get("reason_counts") or {}).items():
            reason_counts[str(key)] = reason_counts.get(str(key), 0) + int(value or 0)
        for key, value in (evidence.get("outcome_counts") or {}).items():
            outcome_counts[str(key)] = outcome_counts.get(str(key), 0) + int(value or 0)

    return {
        "evidence_item_count": evidence_item_count,
        "missing_evidence_count": outcome_counts.get("missing_evidence", 0),
        "validated_evidence_item_count": validated_evidence_item_count,
        "anchor_valid_count": validated_evidence_item_count,
        "anchor_valid_rate": _ratio(validated_evidence_item_count, evidence_item_count),
        "anchor_invalid_count": anchor_invalid_count,
        "anchor_invalid_rate": _ratio(anchor_invalid_count, evidence_item_count),
        "evidence_present_but_unvalidated_count": evidence_present_but_unvalidated_count,
        "evidence_present_but_unvalidated_rate": _ratio(
            evidence_present_but_unvalidated_count, evidence_item_count
        ),
        "reason_counts": dict(sorted(reason_counts.items())),
        "outcome_counts": dict(sorted(outcome_counts.items())),
    }


def _metadata_field_kind(record: ScoredCell) -> str:
    field_kind = (
        (record.diagnostics.get("metadata_diagnostics") or {}).get("field_kind")
        if isinstance(record.diagnostics, dict)
        else None
    )
    if isinstance(field_kind, str) and field_kind.strip():
        return field_kind.strip()
    return (record.column_name or "unknown").strip().lower()


def _build_metadata_summary(records: Iterable[ScoredCell]) -> dict[str, object]:
    by_field: dict[str, dict[str, object]] = {}
    for record in records:
        field_kind = _metadata_field_kind(record)
        field_row = by_field.setdefault(
            field_kind,
            {
                "total": 0,
                "found": 0,
                "unclear": 0,
                "missing_proposal": 0,
                "failure_attribution": {},
            },
        )
        field_row["total"] = int(field_row["total"]) + 1
        state = "found" if record.join_status == "matched" else ("missing_proposal" if record.join_status == "missing_proposal" else "unclear")
        field_row[state] = int(field_row[state]) + 1
        if record.failure_attribution:
            failure_map = field_row["failure_attribution"]
            assert isinstance(failure_map, dict)
            failure_map[record.failure_attribution] = int(failure_map.get(record.failure_attribution, 0)) + 1

    aggregate_failure_counts: dict[str, int] = {}
    for row in by_field.values():
        failure_map = row["failure_attribution"]
        assert isinstance(failure_map, dict)
        total = int(row["total"])
        row["found_rate"] = _ratio(int(row["found"]), total)
        row["unclear_rate"] = _ratio(int(row["unclear"]), total)
        row["missing_proposal_rate"] = _ratio(int(row["missing_proposal"]), total)
        row["failure_attribution"] = dict(sorted(failure_map.items()))
        for key, value in failure_map.items():
            aggregate_failure_counts[key] = aggregate_failure_counts.get(key, 0) + int(value)

    return {
        "field_kind_count": len(by_field),
        "fields": dict(sorted(by_field.items())),
        "failure_attribution": dict(sorted(aggregate_failure_counts.items())),
    }


def _build_judge_summary(records: Iterable[ScoredCell]) -> dict[str, object]:
    records_list = list(records)
    labels = sorted(
        {
            label
            for record in records_list
            for label in (record.judge_results or {}).keys()
        }
    )
    response_modes: dict[str, dict[str, int]] = {}
    request_failed: dict[str, int] = {}
    unclear_counts: dict[str, int] = {}
    verdict_counts: dict[str, dict[str, int]] = {}
    for label in labels:
        response_modes[label] = {}
        verdict_counts[label] = {}
        request_failed[label] = _judge_flag_count(records_list, label, "error_message")
        unclear_counts[label] = _judge_verdict_count(records_list, label, "unclear")
    for label in labels:
        for record in records_list:
            result = (record.judge_results or {}).get(label, {})
            mode = result.get("response_mode")
            verdict = result.get("verdict")
            if mode:
                response_modes[label][str(mode)] = response_modes[label].get(str(mode), 0) + 1
            if verdict:
                verdict_counts[label][str(verdict)] = verdict_counts[label].get(str(verdict), 0) + 1
        response_modes[label] = dict(sorted(response_modes[label].items()))
        verdict_counts[label] = dict(sorted(verdict_counts[label].items()))
    return {
        "configured_labels": labels,
        "dual_judge_configured": {"judge_a", "judge_b"}.issubset(set(labels)),
        "request_failed_count": request_failed,
        "unclear_count": unclear_counts,
        "response_modes": response_modes,
        "verdict_counts": verdict_counts,
    }


def _is_metadata_record(record: ScoredCell) -> bool:
    if record.extraction_lane == "metadata_front_matter":
        return True
    metadata_columns = {
        "title",
        "authors",
        "author",
        "journal",
        "publication",
        "venue",
        "year",
        "publication_year",
        "doi",
        "pmid",
        "url",
        "link",
        "abstract",
    }
    return record.column_name.strip().lower() in metadata_columns


def _failure_attribution_count(records: Iterable[ScoredCell], reason: str) -> int:
    return sum(1 for record in records if record.failure_attribution == reason)


def _determine_unscored_reason(
    *,
    loaded_run: LoadedRun,
    metrics: dict[str, object],
    gold_present_records: list[ScoredCell],
    join_problem_records: list[ScoredCell],
) -> str | None:
    if metrics.get("content_correctness_scored_only") is not None:
        return None
    extraction_contract_valid = loaded_run.metadata.extraction_contract_valid
    if extraction_contract_valid is False:
        return "invalid_run_bundle_contract"
    if not gold_present_records:
        return "missing_required_eval_inputs"
    if int(metrics.get("judge_request_failed_count", 0) or 0) > 0:
        return "judge_failure"
    if join_problem_records:
        return "no_joinable_predictions"
    return "missing_required_eval_inputs"


def _determine_unscored_reason_detail(
    *,
    loaded_run: LoadedRun,
    metrics: dict[str, object],
    gold_present_records: list[ScoredCell],
    join_problem_records: list[ScoredCell],
) -> str | None:
    if metrics.get("content_correctness_scored_only") is not None:
        return None
    extraction_contract_valid = loaded_run.metadata.extraction_contract_valid
    if extraction_contract_valid is False:
        warnings = loaded_run.metadata.extraction_contract_warnings or loaded_run.contract_warnings
        if warnings:
            return ", ".join(str(item) for item in warnings[:5])
        return "run bundle marked structurally invalid for evaluation"
    if not gold_present_records:
        return "no gold-present cells remained after run/gold scoping"
    judge_failures = int(metrics.get("judge_request_failed_count", 0) or 0)
    if judge_failures > 0:
        return f"{judge_failures} judge request failures prevented a headline score"
    if join_problem_records:
        return f"{len(join_problem_records)} join problems prevented a usable score"
    return "required eval inputs were missing or no scoreable cells remained"
