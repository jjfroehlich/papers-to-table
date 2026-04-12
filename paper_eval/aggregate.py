from __future__ import annotations

import json
from typing import Iterable

from paper_eval.contracts import GoldDataset, LoadedRun, RunSummary, ScoredCell


def build_run_summary(
    loaded_run: LoadedRun,
    gold_dataset: GoldDataset,
    scored_cells: Iterable[ScoredCell],
) -> RunSummary:
    scored_cells = list(scored_cells)
    gold_cell_records = [cell for cell in scored_cells if cell.record_kind == "gold_cell"]
    gold_present_records = [cell for cell in gold_cell_records if cell.is_gold_present]
    gold_empty_records = [cell for cell in gold_cell_records if cell.is_gold_empty]
    scored_records = [cell for cell in gold_cell_records if cell.was_scored]
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
    anchor_valid_records = [cell for cell in scored_records if cell.anchor_valid]
    evidence_unvalidated_records = [
        cell for cell in scored_records if cell.evidence_present_but_unvalidated
    ]
    correct_and_anchored_records = [
        cell for cell in scored_records if cell.is_correct and cell.anchor_valid
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
        label: _correctness_for_judge(gold_present_records, label)
        for label in judge_labels
    }
    available_correctness = [value for value in correctness_by_judge.values() if value is not None]
    correctness_mean = (
        sum(available_correctness) / len(available_correctness)
        if available_correctness
        else _accuracy(scored_records)
    )
    judge_disagreement_records = [
        cell
        for cell in gold_present_records
        if bool(cell.judge_disagreement)
    ]
    judge_disagreement_evaluable = [
        cell
        for cell in gold_present_records
        if len(
            [
                result
                for result in (cell.judge_results or {}).values()
                if result.get("verdict") in {"correct", "incorrect"}
            ]
        ) >= 2
    ]
    correctness_abs_delta = _judge_abs_delta(correctness_by_judge.get("judge_a"), correctness_by_judge.get("judge_b"))

    metrics = {
        "correctness": correctness_mean,
        "correctness_mean": correctness_mean,
        "correctness_judge_a": correctness_by_judge.get("judge_a"),
        "correctness_judge_b": correctness_by_judge.get("judge_b"),
        "correctness_abs_delta": correctness_abs_delta,
        "judge_disagreement": correctness_abs_delta,
        "judge_disagreement_count": len(judge_disagreement_records),
        "judge_disagreement_rate": _ratio(len(judge_disagreement_records), len(judge_disagreement_evaluable)),
        "structured_accuracy": _accuracy(structured_records),
        "boolean_accuracy": _accuracy(boolean_records),
        "categorical_accuracy": _accuracy(categorical_records),
        "numeric_accuracy": _accuracy(numeric_records),
        "text_accuracy": _accuracy(text_records),
        "proposal_coverage_on_gold_present": _ratio(len(covered_gold_present), len(gold_present_records)),
        "anchor_valid_rate": _ratio(len(anchor_valid_records), len(scored_records)),
        "correct_and_anchored_rate": _ratio(len(correct_and_anchored_records), len(scored_records)),
        "structured_support_proxy_supported_rate": _ratio(
            len(structured_support_supported_records), len(structured_support_evaluated_records)
        ),
        "gold_present_cell_count": len(gold_present_records),
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
    }

    scored = correctness_mean is not None
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


def _determine_unscored_reason(
    *,
    loaded_run: LoadedRun,
    metrics: dict[str, object],
    gold_present_records: list[ScoredCell],
    join_problem_records: list[ScoredCell],
) -> str | None:
    if metrics.get("correctness_mean") is not None:
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
    if metrics.get("correctness_mean") is not None:
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
