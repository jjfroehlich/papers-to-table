from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from paper_eval.compare_structured import compare_boolean, compare_categorical, compare_numeric
from paper_eval.contracts import (
    GoldDataset,
    JudgeConfig,
    JudgeResponse,
    LoadedRun,
    NumericTolerance,
    ResolvedFieldConfig,
    ScoredCell,
    ScoreRunResult,
    STRUCTURED_FIELD_TYPES,
    EvaluatorSchema,
)
from paper_eval.evidence import validate_evidence_anchors
from paper_eval.errors import ContractError, EvaluationError
from paper_eval.judge import TextJudge, build_judge_request, judge_record_from_result
from paper_eval.normalize import normalize_boolean, normalize_numeric, normalize_text_for_match, text_overlap_diagnostics
from paper_eval.structured_support import evaluate_structured_support_proxy


@dataclass
class _PendingJudgeCell:
    sequence: int
    loaded_run: LoadedRun
    gold_cell: Any
    proposal: Any
    field_config: ResolvedFieldConfig
    evidence_result: Any
    normalized_gold: str | None
    normalized_proposed: str | None
    text_diagnostics: dict[str, Any]
    ordered_labels: list[str]


def score_run(
    loaded_run: LoadedRun,
    gold_dataset: GoldDataset,
    schema: EvaluatorSchema,
    *,
    text_judge: TextJudge | None = None,
    judge_config: JudgeConfig | None = None,
    text_judges: dict[str, TextJudge] | None = None,
    judge_configs: dict[str, JudgeConfig] | None = None,
) -> ScoreRunResult:
    normalized_judges, normalized_configs = _normalize_judge_runtime(
        text_judge=text_judge,
        judge_config=judge_config,
        text_judges=text_judges,
        judge_configs=judge_configs,
    )
    proposals_by_key: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for proposal in loaded_run.proposals:
        proposals_by_key[proposal.join_key].append(proposal)

    gold_keys = {cell.join_key for cell in gold_dataset.cells}
    allowed_row_ids = {cell.row_id for cell in gold_dataset.cells if cell.row_id is not None}
    scoped_row_ids = allowed_row_ids if loaded_run.matched_row_indices is not None else None
    scored_entries: list[ScoredCell | _PendingJudgeCell] = []
    pending_judge_cells: list[_PendingJudgeCell] = []

    for gold_cell in gold_dataset.cells:
        proposals = proposals_by_key.get(gold_cell.join_key, [])
        proposal_count = len(proposals)

        if not gold_cell.is_present:
            scored_entries.append(
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
                    judge_provider=None,
                    judge_configured_model_id=None,
                    judge_resolved_model_id=None,
                    judge_verdict=None,
                    judge_model_id=None,
                    judge_prompt_version=None,
                    judge_prompt_hash=None,
                    judge_temperature=None,
                    judge_input_hash=None,
                    diagnostic_flags=["gold_empty_unscored"] + (["filled_on_gold_empty"] if proposal_count else []),
                    diagnostics={},
                    )
                )
            continue

        if proposal_count == 0:
            scored_entries.append(
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
                    judge_provider=None,
                    judge_configured_model_id=None,
                    judge_resolved_model_id=None,
                    judge_verdict=None,
                    judge_model_id=None,
                    judge_prompt_version=None,
                    judge_prompt_hash=None,
                    judge_temperature=None,
                    judge_input_hash=None,
                    diagnostic_flags=["missing_proposal_for_gold_present"],
                    diagnostics={},
                    )
                )
            continue

        if proposal_count > 1:
            scored_entries.append(
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
                    judge_provider=None,
                    judge_configured_model_id=None,
                    judge_resolved_model_id=None,
                    judge_verdict=None,
                    judge_model_id=None,
                    judge_prompt_version=None,
                    judge_prompt_hash=None,
                    judge_temperature=None,
                    judge_input_hash=None,
                    diagnostic_flags=["duplicate_proposals_for_join_key"],
                    diagnostics={"proposal_cell_ids": [proposal.cell_id for proposal in proposals]},
                    )
                )
            continue

        proposal = proposals[0]
        if gold_cell.cell_id and proposal.cell_id != gold_cell.cell_id:
            scored_entries.append(
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
                    anchor_valid=False,
                    evidence_present_but_unvalidated=False,
                    row_index=gold_cell.row_index,
                    judge_provider=None,
                    judge_configured_model_id=None,
                    judge_resolved_model_id=None,
                    judge_verdict=None,
                    judge_model_id=None,
                    judge_prompt_version=None,
                    judge_prompt_hash=None,
                    judge_temperature=None,
                    judge_input_hash=None,
                    diagnostic_flags=["proposal_cell_id_mismatch"],
                    diagnostics={"gold_cell_id": gold_cell.cell_id, "proposal_cell_id": proposal.cell_id},
                    selected_proposal_status=proposal.proposal_status,
                )
            )
            continue

        evidence_result = validate_evidence_anchors(
            proposal.evidence_items,
            page_text_by_page=loaded_run.page_text_by_page,
            page_count=loaded_run.metadata.page_count,
        )
        field_config = resolve_field_config(
            column_name=gold_cell.column_name,
            gold_value=gold_cell.raw_value,
            proposal=proposal,
            schema=schema,
        )
        if field_config.field_type not in STRUCTURED_FIELD_TYPES:
            scored_cell_or_pending = _prepare_text_cell(
                loaded_run=loaded_run,
                gold_cell=gold_cell,
                proposal=proposal,
                field_config=field_config,
                evidence_result=evidence_result,
                judge_configs=normalized_configs,
                sequence=len(scored_entries),
            )
            scored_entries.append(scored_cell_or_pending)
            if isinstance(scored_cell_or_pending, _PendingJudgeCell):
                pending_judge_cells.append(scored_cell_or_pending)
            continue

        comparison = _compare_structured(
            field_type=field_config.field_type,
            gold_value=gold_cell.raw_value,
            proposed_value=proposal.proposed_value,
            aliases=field_config.aliases,
            allowed_values=field_config.allowed_values,
            numeric_tolerance=field_config.numeric_tolerance,
        )
        support_proxy = evaluate_structured_support_proxy(
            field_type=field_config.field_type,
            proposed_value=proposal.proposed_value,
            normalized_proposed=comparison.normalized_proposed,
            evidence_items=proposal.evidence_items,
            page_text_by_page=loaded_run.page_text_by_page,
        )

        scored_entries.append(
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
                evidence_outcome=evidence_result.outcome,
                proposal_count=1,
                anchor_valid=evidence_result.anchor_valid,
                evidence_present_but_unvalidated=evidence_result.evidence_present_but_unvalidated,
                row_index=gold_cell.row_index,
                normalized_gold=comparison.normalized_gold,
                normalized_proposed=comparison.normalized_proposed,
                judge_provider=None,
                judge_configured_model_id=None,
                judge_resolved_model_id=None,
                judge_verdict=None,
                judge_model_id=None,
                judge_prompt_version=None,
                judge_prompt_hash=None,
                judge_temperature=None,
                judge_input_hash=None,
                    diagnostics={
                        **comparison.diagnostics,
                        "metadata_diagnostics": proposal.metadata_diagnostics,
                        "evidence": evidence_result.diagnostics,
                        "structured_support_proxy": {
                        "status": support_proxy.status,
                        "matched_evidence_ids": support_proxy.matched_evidence_ids,
                        **support_proxy.diagnostics,
                    },
                },
                selected_proposal_status=proposal.proposal_status,
                extraction_lane=proposal.extraction_lane,
                failure_attribution=proposal.failure_attribution,
            )
        )

    for join_key, proposals in proposals_by_key.items():
        if join_key in gold_keys:
            continue
        for proposal in proposals:
            if scoped_row_ids and proposal.row_id not in scoped_row_ids:
                continue
            scored_entries.append(
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
                    judge_provider=None,
                    judge_configured_model_id=None,
                    judge_resolved_model_id=None,
                    judge_verdict=None,
                    judge_model_id=None,
                    judge_prompt_version=None,
                    judge_prompt_hash=None,
                    judge_temperature=None,
                    judge_input_hash=None,
                    diagnostic_flags=["proposal_without_matching_gold_cell"],
                    diagnostics={},
                    selected_proposal_status=proposal.proposal_status,
                )
            )

    judged_cells, judge_records, judge_execution_summary = _execute_pending_judge_cells(
        pending_judge_cells,
        text_judges=normalized_judges,
        judge_configs=normalized_configs,
    )
    scored_cells: list[ScoredCell] = [
        judged_cells[entry.sequence] if isinstance(entry, _PendingJudgeCell) else entry
        for entry in scored_entries
    ]
    return ScoreRunResult(
        scored_cells=scored_cells,
        judge_records=judge_records,
        judge_execution_summary=judge_execution_summary,
    )


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
        description=column_schema.description if column_schema else None,
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


def _prepare_text_cell(
    *,
    loaded_run: LoadedRun,
    gold_cell: Any,
    proposal: Any,
    field_config: ResolvedFieldConfig,
    evidence_result: Any,
    judge_configs: dict[str, JudgeConfig],
    sequence: int,
) -> ScoredCell | _PendingJudgeCell:
    normalized_gold = normalize_text_for_match(gold_cell.raw_value)
    normalized_proposed = normalize_text_for_match(proposal.proposed_value)
    text_diagnostics = {
        **text_overlap_diagnostics(gold_cell.raw_value, proposal.proposed_value),
        "normalized_gold_text": normalized_gold,
        "normalized_proposed_text": normalized_proposed,
    }
    if normalized_gold is not None and normalized_gold == normalized_proposed:
        return ScoredCell(
            record_kind="gold_cell",
            run_id=loaded_run.metadata.run_id,
            row_id=gold_cell.row_id,
            column_name=gold_cell.column_name,
            cell_id=proposal.cell_id,
            gold_value=gold_cell.raw_value,
            proposed_value=proposal.proposed_value,
            field_type=field_config.field_type,
            scoring_policy="deterministic",
            is_gold_present=True,
            is_gold_empty=False,
            was_scored=True,
            is_correct=True,
            join_status="matched",
            comparison_kind="text",
            evidence_outcome=evidence_result.outcome,
            proposal_count=1,
            anchor_valid=evidence_result.anchor_valid,
            evidence_present_but_unvalidated=evidence_result.evidence_present_but_unvalidated,
            row_index=gold_cell.row_index,
            normalized_gold=normalized_gold,
            normalized_proposed=normalized_proposed,
            diagnostic_flags=["text_exact_match_fast_path"],
            diagnostics={
                "text": text_diagnostics,
                "evidence": evidence_result.diagnostics,
            },
            selected_proposal_status=proposal.proposal_status,
            extraction_lane=proposal.extraction_lane,
            failure_attribution=proposal.failure_attribution,
        )
    if field_config.scoring_policy == "deterministic":
        is_correct = normalized_gold is not None and normalized_gold == normalized_proposed
        return ScoredCell(
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
            is_correct=is_correct,
            join_status="matched",
            comparison_kind="text",
            evidence_outcome=evidence_result.outcome,
            proposal_count=1,
            anchor_valid=evidence_result.anchor_valid,
            evidence_present_but_unvalidated=evidence_result.evidence_present_but_unvalidated,
            row_index=gold_cell.row_index,
            normalized_gold=normalized_gold,
            normalized_proposed=normalized_proposed,
            diagnostics={
                "text": text_diagnostics,
                "evidence": evidence_result.diagnostics,
            },
            selected_proposal_status=proposal.proposal_status,
            extraction_lane=proposal.extraction_lane,
            failure_attribution=proposal.failure_attribution,
        )
    if field_config.scoring_policy != "judge":
        raise ContractError(
            f"Unsupported text scoring policy '{field_config.scoring_policy}' for column '{gold_cell.column_name}'."
        )
    if not judge_configs:
        raise ContractError(
            "Judge-scored text fields require --judge-model or a deterministic text scoring override in schema/proposals."
        )
    ordered_labels = [label for label in ["judge_a", "judge_b"] if label in judge_configs] + [
        label for label in judge_configs if label not in {"judge_a", "judge_b"}
    ]
    return _PendingJudgeCell(
        sequence=sequence,
        loaded_run=loaded_run,
        gold_cell=gold_cell,
        proposal=proposal,
        field_config=field_config,
        evidence_result=evidence_result,
        normalized_gold=normalized_gold,
        normalized_proposed=normalized_proposed,
        text_diagnostics=text_diagnostics,
        ordered_labels=ordered_labels,
    )


def _execute_pending_judge_cells(
    pending_cells: list[_PendingJudgeCell],
    *,
    text_judges: dict[str, TextJudge],
    judge_configs: dict[str, JudgeConfig],
) -> tuple[dict[int, ScoredCell], list[Any], dict[str, Any]]:
    if not pending_cells:
        return {}, [], {
            "batched": True,
            "eligible_cell_count": 0,
            "batch_count": 0,
            "batches": [],
            "runtime_seconds_by_judge": {},
            "execution_order": [],
        }
    if not text_judges:
        raise ContractError(
            "Judge-scored text fields require --judge-model or a deterministic text scoring override in schema/proposals."
        )

    labels = [label for label in ["judge_a", "judge_b"] if label in judge_configs] + [
        label for label in judge_configs if label not in {"judge_a", "judge_b"}
    ]
    judge_results_by_sequence: dict[int, dict[str, dict[str, Any]]] = {
        pending.sequence: {} for pending in pending_cells
    }
    judge_records_by_sequence: dict[int, list[Any]] = {pending.sequence: [] for pending in pending_cells}
    all_records: list[Any] = []
    batches: list[dict[str, Any]] = []
    runtime_seconds_by_judge: dict[str, float] = {}
    execution_order: list[str] = []
    cleanup_failures: list[dict[str, Any]] = []

    for label in labels:
        judge_config = judge_configs[label]
        text_judge = text_judges.get(label)
        if text_judge is None:
            continue
        label_cells = [pending for pending in pending_cells if label in pending.ordered_labels]
        grouped: dict[tuple[str, str, float], list[_PendingJudgeCell]] = defaultdict(list)
        for pending in label_cells:
            grouped[(judge_config.provider, judge_config.model_id, judge_config.temperature)].append(pending)
        for (provider, model_id, temperature), group in grouped.items():
            batch_started = perf_counter()
            batch_failed = 0
            for pending in group:
                judge_request = build_judge_request(
                    judge_config=judge_config,
                    run_id=pending.loaded_run.metadata.run_id,
                    row_id=pending.gold_cell.row_id,
                    column_name=pending.gold_cell.column_name,
                    cell_id=pending.proposal.cell_id,
                    gold_value=pending.gold_cell.raw_value,
                    proposed_value=pending.proposal.proposed_value,
                    field_description=pending.field_config.description,
                    evidence_excerpt=_first_evidence_excerpt(pending.proposal),
                )
                judge_failure_message = None
                try:
                    judge_response = text_judge.judge(judge_request)
                except EvaluationError as exc:
                    batch_failed += 1
                    judge_failure_message = str(exc)
                    judge_response = JudgeResponse(
                        verdict="unclear",
                        rationale_label="judge_error",
                        metadata={
                            "provider": judge_config.provider,
                            "configured_model_id": judge_config.model_id,
                            "resolved_model_id": None,
                            "error_message": judge_failure_message,
                        },
                    )
                if judge_response.verdict not in {"correct", "incorrect", "unclear"}:
                    raise EvaluationError(f"Unsupported judge verdict '{judge_response.verdict}'.")
                judge_record = judge_record_from_result(
                    judge_config=judge_config,
                    judge_request=judge_request,
                    judge_response=judge_response,
                )
                all_records.append(judge_record)
                judge_records_by_sequence[pending.sequence].append(judge_record)
                judge_results_by_sequence[pending.sequence][label] = {
                    "verdict": judge_response.verdict,
                    "configured_model_id": judge_config.model_id,
                    "resolved_model_id": judge_record.judge_resolved_model_id,
                    "response_mode": judge_record.judge_response_mode,
                    "prompt_version": judge_request.prompt_version,
                    "prompt_hash": judge_request.prompt_hash,
                    "input_hash": judge_request.input_hash,
                    "provider": judge_config.provider,
                    "temperature": judge_config.temperature,
                    "rationale_label": judge_response.rationale_label,
                    "error_message": judge_failure_message,
                }
            runtime_seconds = perf_counter() - batch_started
            runtime_seconds_by_judge[label] = runtime_seconds_by_judge.get(label, 0.0) + runtime_seconds
            execution_order.append(label)
            batches.append(
                {
                    "judge_label": label,
                    "provider": provider,
                    "model_id": model_id,
                    "temperature": temperature,
                    "eligible_cell_count": len(group),
                    "request_failed_count": batch_failed,
                    "runtime_seconds": runtime_seconds,
                }
            )
            cleanup = getattr(text_judge, "cleanup_model_residency", None)
            if callable(cleanup):
                try:
                    cleanup()
                except Exception as exc:
                    cleanup_failures.append(
                        {
                            "judge_label": label,
                            "provider": provider,
                            "model_id": model_id,
                            "message": str(exc),
                        }
                    )

    judged_cells = {
        pending.sequence: _merge_judged_text_cell(
            pending,
            judge_results=judge_results_by_sequence[pending.sequence],
            judge_records=judge_records_by_sequence[pending.sequence],
        )
        for pending in pending_cells
    }
    summary = {
        "batched": True,
        "execution_policy": "judge_major_grouped_by_provider_model_settings",
        "eligible_cell_count": len(pending_cells),
        "configured_labels": labels,
        "batch_count": len(batches),
        "batches": batches,
        "batch_counts_by_judge": {label: sum(1 for batch in batches if batch["judge_label"] == label) for label in labels},
        "eligible_cell_counts_by_judge": {
            label: sum(int(batch["eligible_cell_count"]) for batch in batches if batch["judge_label"] == label)
            for label in labels
        },
        "runtime_seconds_by_judge": runtime_seconds_by_judge,
        "execution_order": execution_order,
        "model_switch_count": _count_model_switches(batches),
        "cleanup_failures": cleanup_failures,
    }
    return judged_cells, all_records, summary


def _merge_judged_text_cell(
    pending: _PendingJudgeCell,
    *,
    judge_results: dict[str, dict[str, Any]],
    judge_records: list[Any],
) -> ScoredCell:
    judge_scores: list[float] = []
    for result in judge_results.values():
        if result.get("verdict") == "correct":
            judge_scores.append(1.0)
        elif result.get("verdict") == "incorrect":
            judge_scores.append(0.0)

    primary_label = pending.ordered_labels[0] if pending.ordered_labels else None
    primary_result = judge_results.get(primary_label or "", {})
    primary_verdict = primary_result.get("verdict")
    was_scored = any(result.get("verdict") in {"correct", "incorrect"} for result in judge_results.values())
    is_correct = _is_correct_for_judge_verdict(str(primary_verdict)) if primary_verdict is not None else None
    judge_score_mean = (sum(judge_scores) / len(judge_scores)) if judge_scores else None
    deterministic_verdicts = [
        str(result.get("verdict"))
        for result in judge_results.values()
        if result.get("verdict") in {"correct", "incorrect"}
    ]
    judge_disagreement = len(set(deterministic_verdicts)) > 1 if len(deterministic_verdicts) >= 2 else False
    diagnostic_flags = []
    if any(record.input_was_truncated for record in judge_records):
        diagnostic_flags.append("judge_input_truncated")
    if any(result.get("verdict") == "unclear" for result in judge_results.values()):
        diagnostic_flags.append("judge_verdict_unclear")
    if any(result.get("error_message") for result in judge_results.values()):
        diagnostic_flags.append("judge_request_failed")
    if judge_disagreement:
        diagnostic_flags.append("judge_disagreement")

    return ScoredCell(
        record_kind="gold_cell",
        run_id=pending.loaded_run.metadata.run_id,
        row_id=pending.gold_cell.row_id,
        column_name=pending.gold_cell.column_name,
        cell_id=pending.proposal.cell_id,
        gold_value=pending.gold_cell.raw_value,
        proposed_value=pending.proposal.proposed_value,
        field_type=pending.field_config.field_type,
        scoring_policy=pending.field_config.scoring_policy,
        is_gold_present=True,
        is_gold_empty=False,
        was_scored=was_scored,
        is_correct=is_correct,
        join_status="matched",
        comparison_kind="text",
        evidence_outcome=pending.evidence_result.outcome,
        proposal_count=1,
        anchor_valid=pending.evidence_result.anchor_valid,
        evidence_present_but_unvalidated=pending.evidence_result.evidence_present_but_unvalidated,
        row_index=pending.gold_cell.row_index,
        normalized_gold=pending.normalized_gold,
        normalized_proposed=pending.normalized_proposed,
        judge_provider=primary_result.get("provider"),
        judge_configured_model_id=primary_result.get("configured_model_id"),
        judge_resolved_model_id=primary_result.get("resolved_model_id"),
        judge_verdict=primary_verdict,
        judge_response_mode=primary_result.get("response_mode"),
        judge_model_id=primary_result.get("configured_model_id"),
        judge_prompt_version=primary_result.get("prompt_version"),
        judge_prompt_hash=primary_result.get("prompt_hash"),
        judge_temperature=primary_result.get("temperature"),
        judge_input_hash=primary_result.get("input_hash"),
        judge_results=judge_results,
        judge_score_mean=judge_score_mean,
        judge_disagreement=judge_disagreement,
        diagnostic_flags=diagnostic_flags,
        diagnostics={
            "text": pending.text_diagnostics,
            "metadata_diagnostics": pending.proposal.metadata_diagnostics,
            "judge": {
                "provider": primary_result.get("provider"),
                "configured_model_id": primary_result.get("configured_model_id"),
                "resolved_model_id": primary_result.get("resolved_model_id"),
                "verdict": primary_verdict,
                "response_mode": primary_result.get("response_mode"),
                "rationale_label": primary_result.get("rationale_label"),
                "input_was_truncated": any(record.input_was_truncated for record in judge_records),
                "error_message": primary_result.get("error_message"),
            },
            "judges": {
                label: {
                    **result,
                    "score": _score_for_verdict(str(result.get("verdict"))) if result.get("verdict") is not None else None,
                }
                for label, result in judge_results.items()
            },
            "evidence": pending.evidence_result.diagnostics,
        },
        selected_proposal_status=pending.proposal.proposal_status,
        extraction_lane=pending.proposal.extraction_lane,
        failure_attribution=(
            "judge_failure"
            if any(result.get("error_message") for result in judge_results.values())
            else ("judge_unclear" if primary_verdict == "unclear" else pending.proposal.failure_attribution)
        ),
    )


def _count_model_switches(batches: list[dict[str, Any]]) -> int:
    switches = 0
    previous: tuple[str, str] | None = None
    for batch in batches:
        current = (str(batch.get("provider")), str(batch.get("model_id")))
        if previous is not None and current != previous:
            switches += 1
        previous = current
    return switches


def _first_evidence_excerpt(proposal: Any) -> str | None:
    for evidence_item in proposal.evidence_items:
        if evidence_item.quote_text:
            return evidence_item.quote_text
    return None


def _is_correct_for_judge_verdict(verdict: str) -> bool | None:
    if verdict == "correct":
        return True
    if verdict == "incorrect":
        return False
    return None


def _score_for_verdict(verdict: str) -> float | None:
    if verdict == "correct":
        return 1.0
    if verdict == "incorrect":
        return 0.0
    return None


def _normalize_judge_runtime(
    *,
    text_judge: TextJudge | None,
    judge_config: JudgeConfig | None,
    text_judges: dict[str, TextJudge] | None,
    judge_configs: dict[str, JudgeConfig] | None,
) -> tuple[dict[str, TextJudge], dict[str, JudgeConfig]]:
    normalized_judges = dict(text_judges or {})
    normalized_configs = dict(judge_configs or {})
    if text_judge is not None and judge_config is not None and "judge_a" not in normalized_judges:
        normalized_judges["judge_a"] = text_judge
        normalized_configs["judge_a"] = JudgeConfig(**{**judge_config.__dict__, "label": "judge_a"})
    return normalized_judges, normalized_configs
