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


class ErrorResponse(BaseModel):
    detail: str


class GenericPayload(BaseModel):
    data: dict[str, Any]
