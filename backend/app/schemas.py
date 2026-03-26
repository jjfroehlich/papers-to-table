from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RunStatus(StrEnum):
    CREATED = "created"
    VALIDATING = "validating"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class OperatorRunStatus(StrEnum):
    READY = "ready"
    VALIDATING = "validating"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed with warnings"
    FAILED = "failed"


class MatchOutcome(StrEnum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"
    DUPLICATE_ROW_CONFLICT = "duplicate_row_conflict"


class ProposalState(StrEnum):
    FOUND = "found"
    INFERRED = "inferred"
    UNCLEAR = "unclear"
    BLOCKED = "blocked"
    ERROR = "error"
    SKIPPED = "skipped"


class SupportLabel(StrEnum):
    DIRECT_EVIDENCE = "direct_evidence"
    INFERRED_FROM_EVIDENCE = "inferred_from_evidence"
    WEAK_EVIDENCE = "weak_evidence"
    FIGURE_BASED_EVIDENCE = "figure_based_evidence"


class EvidenceSourceType(StrEnum):
    TEXT_QUOTE = "text_quote"
    TEXT_HIGHLIGHT = "text_highlight"
    FIGURE_CROP = "figure_crop"
    CAPTION = "caption"
    FULL_PAGE = "full_page"


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    ACCEPT_WITH_EDIT = "accept_with_edit"
    REJECT = "reject"
    UNDECIDED = "undecided"


class WarningStatusCategory(StrEnum):
    AMBIGUOUS_MATCH = "ambiguous_match"
    DUPLICATE_ROW_CONFLICT = "duplicate_row_conflict"
    WEAK_EVIDENCE = "weak_evidence"
    QUOTE_PAGE_FALLBACK = "quote_page_fallback"
    FIGURE_DERIVED = "figure_derived"
    NO_REVIEWED_VERIFIED_CELLS = "no_reviewed_verified_cells"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"


class ProviderLocality(StrEnum):
    LOCAL = "local"
    CLOUD = "cloud"


class RunProgress(BaseModel):
    stage: str | None = None
    item: str | None = None


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    operator_status: OperatorRunStatus
    config_path: str
    artifact_dir: str
    message: str | None = None
    progress: RunProgress = Field(default_factory=RunProgress)
    created_at: datetime
    updated_at: datetime


class RunCreateRequest(BaseModel):
    config_path: str


class RunCreateResponse(BaseModel):
    run_id: str
    status: RunStatus
    operator_status: OperatorRunStatus


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    operator_status: OperatorRunStatus
    message: str | None = None
    progress: RunProgress
    config_path: str
    artifact_dir: str
    verify_mode: bool
    table_path: str | None = None
    schema_path: str | None = None
    pdf_dir: str | None = None
    output_dir: str | None = None
    target_columns: list[str] = Field(default_factory=list)
    provider_name: str | None = None
    model_name: str | None = None
    provider_locality: ProviderLocality = ProviderLocality.LOCAL


class InputSummary(BaseModel):
    table_path: str
    schema_path: str | None
    pdf_dir: str
    output_dir: str
    verify_mode: bool
    target_columns: list[str]
    row_count: int
    eligible_missing_cells: int
    eligible_filled_cells: int
    ineligible_cells: int
    placeholders_treated_as_empty: list[str] = Field(default_factory=list)


class ProposalRecord(BaseModel):
    proposal_id: str
    run_id: str
    pdf_id: str
    row_id: str
    column_name: str
    cell_id: str
    source_mode: str = "text"
    proposal_state: ProposalState
    support_label: SupportLabel
    proposed_value: str | None = None
    rationale: str | None = None
    calculation: str | None = None
    needs_more_evidence: bool = False
    primary_evidence_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    status_flags: list[WarningStatusCategory] = Field(default_factory=list)


class EvidenceHighlight(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class EvidenceRecord(BaseModel):
    evidence_id: str
    proposal_id: str
    pdf_id: str
    source_type: EvidenceSourceType
    page: int | None = None
    quote_text: str | None = None
    highlight: EvidenceHighlight | None = None
    figure_ref: str | None = None
    caption_text: str | None = None
    crop_path: str | None = None
    full_page_path: str | None = None
    anchor_confidence: float | None = None


class ReviewDecisionRecord(BaseModel):
    decision_id: str
    run_id: str
    proposal_id: str
    cell_id: str
    decision: ReviewDecision
    edited_value: str | None = None
    decided_at: datetime


class SummaryCounts(BaseModel):
    proposals_generated: int = 0
    reviewed_proposals: int = 0
    accepted_as_is: int = 0
    accepted_with_edit: int = 0
    rejected: int = 0
    pending: int = 0
    changed_cells_exported: int = 0


class ReviewerSummary(BaseModel):
    run_id: str
    counts: SummaryCounts = Field(default_factory=SummaryCounts)
    verify_mode: bool = True
    provider_locality: ProviderLocality = ProviderLocality.LOCAL


class ErrorResponse(BaseModel):
    detail: str


class GenericPayload(BaseModel):
    data: dict[str, Any]


# ---------------------------------------------------------------------------
# Batch 4 — Review backend schemas
# ---------------------------------------------------------------------------


class RecordDecisionRequest(BaseModel):
    decision: ReviewDecision
    edited_value: str | None = None


class BulkAcceptRequest(BaseModel):
    """Filter that scopes bulk-accept to the currently visible subset."""
    row_id: str | None = None
    column_name: str | None = None
    pdf_id: str | None = None


class ProposalProgress(BaseModel):
    total: int = 0
    accepted_as_is: int = 0
    accepted_with_edit: int = 0
    rejected: int = 0
    pending: int = 0


class ProposalListItem(BaseModel):
    proposal_id: str
    run_id: str
    pdf_id: str
    row_id: str
    column_name: str
    cell_id: str
    source_mode: str
    proposal_state: ProposalState
    support_label: SupportLabel
    proposed_value: str | None = None
    status_flags: list[WarningStatusCategory] = Field(default_factory=list)
    latest_decision: ReviewDecision = ReviewDecision.UNDECIDED


class ProposalDetail(BaseModel):
    proposal_id: str
    run_id: str
    pdf_id: str
    row_id: str
    column_name: str
    cell_id: str
    source_mode: str
    proposal_state: ProposalState
    support_label: SupportLabel
    proposed_value: str | None = None
    rationale: str | None = None
    calculation: str | None = None
    needs_more_evidence: bool = False
    status_flags: list[WarningStatusCategory] = Field(default_factory=list)
    row_context: dict[str, Any] = Field(default_factory=dict)
    column_definition: dict[str, Any] = Field(default_factory=dict)
    current_cell_value: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    latest_decision: ReviewDecision = ReviewDecision.UNDECIDED
    latest_decision_record: dict[str, Any] | None = None


class ExportCandidate(BaseModel):
    proposal_id: str
    run_id: str
    pdf_id: str
    row_id: str
    column_name: str
    cell_id: str
    accepted_value: str | None = None
    decision: ReviewDecision


def parse_status_flags(raw_flags: list[str]) -> list[WarningStatusCategory]:
    """Safely parse a list of raw flag strings into WarningStatusCategory values, ignoring unknowns."""
    result: list[WarningStatusCategory] = []
    for f in raw_flags:
        try:
            result.append(WarningStatusCategory(f))
        except ValueError:
            pass
    return result


class RunSummaryFull(BaseModel):
    run_id: str
    status: RunStatus
    operator_status: OperatorRunStatus
    message: str | None = None
    progress: RunProgress = Field(default_factory=RunProgress)
    config_path: str = ""
    artifact_dir: str = ""
    verify_mode: bool = True
    table_path: str | None = None
    schema_path: str | None = None
    pdf_dir: str | None = None
    output_dir: str | None = None
    target_columns: list[str] = Field(default_factory=list)
    provider_name: str | None = None
    model_name: str | None = None
    provider_locality: ProviderLocality = ProviderLocality.LOCAL
    counts: SummaryCounts = Field(default_factory=SummaryCounts)
    pdfs_processed: int = 0
    pdfs_matched: int = 0
    pdfs_unmatched: int = 0
    pdfs_ambiguous: int = 0
    run_status_flags: list[WarningStatusCategory] = Field(default_factory=list)
