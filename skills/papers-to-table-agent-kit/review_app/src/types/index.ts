export type RunStatus =
  | 'created'
  | 'validating'
  | 'running'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'
  | 'interrupted'

export type MatchOutcome = 'matched' | 'ambiguous' | 'unmatched' | 'duplicate_row_conflict'
export type ProposalStatus = 'value_proposed' | 'no_data' | 'unresolved' | 'not_applicable' | 'not_attempted' | 'error'
export type EvidenceStatus = 'direct_strong' | 'direct_weak' | 'inferred_strong' | 'inferred_weak' | 'no_evidence' | 'not_applicable'
export type ReviewBucket = 'review' | 'attention' | 'diagnostic'
export type EvidenceSourceType =
  | 'direct_quote'
  | 'inferred_reasoning'
  | 'calculation'
  | 'approximate_highlight'
  | 'quote_plus_page'
  | 'caption_grounded_figure_evidence'
  | 'visual_interpretation_figure_evidence'
export type ReviewDecision = 'accepted' | 'accepted_with_edit' | 'confirmed_no_data' | 'rejected'

export interface WarningItem {
  category: string
  message: string
  context?: Record<string, unknown>
}

export interface RunData {
  run_id: string
  status: RunStatus
  config_path: string | null
  table_path: string | null
  schema_path: string | null
  pdf_dir: string | null
  resolved_inputs?: {
    table_path?: {
      source_kind: 'config' | 'path_override' | 'staged_handle'
      logical_source: string | null
      runtime_locator: string | null
      staged_handle?: string | null
    } | null
    schema_path?: {
      source_kind: 'config' | 'path_override' | 'staged_handle'
      logical_source: string | null
      runtime_locator: string | null
      staged_handle?: string | null
    } | null
    pdf_dir?: {
      source_kind: 'config' | 'path_override' | 'staged_handle'
      logical_source: string | null
      runtime_locator: string | null
      staged_handle?: string | null
    } | null
  }
  output_dir: string
  verify_mode: boolean
  eval_mode: boolean
  run_mode: 'normal' | 'verify' | 'eval'
  provider_token: string | null
  provider_locality: string | null
  provider_mode?: string | null
  provider_text_model_id?: string | null
  provider_vision_model_id?: string | null
  structured_output_mode?: 'json_schema' | 'json_object' | 'none' | null
  structured_output_reason?: string | null
  structured_output_fallback_used?: boolean
  vision_structured_output_mode?: 'json_schema' | 'json_object' | 'none' | null
  vision_structured_output_reason?: string | null
  provider_readiness_error?: string | null
  provider_readiness_reason?: string | null
  prompt_version?: string | null
  prompt_hash?: string | null
  config_hash?: string | null
  config_snapshot_path?: string | null
  schema_hash?: string | null
  schema_version?: string | null
  parser_identity?: string | null
  parser_version?: string | null
  eval_artifacts?: {
    gold_table?: {
      source_reference?: string | null
      content_hash?: string | null
      snapshot_path?: string | null
    } | null
    masked_working_table?: {
      path?: string | null
      content_hash?: string | null
    } | null
    target_columns?: string[]
    target_cell_count?: number
    masked_non_empty_cell_count?: number
  } | null
  started_at: string | null
  completed_at: string | null
  current_stage: string | null
  total_rows: number
  eligible_cells: number
  proposals_generated: number
  proposals_reviewed: number
  warnings: WarningItem[]
  last_export?: {
    exported_at: string
    accepted_changes_count: number
    workbook_path: string
    audit_log_path: string
    diagnostics_path: string
  } | null
  error_message: string | null
  created_at: string
}

export interface InputSummary {
  run_id: string
  table_path: string | null
  schema_path: string | null
  pdf_dir: string | null
  resolved_inputs?: RunData['resolved_inputs']
  output_dir: string
  verify_mode: boolean
  eval_mode: boolean
  run_mode: 'normal' | 'verify' | 'eval'
  table_rows: number | null
  schema_columns: number | null
  pdf_count: number | null
  recorded_at: string
}

export interface CreateRunRequest {
  config_path: string
  table_path?: string
  schema_path?: string
  pdf_dir?: string
  output_dir?: string
  table_staged_handle?: string
  schema_staged_handle?: string
  pdf_dir_staged_handle?: string
}

export interface RunPreflight {
  config_path: string
  run_mode: 'normal' | 'verify' | 'eval'
  output_dir: string
  resolved_inputs: Required<NonNullable<RunData['resolved_inputs']>>
  provider: {
    token: string
    locality: string
    base_url: string
    text_model_id: string
    vision_model_id?: string | null
  }
  scope: {
    table_rows: number | null
    schema_columns: number | null
    pdf_count: number | null
  }
  readiness: {
    ok: boolean
    errors: string[]
    warnings: string[]
    provider_mode: string | null
    provider_readiness_reason: string | null
    provider_readiness_error: string | null
  }
  what_happens_next: string[]
}

export interface CreateRunResponse {
  run_id: string
  status: string
  resolved_inputs: Required<NonNullable<RunData['resolved_inputs']>>
}

export interface RunStreamEvent {
  event: 'run.updated' | 'run.deleted'
  run_id: string
  recorded_at: string
  run?: RunData
}

export interface StagedInputResponse {
  handle: string
  kind: 'table_path' | 'schema_path' | 'pdf_dir'
  logical_source: string
  runtime_locator: string
}

export interface ListRunsResponse {
  runs: RunData[]
}

export interface Proposal {
  proposal_id: string
  run_id: string
  cell_id: string
  row_id: string
  column_name: string
  pdf_id: string
  proposal_status: ProposalStatus
  evidence_status: EvidenceStatus
  review_bucket: ReviewBucket
  reason_codes: string[]
  proposed_value: string | null
  rationale: string | null
  calculation: string | null
  evidence_ids: string[]
  warning_flags?: string[]
  candidate_answers?: Array<Record<string, unknown>> | null
  selection_diagnostics?: Record<string, unknown> | null
  created_at: string
}

export interface EvidenceItem {
  evidence_id: string
  proposal_id: string
  pdf_id: string
  source_type: EvidenceSourceType
  quote_text: string | null
  table_text?: string | null
  evidence_text?: string | null
  page_number: number | null
  exact_highlight_regions: Array<{x0: number; y0: number; x1: number; y1: number; page: number}> | null
  approximate_highlight_regions: Array<{x0: number; y0: number; x1: number; y1: number; page: number}> | null
  figure_ref: string | null
  caption_text: string | null
  crop_path: string | null
  full_page_path: string | null
  anchor_confidence: number | null
  evidence_rank: number
  source_label: string
}

export interface DecisionRecord {
  review_decision_id: string
  run_id: string
  proposal_id: string
  cell_id: string
  decision: ReviewDecision
  decision_source?: string | null
  resolution_reason: string | null
  edited_value: string | null
  reviewer_note: string | null
  decided_at: string
}

export interface EnrichedProposal {
  proposal_id: string
  run_id: string
  cell_id: string
  row_id: string
  column_name: string
  pdf_id: string
  proposal_status: ProposalStatus
  evidence_status: EvidenceStatus
  review_bucket: ReviewBucket
  reason_codes: string[]
  proposed_value: string | null
  rationale: string | null
  calculation: string | null
  primary_evidence_id: string | null
  ordered_supporting_evidence_ids: string[]
  evidence_ids: string[]
  warning_flags?: string[]
  needs_more_evidence: boolean
  is_verify_mode: boolean
  existing_value?: string | null
  field_type?: 'text' | 'number' | 'categorical' | 'boolean' | null
  allowed_values?: string[] | null
  numeric_value_form?: 'exact' | 'range' | 'approximate' | null
  recall_rescue_used?: boolean
  whole_document_used?: boolean
  candidate_answers?: Array<Record<string, unknown>> | null
  selection_diagnostics?: Record<string, unknown> | null
  provider_diagnostics?: Record<string, unknown> | null
  retrieval_diagnostics?: Record<string, unknown> | null
  metadata_diagnostics?: Record<string, unknown> | null
  figure_review_diagnostics?: Record<string, unknown> | null
  figure_planner_diagnostics?: Record<string, unknown> | null
  provider_mode?: string
  created_at: string
  latest_decision: DecisionRecord | null
  warning_categories?: string[]
  is_figure_derived: boolean
  is_fallback_evidence: boolean
  paper_title?: string | null
  paper_authors?: string | null
  paper_year?: string | number | null
}

export interface ProposalDetail {
  proposal: EnrichedProposal
  evidence: EvidenceItem[]
  latest_decision: DecisionRecord | null
  decision_history: DecisionRecord[]
  row_context: Record<string, unknown>
  column_definition: Record<string, unknown> | null
  evidence_status_display?: string
}

export interface ReviewTableColumn {
  name: string
  description: string | null
  field_type: string | null
  is_target: boolean
}

export interface ReviewTableEvidenceSummary {
  count: number
  primary_evidence_id: string | null
  primary_source_type: string | null
  primary_page_number: number | null
  primary_quote_text: string | null
}

export interface ReviewTableProposal extends EnrichedProposal {
  evidence_summary?: ReviewTableEvidenceSummary
}

export type ReviewTableCellStatus =
  | 'unchanged'
  | 'pending'
  | 'accepted'
  | 'accepted_with_edit'
  | 'confirmed_no_data'
  | 'rejected'

export interface ReviewTableCell {
  column_name: string
  original_value: unknown
  display_value: unknown
  display_status: ReviewTableCellStatus | string
  has_proposal: boolean
  proposal: ReviewTableProposal | null
}

export interface ReviewTableRow {
  row_id: string
  row_index: number | null
  paper_label: string
  title: string | null
  values: Record<string, unknown>
  cells: Record<string, ReviewTableCell>
}

export interface ReviewTableData {
  run_id: string
  columns: ReviewTableColumn[]
  rows: ReviewTableRow[]
  proposal_count: number
}

export interface MatchingSummary {
  run_id: string
  total_pdfs: number
  matched: number
  unmatched: number
  ambiguous: number
  duplicate_row_conflict: number
}

export interface ReviewProgress {
  run_id: string
  total_proposals: number
  reviewed: number
  accepted: number
  accepted_with_edit: number
  confirmed_no_data: number
  rejected: number
  pending: number
}

export interface ReviewerSummary {
  run_id: string
  verify_mode?: boolean
  eval_mode?: boolean
  run_mode?: 'normal' | 'verify' | 'eval'
  provider_token?: string | null
  provider_locality?: string | null
  provider_mode?: string | null
  provider_text_model_id?: string | null
  provider_vision_model_id?: string | null
  structured_output_mode?: 'json_schema' | 'json_object' | 'none' | null
  structured_output_reason?: string | null
  structured_output_fallback_used?: boolean
  vision_structured_output_mode?: 'json_schema' | 'json_object' | 'none' | null
  vision_structured_output_reason?: string | null
  provider_readiness_error?: string | null
  provider_readiness_reason?: string | null
  prompt_version?: string | null
  prompt_hash?: string | null
  config_hash?: string | null
  config_snapshot_path?: string | null
  schema_hash?: string | null
  schema_version?: string | null
  parser_identity?: string | null
  parser_version?: string | null
  eval_artifacts?: RunData['eval_artifacts']
  total_proposals: number
  reviewed: number
  pending: number
  accepted: number
  accepted_with_edit: number
  confirmed_no_data: number
  rejected: number
  actionable_total_proposals?: number
  actionable_reviewed?: number
  actionable_pending?: number
  diagnostic_only_total_proposals?: number
  by_column: Record<string, {total: number; accepted: number; rejected: number; confirmed_no_data: number; pending: number}>
}

export interface ExportResult {
  run_id: string
  exported_at: string
  accepted_changes_count: number
  workbook_path: string
  reviewed_table_path?: string | null
  audit_log_path: string
  diagnostics_path: string
  unsupported_feature_warnings: string[]
  unsupported_feature_warnings_count: number
  fidelity_boundary: string
}
