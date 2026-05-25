"""Batch 4: Review backend — decision persistence, list/detail/filter APIs,
summaries, and export gating.

Tasks covered: T068 (warning categories), T069 (proposal list/filter),
T070 (proposal detail), T071 (asset serving helpers), T072 (decision
persistence), T073 (audit history), T074 (bulk-accept), T075/T075a
(progress counters), T076/T077 (run/reviewer summaries), T078/T078a
(recomputation + integrity), T079 (export candidates).
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timezone
from typing import Any, Optional

from .artifacts import (
    append_jsonl,
    get_review_dir,
    get_reviewer_summary_path,
    get_run_dir,
    get_run_json_path,
    get_run_summary_path,
    read_json,
    read_jsonl,
    write_json,
)
from .extraction import EvidenceRecord, ProposalRecord, load_evidence, load_proposals
from .ids import generate_review_decision_id
from .parsing import get_parsed_dir
from .schemas import (
    DecisionSource,
    EvidenceSourceType,
    ProviderLocality,
    EvidenceStatus,
    ReviewBucket,
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewResolutionReason,
    ReviewerSummary,
    RunStatus,
    RunSummary,
    WarningCategory,
)

# ---------------------------------------------------------------------------
# Artifact paths for review decisions
# ---------------------------------------------------------------------------

def get_decisions_path(run_dir: pathlib.Path) -> pathlib.Path:
    """JSONL file storing all review-decision records (append-only)."""
    return run_dir / "review" / "decisions.jsonl"


def get_proposal_history_path(run_dir: pathlib.Path, proposal_id: str) -> pathlib.Path:
    """Per-proposal decision history JSON (latest + full log)."""
    return run_dir / "review" / "history" / f"{proposal_id}.json"


# ---------------------------------------------------------------------------
# T072/T073 — Decision persistence and audit history
# ---------------------------------------------------------------------------

def record_review_decision(
    run_dir: pathlib.Path,
    proposal_id: str,
    cell_id: str,
    run_id: str,
    decision: ReviewDecision,
    decision_source: DecisionSource = DecisionSource.human_individual,
    resolution_reason: Optional[ReviewResolutionReason] = None,
    edited_value: Optional[str] = None,
    reviewer_note: Optional[str] = None,
) -> ReviewDecisionRecord:
    """Persist a review decision as an explicit record.

    - Appends to the shared decisions JSONL (audit trail, T073).
    - Overwrites the per-proposal history file so the latest decision is fast
      to look up while the full history remains in the JSONL.
    """
    decision_id = generate_review_decision_id(proposal_id)
    decided_at = datetime.now(timezone.utc).isoformat()

    record = ReviewDecisionRecord(
        review_decision_id=decision_id,
        run_id=run_id,
        proposal_id=proposal_id,
        cell_id=cell_id,
        decision=decision,
        decision_source=decision_source,
        resolution_reason=resolution_reason,
        edited_value=edited_value,
        reviewer_note=reviewer_note,
        decided_at=decided_at,
    )

    # Append to global decisions log (audit trail)
    append_jsonl(get_decisions_path(run_dir), record.model_dump())

    # Write latest decision to per-proposal history file (fast lookup)
    history_path = get_proposal_history_path(run_dir, proposal_id)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing history to preserve prior decisions
    prior: list[dict] = []
    if history_path.exists():
        try:
            existing = read_json(history_path)
            prior = existing.get("history", [])
        except Exception:
            prior = []

    write_json(
        history_path,
        {
            "proposal_id": proposal_id,
            "run_id": run_id,
            "latest_decision": record.model_dump(),
            "history": prior + [record.model_dump()],
        },
    )

    return record


def get_latest_decision(
    run_dir: pathlib.Path, proposal_id: str
) -> Optional[ReviewDecisionRecord]:
    """Return the most-recent decision for a proposal, or None if undecided."""
    history_path = get_proposal_history_path(run_dir, proposal_id)
    if not history_path.exists():
        return None
    try:
        data = read_json(history_path)
        latest = data.get("latest_decision")
        if latest is None:
            return None
        return ReviewDecisionRecord.model_validate(latest)
    except Exception:
        return None


def get_decision_history(
    run_dir: pathlib.Path, proposal_id: str
) -> list[ReviewDecisionRecord]:
    """Return full decision history for a proposal (oldest first)."""
    history_path = get_proposal_history_path(run_dir, proposal_id)
    if not history_path.exists():
        return []
    try:
        data = read_json(history_path)
        return [ReviewDecisionRecord.model_validate(d) for d in data.get("history", [])]
    except Exception:
        return []


def load_all_decisions(run_dir: pathlib.Path) -> list[ReviewDecisionRecord]:
    """Load every decision record from the append-only JSONL."""
    records = read_jsonl(get_decisions_path(run_dir))
    result: list[ReviewDecisionRecord] = []
    for r in records:
        try:
            result.append(ReviewDecisionRecord.model_validate(r))
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# T068 — Warning-category helpers
# ---------------------------------------------------------------------------

_EVIDENCE_WARNING_FLAGS = {
    "provider_error": WarningCategory.provider_unreachable,
    "needs_more_evidence": WarningCategory.weak_evidence,
    "low_confidence": WarningCategory.low_confidence_proposal,
}

_WARNING_REASON_CODES = {
    "ambiguous_evidence",
    "conflicting_evidence",
    "insufficient_evidence",
    "invalid_model_output",
    "provider_error",
    "parser_error",
    "evidence_missing_for_value",
}


def _proposal_warning_categories(proposal: ProposalRecord) -> list[WarningCategory]:
    """Derive WarningCategory values from a ProposalRecord's warning_flags."""
    cats: list[WarningCategory] = []
    for flag in proposal.warning_flags:
        cat = _EVIDENCE_WARNING_FLAGS.get(flag)
        if cat:
            cats.append(cat)
    if _WARNING_REASON_CODES & set(proposal.reason_codes):
        if WarningCategory.weak_evidence not in cats:
            cats.append(WarningCategory.weak_evidence)
    if proposal.evidence_status in {EvidenceStatus.direct_weak, EvidenceStatus.inferred_weak}:
        if WarningCategory.weak_evidence not in cats:
            cats.append(WarningCategory.weak_evidence)
    return cats


def _is_figure_derived(proposal: ProposalRecord) -> bool:
    figure_diag = proposal.figure_review_diagnostics or {}
    if int(figure_diag.get("figure_evidence_persisted", 0) or 0) > 0:
        return True
    return "figure_derived" in proposal.warning_flags


def _is_fallback_evidence(proposal: ProposalRecord) -> bool:
    return (
        "anchor_fallback" in proposal.reason_codes
        or "fallback_evidence_used" in proposal.warning_flags
        or "fallback_evidence" in proposal.warning_flags
    )


# ---------------------------------------------------------------------------
# T069 — Proposal list with filters
# ---------------------------------------------------------------------------

class ProposalFilter:
    """Filtering parameters for the proposal list endpoint."""

    def __init__(
        self,
        row_id: Optional[str] = None,
        column_name: Optional[str] = None,
        pdf_id: Optional[str] = None,
        evidence_status: Optional[str] = None,   # "figure_derived" | "fallback" | "weak"
        figure_derived: Optional[bool] = None,
        decision: Optional[str] = None,           # ReviewDecision value or "undecided"
        match_status: Optional[str] = None,       # MatchOutcome value
        reviewable_only: bool = False,
    ) -> None:
        self.row_id = row_id
        self.column_name = column_name
        self.pdf_id = pdf_id
        self.evidence_status = evidence_status
        self.figure_derived = figure_derived
        self.decision = decision
        self.match_status = match_status
        self.reviewable_only = reviewable_only

    def matches(
        self,
        proposal: ProposalRecord,
        latest_decision: Optional[ReviewDecisionRecord],
    ) -> bool:
        if self.reviewable_only and not _is_reviewable_proposal(proposal):
            return False
        if self.row_id and proposal.row_id != self.row_id:
            return False
        if self.column_name and proposal.column_name != self.column_name:
            return False
        if self.pdf_id and proposal.pdf_id != self.pdf_id:
            return False
        if self.evidence_status:
            if self.evidence_status == "figure_derived" and not _is_figure_derived(proposal):
                return False
            elif self.evidence_status == "fallback" and not _is_fallback_evidence(proposal):
                return False
            elif self.evidence_status == "weak" and proposal.evidence_status not in {EvidenceStatus.direct_weak, EvidenceStatus.inferred_weak}:
                return False
        if self.figure_derived is not None:
            if self.figure_derived != _is_figure_derived(proposal):
                return False
        if self.decision:
            if self.decision == "undecided":
                if latest_decision is not None:
                    return False
            else:
                if latest_decision is None:
                    return False
                if latest_decision.decision.value != self.decision:
                    return False
        return True


def _is_reviewable_proposal(proposal: ProposalRecord) -> bool:
    return proposal.review_bucket != ReviewBucket.diagnostic


def list_proposals(
    run_dir: pathlib.Path,
    filt: Optional[ProposalFilter] = None,
) -> list[dict]:
    """Return enriched proposal dicts (proposal + latest decision) matching filt."""
    proposals = load_proposals(run_dir)
    result: list[dict] = []
    for p in proposals:
        latest = get_latest_decision(run_dir, p.proposal_id)
        if filt and not filt.matches(p, latest):
            continue
        d = p.model_dump()
        d["latest_decision"] = latest.model_dump() if latest else None
        d["warning_categories"] = [c.value for c in _proposal_warning_categories(p)]
        d["is_figure_derived"] = _is_figure_derived(p)
        d["is_fallback_evidence"] = _is_fallback_evidence(p)
        result.append(d)
    return result


def _display_value_for_review_cell(original_value: Any, proposal: ProposalRecord, latest: Optional[ReviewDecisionRecord]) -> Any:
    if latest is None:
        return proposal.proposed_value
    if latest.decision == ReviewDecision.accepted:
        return proposal.proposed_value
    if latest.decision == ReviewDecision.accepted_with_edit:
        return latest.edited_value
    return original_value


def _display_status_for_review_cell(proposal: ProposalRecord, latest: Optional[ReviewDecisionRecord]) -> str:
    if latest is None:
        return "pending"
    if latest.decision == ReviewDecision.accepted:
        return "accepted"
    if latest.decision == ReviewDecision.accepted_with_edit:
        return "accepted_with_edit"
    if latest.decision == ReviewDecision.confirmed_no_data:
        return "confirmed_no_data"
    if latest.decision == ReviewDecision.rejected:
        return "rejected"
    return proposal.proposal_status.value if hasattr(proposal.proposal_status, "value") else str(proposal.proposal_status)


def build_review_table(run_dir: pathlib.Path, review_lookup: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Return a grid-oriented review payload from table, proposal, evidence, and decision artifacts."""
    proposals = load_proposals(run_dir)
    evidence = load_evidence(run_dir)
    evidence_by_proposal_id: dict[str, list[EvidenceRecord]] = {}
    for item in evidence:
        evidence_by_proposal_id.setdefault(item.proposal_id, []).append(item)
    for items in evidence_by_proposal_id.values():
        items.sort(key=lambda item: item.evidence_rank)

    rows_by_id = (review_lookup or {}).get("rows_by_id") if isinstance(review_lookup, dict) else {}
    if not isinstance(rows_by_id, dict):
        rows_by_id = {}
    columns_by_name = (review_lookup or {}).get("columns_by_name") if isinstance(review_lookup, dict) else {}
    if not isinstance(columns_by_name, dict):
        columns_by_name = {}

    column_names: list[str] = []
    for row_info in sorted(rows_by_id.values(), key=lambda row: int(row.get("row_index", 0) or 0)):
        values = row_info.get("values", {}) if isinstance(row_info, dict) else {}
        if not isinstance(values, dict):
            continue
        for name in values.keys():
            if name not in column_names:
                column_names.append(str(name))
    for name in columns_by_name.keys():
        if name not in column_names:
            column_names.append(str(name))
    for proposal in proposals:
        if proposal.column_name not in column_names:
            column_names.append(proposal.column_name)

    proposals_by_cell: dict[tuple[str, str], ProposalRecord] = {}
    for proposal in proposals:
        proposals_by_cell[(proposal.row_id, proposal.column_name)] = proposal

    rows: list[dict[str, Any]] = []
    for row_id, row_info in sorted(rows_by_id.items(), key=lambda item: int(item[1].get("row_index", 0) or 0)):
        values = row_info.get("values", {}) if isinstance(row_info, dict) else {}
        if not isinstance(values, dict):
            values = {}
        cells: dict[str, Any] = {}
        for column_name in column_names:
            original_value = values.get(column_name)
            proposal = proposals_by_cell.get((row_id, column_name))
            if proposal is None:
                cells[column_name] = {
                    "column_name": column_name,
                    "original_value": original_value,
                    "display_value": original_value,
                    "display_status": "unchanged",
                    "has_proposal": False,
                    "proposal": None,
                }
                continue

            latest = get_latest_decision(run_dir, proposal.proposal_id)
            proposal_evidence = evidence_by_proposal_id.get(proposal.proposal_id, [])
            primary_evidence = proposal_evidence[0] if proposal_evidence else None
            cells[column_name] = {
                "column_name": column_name,
                "original_value": original_value,
                "display_value": _display_value_for_review_cell(original_value, proposal, latest),
                "display_status": _display_status_for_review_cell(proposal, latest),
                "has_proposal": True,
                "proposal": {
                    **proposal.model_dump(),
                    "latest_decision": latest.model_dump() if latest else None,
                    "warning_categories": [c.value for c in _proposal_warning_categories(proposal)],
                    "is_figure_derived": _is_figure_derived(proposal),
                    "is_fallback_evidence": _is_fallback_evidence(proposal),
                    "evidence_summary": {
                        "count": len(proposal_evidence),
                        "primary_evidence_id": primary_evidence.evidence_id if primary_evidence else None,
                        "primary_source_type": (
                            primary_evidence.source_type.value
                            if primary_evidence and hasattr(primary_evidence.source_type, "value")
                            else str(primary_evidence.source_type)
                            if primary_evidence
                            else None
                        ),
                        "primary_page_number": primary_evidence.page_number if primary_evidence else None,
                        "primary_quote_text": primary_evidence.quote_text if primary_evidence else None,
                    },
                },
            }
        rows.append(
            {
                "row_id": row_id,
                "row_index": row_info.get("row_index") if isinstance(row_info, dict) else None,
                "paper_label": row_info.get("paper_label") if isinstance(row_info, dict) else row_id,
                "title": row_info.get("title") if isinstance(row_info, dict) else None,
                "values": values,
                "cells": cells,
            }
        )

    if not rows:
        rows_with_proposals: dict[str, dict[str, Any]] = {}
        for proposal in proposals:
            rows_with_proposals.setdefault(
                proposal.row_id,
                {"row_id": proposal.row_id, "row_index": None, "paper_label": proposal.row_id, "values": {}, "cells": {}},
            )
        for row_id, row in rows_with_proposals.items():
            for column_name in column_names:
                proposal = proposals_by_cell.get((row_id, column_name))
                row["cells"][column_name] = {
                    "column_name": column_name,
                    "original_value": None,
                    "display_value": proposal.proposed_value if proposal else None,
                    "display_status": "pending" if proposal else "unchanged",
                    "has_proposal": proposal is not None,
                    "proposal": proposal.model_dump() if proposal else None,
                }
            rows.append(row)

    return {
        "run_id": load_run_json(run_dir).get("run_id", run_dir.name),
        "columns": [
            {
                "name": name,
                "description": (columns_by_name.get(name) or {}).get("description") if isinstance(columns_by_name.get(name), dict) else None,
                "field_type": (columns_by_name.get(name) or {}).get("field_type") if isinstance(columns_by_name.get(name), dict) else None,
                "is_target": name in columns_by_name,
            }
            for name in column_names
        ],
        "rows": rows,
        "proposal_count": len(proposals),
    }


# ---------------------------------------------------------------------------
# T070 — Proposal detail payload
# ---------------------------------------------------------------------------

def get_proposal_detail(
    run_dir: pathlib.Path,
    proposal_id: str,
    row_data: Optional[dict] = None,
    column_defs: Optional[dict] = None,
) -> Optional[dict]:
    """Return full detail payload for a single proposal.

    Includes the proposal, all evidence, latest decision, decision history,
    row context, and column definition.
    """
    proposals = load_proposals(run_dir)
    proposal: Optional[ProposalRecord] = None
    for p in proposals:
        if p.proposal_id == proposal_id:
            proposal = p
            break
    if proposal is None:
        return None

    all_evidence = load_evidence(run_dir)
    proposal_evidence = [e for e in all_evidence if e.proposal_id == proposal_id]
    proposal_evidence.sort(key=lambda e: e.evidence_rank)

    latest = get_latest_decision(run_dir, proposal_id)
    history = get_decision_history(run_dir, proposal_id)

    # Enrich evidence with display labels
    evidence_dicts = []
    for ev in proposal_evidence:
        ed = ev.model_dump()
        ed["source_type_display"] = _evidence_source_display(ev.source_type)
        evidence_dicts.append(ed)

    detail: dict[str, Any] = {
        "proposal": proposal.model_dump(),
        "evidence": evidence_dicts,
        "latest_decision": latest.model_dump() if latest else None,
        "decision_history": [d.model_dump() for d in history],
        "row_context": {},
        "column_definition": None,
        "warning_categories": [c.value for c in _proposal_warning_categories(proposal)],
        "evidence_status_display": _evidence_status_display(proposal.evidence_status),
        "is_figure_derived": _is_figure_derived(proposal),
        "is_fallback_evidence": _is_fallback_evidence(proposal),
    }

    # Row context (if provided)
    if row_data:
        detail["row_context"] = row_data.get(proposal.row_id)

    # Column definition (if provided)
    if column_defs:
        detail["column_definition"] = column_defs.get(proposal.column_name)

    return detail


def _evidence_status_display(evidence_status: EvidenceStatus) -> str:
    return {
        EvidenceStatus.direct_strong: "Direct strong",
        EvidenceStatus.direct_weak: "Direct weak",
        EvidenceStatus.inferred_strong: "Inferred strong",
        EvidenceStatus.inferred_weak: "Inferred weak",
        EvidenceStatus.no_evidence: "No evidence",
        EvidenceStatus.not_applicable: "Not applicable",
    }.get(evidence_status, evidence_status.value)


def _evidence_source_display(source_type: EvidenceSourceType) -> str:
    return {
        EvidenceSourceType.direct_quote: "Direct quote",
        EvidenceSourceType.inferred_reasoning: "Inferred reasoning",
        EvidenceSourceType.calculation: "Calculation",
        EvidenceSourceType.approximate_highlight: "Approximate highlight",
        EvidenceSourceType.quote_plus_page: "Quote + page (no highlight)",
        EvidenceSourceType.caption_grounded_figure_evidence: "Caption-grounded figure evidence",
        EvidenceSourceType.visual_interpretation_figure_evidence: "Visual-interpretation figure evidence",
    }.get(source_type, source_type.value)


# ---------------------------------------------------------------------------
# T074 — Guarded bulk-accept
# ---------------------------------------------------------------------------

def bulk_accept_proposals(
    run_dir: pathlib.Path,
    run_id: str,
    proposal_ids: list[str],
    *,
    decision_source: DecisionSource = DecisionSource.human_bulk_accept,
    reviewer_note: Optional[str] = None,
) -> list[ReviewDecisionRecord]:
    """Accept a list of proposal IDs as a bulk operation.

    Callers must pass only the IDs from the currently-visible filtered
    subset; this function records an accepted decision for each ID that
    does not already have a decision (undecided only).  IDs that already
    have a decision are skipped to avoid overwriting explicit decisions.
    """
    proposals = load_proposals(run_dir)
    proposal_map = {p.proposal_id: p for p in proposals}

    recorded: list[ReviewDecisionRecord] = []
    for pid in proposal_ids:
        p = proposal_map.get(pid)
        if p is None:
            continue
        existing = get_latest_decision(run_dir, pid)
        if existing is not None:
            # Skip already-decided proposals
            continue
        rec = record_review_decision(
            run_dir=run_dir,
            proposal_id=pid,
            cell_id=p.cell_id,
            run_id=run_id,
            decision=ReviewDecision.accepted,
            decision_source=decision_source,
            resolution_reason=ReviewResolutionReason.accepted_as_proposed,
            reviewer_note=reviewer_note,
        )
        recorded.append(rec)
    return recorded


# ---------------------------------------------------------------------------
# T075/T075a — Progress counters
# ---------------------------------------------------------------------------

def get_progress(run_dir: pathlib.Path) -> dict:
    """Return progress counters distinguished by decision type (T075/T075a).

    confirmed_no_data and rejected are kept separate in the payload so callers
    can distinguish 'paper has no data' from 'model was wrong'.
    """
    proposals = load_proposals(run_dir)
    total = len(proposals)
    accepted = 0
    accepted_with_edit = 0
    confirmed_no_data = 0
    rejected = 0
    pending = 0
    automation_accepted_count = 0

    for p in proposals:
        d = get_latest_decision(run_dir, p.proposal_id)
        if d is None:
            pending += 1
        elif d.decision == ReviewDecision.accepted:
            accepted += 1
            if d.decision_source == DecisionSource.automation_accept_all:
                automation_accepted_count += 1
        elif d.decision == ReviewDecision.accepted_with_edit:
            accepted_with_edit += 1
            if d.decision_source == DecisionSource.automation_accept_all:
                automation_accepted_count += 1
        elif d.decision == ReviewDecision.confirmed_no_data:
            confirmed_no_data += 1
        elif d.decision == ReviewDecision.rejected:
            rejected += 1
        else:
            pending += 1

    reviewed = accepted + accepted_with_edit + confirmed_no_data + rejected
    return {
        "total": total,
        "total_proposals": total,
        "reviewed": reviewed,
        "pending": pending,
        "accepted": accepted,
        "accepted_with_edit": accepted_with_edit,
        "confirmed_no_data": confirmed_no_data,   # paper truly has no data (T075a)
        "rejected": rejected,                     # model wrong / out-of-scope (T075a)
        "explicitly_accepted": accepted + accepted_with_edit,
        "explicitly_rejected": rejected,
        "confirmed_absent": confirmed_no_data,
        "automation_accepted_count": automation_accepted_count,
        "automation_review_applied": automation_accepted_count > 0,
    }


def get_progress_for_review(run_dir: pathlib.Path) -> dict:
    """Return progress counters for actionable review proposals only."""
    proposals = [p for p in load_proposals(run_dir) if _is_reviewable_proposal(p)]
    total = len(proposals)
    accepted = 0
    accepted_with_edit = 0
    confirmed_no_data = 0
    rejected = 0
    pending = 0

    for p in proposals:
        d = get_latest_decision(run_dir, p.proposal_id)
        if d is None:
            pending += 1
        elif d.decision == ReviewDecision.accepted:
            accepted += 1
        elif d.decision == ReviewDecision.accepted_with_edit:
            accepted_with_edit += 1
        elif d.decision == ReviewDecision.confirmed_no_data:
            confirmed_no_data += 1
        elif d.decision == ReviewDecision.rejected:
            rejected += 1
        else:
            pending += 1

    reviewed = accepted + accepted_with_edit + confirmed_no_data + rejected
    return {
        "total": total,
        "total_proposals": total,
        "reviewed": reviewed,
        "pending": pending,
        "accepted": accepted,
        "accepted_with_edit": accepted_with_edit,
        "confirmed_no_data": confirmed_no_data,
        "rejected": rejected,
        "explicitly_accepted": accepted + accepted_with_edit,
        "explicitly_rejected": rejected,
        "confirmed_absent": confirmed_no_data,
    }


# ---------------------------------------------------------------------------
# T076/T077 — Run and reviewer summary generation
# ---------------------------------------------------------------------------

def compute_reviewer_summary(run_dir: pathlib.Path, run_id: str) -> ReviewerSummary:
    """Pure function: compute reviewer summary from proposal + decision artifacts."""
    progress = get_progress(run_dir)
    actionable_progress = get_progress_for_review(run_dir)
    run_data = load_run_json(run_dir)
    return ReviewerSummary(
        run_id=run_id,
        verify_mode=bool(run_data.get("verify_mode", False)),
        eval_mode=bool(run_data.get("eval_mode", False)),
        run_mode=str(run_data.get("run_mode") or ("verify" if run_data.get("verify_mode") else "normal")),
        provider_token=run_data.get("provider_token"),
        provider_locality=run_data.get("provider_locality"),
        provider_mode=run_data.get("provider_mode"),
        provider_text_model_id=run_data.get("provider_text_model_id"),
        provider_vision_model_id=run_data.get("provider_vision_model_id"),
        structured_output_mode=run_data.get("structured_output_mode"),
        structured_output_reason=run_data.get("structured_output_reason"),
        structured_output_fallback_used=bool(run_data.get("structured_output_fallback_used", False)),
        prompt_only_degraded_mode_used=bool(run_data.get("prompt_only_degraded_mode_used", False)),
        parse_repair_used=bool(run_data.get("parse_repair_used", False)),
        parse_repair_summary=run_data.get("parse_repair_summary"),
        vision_structured_output_mode=run_data.get("vision_structured_output_mode"),
        vision_structured_output_reason=run_data.get("vision_structured_output_reason"),
        provider_readiness_error=run_data.get("provider_readiness_error"),
        provider_readiness_reason=run_data.get("provider_readiness_reason"),
        provider_model_management_path=run_data.get("provider_model_management_path"),
        retrieval_mode=run_data.get("retrieval_mode"),
        retrieval_top_k=run_data.get("retrieval_top_k"),
        recall_rescue_enabled=bool(run_data.get("recall_rescue_enabled", False)),
        whole_document_mode=bool(run_data.get("whole_document_mode", False)),
        recall_rescue_used=bool(run_data.get("recall_rescue_used", False)),
        retrieval_provenance=run_data.get("retrieval_provenance"),
        prompt_version=run_data.get("prompt_version"),
        prompt_hash=run_data.get("prompt_hash"),
        prompt_bundle_id=run_data.get("prompt_bundle_id"),
        prompt_bundle_version=run_data.get("prompt_bundle_version"),
        prompt_bundle_path=run_data.get("prompt_bundle_path"),
        prompt_manifest_hash=run_data.get("prompt_manifest_hash"),
        prompt_bundle_hash=run_data.get("prompt_bundle_hash"),
        prompt_keys_used=run_data.get("prompt_keys_used"),
        prompt_files=run_data.get("prompt_files"),
        config_hash=run_data.get("config_hash"),
        config_snapshot_path=run_data.get("config_snapshot_path"),
        schema_hash=run_data.get("schema_hash"),
        schema_version=run_data.get("schema_version"),
        parser_identity=run_data.get("parser_identity"),
        parser_version=run_data.get("parser_version"),
        eval_artifacts=run_data.get("eval_artifacts"),
        extraction_contract_valid=bool(run_data.get("extraction_contract_valid", False)),
        extraction_contract_warnings=run_data.get("extraction_contract_warnings", []),
        extraction_provenance=run_data.get("extraction_provenance"),
        total_proposals=progress["total"],
        reviewed=progress["reviewed"],
        accepted=progress["accepted"],
        accepted_with_edit=progress["accepted_with_edit"],
        confirmed_no_data=progress["confirmed_no_data"],
        rejected=progress["rejected"],
        pending=progress["pending"],
        actionable_total_proposals=actionable_progress["total"],
        actionable_reviewed=actionable_progress["reviewed"],
        actionable_pending=actionable_progress["pending"],
        diagnostic_only_total_proposals=max(0, progress["total"] - actionable_progress["total"]),
        explicitly_accepted=progress["explicitly_accepted"],
        explicitly_rejected=progress["explicitly_rejected"],
        confirmed_absent=progress["confirmed_absent"],
        automation_review_applied=bool(progress.get("automation_review_applied", False)),
        automation_accepted_count=int(progress.get("automation_accepted_count", 0) or 0),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def persist_reviewer_summary(run_dir: pathlib.Path, run_id: str) -> ReviewerSummary:
    """Recompute and persist the reviewer summary to summaries/reviewer_summary.json."""
    summary = compute_reviewer_summary(run_dir, run_id)
    path = get_reviewer_summary_path(str(run_dir.parent), run_id)
    write_json(path, summary.model_dump())
    return summary


def load_run_json(run_dir: pathlib.Path) -> dict:
    """Load run.json for a run."""
    path = run_dir / "run.json"
    if not path.exists():
        return {}
    return read_json(path)


def compute_run_summary(run_dir: pathlib.Path, run_id: str) -> dict:
    """Compute a run summary dict from artifacts (T076, T078).

    Merges the persisted run.json with live reviewer progress so the summary
    always reflects the current decision state even before a full recompute.
    """
    run_data = load_run_json(run_dir)
    progress = get_progress(run_dir)
    actionable_progress = get_progress_for_review(run_dir)

    summary = dict(run_data)
    summary["run_id"] = run_id
    summary["proposals_generated"] = summary.get("proposals_generated", progress["total"])
    summary["proposals_reviewed"] = progress["reviewed"]
    # Enrich with decision breakdown
    summary["review_progress"] = progress
    summary["actionable_review_progress"] = actionable_progress
    summary["diagnostic_only_total_proposals"] = max(0, progress["total"] - actionable_progress["total"])

    return summary


def persist_run_summary(run_dir: pathlib.Path, run_id: str) -> dict:
    """Recompute and persist the run summary to summaries/run_summary.json."""
    summary = compute_run_summary(run_dir, run_id)
    # Determine output_dir from run_dir (run_dir is output_dir/run_id)
    output_dir = str(run_dir.parent)
    path = get_run_summary_path(output_dir, run_id)
    write_json(path, summary)
    return summary


# ---------------------------------------------------------------------------
# T078 — Summary recomputation entry point
# ---------------------------------------------------------------------------

def recompute_summaries(run_dir: pathlib.Path, run_id: str) -> dict:
    """Recompute both run and reviewer summaries from artifact files.

    Returns a dict with both recomputed summaries. Raises ValueError if
    integrity checks fail (T078a).
    """
    reviewer = compute_reviewer_summary(run_dir, run_id)

    # Integrity check before persisting (T078a)
    validate_reviewer_summary_integrity(reviewer)

    run_summary = compute_run_summary(run_dir, run_id)

    # Persist
    output_dir = str(run_dir.parent)
    write_json(get_reviewer_summary_path(output_dir, run_id), reviewer.model_dump())
    write_json(get_run_summary_path(output_dir, run_id), run_summary)

    return {
        "run_summary": run_summary,
        "reviewer_summary": reviewer.model_dump(),
    }


# ---------------------------------------------------------------------------
# T078a — Summary integrity checks
# ---------------------------------------------------------------------------

def validate_reviewer_summary_integrity(summary: ReviewerSummary) -> None:
    """Raise ValueError if the summary is internally inconsistent.

    Checks:
    - total == reviewed + pending
    - reviewed == accepted + accepted_with_edit + confirmed_no_data + rejected
    - explicitly_accepted == accepted + accepted_with_edit
    - confirmed_absent == confirmed_no_data (T075a: must stay separate)
    - no count is negative
    """
    counts = [
        summary.total_proposals,
        summary.accepted,
        summary.accepted_with_edit,
        summary.confirmed_no_data,
        summary.rejected,
        summary.pending,
    ]
    for name, val in zip(
        ["total", "accepted", "accepted_with_edit", "confirmed_no_data", "rejected", "pending"],
        counts,
    ):
        if val < 0:
            raise ValueError(f"ReviewerSummary.{name} is negative ({val})")

    reviewed = summary.accepted + summary.accepted_with_edit + summary.confirmed_no_data + summary.rejected
    if summary.reviewed not in (0, reviewed):
        raise ValueError(
            f"ReviewerSummary.reviewed={summary.reviewed} is inconsistent with "
            f"accepted+accepted_with_edit+confirmed_no_data+rejected ({reviewed})"
        )
    if summary.total_proposals != reviewed + summary.pending:
        raise ValueError(
            f"ReviewerSummary count mismatch: total={summary.total_proposals} "
            f"!= reviewed({reviewed}) + pending({summary.pending})"
        )

    if summary.explicitly_accepted != summary.accepted + summary.accepted_with_edit:
        raise ValueError(
            "ReviewerSummary.explicitly_accepted is inconsistent with accepted + accepted_with_edit"
        )

    if summary.confirmed_absent != summary.confirmed_no_data:
        raise ValueError(
            "ReviewerSummary.confirmed_absent must equal confirmed_no_data (T075a)"
        )

    actionable_total = summary.actionable_total_proposals or summary.total_proposals
    actionable_reviewed = summary.actionable_reviewed or reviewed
    actionable_pending = summary.actionable_pending or summary.pending
    diagnostic_only_total = (
        summary.diagnostic_only_total_proposals
        if summary.diagnostic_only_total_proposals
        else summary.total_proposals - actionable_total
    )

    if actionable_total != actionable_reviewed + actionable_pending:
        raise ValueError(
            "ReviewerSummary actionable totals are inconsistent with actionable_reviewed + actionable_pending"
        )

    if diagnostic_only_total != summary.total_proposals - actionable_total:
        raise ValueError(
            "ReviewerSummary diagnostic_only_total_proposals must equal total_proposals - actionable_total_proposals"
        )


# ---------------------------------------------------------------------------
# T079 — Export candidate selection (accepted-only, by construction)
# ---------------------------------------------------------------------------

def get_export_candidates(run_dir: pathlib.Path) -> list[dict]:
    """Return proposals that have been explicitly accepted (as-is or with edit).

    This function constructs the export list from explicit decision records only.
    Unreviewed proposals are excluded by construction.  confirmed_no_data and
    rejected are also excluded — only accepted and accepted_with_edit qualify.
    """
    proposals = load_proposals(run_dir)
    proposal_map = {p.proposal_id: p for p in proposals}

    candidates: list[dict] = []
    for p in proposals:
        latest = get_latest_decision(run_dir, p.proposal_id)
        if latest is None:
            continue  # Unreviewed — excluded by construction
        if latest.decision not in (ReviewDecision.accepted, ReviewDecision.accepted_with_edit):
            continue  # confirmed_no_data and rejected are not export candidates

        candidate: dict = {
            "proposal_id": p.proposal_id,
            "cell_id": p.cell_id,
            "row_id": p.row_id,
            "column_name": p.column_name,
            "pdf_id": p.pdf_id,
            "proposed_value": p.proposed_value,
            "decision": latest.decision.value,
            "decision_source": latest.decision_source.value,
            "edited_value": latest.edited_value,
            "reviewer_note": latest.reviewer_note,
            # Export value: edited if accepted_with_edit, otherwise proposed
            "export_value": (
                latest.edited_value
                if latest.decision == ReviewDecision.accepted_with_edit
                else p.proposed_value
            ),
            "decided_at": latest.decided_at,
            "review_decision_id": latest.review_decision_id,
        }
        candidates.append(candidate)

    return candidates


# ---------------------------------------------------------------------------
# T071 — Asset path helpers for review-asset serving
# ---------------------------------------------------------------------------

def get_pdf_asset_path(run_dir: pathlib.Path, pdf_id: str) -> Optional[pathlib.Path]:
    """Return the path to the original PDF file for a given pdf_id.

    The original PDF path is stored in the parsed document metadata.
    """
    parsed_path = get_parsed_dir(run_dir, pdf_id) / "parsed_document.json"
    if not parsed_path.exists():
        return None
    try:
        doc = read_json(parsed_path)
        source_path = doc.get("source_path") or doc.get("pdf_path")
        if source_path:
            p = pathlib.Path(source_path)
            if p.exists():
                return p
    except Exception:
        pass
    return None


def get_page_image_path(run_dir: pathlib.Path, pdf_id: str, page: int) -> Optional[pathlib.Path]:
    """Return the path to a rendered page image if it was stored during parsing."""
    img_path = get_parsed_dir(run_dir, pdf_id) / "pages" / f"page_{page:04d}.png"
    if img_path.exists():
        return img_path
    return None


def get_figure_crop_path(
    run_dir: pathlib.Path, pdf_id: str, figure_id: str
) -> Optional[pathlib.Path]:
    """Return the path to a figure crop image if available."""
    figures_dir = get_parsed_dir(run_dir, pdf_id) / "figures"
    for candidate in [
        figures_dir / f"{figure_id}.png",
        figures_dir / f"{figure_id}.jpg",
        figures_dir / f"{figure_id}_crop.png",
    ]:
        if candidate.exists():
            return candidate
    parsed_path = get_parsed_dir(run_dir, pdf_id) / "parsed_document.json"
    if parsed_path.exists():
        try:
            doc = read_json(parsed_path)
            for figure in doc.get("figures", []) or []:
                if not isinstance(figure, dict) or figure.get("figure_id") != figure_id:
                    continue
                crop_path = figure.get("crop_path")
                if not isinstance(crop_path, str) or not crop_path.strip():
                    continue
                candidate = pathlib.Path(crop_path)
                resolved = candidate if candidate.is_absolute() else run_dir / candidate
                if resolved.exists():
                    return resolved
        except Exception:
            pass
    return None


def get_evidence_asset_metadata(
    run_dir: pathlib.Path, evidence_id: str
) -> Optional[dict]:
    """Return evidence metadata for a given evidence_id."""
    all_evidence = load_evidence(run_dir)
    for ev in all_evidence:
        if ev.evidence_id == evidence_id:
            return ev.model_dump()
    return None
