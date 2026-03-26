"""
Batch 4 — Review decision persistence, bulk-accept, progress counters, export candidates.

Implements:
- T072: Review-decision persistence (accept/accept_with_edit/reject/undecided)
- T073: Audit history preservation (all decisions appended, latest wins for progress)
- T074: Guarded bulk-accept limited to the currently visible filtered subset of undecided proposals
- T075: Progress counters and decision-breakdown aggregation
- T079: Export candidate selection (only explicitly accepted proposals)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from .ids import make_review_decision_id
from .schemas import (
    ExportCandidate,
    ProposalListItem,
    ProposalProgress,
    ReviewDecision,
    ReviewDecisionRecord,
    WarningStatusCategory,
)

if TYPE_CHECKING:
    from .artifacts import RunArtifacts


def _load_latest_decisions(artifacts: "RunArtifacts") -> dict[str, ReviewDecisionRecord]:
    """Return the most recent ReviewDecisionRecord for each proposal_id."""
    decision_rows = artifacts.read_jsonl("review/decisions.jsonl")
    latest: dict[str, ReviewDecisionRecord] = {}
    for row in decision_rows:
        try:
            rec = ReviewDecisionRecord.model_validate(row)
        except Exception:
            continue
        current = latest.get(rec.proposal_id)
        if current is None or rec.decided_at >= current.decided_at:
            latest[rec.proposal_id] = rec
    return latest


def _count_existing_decisions(artifacts: "RunArtifacts", proposal_id: str) -> int:
    """Count how many decision records exist for a proposal (for ordinal generation)."""
    decision_rows = artifacts.read_jsonl("review/decisions.jsonl")
    return sum(1 for row in decision_rows if row.get("proposal_id") == proposal_id)


def record_review_decision(
    artifacts: "RunArtifacts",
    run_id: str,
    proposal_id: str,
    cell_id: str,
    decision: ReviewDecision,
    edited_value: str | None = None,
) -> ReviewDecisionRecord:
    """
    T072 + T073: Record a review decision and append it to the audit log.

    All decisions are appended (never replaced), preserving full history for auditability.
    The latest decision per proposal wins for progress and export purposes.
    """
    ordinal = _count_existing_decisions(artifacts, proposal_id)
    decision_id = make_review_decision_id(run_id, proposal_id, ordinal)
    record = ReviewDecisionRecord(
        decision_id=decision_id,
        run_id=run_id,
        proposal_id=proposal_id,
        cell_id=cell_id,
        decision=decision,
        edited_value=edited_value,
        decided_at=datetime.now(timezone.utc),
    )
    artifacts.append_jsonl("review/decisions.jsonl", record.model_dump(mode="json"))
    return record


def get_progress(artifacts: "RunArtifacts") -> ProposalProgress:
    """T075: Compute progress counters and decision-breakdown aggregation."""
    proposals = artifacts.read_jsonl("proposals/proposals.jsonl")
    latest_decisions = _load_latest_decisions(artifacts)

    accepted = 0
    accepted_with_edit = 0
    rejected = 0

    for proposal in proposals:
        pid = proposal.get("proposal_id", "")
        decision = latest_decisions.get(pid)
        if decision is None or decision.decision == ReviewDecision.UNDECIDED:
            continue
        if decision.decision == ReviewDecision.ACCEPT:
            accepted += 1
        elif decision.decision == ReviewDecision.ACCEPT_WITH_EDIT:
            accepted_with_edit += 1
        elif decision.decision == ReviewDecision.REJECT:
            rejected += 1

    total = len(proposals)
    decided = accepted + accepted_with_edit + rejected
    return ProposalProgress(
        total=total,
        accepted_as_is=accepted,
        accepted_with_edit=accepted_with_edit,
        rejected=rejected,
        pending=max(total - decided, 0),
    )


def list_proposals(
    artifacts: "RunArtifacts",
    row_id: str | None = None,
    column_name: str | None = None,
    pdf_id: str | None = None,
    has_figure_evidence: bool | None = None,
    has_ambiguous_match: bool | None = None,
    decision_status: ReviewDecision | None = None,
) -> list[ProposalListItem]:
    """T069: Return proposals matching the provided filters with latest decision attached."""
    proposal_rows = artifacts.read_jsonl("proposals/proposals.jsonl")
    latest_decisions = _load_latest_decisions(artifacts)

    items: list[ProposalListItem] = []
    for row in proposal_rows:
        # Filters
        if row_id is not None and row.get("row_id") != row_id:
            continue
        if column_name is not None and row.get("column_name") != column_name:
            continue
        if pdf_id is not None and row.get("pdf_id") != pdf_id:
            continue

        flags: list[str] = row.get("status_flags", [])

        if has_figure_evidence is not None:
            is_fig = WarningStatusCategory.FIGURE_DERIVED in flags
            if has_figure_evidence != is_fig:
                continue

        if has_ambiguous_match is not None:
            is_amb = WarningStatusCategory.AMBIGUOUS_MATCH in flags
            if has_ambiguous_match != is_amb:
                continue

        pid = row.get("proposal_id", "")
        decision_rec = latest_decisions.get(pid)
        latest_decision = decision_rec.decision if decision_rec else ReviewDecision.UNDECIDED

        if decision_status is not None and latest_decision != decision_status:
            continue

        try:
            item = ProposalListItem(
                proposal_id=pid,
                run_id=row.get("run_id", ""),
                pdf_id=row.get("pdf_id", ""),
                row_id=row.get("row_id", ""),
                column_name=row.get("column_name", ""),
                cell_id=row.get("cell_id", ""),
                source_mode=row.get("source_mode", "text"),
                proposal_state=row.get("proposal_state", "unclear"),
                support_label=row.get("support_label", "weak_evidence"),
                proposed_value=row.get("proposed_value"),
                status_flags=[WarningStatusCategory(f) for f in flags if f in WarningStatusCategory._value2member_map_],
                latest_decision=latest_decision,
            )
            items.append(item)
        except Exception:
            continue

    return items


def bulk_accept(
    artifacts: "RunArtifacts",
    run_id: str,
    row_id: str | None = None,
    column_name: str | None = None,
    pdf_id: str | None = None,
) -> list[ReviewDecisionRecord]:
    """
    T074: Bulk-accept all currently undecided proposals within the visible filtered subset.

    Applies the ACCEPT decision only to proposals that are currently UNDECIDED (or have no decision)
    within the filtered subset. Already-decided proposals are not changed.
    """
    # Get undecided proposals matching the filter
    undecided = list_proposals(
        artifacts,
        row_id=row_id,
        column_name=column_name,
        pdf_id=pdf_id,
        decision_status=ReviewDecision.UNDECIDED,
    )
    recorded: list[ReviewDecisionRecord] = []
    for item in undecided:
        rec = record_review_decision(
            artifacts=artifacts,
            run_id=run_id,
            proposal_id=item.proposal_id,
            cell_id=item.cell_id,
            decision=ReviewDecision.ACCEPT,
        )
        recorded.append(rec)
    return recorded


def get_export_candidates(artifacts: "RunArtifacts") -> list[ExportCandidate]:
    """
    T079: Return only proposals that were explicitly accepted (ACCEPT or ACCEPT_WITH_EDIT).

    Unreviewed proposals are excluded by construction.
    """
    proposal_rows = artifacts.read_jsonl("proposals/proposals.jsonl")
    latest_decisions = _load_latest_decisions(artifacts)
    candidates: list[ExportCandidate] = []

    for row in proposal_rows:
        pid = row.get("proposal_id", "")
        decision_rec = latest_decisions.get(pid)
        if decision_rec is None:
            continue
        if decision_rec.decision not in (ReviewDecision.ACCEPT, ReviewDecision.ACCEPT_WITH_EDIT):
            continue

        accepted_value = (
            decision_rec.edited_value
            if decision_rec.decision == ReviewDecision.ACCEPT_WITH_EDIT and decision_rec.edited_value is not None
            else row.get("proposed_value")
        )
        candidates.append(
            ExportCandidate(
                proposal_id=pid,
                run_id=row.get("run_id", ""),
                pdf_id=row.get("pdf_id", ""),
                row_id=row.get("row_id", ""),
                column_name=row.get("column_name", ""),
                cell_id=row.get("cell_id", ""),
                accepted_value=accepted_value,
                decision=decision_rec.decision,
            )
        )
    return candidates


def get_proposal_decision_history(artifacts: "RunArtifacts", proposal_id: str) -> list[dict[str, Any]]:
    """T073: Return the full decision history for a proposal (for audit purposes)."""
    decision_rows = artifacts.read_jsonl("review/decisions.jsonl")
    return [row for row in decision_rows if row.get("proposal_id") == proposal_id]
