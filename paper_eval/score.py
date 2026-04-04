from __future__ import annotations

from collections import defaultdict
from typing import Any

from paper_eval.compare_structured import compare_boolean, compare_categorical, compare_numeric
from paper_eval.contracts import (
    GoldDataset,
    LoadedRun,
    NumericTolerance,
    ResolvedFieldConfig,
    ScoredCell,
    STRUCTURED_FIELD_TYPES,
    EvaluatorSchema,
)
from paper_eval.normalize import normalize_boolean, normalize_numeric


def score_run(
    loaded_run: LoadedRun,
    gold_dataset: GoldDataset,
    schema: EvaluatorSchema,
) -> list[ScoredCell]:
    proposals_by_key: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for proposal in loaded_run.proposals:
        proposals_by_key[proposal.join_key].append(proposal)

    gold_keys = {cell.join_key for cell in gold_dataset.cells}
    scored_cells: list[ScoredCell] = []

    for gold_cell in gold_dataset.cells:
        proposals = proposals_by_key.get(gold_cell.join_key, [])
        proposal_count = len(proposals)

        if not gold_cell.is_present:
            scored_cells.append(
                ScoredCell(
                    record_kind="gold_cell",
                    run_id=loaded_run.metadata.run_id,
                    row_id=gold_cell.row_id,
                    column_name=gold_cell.column_name,
                    cell_id=gold_cell.cell_id,
                    gold_value=gold_cell.raw_value,
                    proposed_value=proposals[0].proposed_value if proposal_count == 1 else None,
                    field_type=proposals[0].field_type if proposal_count == 1 else None,
                    scoring_policy=proposals[0].scoring_policy if proposal_count == 1 else None,
                    is_gold_present=False,
                    is_gold_empty=True,
                    was_scored=False,
                    is_correct=None,
                    join_status="gold_empty_diagnostic",
                    comparison_kind="not_scored",
                    evidence_outcome="not_evaluated",
                    proposal_count=proposal_count,
                    row_index=gold_cell.row_index,
                    diagnostic_flags=["gold_empty_unscored"]
                    + (["filled_on_gold_empty"] if proposal_count else []),
                    diagnostics={},
                )
            )
            continue

        if proposal_count == 0:
            scored_cells.append(
                ScoredCell(
                    record_kind="gold_cell",
                    run_id=loaded_run.metadata.run_id,
                    row_id=gold_cell.row_id,
                    column_name=gold_cell.column_name,
                    cell_id=gold_cell.cell_id,
                    gold_value=gold_cell.raw_value,
                    proposed_value=None,
                    field_type=None,
                    scoring_policy=None,
                    is_gold_present=True,
                    is_gold_empty=False,
                    was_scored=False,
                    is_correct=None,
                    join_status="missing_proposal",
                    comparison_kind="not_scored",
                    evidence_outcome="not_evaluated",
                    proposal_count=0,
                    row_index=gold_cell.row_index,
                    diagnostic_flags=["missing_proposal_for_gold_present"],
                    diagnostics={},
                )
            )
            continue

        if proposal_count > 1:
            scored_cells.append(
                ScoredCell(
                    record_kind="gold_cell",
                    run_id=loaded_run.metadata.run_id,
                    row_id=gold_cell.row_id,
                    column_name=gold_cell.column_name,
                    cell_id=gold_cell.cell_id,
                    gold_value=gold_cell.raw_value,
                    proposed_value=None,
                    field_type=None,
                    scoring_policy=None,
                    is_gold_present=True,
                    is_gold_empty=False,
                    was_scored=False,
                    is_correct=None,
                    join_status="duplicate_proposals",
                    comparison_kind="not_scored",
                    evidence_outcome="not_evaluated",
                    proposal_count=proposal_count,
                    row_index=gold_cell.row_index,
                    diagnostic_flags=["duplicate_proposals_for_join_key"],
                    diagnostics={"proposal_cell_ids": [proposal.cell_id for proposal in proposals]},
                )
            )
            continue

        proposal = proposals[0]
        if gold_cell.cell_id and proposal.cell_id != gold_cell.cell_id:
            scored_cells.append(
                ScoredCell(
                    record_kind="gold_cell",
                    run_id=loaded_run.metadata.run_id,
                    row_id=gold_cell.row_id,
                    column_name=gold_cell.column_name,
                    cell_id=gold_cell.cell_id,
                    gold_value=gold_cell.raw_value,
                    proposed_value=proposal.proposed_value,
                    field_type=proposal.field_type,
                    scoring_policy=proposal.scoring_policy,
                    is_gold_present=True,
                    is_gold_empty=False,
                    was_scored=False,
                    is_correct=None,
                    join_status="cell_id_mismatch",
                    comparison_kind="not_scored",
                    evidence_outcome="not_evaluated",
                    proposal_count=1,
                    row_index=gold_cell.row_index,
                    diagnostic_flags=["proposal_cell_id_mismatch"],
                    diagnostics={"gold_cell_id": gold_cell.cell_id, "proposal_cell_id": proposal.cell_id},
                    selected_proposal_state=proposal.state,
                )
            )
            continue

        field_config = resolve_field_config(
            column_name=gold_cell.column_name,
            gold_value=gold_cell.raw_value,
            proposal=proposal,
            schema=schema,
        )
        if field_config.field_type not in STRUCTURED_FIELD_TYPES:
            scored_cells.append(
                ScoredCell(
                    record_kind="gold_cell",
                    run_id=loaded_run.metadata.run_id,
                    row_id=gold_cell.row_id,
                    column_name=gold_cell.column_name,
                    cell_id=proposal.cell_id,
                    gold_value=gold_cell.raw_value,
                    proposed_value=proposal.proposed_value,
                    field_type=field_config.field_type,
                    scoring_policy=field_config.scoring_policy,
                    is_gold_present=True,
                    is_gold_empty=False,
                    was_scored=False,
                    is_correct=None,
                    join_status="matched",
                    comparison_kind="text",
                    evidence_outcome="not_evaluated",
                    proposal_count=1,
                    row_index=gold_cell.row_index,
                    diagnostic_flags=["text_scoring_not_implemented_in_batch_1"],
                    diagnostics={},
                    selected_proposal_state=proposal.state,
                )
            )
            continue

        comparison = _compare_structured(
            field_type=field_config.field_type,
            gold_value=gold_cell.raw_value,
            proposed_value=proposal.proposed_value,
            aliases=field_config.aliases,
            allowed_values=field_config.allowed_values,
            numeric_tolerance=field_config.numeric_tolerance,
        )

        scored_cells.append(
            ScoredCell(
                record_kind="gold_cell",
                run_id=loaded_run.metadata.run_id,
                row_id=gold_cell.row_id,
                column_name=gold_cell.column_name,
                cell_id=proposal.cell_id,
                gold_value=gold_cell.raw_value,
                proposed_value=proposal.proposed_value,
                field_type=field_config.field_type,
                scoring_policy=field_config.scoring_policy,
                is_gold_present=True,
                is_gold_empty=False,
                was_scored=True,
                is_correct=comparison.is_correct,
                join_status="matched",
                comparison_kind=field_config.field_type,
                evidence_outcome="not_evaluated",
                proposal_count=1,
                row_index=gold_cell.row_index,
                normalized_gold=comparison.normalized_gold,
                normalized_proposed=comparison.normalized_proposed,
                diagnostics=comparison.diagnostics,
                selected_proposal_state=proposal.state,
            )
        )

    for join_key, proposals in proposals_by_key.items():
        if join_key in gold_keys:
            continue
        for proposal in proposals:
            scored_cells.append(
                ScoredCell(
                    record_kind="proposal_diagnostic",
                    run_id=loaded_run.metadata.run_id,
                    row_id=proposal.row_id,
                    column_name=proposal.column_name,
                    cell_id=proposal.cell_id,
                    gold_value=None,
                    proposed_value=proposal.proposed_value,
                    field_type=proposal.field_type,
                    scoring_policy=proposal.scoring_policy,
                    is_gold_present=False,
                    is_gold_empty=False,
                    was_scored=False,
                    is_correct=None,
                    join_status="unmatched_proposal",
                    comparison_kind="not_scored",
                    evidence_outcome="not_evaluated",
                    proposal_count=1,
                    row_index=proposal.row_index,
                    diagnostic_flags=["proposal_without_matching_gold_cell"],
                    diagnostics={},
                    selected_proposal_state=proposal.state,
                )
            )

    return scored_cells


def resolve_field_config(
    *,
    column_name: str,
    gold_value: Any,
    proposal: Any,
    schema: EvaluatorSchema,
) -> ResolvedFieldConfig:
    column_schema = schema.column(column_name)
    field_type = (
        proposal.field_type
        or (column_schema.field_type if column_schema else None)
        or _infer_field_type(gold_value, proposal.proposed_value, proposal.allowed_values, column_schema)
    )
    scoring_policy = (
        proposal.scoring_policy
        or (column_schema.scoring_policy if column_schema and column_schema.scoring_policy else None)
        or ("judge" if field_type == "text" else "deterministic")
    )
    allowed_values = proposal.allowed_values or (column_schema.allowed_values if column_schema else [])
    aliases = proposal.aliases or (column_schema.aliases if column_schema else {})
    numeric_tolerance = (
        column_schema.numeric_tolerance if column_schema and column_schema.numeric_tolerance else schema.global_numeric_tolerance
    )
    return ResolvedFieldConfig(
        column_name=column_name,
        field_type=field_type,
        scoring_policy=scoring_policy,
        allowed_values=list(allowed_values),
        aliases=dict(aliases),
        numeric_tolerance=numeric_tolerance,
    )


def _infer_field_type(
    gold_value: Any,
    proposed_value: Any,
    allowed_values: list[str],
    column_schema: Any,
) -> str:
    if normalize_boolean(gold_value) is not None and normalize_boolean(proposed_value) is not None:
        return "boolean"
    if normalize_numeric(gold_value) is not None and normalize_numeric(proposed_value) is not None:
        return "numeric"
    if allowed_values or (column_schema and column_schema.allowed_values):
        return "categorical"
    return "text"


def _compare_structured(
    *,
    field_type: str,
    gold_value: Any,
    proposed_value: Any,
    aliases: dict[str, str],
    allowed_values: list[str],
    numeric_tolerance: NumericTolerance,
):
    if field_type == "boolean":
        return compare_boolean(gold_value, proposed_value)
    if field_type == "categorical":
        return compare_categorical(
            gold_value,
            proposed_value,
            aliases=aliases,
            allowed_values=allowed_values,
        )
    return compare_numeric(gold_value, proposed_value, tolerance=numeric_tolerance)
