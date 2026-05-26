from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .schemas import EvidenceStatus, ProposalStatus, ReviewBucket


EXPLICITLY_NOT_REPORTED = "explicitly_not_reported"
NOT_REPORTED = "not_reported"
RETRIEVAL_EMPTY = "retrieval_empty"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
AMBIGUOUS_EVIDENCE = "ambiguous_evidence"
CONFLICTING_EVIDENCE = "conflicting_evidence"
ANCHOR_FALLBACK = "anchor_fallback"
APPROXIMATE_ANCHOR = "approximate_anchor"
CALCULATION = "calculation"
SCHEMA_NOT_APPLICABLE = "schema_not_applicable"
CELL_NOT_TARGETED = "cell_not_targeted"
COLUMN_EXCLUDED = "column_excluded"
PDF_UNMATCHED = "pdf_unmatched"
ROW_UNMATCHED = "row_unmatched"
DUPLICATE_ROW_CONFLICT = "duplicate_row_conflict"
PROVIDER_ERROR = "provider_error"
PARSER_ERROR = "parser_error"
INVALID_MODEL_OUTPUT = "invalid_model_output"

KNOWN_REASON_CODES = {
    EXPLICITLY_NOT_REPORTED,
    NOT_REPORTED,
    RETRIEVAL_EMPTY,
    INSUFFICIENT_EVIDENCE,
    AMBIGUOUS_EVIDENCE,
    CONFLICTING_EVIDENCE,
    ANCHOR_FALLBACK,
    APPROXIMATE_ANCHOR,
    CALCULATION,
    SCHEMA_NOT_APPLICABLE,
    CELL_NOT_TARGETED,
    COLUMN_EXCLUDED,
    PDF_UNMATCHED,
    ROW_UNMATCHED,
    DUPLICATE_ROW_CONFLICT,
    PROVIDER_ERROR,
    PARSER_ERROR,
    INVALID_MODEL_OUTPUT,
}

ATTENTION_REASON_CODES = {
    ANCHOR_FALLBACK,
    APPROXIMATE_ANCHOR,
    INSUFFICIENT_EVIDENCE,
    AMBIGUOUS_EVIDENCE,
    CONFLICTING_EVIDENCE,
}

DIAGNOSTIC_NO_EVIDENCE_REASON_CODES = {
    RETRIEVAL_EMPTY,
    PDF_UNMATCHED,
    ROW_UNMATCHED,
    DUPLICATE_ROW_CONFLICT,
}


@dataclass(frozen=True)
class ProposalSemantics:
    proposal_status: ProposalStatus
    evidence_status: EvidenceStatus
    review_bucket: ReviewBucket
    reason_codes: list[str]


def normalize_reason_codes(reason_codes: Iterable[str] | None) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for code in reason_codes or []:
        text = str(code or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def derive_review_bucket(
    proposal_status: ProposalStatus | str,
    evidence_status: EvidenceStatus | str,
    reason_codes: Iterable[str] | None = None,
) -> ReviewBucket:
    proposal_status = ProposalStatus(proposal_status)
    evidence_status = EvidenceStatus(evidence_status)
    reasons = set(normalize_reason_codes(reason_codes))

    if proposal_status in {
        ProposalStatus.error,
        ProposalStatus.not_attempted,
        ProposalStatus.not_applicable,
    }:
        return ReviewBucket.diagnostic
    if (
        proposal_status == ProposalStatus.unresolved
        and evidence_status == EvidenceStatus.no_evidence
        and reasons
        and reasons <= DIAGNOSTIC_NO_EVIDENCE_REASON_CODES
    ):
        return ReviewBucket.diagnostic
    if evidence_status in {EvidenceStatus.direct_weak, EvidenceStatus.inferred_weak}:
        return ReviewBucket.attention
    if reasons & ATTENTION_REASON_CODES:
        return ReviewBucket.attention
    if proposal_status == ProposalStatus.no_data and evidence_status in {
        EvidenceStatus.direct_weak,
        EvidenceStatus.inferred_weak,
        EvidenceStatus.no_evidence,
    }:
        return ReviewBucket.attention
    if proposal_status == ProposalStatus.unresolved:
        return ReviewBucket.attention
    return ReviewBucket.review


def validate_proposal_semantics(
    proposal_status: ProposalStatus | str,
    evidence_status: EvidenceStatus | str,
    review_bucket: ReviewBucket | str,
    reason_codes: Iterable[str] | None = None,
) -> ProposalSemantics:
    proposal_status = ProposalStatus(proposal_status)
    evidence_status = EvidenceStatus(evidence_status)
    review_bucket = ReviewBucket(review_bucket)
    reasons = normalize_reason_codes(reason_codes)

    _validate_combination(proposal_status, evidence_status, reasons)
    derived = derive_review_bucket(proposal_status, evidence_status, reasons)
    if review_bucket != derived:
        raise ValueError(
            "review_bucket must match derived proposal semantics: "
            f"serialized={review_bucket.value!r}, derived={derived.value!r}"
        )
    return ProposalSemantics(proposal_status, evidence_status, derived, reasons)


def build_semantics(
    proposal_status: ProposalStatus | str,
    evidence_status: EvidenceStatus | str,
    reason_codes: Iterable[str] | None = None,
) -> ProposalSemantics:
    proposal_status = ProposalStatus(proposal_status)
    evidence_status = EvidenceStatus(evidence_status)
    reasons = normalize_reason_codes(reason_codes)
    bucket = derive_review_bucket(proposal_status, evidence_status, reasons)
    return validate_proposal_semantics(proposal_status, evidence_status, bucket, reasons)


def _validate_combination(
    proposal_status: ProposalStatus,
    evidence_status: EvidenceStatus,
    reason_codes: list[str],
) -> None:
    if proposal_status in {ProposalStatus.error, ProposalStatus.not_attempted}:
        if evidence_status != EvidenceStatus.not_applicable:
            raise ValueError(f"{proposal_status.value} requires evidence_status=not_applicable")
    if proposal_status == ProposalStatus.not_applicable:
        if evidence_status != EvidenceStatus.not_applicable:
            raise ValueError("not_applicable requires evidence_status=not_applicable")
    if proposal_status in {
        ProposalStatus.value_proposed,
        ProposalStatus.no_data,
        ProposalStatus.unresolved,
    } and evidence_status == EvidenceStatus.not_applicable:
        raise ValueError(f"{proposal_status.value} cannot use evidence_status=not_applicable")
    if proposal_status == ProposalStatus.value_proposed and evidence_status == EvidenceStatus.no_evidence:
        if INSUFFICIENT_EVIDENCE not in reason_codes:
            raise ValueError("value_proposed with no_evidence requires insufficient_evidence")
    if proposal_status == ProposalStatus.unresolved and evidence_status in {
        EvidenceStatus.direct_strong,
        EvidenceStatus.inferred_strong,
    }:
        if not ({CONFLICTING_EVIDENCE, AMBIGUOUS_EVIDENCE} & set(reason_codes)):
            raise ValueError("unresolved with strong evidence requires ambiguity/conflict reason")


def semantics_from_extraction(
    *,
    raw_state: str,
    evidence_status_hint: str,
    proposed_value: object | None,
    evidence_count: int,
    reason_codes: Iterable[str] | None = None,
) -> ProposalSemantics:
    reasons = normalize_reason_codes(reason_codes)
    raw_state = str(raw_state or "unclear").strip().lower()
    evidence_status = EvidenceStatus(evidence_status_hint)

    if raw_state == "error":
        return build_semantics(ProposalStatus.error, EvidenceStatus.not_applicable, reasons or [PROVIDER_ERROR])
    if proposed_value not in (None, "") and raw_state in {"found", "inferred"}:
        return build_semantics(ProposalStatus.value_proposed, evidence_status, reasons)
    if RETRIEVAL_EMPTY in reasons and evidence_count == 0:
        return build_semantics(ProposalStatus.unresolved, EvidenceStatus.no_evidence, reasons)
    if evidence_count == 0:
        return build_semantics(ProposalStatus.unresolved, EvidenceStatus.no_evidence, reasons or [INSUFFICIENT_EVIDENCE])
    if evidence_status in {EvidenceStatus.direct_strong, EvidenceStatus.inferred_strong} and not (
        {CONFLICTING_EVIDENCE, AMBIGUOUS_EVIDENCE} & set(reasons)
    ):
        reasons.append(AMBIGUOUS_EVIDENCE)
    return build_semantics(ProposalStatus.unresolved, evidence_status, reasons or [INSUFFICIENT_EVIDENCE])
