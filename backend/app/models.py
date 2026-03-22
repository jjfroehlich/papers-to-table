from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, Enum):
    CREATED = "created"
    VALIDATING = "validating"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class MatchOutcome(str, Enum):
    MATCHED = "matched"
    AMBIGUOUS = "ambiguous"
    UNMATCHED = "unmatched"
    DUPLICATE_ROW_CONFLICT = "duplicate_row_conflict"


class ProposalState(str, Enum):
    FOUND = "found"
    INFERRED = "inferred"
    UNCLEAR = "unclear"
    BLOCKED = "blocked"
    ERROR = "error"
    SKIPPED = "skipped"


class SupportLabel(str, Enum):
    DIRECT = "Direct evidence"
    INFERRED = "Inferred from evidence"
    WEAK_TEXT = "Weak text evidence"
    FIGURE = "Figure-derived evidence"
    BLOCKED = "Blocked"
    UNCLEAR = "Unclear"
    ERROR = "Error"


class EvidenceSourceType(str, Enum):
    TEXT = "text"
    FIGURE = "figure"
    TABLE = "table"


class ReviewDecisionType(str, Enum):
    ACCEPT = "accept"
    ACCEPT_EDIT = "accept_with_edit"
    REJECT = "reject"
    NONE = "no_decision"


class WarningCategory(str, Enum):
    AMBIGUOUS_MATCH = "ambiguous_match"
    DUPLICATE_ROW_CONFLICT = "duplicate_row_conflict"
    WEAK_EVIDENCE = "weak_evidence"
    QUOTE_PAGE_FALLBACK = "quote_page_fallback"
    FIGURE_DERIVED = "figure_derived"
    NO_REVIEWED_VERIFIED_CELLS = "no_reviewed_verified_cells"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    UNSUPPORTED_WORKBOOK_FEATURES = "unsupported_workbook_features"
    OCR_UNAVAILABLE = "ocr_unavailable"


class ProviderLocality(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class BlockType(str, Enum):
    PARAGRAPH = "paragraph"
    SECTION = "section"
    CAPTION = "caption"
    TABLE = "table"
    FIGURE = "figure"


class HighlightBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ParsedBlock(BaseModel):
    block_id: str
    page: int
    block_type: BlockType
    text: str = ""
    source_text: str = ""
    retrieval_text: str = ""
    bbox: HighlightBox | None = None
    neighbors: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedPage(BaseModel):
    page_number: int
    width: float
    height: float
    image_path: str | None = None
    text: str = ""


class ParsedDocumentMetadata(BaseModel):
    title: str = ""
    authors: list[str] = Field(default_factory=list)
    publication_year: str = ""
    identifiers: dict[str, str] = Field(default_factory=dict)


class FigureRef(BaseModel):
    figure_id: str
    page: int
    caption: str = ""
    crop_path: str | None = None
    full_page_path: str | None = None
    nearby_text: str = ""


class ParsedDocument(BaseModel):
    pdf_id: str
    pdf_name: str
    parser_name: str
    parser_path: str
    ocr_used: bool = False
    metadata: ParsedDocumentMetadata
    pages: list[ParsedPage]
    blocks: list[ParsedBlock]
    figures: list[FigureRef] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class RunRecord(BaseModel):
    run_id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    status: RunStatus = RunStatus.CREATED
    warnings: list[WarningCategory] = Field(default_factory=list)
    provider_name: str = "stub-lmstudio"
    provider_model: str = "stub-model"
    provider_locality: ProviderLocality = ProviderLocality.LOCAL
    verify_mode: bool = True
    artifact_root: str
    config_path: str = ""
    message: str = ""


class SchemaColumn(BaseModel):
    column_name: str
    description: str
    data_type: str = "text"
    figure_likely: bool = False


class InputSummary(BaseModel):
    config_path: str = ""
    table_path: str
    schema_path: str | None = None
    pdf_dir: str
    output_dir: str
    row_count: int
    pdf_count: int
    target_columns: list[str]
    verify_mode: bool


class CellStatus(str, Enum):
    EMPTY = "empty"
    FILLED = "filled"
    PLACEHOLDER = "placeholder"
    SKIPPED = "skipped"


class CellEligibility(BaseModel):
    row_id: str
    column_name: str
    cell_id: str
    current_value: str
    status: CellStatus
    eligible: bool
    verify_target: bool = False
    reason: str = ""


class MatchRecord(BaseModel):
    pdf_id: str
    pdf_name: str
    outcome: MatchOutcome
    row_id: str | None = None
    row_index: int | None = None
    score: float = 0.0
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""
    warnings: list[WarningCategory] = Field(default_factory=list)


class StyleProfile(BaseModel):
    column_name: str
    field_type_guess: str
    expected_length: str
    tone: str
    detail_level: str
    value_shape: str
    unit_style: str
    format_notes: str
    example_risk: str = "low"


class RetrievalChunk(BaseModel):
    chunk_id: str
    pdf_id: str
    page: int
    block_type: BlockType
    retrieval_text: str
    display_text: str
    score: float
    bbox: HighlightBox | None = None
    neighbor_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    evidence_id: str
    proposal_id: str
    pdf_id: str
    source_type: EvidenceSourceType
    page: int
    page_width: float | None = None
    page_height: float | None = None
    quote_text: str = ""
    highlight: list[HighlightBox] = Field(default_factory=list)
    figure_ref: str | None = None
    caption_text: str = ""
    crop_path: str | None = None
    full_page_path: str | None = None
    anchor_confidence: float = 0.0


class ProposalRecord(BaseModel):
    proposal_id: str
    run_id: str
    pdf_id: str
    row_id: str
    row_index: int
    column_name: str
    column_order: int = 0
    cell_id: str
    source_mode: Literal["text", "vision"] = "text"
    proposal_state: ProposalState
    support_label: SupportLabel
    proposed_value: str | None = None
    rationale: str = ""
    calculation: str = ""
    needs_more_evidence: bool = False
    primary_evidence_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    current_value: str = ""
    is_verify_target: bool = False
    warning_flags: list[WarningCategory] = Field(default_factory=list)
    review_decision: ReviewDecisionType = ReviewDecisionType.NONE
    review_decision_id: str | None = None
    reviewed_value: str | None = None
    pdf_name: str = ""
    support_sort_bucket: int = 0


class ReviewDecisionRecord(BaseModel):
    review_decision_id: str
    proposal_id: str
    run_id: str
    cell_id: str
    decision: ReviewDecisionType
    edited_value: str | None = None
    decided_at: datetime = Field(default_factory=utc_now)
    reviewer_note: str = ""


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    pdfs_processed: int
    matched_pdfs: int
    unmatched_pdfs: int
    ambiguous_pdfs: int
    duplicate_conflict_pdfs: int = 0
    proposals_generated: int
    reviewed_proposals: int
    accepted_as_is: int
    accepted_with_edit: int
    rejected: int
    pending: int
    changed_cells_exported: int
    verify_mode: bool
    provider_name: str
    provider_model: str
    provider_locality: ProviderLocality
    warnings: list[str] = Field(default_factory=list)


class ReviewerColumnSummary(BaseModel):
    column_name: str
    reviewed_verified_cell_count: int
    accepted_as_is: int
    accepted_with_edit: int
    rejected: int
    evidence_coverage: float
    anchorable_evidence_rate: float


class ReviewerSummary(BaseModel):
    run_id: str
    proposals_generated: int
    reviewed_proposals: int
    accepted_as_is: int
    accepted_with_edit: int
    rejected: int
    pending: int
    changed_cells_exported: int
    matched_pdfs: int
    unmatched_pdfs: int
    ambiguous_pdfs: int
    verify_mode: bool
    provider_name: str
    provider_model: str
    provider_locality: ProviderLocality
    reviewed_verified_cell_count: int
    proposal_coverage: float
    evidence_coverage: float
    anchorable_evidence_rate: float
    per_column: list[ReviewerColumnSummary] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RuntimePaths(BaseModel):
    table_path: str
    schema_path: str | None = None
    pdf_dir: str
    output_dir: str


class ParserSettings(BaseModel):
    prefer_docling: bool = True
    sidecar_fixture_overrides: bool = True
    render_dpi: int = 72


class OCRSettings(BaseModel):
    enabled: bool = True
    command: str = "ocrmypdf"
    min_text_chars: int = 20


class MatchingSettings(BaseModel):
    title_threshold: float = 0.72
    ambiguous_margin: float = 0.08
    year_bonus: float = 0.1
    author_bonus: float = 0.1


class StyleProfileSettings(BaseModel):
    enabled: bool = True
    max_examples_analyzed: int = 5


class RetrievalSettings(BaseModel):
    top_k: int = 6
    neighbor_window: int = 1


class ProviderSettings(BaseModel):
    provider: Literal["stub", "lmstudio"] = "stub"
    base_url: str = "http://127.0.0.1:1234/v1"
    model: str = "stub-model"
    timeout_seconds: float = 15.0
    live_smoke_enabled: bool = False


class FigureFallbackSettings(BaseModel):
    enabled: bool = True
    trigger_keywords: list[str] = Field(default_factory=lambda: ["image", "figure", "microscopy", "diagram", "plot"])


class ReviewSettings(BaseModel):
    verify_mode: bool = True
    placeholder_values: list[str] = Field(default_factory=lambda: ["", " ", "NA", "N/A", "-"])


class ExportSettings(BaseModel):
    highlight_hex: str = "FFF3B0"
    changed_sheet_name: str = "Updated"


class AppConfig(BaseModel):
    paths: RuntimePaths
    parser: ParserSettings = Field(default_factory=ParserSettings)
    ocr: OCRSettings = Field(default_factory=OCRSettings)
    matching: MatchingSettings = Field(default_factory=MatchingSettings)
    style_profiles: StyleProfileSettings = Field(default_factory=StyleProfileSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    figure_fallback: FigureFallbackSettings = Field(default_factory=FigureFallbackSettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)


class CreateRunRequest(BaseModel):
    config_path: str | None = None
    config: AppConfig | None = None


class ReviewDecisionRequest(BaseModel):
    proposal_id: str
    decision: ReviewDecisionType
    edited_value: str | None = None
    reviewer_note: str = ""


class BulkAcceptRequest(BaseModel):
    proposal_ids: list[str]


class ProposalListResponse(BaseModel):
    proposals: list[ProposalRecord]
    total: int


class MatchListResponse(BaseModel):
    matches: list[MatchRecord]


class RunInspectionResponse(BaseModel):
    run: RunRecord
    summary: RunSummary
    reviewer_summary: ReviewerSummary
    input_summary: InputSummary
