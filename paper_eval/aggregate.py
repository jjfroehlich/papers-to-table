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

    metrics = {
        "structured_accuracy": _accuracy(structured_records),
        "boolean_accuracy": _accuracy(boolean_records),
        "categorical_accuracy": _accuracy(categorical_records),
        "numeric_accuracy": _accuracy(numeric_records),
        "text_accuracy": _accuracy(text_records),
        "proposal_coverage_on_gold_present": _ratio(len(covered_gold_present), len(gold_present_records)),
        "anchor_valid_rate": _ratio(len(anchor_valid_records), len(scored_records)),
        "correct_and_anchored_rate": _ratio(len(correct_and_anchored_records), len(scored_records)),
        "gold_present_cell_count": len(gold_present_records),
        "gold_empty_cell_count": len(gold_empty_records),
        "filled_on_gold_empty_count": sum(1 for cell in gold_empty_records if cell.proposal_count > 0),
        "structured_scored_cell_count": len(structured_records),
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
    }

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
        contract_warnings=list(loaded_run.contract_warnings),
        join_diagnostics=join_diagnostics,
    )


def comparison_row_from_summary(summary: RunSummary) -> dict[str, object]:
    row: dict[str, object] = {
        "run_id": summary.run_id,
        "run_dir": str(summary.run_dir),
        "gold_source": str(summary.gold_source),
        "gold_sheet": summary.gold_sheet,
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
