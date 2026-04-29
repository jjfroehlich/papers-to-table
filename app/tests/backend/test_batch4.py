"""Batch 4 tests: review decision persistence, list/detail/filter APIs,
summaries, recomputation, warning categories, confirmed-no-data semantics,
bulk-accept gating, and export candidates (T080).
"""
from __future__ import annotations

import pathlib
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app.extraction import (
    EvidenceRecord,
    ProposalRecord,
    persist_evidence,
    persist_proposal,
)
from backend.app.ids import (
    generate_cell_id,
    generate_evidence_id,
    generate_pdf_id,
    generate_proposal_id,
    generate_row_id,
    generate_run_id,
)
from backend.app.artifacts import (
    get_run_dir,
    get_reviewer_summary_path,
    get_run_summary_path,
    init_run_bundle,
    read_json,
    write_json,
)
from backend.app.review import (
    ProposalFilter,
    bulk_accept_proposals,
    compute_reviewer_summary,
    get_decision_history,
    get_export_candidates,
    get_latest_decision,
    get_progress,
    get_progress_for_review,
    get_proposal_detail,
    list_proposals,
    record_review_decision,
    recompute_summaries,
    validate_reviewer_summary_integrity,
)
from backend.app.schemas import (
    ReviewDecision,
    ReviewResolutionReason,
    ReviewerSummary,
    RunStatus,
    WarningCategory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(tmp_path: pathlib.Path) -> tuple[pathlib.Path, str]:
    """Create a minimal run bundle and return (run_dir, run_id)."""
    run_id = generate_run_id()
    output_dir = str(tmp_path)
    run_dir = init_run_bundle(output_dir, run_id)
    run_data = {
        "run_id": run_id,
        "status": RunStatus.completed.value,
        "output_dir": output_dir,
        "verify_mode": False,
        "total_rows": 1,
        "eligible_cells": 3,
        "proposals_generated": 0,
        "proposals_reviewed": 0,
        "warnings": [],
    }
    write_json(run_dir / "run.json", run_data)
    return run_dir, run_id


def _make_proposal(
    run_dir: pathlib.Path,
    run_id: str,
    pdf_id: str,
    row_id: str,
    column_name: str,
    warning_flags: list[str] | None = None,
    support: str = "direct_evidence",
    state: str = "found",
    proposed_value: str = "test_value",
) -> ProposalRecord:
    cell_id = generate_cell_id(row_id, column_name)
    proposal_id = generate_proposal_id(run_id, cell_id)
    p = ProposalRecord(
        proposal_id=proposal_id,
        run_id=run_id,
        pdf_id=pdf_id,
        row_id=row_id,
        column_name=column_name,
        cell_id=cell_id,
        state=state,
        support=support,
        proposed_value=proposed_value,
        rationale="Some rationale.",
        evidence_ids=[],
        warning_flags=warning_flags or [],
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_proposal(run_dir, p)
    return p


def _make_evidence(
    run_dir: pathlib.Path,
    proposal: ProposalRecord,
    source_type: str = "direct_quote",
    is_figure: bool = False,
) -> EvidenceRecord:
    ev_id = generate_evidence_id(proposal.proposal_id)
    ev = EvidenceRecord(
        evidence_id=ev_id,
        run_id=proposal.run_id,
        proposal_id=proposal.proposal_id,
        pdf_id=proposal.pdf_id,
        source_type=source_type,
        quote_text="Some quote.",
        page_number=1,
        evidence_rank=1,
        is_primary=True,
        is_figure_derived=is_figure,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    persist_evidence(run_dir, ev)
    return ev


# ---------------------------------------------------------------------------
# T072 — Review decision persistence
# ---------------------------------------------------------------------------

class TestDecisionPersistence:
    def test_record_accepted_decision(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        rec = record_review_decision(
            run_dir=run_dir,
            proposal_id=p.proposal_id,
            cell_id=p.cell_id,
            run_id=run_id,
            decision=ReviewDecision.accepted,
            resolution_reason=ReviewResolutionReason.accepted_as_proposed,
        )

        assert rec.decision == ReviewDecision.accepted
        assert rec.proposal_id == p.proposal_id
        assert rec.cell_id == p.cell_id
        assert rec.decided_at

    def test_record_accepted_with_edit(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        rec = record_review_decision(
            run_dir=run_dir,
            proposal_id=p.proposal_id,
            cell_id=p.cell_id,
            run_id=run_id,
            decision=ReviewDecision.accepted_with_edit,
            resolution_reason=ReviewResolutionReason.accepted_with_edit,
            edited_value="corrected_value",
        )

        assert rec.decision == ReviewDecision.accepted_with_edit
        assert rec.edited_value == "corrected_value"

    def test_record_rejected_decision(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        rec = record_review_decision(
            run_dir=run_dir,
            proposal_id=p.proposal_id,
            cell_id=p.cell_id,
            run_id=run_id,
            decision=ReviewDecision.rejected,
            resolution_reason=ReviewResolutionReason.rejected_incorrect,
        )

        assert rec.decision == ReviewDecision.rejected

    def test_record_confirmed_no_data(self, tmp_path):
        """T075a: confirmed_no_data must be persistable and distinct from rejected."""
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        rec = record_review_decision(
            run_dir=run_dir,
            proposal_id=p.proposal_id,
            cell_id=p.cell_id,
            run_id=run_id,
            decision=ReviewDecision.confirmed_no_data,
            resolution_reason=ReviewResolutionReason.confirmed_no_data_in_paper,
        )

        assert rec.decision == ReviewDecision.confirmed_no_data
        assert rec.decision != ReviewDecision.rejected

    def test_get_latest_decision_none_before_any_decision(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        latest = get_latest_decision(run_dir, p.proposal_id)
        assert latest is None

    def test_get_latest_decision_returns_most_recent(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        record_review_decision(
            run_dir, p.proposal_id, p.cell_id, run_id,
            decision=ReviewDecision.rejected,
        )
        record_review_decision(
            run_dir, p.proposal_id, p.cell_id, run_id,
            decision=ReviewDecision.accepted,
        )

        latest = get_latest_decision(run_dir, p.proposal_id)
        assert latest is not None
        assert latest.decision == ReviewDecision.accepted


# ---------------------------------------------------------------------------
# T073 — Audit history preservation
# ---------------------------------------------------------------------------

class TestAuditHistory:
    def test_history_accumulates_decisions(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.rejected)
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        history = get_decision_history(run_dir, p.proposal_id)
        assert len(history) == 2
        assert history[0].decision == ReviewDecision.rejected
        assert history[1].decision == ReviewDecision.accepted

    def test_prior_decisions_not_overwritten_in_history(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)

        history = get_decision_history(run_dir, p.proposal_id)
        assert any(d.decision == ReviewDecision.confirmed_no_data for d in history)


# ---------------------------------------------------------------------------
# T069 — Proposal list and filters
# ---------------------------------------------------------------------------

class TestProposalListFilter:
    def test_list_all_proposals(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        proposals = list_proposals(run_dir)
        assert len(proposals) == 2

    def test_filter_by_column_name(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        filt = ProposalFilter(column_name="Dose")
        proposals = list_proposals(run_dir, filt)
        assert len(proposals) == 1
        assert proposals[0]["column_name"] == "Dose"

    def test_filter_by_pdf_id(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_a = generate_pdf_id("paper_a.pdf")
        pdf_b = generate_pdf_id("paper_b.pdf")
        row_a = generate_row_id(0, "Title A")
        row_b = generate_row_id(1, "Title B")
        # Each PDF matches a different row, so different cell_ids
        _make_proposal(run_dir, run_id, pdf_a, row_a, "Dose")
        _make_proposal(run_dir, run_id, pdf_b, row_b, "Dose")

        filt = ProposalFilter(pdf_id=pdf_a)
        proposals = list_proposals(run_dir, filt)
        assert len(proposals) == 1
        assert proposals[0]["pdf_id"] == pdf_a

    def test_filter_by_row_id(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_a = generate_row_id(0, "Title A")
        row_b = generate_row_id(1, "Title B")
        _make_proposal(run_dir, run_id, pdf_id, row_a, "Dose")
        _make_proposal(run_dir, run_id, pdf_id, row_b, "Dose")

        filt = ProposalFilter(row_id=row_a)
        proposals = list_proposals(run_dir, filt)
        assert len(proposals) == 1
        assert proposals[0]["row_id"] == row_a

    def test_filter_by_decision_undecided(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        filt = ProposalFilter(decision="undecided")
        proposals = list_proposals(run_dir, filt)
        assert len(proposals) == 1
        assert proposals[0]["proposal_id"] == p2.proposal_id

    def test_filter_by_decision_accepted(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        filt = ProposalFilter(decision="accepted")
        proposals = list_proposals(run_dir, filt)
        assert len(proposals) == 1
        assert proposals[0]["proposal_id"] == p1.proposal_id

    def test_filter_figure_derived(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose",
                       warning_flags=["figure_derived"])
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        filt = ProposalFilter(figure_derived=True)
        proposals = list_proposals(run_dir, filt)
        assert len(proposals) == 1
        assert proposals[0]["is_figure_derived"] is True

    def test_proposal_includes_latest_decision(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        proposals = list_proposals(run_dir)
        assert proposals[0]["latest_decision"]["decision"] == "accepted"

    def test_undecided_proposal_has_null_decision(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        proposals = list_proposals(run_dir)
        assert proposals[0]["latest_decision"] is None

    def test_reviewable_only_excludes_blocked_and_skipped(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        reviewable = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose", state="unclear")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome", state="blocked")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Study Type", state="skipped")

        proposals = list_proposals(run_dir, ProposalFilter(reviewable_only=True))

        assert len(proposals) == 1
        assert proposals[0]["proposal_id"] == reviewable.proposal_id


# ---------------------------------------------------------------------------
# T070 — Proposal detail
# ---------------------------------------------------------------------------

class TestProposalDetail:
    def test_returns_proposal_and_evidence(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        _make_evidence(run_dir, p)

        detail = get_proposal_detail(run_dir, p.proposal_id)
        assert detail is not None
        assert detail["proposal"]["proposal_id"] == p.proposal_id
        assert len(detail["evidence"]) == 1

    def test_returns_none_for_unknown_id(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        detail = get_proposal_detail(run_dir, "prop_nonexistent")
        assert detail is None

    def test_includes_decision_history(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.rejected)
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        detail = get_proposal_detail(run_dir, p.proposal_id)
        assert detail["latest_decision"]["decision"] == "accepted"
        assert len(detail["decision_history"]) == 2

    def test_includes_warning_categories(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose",
                           warning_flags=["fallback_evidence"])

        detail = get_proposal_detail(run_dir, p.proposal_id)
        assert WarningCategory.fallback_evidence_used.value in detail["warning_categories"]

    def test_defaults_missing_row_and_column_context(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        detail = get_proposal_detail(run_dir, p.proposal_id)

        assert detail["row_context"] == {}
        assert detail["column_definition"] is None


# ---------------------------------------------------------------------------
# T068 — Warning categories
# ---------------------------------------------------------------------------

class TestWarningCategories:
    def test_figure_derived_flag_maps_to_category(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose",
                           warning_flags=["figure_derived"])
        proposals = list_proposals(run_dir)
        assert WarningCategory.figure_derived_evidence.value in proposals[0]["warning_categories"]

    def test_fallback_evidence_maps_to_category(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose",
                           warning_flags=["fallback_evidence"])
        proposals = list_proposals(run_dir)
        assert WarningCategory.fallback_evidence_used.value in proposals[0]["warning_categories"]

    def test_weak_evidence_support_maps_to_category(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose", support="weak_evidence")
        proposals = list_proposals(run_dir)
        assert WarningCategory.weak_evidence.value in proposals[0]["warning_categories"]

    def test_no_false_warning_for_clean_proposal(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        proposals = list_proposals(run_dir)
        assert proposals[0]["warning_categories"] == []


# ---------------------------------------------------------------------------
# T074 — Bulk-accept semantics
# ---------------------------------------------------------------------------

class TestBulkAccept:
    def test_bulk_accept_undecided_only(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")
        p3 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Study Type")

        # Pre-decide p2 as rejected
        record_review_decision(run_dir, p2.proposal_id, p2.cell_id, run_id,
                               decision=ReviewDecision.rejected)

        recorded = bulk_accept_proposals(
            run_dir, run_id,
            [p1.proposal_id, p2.proposal_id, p3.proposal_id]
        )

        # Only p1 and p3 should have been accepted (p2 already decided)
        assert len(recorded) == 2
        accepted_ids = {r.proposal_id for r in recorded}
        assert p1.proposal_id in accepted_ids
        assert p3.proposal_id in accepted_ids
        assert p2.proposal_id not in accepted_ids

    def test_bulk_accept_does_not_overwrite_existing_rejection(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.rejected)
        bulk_accept_proposals(run_dir, run_id, [p.proposal_id])

        latest = get_latest_decision(run_dir, p.proposal_id)
        assert latest.decision == ReviewDecision.rejected

    def test_bulk_accept_empty_list(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        recorded = bulk_accept_proposals(run_dir, run_id, [])
        assert recorded == []

    def test_bulk_accept_ignores_unknown_ids(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        recorded = bulk_accept_proposals(run_dir, run_id, ["prop_nonexistent"])
        assert recorded == []

    def test_individual_decision_source_defaults_to_human_individual(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        rec = record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id, decision=ReviewDecision.accepted)
        assert rec.decision_source.value == "human_individual"

    def test_bulk_accept_uses_human_bulk_accept_source(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        recorded = bulk_accept_proposals(run_dir, run_id, [p.proposal_id])
        assert recorded[0].decision_source.value == "human_bulk_accept"


# ---------------------------------------------------------------------------
# T075/T075a — Progress counters (confirmed-no-data distinct from rejected)
# ---------------------------------------------------------------------------

class TestProgressCounters:
    def test_all_pending_when_no_decisions(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        progress = get_progress(run_dir)
        assert progress["total"] == 2
        assert progress["pending"] == 2
        assert progress["reviewed"] == 0

    def test_confirmed_no_data_separate_from_rejected(self, tmp_path):
        """T075a: confirmed_no_data and rejected must be separate counters."""
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)
        record_review_decision(run_dir, p2.proposal_id, p2.cell_id, run_id,
                               decision=ReviewDecision.rejected)

        progress = get_progress(run_dir)
        assert progress["confirmed_no_data"] == 1
        assert progress["rejected"] == 1
        # confirmed_no_data != rejected — they are separate
        assert progress["confirmed_no_data"] != progress["rejected"] + 1

    def test_progress_totals_are_consistent(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")
        p3 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Study Type")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.accepted)
        record_review_decision(run_dir, p2.proposal_id, p2.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)

        progress = get_progress(run_dir)
        assert progress["total"] == 3
        assert progress["reviewed"] == 2
        assert progress["pending"] == 1
        assert progress["total"] == progress["reviewed"] + progress["pending"]

    def test_explicitly_accepted_and_rejected_helpers(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")
        p3 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Study Type")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.accepted)
        record_review_decision(run_dir, p2.proposal_id, p2.cell_id, run_id,
                               decision=ReviewDecision.accepted_with_edit,
                               edited_value="edited")
        record_review_decision(run_dir, p3.proposal_id, p3.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)

        progress = get_progress(run_dir)
        assert progress["explicitly_accepted"] == 2  # accepted + accepted_with_edit
        assert progress["explicitly_rejected"] == 0
        assert progress["confirmed_absent"] == 1     # T075a: confirmed_no_data

    def test_review_progress_excludes_blocked_proposals(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        reviewable = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose", state="unclear")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome", state="blocked")

        record_review_decision(run_dir, reviewable.proposal_id, reviewable.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        progress = get_progress_for_review(run_dir)
        assert progress["total_proposals"] == 1
        assert progress["reviewed"] == 1
        assert progress["pending"] == 0


# ---------------------------------------------------------------------------
# T076/T077 — Summary generation
# ---------------------------------------------------------------------------

class TestSummaryGeneration:
    def test_reviewer_summary_reflects_decisions(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")
        p3 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Study Type")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.accepted)
        record_review_decision(run_dir, p2.proposal_id, p2.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)

        summary = compute_reviewer_summary(run_dir, run_id)
        assert summary.total_proposals == 3
        assert summary.accepted == 1
        assert summary.confirmed_no_data == 1
        assert summary.pending == 1
        assert summary.rejected == 0

    def test_reviewer_summary_confirmed_no_data_distinct_from_rejected(self, tmp_path):
        """T075a: confirmed_no_data must remain separate from rejected in summaries."""
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)
        record_review_decision(run_dir, p2.proposal_id, p2.cell_id, run_id,
                               decision=ReviewDecision.rejected)

        summary = compute_reviewer_summary(run_dir, run_id)
        assert summary.confirmed_no_data == 1
        assert summary.rejected == 1
        assert summary.confirmed_absent == 1
        assert summary.explicitly_rejected == 1

    def test_reviewer_summary_all_pending_initially(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        summary = compute_reviewer_summary(run_dir, run_id)
        assert summary.total_proposals == 1
        assert summary.pending == 1
        assert summary.accepted == 0

    def test_reviewer_summary_includes_eval_mode_provenance(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        run_data = read_json(run_dir / "run.json")
        run_data.update(
            {
                "verify_mode": False,
                "eval_mode": True,
                "run_mode": "eval",
                "provider_token": "lm_studio",
                "provider_locality": "local",
                "provider_mode": "live_local",
                "provider_text_model_id": "text-model-id",
                "provider_vision_model_id": "vision-model-id",
                "prompt_hash": "prompt-hash",
                "config_hash": "config-hash",
                "schema_hash": "schema-hash",
                "parser_identity": "docling",
                "eval_artifacts": {
                    "gold_table": {
                        "source_reference": "/tmp/gold.xlsx",
                        "snapshot_path": "inputs/gold_table.xlsx",
                        "content_hash": "gold-hash",
                    },
                    "masked_working_table": {
                        "path": "inputs/masked_working_table.xlsx",
                        "content_hash": "masked-hash",
                    },
                },
            }
        )
        write_json(run_dir / "run.json", run_data)

        summary = compute_reviewer_summary(run_dir, run_id)

        assert summary.eval_mode is True
        assert summary.run_mode == "eval"
        assert summary.provider_token == "lm_studio"
        assert summary.provider_mode == "live_local"
        assert summary.provider_text_model_id == "text-model-id"
        assert summary.provider_vision_model_id == "vision-model-id"
        assert summary.prompt_hash == "prompt-hash"
        assert summary.config_hash == "config-hash"
        assert summary.schema_hash == "schema-hash"
        assert summary.parser_identity == "docling"
        assert summary.eval_artifacts is not None
        assert summary.eval_artifacts["gold_table"]["snapshot_path"] == "inputs/gold_table.xlsx"
        assert summary.eval_artifacts["masked_working_table"]["path"] == "inputs/masked_working_table.xlsx"


# ---------------------------------------------------------------------------
# T078 — Summary recomputation
# ---------------------------------------------------------------------------

class TestSummaryRecomputation:
    def test_recompute_updates_summaries(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        result = recompute_summaries(run_dir, run_id)
        assert result["reviewer_summary"]["accepted"] == 1
        assert result["reviewer_summary"]["pending"] == 0

    def test_recomputed_summaries_are_persisted(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        recompute_summaries(run_dir, run_id)

        output_dir = str(run_dir.parent)
        from backend.app.artifacts import read_json, get_reviewer_summary_path
        persisted = read_json(get_reviewer_summary_path(output_dir, run_id))
        assert persisted["accepted"] == 1

    def test_recompute_raises_on_inconsistency(self, tmp_path):
        """T078a: integrity check prevents inconsistent summaries."""
        bad_summary = ReviewerSummary(
            run_id="run_test",
            total_proposals=5,
            accepted=3,
            accepted_with_edit=0,
            confirmed_no_data=0,
            rejected=0,
            pending=3,   # 5 != 3 + 3 => inconsistent
            explicitly_accepted=3,
            explicitly_rejected=0,
            confirmed_absent=0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        with pytest.raises(ValueError, match="count mismatch"):
            validate_reviewer_summary_integrity(bad_summary)


# ---------------------------------------------------------------------------
# T078a — Integrity checks
# ---------------------------------------------------------------------------

class TestSummaryIntegrity:
    def test_valid_summary_passes(self, tmp_path):
        summary = ReviewerSummary(
            run_id="run_test",
            total_proposals=3,
            accepted=1,
            accepted_with_edit=1,
            confirmed_no_data=0,
            rejected=1,
            pending=0,
            explicitly_accepted=2,
            explicitly_rejected=1,
            confirmed_absent=0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        # Should not raise
        validate_reviewer_summary_integrity(summary)

    def test_negative_count_raises(self):
        summary = ReviewerSummary(
            run_id="run_test",
            total_proposals=1,
            accepted=-1,
            accepted_with_edit=0,
            confirmed_no_data=0,
            rejected=0,
            pending=2,
            explicitly_accepted=-1,
            explicitly_rejected=0,
            confirmed_absent=0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        with pytest.raises(ValueError, match="negative"):
            validate_reviewer_summary_integrity(summary)

    def test_explicitly_accepted_mismatch_raises(self):
        summary = ReviewerSummary(
            run_id="run_test",
            total_proposals=2,
            accepted=1,
            accepted_with_edit=1,
            confirmed_no_data=0,
            rejected=0,
            pending=0,
            explicitly_accepted=1,  # should be 2
            explicitly_rejected=0,
            confirmed_absent=0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        with pytest.raises(ValueError, match="explicitly_accepted"):
            validate_reviewer_summary_integrity(summary)

    def test_confirmed_absent_mismatch_raises(self):
        """T075a: confirmed_absent must equal confirmed_no_data."""
        summary = ReviewerSummary(
            run_id="run_test",
            total_proposals=1,
            accepted=0,
            accepted_with_edit=0,
            confirmed_no_data=1,
            rejected=0,
            pending=0,
            explicitly_accepted=0,
            explicitly_rejected=0,
            confirmed_absent=0,  # should equal confirmed_no_data=1
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        with pytest.raises(ValueError, match="confirmed_absent"):
            validate_reviewer_summary_integrity(summary)


# ---------------------------------------------------------------------------
# T079 — Export candidate selection
# ---------------------------------------------------------------------------

class TestExportCandidates:
    def test_accepted_proposals_are_candidates(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        candidates = get_export_candidates(run_dir)
        assert len(candidates) == 1
        assert candidates[0]["proposal_id"] == p.proposal_id
        assert candidates[0]["export_value"] == p.proposed_value

    def test_accepted_with_edit_uses_edited_value(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted_with_edit,
                               edited_value="corrected_value")

        candidates = get_export_candidates(run_dir)
        assert len(candidates) == 1
        assert candidates[0]["export_value"] == "corrected_value"

    def test_unreviewed_proposals_excluded_by_construction(self, tmp_path):
        """T079: unreviewed proposals must never appear in export candidates."""
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        candidates = get_export_candidates(run_dir)
        assert len(candidates) == 0

    def test_rejected_excluded_from_candidates(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.rejected)

        candidates = get_export_candidates(run_dir)
        assert len(candidates) == 0

    def test_confirmed_no_data_excluded_from_candidates(self, tmp_path):
        """T079: confirmed-no-data is not an export candidate."""
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)

        candidates = get_export_candidates(run_dir)
        assert len(candidates) == 0

    def test_mixed_decisions_only_accepted_qualify(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p1 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        p2 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")
        p3 = _make_proposal(run_dir, run_id, pdf_id, row_id, "Study Type")
        p4 = _make_proposal(run_dir, run_id, pdf_id, row_id, "N")

        record_review_decision(run_dir, p1.proposal_id, p1.cell_id, run_id,
                               decision=ReviewDecision.accepted)
        record_review_decision(run_dir, p2.proposal_id, p2.cell_id, run_id,
                               decision=ReviewDecision.accepted_with_edit,
                               edited_value="edited")
        record_review_decision(run_dir, p3.proposal_id, p3.cell_id, run_id,
                               decision=ReviewDecision.confirmed_no_data)
        # p4 is unreviewed

        candidates = get_export_candidates(run_dir)
        assert len(candidates) == 2
        candidate_ids = {c["proposal_id"] for c in candidates}
        assert p1.proposal_id in candidate_ids
        assert p2.proposal_id in candidate_ids
        assert p3.proposal_id not in candidate_ids
        assert p4.proposal_id not in candidate_ids

    def test_export_candidate_includes_audit_fields(self, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        p = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
        record_review_decision(run_dir, p.proposal_id, p.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        candidates = get_export_candidates(run_dir)
        c = candidates[0]
        assert "review_decision_id" in c
        assert "decided_at" in c
        assert "cell_id" in c
        assert "row_id" in c


# ---------------------------------------------------------------------------
# API endpoint tests (T069–T080)
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from backend.app.main import app
    return TestClient(app)


@pytest.fixture
def run_with_proposals(tmp_path):
    """Create a run bundle with two proposals and return (output_dir, run_id)."""
    run_dir, run_id = _make_run(tmp_path)
    pdf_id = generate_pdf_id("paper1.pdf")
    row_id = generate_row_id(0, "Title A")
    _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")
    _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome")
    return str(tmp_path), run_id


class TestProposalListAPI:
    def test_list_proposals_endpoint(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(f"/api/runs/{run_id}/proposals?output_dir={output_dir}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2

    def test_filter_by_column_name_endpoint(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(
            f"/api/runs/{run_id}/proposals?output_dir={output_dir}&column_name=Dose"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["proposals"][0]["column_name"] == "Dose"

    def test_run_not_found_returns_404(self, client, tmp_path):
        resp = client.get(f"/api/runs/nonexistent/proposals?output_dir={tmp_path}")
        assert resp.status_code == 404

    def test_reviewable_only_endpoint_excludes_blocked(self, client, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        reviewable = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose", state="unclear")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome", state="blocked")

        resp = client.get(
            f"/api/runs/{run_id}/proposals?output_dir={tmp_path}&reviewable_only=true"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["proposals"][0]["proposal_id"] == reviewable.proposal_id


class TestProposalDetailAPI:
    def test_get_proposal_detail_endpoint(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        # Get a proposal_id from the list
        resp = client.get(f"/api/runs/{run_id}/proposals?output_dir={output_dir}")
        proposal_id = resp.json()["proposals"][0]["proposal_id"]

        detail_resp = client.get(
            f"/api/runs/{run_id}/proposals/{proposal_id}?output_dir={output_dir}"
        )
        assert detail_resp.status_code == 200
        data = detail_resp.json()
        assert data["proposal"]["proposal_id"] == proposal_id

    def test_unknown_proposal_returns_404(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(
            f"/api/runs/{run_id}/proposals/prop_nonexistent?output_dir={output_dir}"
        )
        assert resp.status_code == 404

    def test_detail_endpoint_returns_safe_defaults(self, client, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        proposal = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose")

        resp = client.get(
            f"/api/runs/{run_id}/proposals/{proposal.proposal_id}?output_dir={tmp_path}"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["row_context"] == {}
        assert data["column_definition"] is None


class TestDecisionAPI:
    def test_record_decision_via_api(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        # Get a proposal_id
        resp = client.get(f"/api/runs/{run_id}/proposals?output_dir={output_dir}")
        proposal_id = resp.json()["proposals"][0]["proposal_id"]

        decision_resp = client.post(
            f"/api/runs/{run_id}/proposals/{proposal_id}/decision?output_dir={output_dir}",
            json={"decision": "accepted"},
        )
        assert decision_resp.status_code == 200
        data = decision_resp.json()
        assert data["decision"] == "accepted"

    def test_invalid_decision_returns_422(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(f"/api/runs/{run_id}/proposals?output_dir={output_dir}")
        proposal_id = resp.json()["proposals"][0]["proposal_id"]

        err_resp = client.post(
            f"/api/runs/{run_id}/proposals/{proposal_id}/decision?output_dir={output_dir}",
            json={"decision": "maybe"},
        )
        assert err_resp.status_code == 422

    def test_confirmed_no_data_decision_api(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(f"/api/runs/{run_id}/proposals?output_dir={output_dir}")
        proposal_id = resp.json()["proposals"][0]["proposal_id"]

        decision_resp = client.post(
            f"/api/runs/{run_id}/proposals/{proposal_id}/decision?output_dir={output_dir}",
            json={
                "decision": "confirmed_no_data",
                "resolution_reason": "confirmed_no_data_in_paper",
            },
        )
        assert decision_resp.status_code == 200
        assert decision_resp.json()["decision"] == "confirmed_no_data"


class TestBulkAcceptAPI:
    def test_bulk_accept_endpoint(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(f"/api/runs/{run_id}/proposals?output_dir={output_dir}")
        proposal_ids = [p["proposal_id"] for p in resp.json()["proposals"]]

        bulk_resp = client.post(
            f"/api/runs/{run_id}/proposals/bulk-accept?output_dir={output_dir}",
            json={"proposal_ids": proposal_ids},
        )
        assert bulk_resp.status_code == 200
        data = bulk_resp.json()
        assert data["accepted_count"] == 2


class TestProgressAPI:
    def test_progress_endpoint(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(f"/api/runs/{run_id}/progress?output_dir={output_dir}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert data["pending"] == 2
        assert "confirmed_no_data" in data
        assert "rejected" in data

    def test_review_progress_endpoint_uses_reviewable_subset(self, client, tmp_path):
        run_dir, run_id = _make_run(tmp_path)
        pdf_id = generate_pdf_id("paper1.pdf")
        row_id = generate_row_id(0, "Title A")
        reviewable = _make_proposal(run_dir, run_id, pdf_id, row_id, "Dose", state="unclear")
        _make_proposal(run_dir, run_id, pdf_id, row_id, "Outcome", state="blocked")

        record_review_decision(run_dir, reviewable.proposal_id, reviewable.cell_id, run_id,
                               decision=ReviewDecision.accepted)

        resp = client.get(f"/api/runs/{run_id}/progress-review?output_dir={tmp_path}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_proposals"] == 1
        assert data["reviewed"] == 1
        assert data["pending"] == 0


class TestAbortAPI:
    def test_abort_rejects_completed_run(self, client, tmp_path):
        _run_dir, run_id = _make_run(tmp_path)

        resp = client.post(f"/api/runs/{run_id}/abort?output_dir={tmp_path}")

        assert resp.status_code == 409
        assert "not active" in resp.json()["detail"]

    def test_abort_returns_interrupting_for_active_run(self, client, tmp_path, monkeypatch):
        run_dir, run_id = _make_run(tmp_path)
        run_json = read_json(run_dir / "run.json")
        run_json["status"] = RunStatus.running.value
        write_json(run_dir / "run.json", run_json)

        async def fake_abort_run(requested_run_id: str) -> bool:
            return requested_run_id == run_id

        monkeypatch.setattr("backend.app.api.routers.runs.get_run_executor", lambda: type("Executor", (), {"abort": staticmethod(fake_abort_run)})())

        resp = client.post(f"/api/runs/{run_id}/abort?output_dir={tmp_path}")

        assert resp.status_code == 200
        assert resp.json() == {"run_id": run_id, "status": "interrupting"}

    def test_abort_marks_stale_run_interrupted(self, client, tmp_path, monkeypatch):
        run_dir, run_id = _make_run(tmp_path)
        run_json = read_json(run_dir / "run.json")
        run_json["status"] = RunStatus.running.value
        write_json(run_dir / "run.json", run_json)

        async def fake_abort_run(_requested_run_id: str) -> bool:
            return False

        async def fake_is_active(_requested_run_id: str) -> bool:
            return False

        monkeypatch.setattr(
            "backend.app.api.routers.runs.get_run_executor",
            lambda: type("Executor", (), {"abort": staticmethod(fake_abort_run), "is_active": staticmethod(fake_is_active)})(),
        )
        resp = client.post(f"/api/runs/{run_id}/abort?output_dir={tmp_path}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "interrupted"
        updated = read_json(run_dir / "run.json")
        assert updated["status"] == RunStatus.interrupted.value


class TestReviewerSummaryAPI:
    def test_reviewer_summary_endpoint(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.get(f"/api/runs/{run_id}/reviewer-summary?output_dir={output_dir}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["total_proposals"] == 2
        assert data["reviewed"] == 0
        assert data["actionable_total_proposals"] == 2
        assert data["diagnostic_only_total_proposals"] == 0
        assert "confirmed_no_data" in data
        assert "rejected" in data


class TestRecomputeAPI:
    def test_recompute_endpoint(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        resp = client.post(f"/api/runs/{run_id}/summaries/recompute?output_dir={output_dir}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_summary"]["review_progress"]["total_proposals"] >= data["run_summary"]["actionable_review_progress"]["total_proposals"]
        assert "diagnostic_only_total_proposals" in data["run_summary"]
        assert "reviewer_summary" in data
        assert "run_summary" in data


class TestExportCandidatesAPI:
    def test_export_candidates_endpoint_empty_when_none_accepted(
        self, client, run_with_proposals
    ):
        output_dir, run_id = run_with_proposals
        resp = client.get(f"/api/runs/{run_id}/export-candidates?output_dir={output_dir}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0

    def test_export_candidates_after_accepting(self, client, run_with_proposals):
        output_dir, run_id = run_with_proposals
        # Accept one proposal
        proposals_resp = client.get(
            f"/api/runs/{run_id}/proposals?output_dir={output_dir}"
        )
        proposal_id = proposals_resp.json()["proposals"][0]["proposal_id"]
        client.post(
            f"/api/runs/{run_id}/proposals/{proposal_id}/decision?output_dir={output_dir}",
            json={"decision": "accepted"},
        )

        candidates_resp = client.get(
            f"/api/runs/{run_id}/export-candidates?output_dir={output_dir}"
        )
        assert candidates_resp.status_code == 200
        data = candidates_resp.json()
        assert data["count"] == 1
        assert data["candidates"][0]["proposal_id"] == proposal_id
