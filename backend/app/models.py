from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


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
    DIRECT = "direct_evidence"
    INFERRED = "inferred_from_evidence"
    WEAK = "weak_evidence"
    FIGURE = "figure_based_evidence"


class EvidenceSourceType(str, Enum):
    TEXT = "text"
    TABLE = "table"
    FIGURE = "figure"


class ReviewDecisionType(str, Enum):
    ACCEPT = "accept"
    ACCEPT_EDITED = "accept_edited"
    REJECT = "reject"
    UNDECIDED = "undecided"


class WarningCategory(str, Enum):
    AMBIGUOUS_MATCH = "ambiguous_match"
    DUPLICATE_ROW_CONFLICT = "duplicate_row_conflict"
    WEAK_EVIDENCE = "weak_evidence"
    QUOTE_PAGE_NO_HIGHLIGHT = "quote_page_no_highlight"
    FIGURE_DERIVED = "figure_derived"
    NO_REVIEWED_VERIFIED_CELLS = "no_reviewed_verified_cells"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"


class ProviderLocality(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class ProposalRecord(BaseModel):
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
    primary_evidence_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class EvidenceRecord(BaseModel):
    evidence_id: str
    proposal_id: str
    pdf_id: str
    source_type: EvidenceSourceType
    page: int | None = None
    quote_text: str | None = None
    highlight: dict[str, Any] | None = None
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
    decision: ReviewDecisionType
    edited_value: str | None = None
    reviewer_note: str | None = None
    decided_at: str


class RunSummary(BaseModel):
    run_id: str
    run_status: RunStatus
    provider_locality: ProviderLocality = ProviderLocality.LOCAL
    provider_name: str = "lm_studio"
    model_name: str = "unconfigured"
    pdfs_processed: int = 0
    proposals_generated: int = 0
    reviewed_proposals: int = 0
    accepted_as_is: int = 0
    accepted_with_edit: int = 0
    rejected: int = 0
    pending: int = 0
    changed_cells_exported: int = 0
    verify_mode: bool = False


class ReviewerSummary(BaseModel):
    run_id: str
    proposals_generated: int = 0
    reviewed_proposals: int = 0
    accepted_as_is: int = 0
    accepted_with_edit: int = 0
    rejected: int = 0
    pending: int = 0
    changed_cells_exported: int = 0
    verify_mode: bool = False
    provider_locality: ProviderLocality = ProviderLocality.LOCAL
    provider_name: str = "lm_studio"
    model_name: str = "unconfigured"


class RunRecord(BaseModel):
    run_id: str
    status: RunStatus
    created_at: str
    updated_at: str
    operator_state: str
    error: str | None = None
    artifact_dir: str


class InputSummary(BaseModel):
    table_path: str
    schema_path: str | None = None
    pdf_dir: str
    pdf_count: int
    row_count: int
    target_column_count: int
    verify_mode: bool
    eligible_missing_cells: int
    eligible_filled_cells: int


class CreateRunRequest(BaseModel):
    config_path: str


class CreateRunResponse(BaseModel):
    run_id: str
    status: RunStatus


class ConfigPaths(BaseModel):
    table_path: str
    schema_path: str | None = None
    pdf_dir: str
    output_dir: str


class ParserSettings(BaseModel):
    parser_name: str = "docling"


class OcrSettings(BaseModel):
    enabled: bool = True
    engine: str = "ocrmypdf"


class MatchingSettings(BaseModel):
    enabled: bool = True


class StyleProfileSettings(BaseModel):
    enabled: bool = True


class RetrievalSettings(BaseModel):
    top_k: int = 6
    include_captions: bool = True
    include_tables: bool = True
    neighbor_window: int = 1
    reranker_enabled: bool = False
    hyde_enabled: bool = False
    query_expansion_enabled: bool = False


class ProviderSettings(BaseModel):
    provider_name: str = "lm_studio"
    model_name: str = "unconfigured"
    base_url: str = "http://localhost:1234/v1"
    locality: ProviderLocality = ProviderLocality.LOCAL


class FigureFallbackSettings(BaseModel):
    enabled: bool = True


class ReviewSettings(BaseModel):
    verify_mode: bool = True
    placeholder_values: list[str] = Field(default_factory=lambda: ["n/a", "na", "-"])


class ExportSettings(BaseModel):
    highlight_color: str = "FFF59D"


class RunConfig(BaseModel):
    paths: ConfigPaths
    parser: ParserSettings = Field(default_factory=ParserSettings)
    ocr: OcrSettings = Field(default_factory=OcrSettings)
    matching: MatchingSettings = Field(default_factory=MatchingSettings)
    style_profiles: StyleProfileSettings = Field(default_factory=StyleProfileSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    provider: ProviderSettings = Field(default_factory=ProviderSettings)
    figure_fallback: FigureFallbackSettings = Field(default_factory=FigureFallbackSettings)
    review: ReviewSettings = Field(default_factory=ReviewSettings)
    export: ExportSettings = Field(default_factory=ExportSettings)


class ParsedMetadata(BaseModel):
    title: str | None = None
    authors: list[str] = Field(default_factory=list)
    publication_year: int | None = None
    identifiers: dict[str, str] = Field(default_factory=dict)


class ParsedBlock(BaseModel):
    block_id: str
    block_type: str
    page: int
    text: str = ""
    normalized_text: str = ""
    reading_order: int
    bbox: dict[str, float] | None = None
    source_span: dict[str, int] | None = None
    provenance: dict[str, str] = Field(default_factory=dict)


class ParsedPage(BaseModel):
    page_number: int
    width: float
    height: float
    full_page_path: str | None = None
    text_length: int = 0
    has_text: bool = False


class ParsedDocument(BaseModel):
    run_id: str
    pdf_id: str
    source_pdf_path: str
    parser_name: str
    ocr_used: bool = False
    metadata: ParsedMetadata
    pages: list[ParsedPage] = Field(default_factory=list)
    blocks: list[ParsedBlock] = Field(default_factory=list)
    source_text: str = ""
    normalized_text: str = ""
    figure_caption_links: list[dict[str, str]] = Field(default_factory=list)
    table_regions: list[dict[str, float]] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
