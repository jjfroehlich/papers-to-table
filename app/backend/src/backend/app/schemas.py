from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class RunStatus(str, Enum):
    created = "created"
    validating = "validating"
    running = "running"
    completed = "completed"
    completed_with_warnings = "completed_with_warnings"
    failed = "failed"
    interrupted = "interrupted"


class MatchOutcome(str, Enum):
    matched = "matched"
    ambiguous = "ambiguous"
    unmatched = "unmatched"
    duplicate_row_conflict = "duplicate_row_conflict"


class ProposalStatus(str, Enum):
    value_proposed = "value_proposed"
    no_data = "no_data"
    unresolved = "unresolved"
    not_applicable = "not_applicable"
    not_attempted = "not_attempted"
    error = "error"


class EvidenceStatus(str, Enum):
    direct_strong = "direct_strong"
    direct_weak = "direct_weak"
    inferred_strong = "inferred_strong"
    inferred_weak = "inferred_weak"
    no_evidence = "no_evidence"
    not_applicable = "not_applicable"


class ReviewBucket(str, Enum):
    review = "review"
    attention = "attention"
    diagnostic = "diagnostic"


class EvidenceSourceType(str, Enum):
    direct_quote = "direct_quote"
    inferred_reasoning = "inferred_reasoning"
    calculation = "calculation"
    approximate_highlight = "approximate_highlight"
    quote_plus_page = "quote_plus_page"
    caption_grounded_figure_evidence = "caption_grounded_figure_evidence"
    visual_interpretation_figure_evidence = "visual_interpretation_figure_evidence"


class SchemaFieldType(str, Enum):
    text = "text"
    number = "number"
    categorical = "categorical"
    boolean = "boolean"


class NumericValueForm(str, Enum):
    exact = "exact"
    range = "range"
    approximate = "approximate"


class ReviewDecision(str, Enum):
    accepted = "accepted"
    accepted_with_edit = "accepted_with_edit"
    confirmed_no_data = "confirmed_no_data"
    rejected = "rejected"


class DecisionSource(str, Enum):
    human_individual = "human_individual"
    human_bulk_accept = "human_bulk_accept"
    human_bulk_selection = "human_bulk_selection"
    automation_accept_all = "automation_accept_all"

    @classmethod
    def _missing_(cls, value):
        if value == "human_reviewer":
            return cls.human_individual
        return None


class ReviewResolutionReason(str, Enum):
    accepted_as_proposed = "accepted_as_proposed"
    accepted_with_edit = "accepted_with_edit"
    confirmed_no_data_in_paper = "confirmed_no_data_in_paper"
    rejected_incorrect = "rejected_incorrect"
    rejected_low_confidence = "rejected_low_confidence"
    rejected_out_of_scope = "rejected_out_of_scope"
    manually_entered = "manually_entered"


class ProviderLocality(str, Enum):
    local = "local"
    cloud = "cloud"


class WarningCategory(str, Enum):
    # Match-outcome warnings
    unmatched_pdf = "unmatched_pdf"
    ambiguous_match = "ambiguous_match"
    duplicate_row_conflict = "duplicate_row_conflict"
    # Schema/data warnings
    missing_required_column = "missing_required_column"
    # Evidence-quality warnings
    low_confidence_proposal = "low_confidence_proposal"
    fallback_evidence_used = "fallback_evidence_used"  # quote+page without highlight
    figure_derived_evidence = "figure_derived_evidence"
    weak_evidence = "weak_evidence"
    # Provider/readiness warnings
    provider_unreachable = "provider_unreachable"
    model_unavailable = "model_unavailable"
    structured_mode_capability_mismatch = "structured_mode_capability_mismatch"
    provider_disabled = "provider_disabled"
    provider_degraded = "provider_degraded"
    readiness_failure = "readiness_failure"
    # Run-outcome warnings
    partial_extraction = "partial_extraction"
    completed_with_warnings = "completed_with_warnings"
    no_reviewed_cells = "no_reviewed_cells"  # run finished but no cells have been confirmed


class Proposal(BaseModel):
    proposal_id: str
    run_id: str
    cell_id: str
    row_id: str
    column_name: str
    pdf_id: str
    proposal_status: ProposalStatus
    evidence_status: EvidenceStatus
    review_bucket: ReviewBucket
    reason_codes: list[str]
    proposed_value: Optional[str] = None
    rationale: Optional[str] = None
    calculation: Optional[str] = None
    evidence_ids: list[str]
    warning_flags: list[str]
    created_at: str


class Evidence(BaseModel):
    evidence_id: str
    run_id: str
    proposal_id: str
    source_type: EvidenceSourceType
    raw_text: Optional[str] = None
    page_number: Optional[int] = None
    bbox: Optional[list[float]] = None  # x0, y0, x1, y1
    figure_id: Optional[str] = None
    caption: Optional[str] = None
    reasoning: Optional[str] = None
    is_primary: bool
    created_at: str


class ReviewDecisionRecord(BaseModel):
    review_decision_id: str
    run_id: str
    proposal_id: str
    cell_id: str
    decision: ReviewDecision
    decision_source: DecisionSource = DecisionSource.human_individual
    resolution_reason: Optional[ReviewResolutionReason] = None
    edited_value: Optional[str] = None
    reviewer_note: Optional[str] = None
    decided_at: str


class RunWarning(BaseModel):
    category: WarningCategory
    message: str
    context: Optional[dict] = None


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    config_path: Optional[str] = None
    table_path: Optional[str] = None
    schema_path: Optional[str] = None
    pdf_dir: Optional[str] = None
    output_dir: str
    verify_mode: bool
    eval_mode: bool = False
    run_mode: str = "normal"
    provider_token: Optional[str] = None
    provider_locality: Optional[ProviderLocality] = None
    provider_mode: Optional[str] = None
    provider_text_model_id: Optional[str] = None
    provider_vision_model_id: Optional[str] = None
    structured_output_mode: Optional[str] = None
    structured_output_reason: Optional[str] = None
    structured_output_fallback_used: bool = False
    vision_structured_output_mode: Optional[str] = None
    vision_structured_output_reason: Optional[str] = None
    provider_readiness_error: Optional[str] = None
    provider_readiness_reason: Optional[str] = None
    prompt_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    prompt_bundle_id: Optional[str] = None
    prompt_bundle_version: Optional[str] = None
    prompt_bundle_path: Optional[str] = None
    prompt_manifest_hash: Optional[str] = None
    prompt_bundle_hash: Optional[str] = None
    prompt_keys_used: Optional[list[str]] = None
    prompt_files: Optional[dict] = None
    config_hash: Optional[str] = None
    config_snapshot_path: Optional[str] = None
    run_stats_path: Optional[str] = None
    schema_hash: Optional[str] = None
    schema_version: Optional[str] = None
    parser_identity: Optional[str] = None
    parser_version: Optional[str] = None
    style_profile_mode: Optional[str] = None
    style_profile_source: Optional[str] = None
    style_profile_benchmark_safe: Optional[bool] = None
    parser_cache_enabled: Optional[bool] = None
    parser_cache_dir: Optional[str] = None
    parse_cache_hit_count: int = 0
    parse_cache_miss_count: int = 0
    parse_cache_rejected_count: int = 0
    eval_artifacts: Optional[dict] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_stage: Optional[str] = None
    total_rows: int
    eligible_cells: int
    proposals_generated: int
    proposals_reviewed: int
    warnings: list[RunWarning]
    error_message: Optional[str] = None


class ReviewerSummary(BaseModel):
    run_id: str
    verify_mode: bool = False
    eval_mode: bool = False
    run_mode: str = "normal"
    provider_token: Optional[str] = None
    provider_locality: Optional[ProviderLocality] = None
    provider_mode: Optional[str] = None
    provider_text_model_id: Optional[str] = None
    provider_vision_model_id: Optional[str] = None
    structured_output_mode: Optional[str] = None
    structured_output_reason: Optional[str] = None
    structured_output_fallback_used: bool = False
    prompt_only_degraded_mode_used: bool = False
    parse_repair_used: bool = False
    parse_repair_summary: Optional[dict] = None
    vision_structured_output_mode: Optional[str] = None
    vision_structured_output_reason: Optional[str] = None
    provider_readiness_error: Optional[str] = None
    provider_readiness_reason: Optional[str] = None
    provider_model_management_path: Optional[str] = None
    retrieval_mode: Optional[str] = None
    retrieval_top_k: Optional[int] = None
    recall_rescue_enabled: bool = False
    whole_document_mode: bool = False
    recall_rescue_used: bool = False
    retrieval_provenance: Optional[dict] = None
    prompt_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    prompt_bundle_id: Optional[str] = None
    prompt_bundle_version: Optional[str] = None
    prompt_bundle_path: Optional[str] = None
    prompt_manifest_hash: Optional[str] = None
    prompt_bundle_hash: Optional[str] = None
    prompt_keys_used: Optional[list[str]] = None
    prompt_files: Optional[dict] = None
    config_hash: Optional[str] = None
    config_snapshot_path: Optional[str] = None
    run_stats_path: Optional[str] = None
    schema_hash: Optional[str] = None
    schema_version: Optional[str] = None
    parser_identity: Optional[str] = None
    parser_version: Optional[str] = None
    style_profile_mode: Optional[str] = None
    style_profile_source: Optional[str] = None
    style_profile_benchmark_safe: Optional[bool] = None
    parser_cache_enabled: Optional[bool] = None
    parser_cache_dir: Optional[str] = None
    parse_cache_hit_count: int = 0
    parse_cache_miss_count: int = 0
    parse_cache_rejected_count: int = 0
    eval_artifacts: Optional[dict] = None
    extraction_contract_valid: bool = False
    extraction_contract_warnings: list[str] = []
    extraction_provenance: Optional[dict] = None
    total_proposals: int
    reviewed: int = 0
    accepted: int
    accepted_with_edit: int
    confirmed_no_data: int
    rejected: int
    pending: int
    actionable_total_proposals: int = 0
    actionable_reviewed: int = 0
    actionable_pending: int = 0
    diagnostic_only_total_proposals: int = 0
    # breakdown helpers (T075a)
    explicitly_accepted: int = 0        # accepted + accepted_with_edit
    explicitly_rejected: int = 0        # rejected (model-wrong)
    confirmed_absent: int = 0           # confirmed_no_data (distinct from rejection)
    automation_review_applied: bool = False
    automation_accepted_count: int = 0
    generated_at: str


class InputSummary(BaseModel):
    run_id: str
    table_path: Optional[str] = None
    schema_path: Optional[str] = None
    pdf_dir: Optional[str] = None
    resolved_inputs: Optional[dict] = None
    output_dir: str
    verify_mode: bool
    eval_mode: bool = False
    run_mode: str = "normal"
    prompt_version: Optional[str] = None
    prompt_hash: Optional[str] = None
    prompt_bundle_id: Optional[str] = None
    prompt_bundle_version: Optional[str] = None
    prompt_bundle_path: Optional[str] = None
    prompt_manifest_hash: Optional[str] = None
    prompt_bundle_hash: Optional[str] = None
    prompt_keys_used: Optional[list[str]] = None
    prompt_files: Optional[dict] = None
    config_hash: Optional[str] = None
    config_snapshot_path: Optional[str] = None
    run_stats_path: Optional[str] = None
    schema_hash: Optional[str] = None
    schema_version: Optional[str] = None
    parser_identity: Optional[str] = None
    parser_version: Optional[str] = None
    eval_artifacts: Optional[dict] = None
    table_rows: Optional[int] = None
    schema_columns: Optional[int] = None
    pdf_count: Optional[int] = None
    recorded_at: str
