from __future__ import annotations

from typing import Iterable

from paper_eval.contracts import GoldDataset, LoadedRun, RunSummary, ScoredCell


def build_run_summary(
    loaded_run: LoadedRun,
    gold_dataset: GoldDataset,
    scored_cells: Iterable[ScoredCell],
) -> RunSummary:
    scored_cells = list(scored_cells)
    gold_cell_records = [cell for cell in scored_cells if cell.record_kind == "gold_cell"]
    structured_records = [cell for cell in gold_cell_records if cell.was_scored]
    boolean_records = [cell for cell in structured_records if cell.field_type == "boolean"]
    categorical_records = [cell for cell in structured_records if cell.field_type == "categorical"]
    numeric_records = [cell for cell in structured_records if cell.field_type == "numeric"]

    gold_present_records = [cell for cell in gold_cell_records if cell.is_gold_present]
    gold_empty_records = [cell for cell in gold_cell_records if cell.is_gold_empty]
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
        "proposal_coverage_on_gold_present": _ratio(len(covered_gold_present), len(gold_present_records)),
        "gold_present_cell_count": len(gold_present_records),
        "gold_empty_cell_count": len(gold_empty_records),
        "filled_on_gold_empty_count": sum(1 for cell in gold_empty_records if cell.proposal_count > 0),
        "structured_scored_cell_count": len(structured_records),
        "boolean_scored_cell_count": len(boolean_records),
        "categorical_scored_cell_count": len(categorical_records),
        "numeric_scored_cell_count": len(numeric_records),
        "unscored_text_cell_count": sum(
            1 for cell in gold_present_records if "text_scoring_not_implemented_in_batch_1" in cell.diagnostic_flags
        ),
        "missing_proposal_count": sum(1 for cell in gold_present_records if cell.join_status == "missing_proposal"),
        "duplicate_proposal_join_count": sum(
            1 for cell in gold_present_records if cell.join_status == "duplicate_proposals"
        ),
        "cell_id_mismatch_count": sum(1 for cell in gold_present_records if cell.join_status == "cell_id_mismatch"),
        "unmatched_proposal_count": sum(
            1 for cell in scored_cells if cell.join_status == "unmatched_proposal"
        ),
        "join_failure_count": len(join_problem_records),
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


def _accuracy(records: list[ScoredCell]) -> float | None:
    if not records:
        return None
    correct = sum(1 for record in records if record.is_correct)
    return correct / len(records)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
