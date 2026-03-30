"""Tests for domain enums and Pydantic schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas import (
    Evidence,
    EvidenceSourceType,
    MatchOutcome,
    Proposal,
    ProposalState,
    ProviderLocality,
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewResolutionReason,
    ReviewerSummary,
    RunStatus,
    RunSummary,
    RunWarning,
    SupportLabel,
    WarningCategory,
)


class TestRunStatus:
    def test_all_values(self):
        assert set(RunStatus) == {
            RunStatus.created,
            RunStatus.validating,
            RunStatus.running,
            RunStatus.completed,
            RunStatus.completed_with_warnings,
            RunStatus.failed,
            RunStatus.interrupted,
        }

    def test_string_coercion(self):
        assert RunStatus("completed") == RunStatus.completed


class TestMatchOutcome:
    def test_all_values(self):
        values = {o.value for o in MatchOutcome}
        assert "matched" in values
        assert "ambiguous" in values
        assert "unmatched" in values
        assert "duplicate_row_conflict" in values


class TestProposalState:
    def test_all_values(self):
        values = {s.value for s in ProposalState}
        assert {"found", "inferred", "unclear", "blocked", "error", "skipped"} == values


class TestSupportLabel:
    def test_all_values(self):
        values = {s.value for s in SupportLabel}
        assert "direct_evidence" in values
        assert "inferred_from_evidence" in values
        assert "weak_evidence" in values
        assert "blocked" in values
        assert "error" in values


class TestEvidenceSourceType:
    def test_all_values(self):
        values = {e.value for e in EvidenceSourceType}
        expected = {
            "direct_quote",
            "inferred_reasoning",
            "calculation",
            "approximate_highlight",
            "quote_plus_page",
            "figure_based_evidence",
        }
        assert values == expected


class TestReviewDecision:
    def test_all_values(self):
        values = {d.value for d in ReviewDecision}
        assert {"accepted", "accepted_with_edit", "confirmed_no_data", "rejected"} == values


class TestReviewResolutionReason:
    def test_has_key_reasons(self):
        values = {r.value for r in ReviewResolutionReason}
        assert "accepted_as_proposed" in values
        assert "confirmed_no_data_in_paper" in values
        assert "rejected_incorrect" in values
        assert "manually_entered" in values


class TestProviderLocality:
    def test_values(self):
        assert set(ProviderLocality) == {ProviderLocality.local, ProviderLocality.cloud}


class TestWarningCategory:
    def test_all_values(self):
        values = {w.value for w in WarningCategory}
        assert "unmatched_pdf" in values
        assert "ambiguous_match" in values
        assert "provider_unreachable" in values


class TestProposalModel:
    def test_valid_proposal(self):
        from datetime import datetime, timezone
        p = Proposal(
            proposal_id="prop_run_abc_cell_xyz_123",
            run_id="run_20240315_143022_abc123",
            cell_id="cell_abc123def456",
            row_id="row_abc123def456",
            column_name="Abstract",
            pdf_id="pdf_paper_1_abc123def456",
            state=ProposalState.found,
            support=SupportLabel.direct_evidence,
            proposed_value="Some value",
            evidence_ids=["ev_p1"],
            warning_flags=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert p.proposal_id.startswith("prop_")
        assert p.proposed_value == "Some value"

    def test_proposal_optional_fields(self):
        from datetime import datetime, timezone
        p = Proposal(
            proposal_id="prop_1",
            run_id="run_1",
            cell_id="cell_1",
            row_id="row_1",
            column_name="Col",
            pdf_id="pdf_1",
            state=ProposalState.blocked,
            support=SupportLabel.blocked,
            evidence_ids=[],
            warning_flags=[],
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert p.proposed_value is None
        assert p.rationale is None


class TestEvidenceModel:
    def test_valid_evidence(self):
        from datetime import datetime, timezone
        e = Evidence(
            evidence_id="ev_prop_1_abcdef12",
            run_id="run_1",
            proposal_id="prop_1",
            source_type=EvidenceSourceType.direct_quote,
            raw_text="The study found that...",
            page_number=3,
            is_primary=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        assert e.source_type == EvidenceSourceType.direct_quote
        assert e.is_primary is True


class TestReviewDecisionRecord:
    def test_valid_review_decision(self):
        from datetime import datetime, timezone
        r = ReviewDecisionRecord(
            review_decision_id="rev_prop_1_abcdef12",
            run_id="run_1",
            proposal_id="prop_1",
            cell_id="cell_1",
            decision=ReviewDecision.accepted,
            resolution_reason=ReviewResolutionReason.accepted_as_proposed,
            decided_at=datetime.now(timezone.utc).isoformat(),
        )
        assert r.decision == ReviewDecision.accepted


class TestRunSummary:
    def test_minimal_run_summary(self):
        from datetime import datetime, timezone
        s = RunSummary(
            run_id="run_1",
            status=RunStatus.completed,
            output_dir="./runs",
            verify_mode=False,
            total_rows=10,
            eligible_cells=50,
            proposals_generated=0,
            proposals_reviewed=0,
            warnings=[],
        )
        assert s.status == RunStatus.completed


class TestReviewerSummary:
    def test_valid_reviewer_summary(self):
        from datetime import datetime, timezone
        s = ReviewerSummary(
            run_id="run_1",
            total_proposals=10,
            accepted=5,
            accepted_with_edit=2,
            confirmed_no_data=1,
            rejected=1,
            pending=1,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        assert s.total_proposals == 10
