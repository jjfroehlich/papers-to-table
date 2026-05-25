"""Tests for domain enums and Pydantic schemas."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.schemas import (
    Evidence,
    EvidenceStatus,
    EvidenceSourceType,
    MatchOutcome,
    Proposal,
    ProposalStatus,
    ProviderLocality,
    ReviewDecision,
    ReviewDecisionRecord,
    ReviewBucket,
    ReviewResolutionReason,
    ReviewerSummary,
    RunStatus,
    RunSummary,
    RunWarning,
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


class TestProposalStatus:
    def test_all_values(self):
        values = {s.value for s in ProposalStatus}
        assert {"value_proposed", "no_data", "unresolved", "not_applicable", "not_attempted", "error"} == values


class TestEvidenceStatus:
    def test_all_values(self):
        values = {s.value for s in EvidenceStatus}
        assert "direct_strong" in values
        assert "direct_weak" in values
        assert "inferred_strong" in values
        assert "inferred_weak" in values
        assert "no_evidence" in values
        assert "not_applicable" in values


class TestReviewBucket:
    def test_all_values(self):
        values = {s.value for s in ReviewBucket}
        assert {"review", "attention", "diagnostic"} == values


class TestEvidenceSourceType:
    def test_all_values(self):
        values = {e.value for e in EvidenceSourceType}
        expected = {
            "direct_quote",
            "inferred_reasoning",
            "calculation",
            "approximate_highlight",
            "quote_plus_page",
            "caption_grounded_figure_evidence",
            "visual_interpretation_figure_evidence",
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
        assert "model_unavailable" in values
        assert "structured_mode_capability_mismatch" in values


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
            proposal_status=ProposalStatus.value_proposed,
            evidence_status=EvidenceStatus.direct_strong,
            review_bucket=ReviewBucket.review,
            reason_codes=[],
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
            proposal_status=ProposalStatus.unresolved,
            evidence_status=EvidenceStatus.no_evidence,
            review_bucket=ReviewBucket.diagnostic,
            reason_codes=["retrieval_empty"],
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
