from __future__ import annotations

import pytest

from backend.app.extraction import ProposalRecord
from backend.app.proposal_semantics import (
    ANCHOR_FALLBACK,
    AMBIGUOUS_EVIDENCE,
    EXPLICITLY_NOT_REPORTED,
    INSUFFICIENT_EVIDENCE,
    PDF_UNMATCHED,
    RETRIEVAL_EMPTY,
    build_semantics,
    derive_review_bucket,
    semantics_from_extraction,
    validate_proposal_semantics,
)
from backend.app.review import _is_figure_derived, _is_reviewable_proposal, _proposal_warning_categories
from backend.app.schemas import EvidenceStatus, ProposalStatus, ReviewBucket


@pytest.mark.parametrize(
    ("proposal_status", "evidence_status", "expected_bucket"),
    [
        (ProposalStatus.value_proposed, EvidenceStatus.direct_strong, ReviewBucket.review),
        (ProposalStatus.value_proposed, EvidenceStatus.direct_weak, ReviewBucket.attention),
        (ProposalStatus.value_proposed, EvidenceStatus.inferred_strong, ReviewBucket.review),
        (ProposalStatus.no_data, EvidenceStatus.direct_strong, ReviewBucket.review),
        (ProposalStatus.no_data, EvidenceStatus.inferred_weak, ReviewBucket.attention),
        (ProposalStatus.unresolved, EvidenceStatus.no_evidence, ReviewBucket.attention),
        (ProposalStatus.not_applicable, EvidenceStatus.not_applicable, ReviewBucket.diagnostic),
        (ProposalStatus.not_attempted, EvidenceStatus.not_applicable, ReviewBucket.diagnostic),
        (ProposalStatus.error, EvidenceStatus.not_applicable, ReviewBucket.diagnostic),
    ],
)
def test_derive_review_bucket_contract_table(proposal_status, evidence_status, expected_bucket):
    assert derive_review_bucket(proposal_status, evidence_status, []) == expected_bucket


def test_contradictory_serialized_review_bucket_is_rejected():
    with pytest.raises(ValueError, match="review_bucket"):
        validate_proposal_semantics(
            ProposalStatus.error,
            EvidenceStatus.not_applicable,
            ReviewBucket.review,
            [],
        )


def test_no_data_direct_evidence_is_reviewable():
    semantics = build_semantics(
        ProposalStatus.no_data,
        EvidenceStatus.direct_strong,
        [EXPLICITLY_NOT_REPORTED],
    )
    assert semantics.review_bucket == ReviewBucket.review


def test_no_data_inferred_absence_needs_attention():
    semantics = build_semantics(
        ProposalStatus.no_data,
        EvidenceStatus.inferred_weak,
        [INSUFFICIENT_EVIDENCE],
    )
    assert semantics.review_bucket == ReviewBucket.attention


def test_retrieval_empty_is_unresolved_diagnostic_not_no_data():
    semantics = build_semantics(
        ProposalStatus.unresolved,
        EvidenceStatus.no_evidence,
        [RETRIEVAL_EMPTY],
    )
    assert semantics.proposal_status == ProposalStatus.unresolved
    assert semantics.review_bucket == ReviewBucket.diagnostic


def test_pdf_unmatched_unresolved_no_evidence_is_diagnostic():
    semantics = build_semantics(
        ProposalStatus.unresolved,
        EvidenceStatus.no_evidence,
        [PDF_UNMATCHED],
    )
    assert semantics.review_bucket == ReviewBucket.diagnostic


def test_unresolved_no_evidence_with_insufficient_evidence_needs_attention():
    semantics = build_semantics(
        ProposalStatus.unresolved,
        EvidenceStatus.no_evidence,
        [INSUFFICIENT_EVIDENCE],
    )
    assert semantics.review_bucket == ReviewBucket.attention


def test_unresolved_strong_evidence_records_ambiguity_reason():
    semantics = semantics_from_extraction(
        raw_state="unclear",
        evidence_status_hint=EvidenceStatus.inferred_strong.value,
        proposed_value=None,
        evidence_count=1,
        reason_codes=[],
    )

    assert semantics.proposal_status == ProposalStatus.unresolved
    assert semantics.evidence_status == EvidenceStatus.inferred_strong
    assert semantics.reason_codes == [AMBIGUOUS_EVIDENCE]
    assert semantics.review_bucket == ReviewBucket.attention


def test_anchor_fallback_is_reason_code_not_evidence_status():
    semantics = build_semantics(
        ProposalStatus.value_proposed,
        EvidenceStatus.direct_strong,
        [ANCHOR_FALLBACK],
    )
    assert semantics.evidence_status == EvidenceStatus.direct_strong
    assert semantics.review_bucket == ReviewBucket.attention


def test_unknown_reason_codes_are_allowed():
    semantics = build_semantics(
        ProposalStatus.value_proposed,
        EvidenceStatus.direct_strong,
        ["future_reason_code"],
    )
    assert semantics.reason_codes == ["future_reason_code"]


def test_proposal_record_serializes_canonical_fields_only():
    proposal = ProposalRecord(
        proposal_id="p1",
        run_id="r1",
        pdf_id="pdf1",
        row_id="row1",
        column_name="Assay",
        cell_id="cell1",
        proposal_status=ProposalStatus.value_proposed,
        evidence_status=EvidenceStatus.direct_strong,
        review_bucket=ReviewBucket.review,
        reason_codes=[],
        proposed_value="Visium",
        evidence_ids=[],
        warning_flags=[],
        created_at="2026-01-01T00:00:00Z",
    )
    payload = proposal.model_dump(mode="json")
    assert payload["proposal_status"] == "value_proposed"
    assert payload["evidence_status"] == "direct_strong"
    assert payload["review_bucket"] == "review"
    assert "state" not in payload
    assert "support" not in payload


def test_unresolved_no_evidence_target_cell_with_context_is_attention_reviewable():
    proposal = ProposalRecord(
        proposal_id="p-unresolved",
        run_id="r1",
        pdf_id="pdf1",
        row_id="row1",
        column_name="Integration site",
        cell_id="cell1",
        proposal_status=ProposalStatus.unresolved,
        evidence_status=EvidenceStatus.no_evidence,
        review_bucket=ReviewBucket.attention,
        reason_codes=[INSUFFICIENT_EVIDENCE],
        proposed_value=None,
        rationale="No usable evidence found in retrieved chunks.",
        evidence_ids=[],
        warning_flags=[],
        created_at="2026-01-01T00:00:00Z",
    )
    assert _is_reviewable_proposal(proposal) is True


def test_diagnostic_bucket_is_not_reviewable_even_with_context():
    proposal = ProposalRecord(
        proposal_id="p-diagnostic",
        run_id="r1",
        pdf_id="pdf1",
        row_id="row1",
        column_name="Integration site",
        cell_id="cell1",
        proposal_status=ProposalStatus.not_attempted,
        evidence_status=EvidenceStatus.not_applicable,
        review_bucket=ReviewBucket.diagnostic,
        reason_codes=["cell_not_targeted"],
        rationale="Selected cell was intentionally not attempted.",
        evidence_ids=[],
        warning_flags=[],
        created_at="2026-01-01T00:00:00Z",
    )
    assert _is_reviewable_proposal(proposal) is False


def test_pure_retrieval_empty_unresolved_stays_diagnostic_only():
    proposal = ProposalRecord(
        proposal_id="p-empty",
        run_id="r1",
        pdf_id="pdf1",
        row_id="row1",
        column_name="Integration site",
        cell_id="cell1",
        proposal_status=ProposalStatus.unresolved,
        evidence_status=EvidenceStatus.no_evidence,
        review_bucket=ReviewBucket.diagnostic,
        reason_codes=[RETRIEVAL_EMPTY],
        evidence_ids=[],
        warning_flags=[],
        created_at="2026-01-01T00:00:00Z",
    )
    assert _is_reviewable_proposal(proposal) is False


def test_figure_and_approximate_flags_are_not_warning_categories():
    proposal = ProposalRecord(
        proposal_id="p-figure",
        run_id="r1",
        pdf_id="pdf1",
        row_id="row1",
        column_name="Architecture",
        cell_id="cell1",
        proposal_status=ProposalStatus.value_proposed,
        evidence_status=EvidenceStatus.inferred_strong,
        review_bucket=ReviewBucket.attention,
        reason_codes=["approximate_anchor"],
        proposed_value="figure-derived value",
        evidence_ids=["ev1"],
        warning_flags=["figure_derived", "approximate_highlight"],
        figure_review_diagnostics={"figure_evidence_persisted": 1},
        created_at="2026-01-01T00:00:00Z",
    )
    assert _is_figure_derived(proposal) is True
    assert _proposal_warning_categories(proposal) == []
