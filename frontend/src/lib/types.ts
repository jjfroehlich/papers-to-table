export type ReviewDecision = 'accept' | 'accept_with_edit' | 'reject' | 'no_decision'

export type RunStatus = 'created' | 'validating' | 'running' | 'completed' | 'completed_with_warnings' | 'failed' | 'interrupted'

export interface RunRecord {
  run_id: string
  created_at: string
  updated_at: string
  status: RunStatus
  provider_name: string
  provider_model: string
  provider_locality: string
  verify_mode: boolean
  warnings: string[]
  config_path: string
  message: string
}

export interface RunSummary {
  run_id: string
  status: string
  pdfs_processed: number
  matched_pdfs: number
  unmatched_pdfs: number
  ambiguous_pdfs: number
  duplicate_conflict_pdfs: number
  proposals_generated: number
  reviewed_proposals: number
  accepted_as_is: number
  accepted_with_edit: number
  rejected: number
  pending: number
  changed_cells_exported: number
  verify_mode: boolean
  provider_name: string
  provider_model: string
  provider_locality: string
  warnings: string[]
}

export interface ReviewerSummary {
  run_id: string
  proposals_generated: number
  reviewed_proposals: number
  accepted_as_is: number
  accepted_with_edit: number
  rejected: number
  pending: number
  changed_cells_exported: number
  matched_pdfs: number
  unmatched_pdfs: number
  ambiguous_pdfs: number
  verify_mode: boolean
  provider_name: string
  provider_model: string
  provider_locality: string
  reviewed_verified_cell_count: number
  proposal_coverage: number
  evidence_coverage: number
  anchorable_evidence_rate: number
  per_column: Array<{
    column_name: string
    reviewed_verified_cell_count: number
    accepted_as_is: number
    accepted_with_edit: number
    rejected: number
    evidence_coverage: number
    anchorable_evidence_rate: number
  }>
  warnings: string[]
}

export interface ProposalRecord {
  proposal_id: string
  pdf_id: string
  row_id: string
  column_name: string
  proposed_value: string | null
  proposal_state: string
  support_label: string
  rationale: string
  calculation: string
  needs_more_evidence: boolean
  current_value: string
  is_verify_target: boolean
  warning_flags: string[]
  review_decision: ReviewDecision
  reviewed_value?: string | null
  pdf_name: string
  source_mode: 'text' | 'vision'
}

export interface MatchRecord {
  pdf_id: string
  pdf_name: string
  outcome: 'matched' | 'ambiguous' | 'unmatched' | 'duplicate_row_conflict'
  row_id: string | null
  rationale: string
}

export interface EvidenceRecord {
  evidence_id: string
  page: number
  page_width?: number | null
  page_height?: number | null
  quote_text: string
  highlight: Array<{ x: number; y: number; width: number; height: number }>
  caption_text: string
  crop_path?: string | null
  full_page_path?: string | null
  anchor_confidence: number
  source_type: string
}

export interface ProposalDetail {
  proposal: ProposalRecord
  row_context: Record<string, string>
  primary_evidence: EvidenceRecord | null
  secondary_evidence: EvidenceRecord[]
}

export interface InputSummary {
  config_path: string
  table_path: string
  schema_path: string | null
  pdf_dir: string
  output_dir: string
  row_count: number
  pdf_count: number
  target_columns: string[]
  verify_mode: boolean
}

export interface ConfigSnapshot {
  paths: {
    table_path: string
    schema_path: string | null
    pdf_dir: string
    output_dir: string
  }
  provider: {
    provider: string
    base_url: string
    model: string
    timeout_seconds: number
    live_smoke_enabled: boolean
  }
  review: {
    verify_mode: boolean
    placeholder_values: string[]
  }
}

export interface RunDiagnostics {
  status?: string
  message?: string
  error?: string
  warnings?: string[]
  exports?: {
    workbook: string
    audit_log: string
  }
  match_outcomes?: MatchRecord[]
}
