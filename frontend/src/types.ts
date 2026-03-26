export type RunStatus =
  | 'created'
  | 'validating'
  | 'running'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'
  | 'interrupted'

export type OperatorRunStatus =
  | 'ready'
  | 'validating'
  | 'running'
  | 'completed'
  | 'completed with warnings'
  | 'failed'

export type ReviewDecision = 'accept' | 'accept_with_edit' | 'reject' | 'undecided'

export type WarningStatusCategory =
  | 'ambiguous_match'
  | 'duplicate_row_conflict'
  | 'weak_evidence'
  | 'quote_page_fallback'
  | 'figure_derived'
  | 'no_reviewed_verified_cells'
  | 'completed_with_warnings'

export type ProposalState = 'actionable' | 'blocked' | 'unclear' | 'skipped' | 'error'

export type SupportLabel = 'strong_evidence' | 'moderate_evidence' | 'weak_evidence' | 'no_evidence'

export interface RunRecord {
  run_id: string
  status: RunStatus
  operator_status: OperatorRunStatus
  config_path: string
  artifact_dir: string
  message: string | null
  progress: {
    stage: string | null
    item: string | null
  }
  created_at: string
  updated_at: string
}

export interface RunSummary {
  run_id: string
  status: RunStatus
  operator_status: OperatorRunStatus
  message: string | null
  progress: {
    stage: string | null
    item: string | null
  }
  config_path: string
  artifact_dir: string
  verify_mode: boolean
  table_path: string | null
  schema_path: string | null
  pdf_dir: string | null
  output_dir: string | null
  target_columns: string[]
  provider_name: string | null
  model_name: string | null
  provider_locality: 'local' | 'cloud'
}

export interface InputSummary {
  table_path: string
  schema_path: string | null
  pdf_dir: string
  output_dir: string
  verify_mode: boolean
  target_columns: string[]
  row_count: number
  eligible_missing_cells: number
  eligible_filled_cells: number
  ineligible_cells: number
  placeholders_treated_as_empty: string[]
}

export interface ProposalListItem {
  proposal_id: string
  run_id: string
  pdf_id: string
  row_id: string
  column_name: string
  cell_id: string
  source_mode: string
  proposal_state: ProposalState
  support_label: SupportLabel
  proposed_value: string | null
  status_flags: WarningStatusCategory[]
  latest_decision: ReviewDecision
}

export interface EvidenceHighlight {
  x0: number
  y0: number
  x1: number
  y1: number
}

export interface EvidenceRecord {
  evidence_id: string
  proposal_id: string
  pdf_id: string
  source_type: 'text_quote' | 'figure_crop' | 'caption' | 'full_page'
  page: number | null
  quote_text: string | null
  highlight: EvidenceHighlight | null
  figure_ref: string | null
  caption_text: string | null
  crop_path: string | null
  full_page_path: string | null
  anchor_confidence: number | null
}

export interface ProposalDetail {
  proposal_id: string
  run_id: string
  pdf_id: string
  row_id: string
  column_name: string
  cell_id: string
  source_mode: string
  proposal_state: ProposalState
  support_label: SupportLabel
  proposed_value: string | null
  rationale: string | null
  calculation: string | null
  needs_more_evidence: boolean
  status_flags: WarningStatusCategory[]
  row_context: Record<string, unknown>
  column_definition: Record<string, unknown>
  current_cell_value: string | null
  evidence: EvidenceRecord[]
  latest_decision: ReviewDecision
  latest_decision_record: Record<string, unknown> | null
}

export interface ReviewDecisionRecord {
  decision_id: string
  run_id: string
  proposal_id: string
  cell_id: string
  decision: ReviewDecision
  edited_value: string | null
  decided_at: string
}

export interface ProposalProgress {
  total: number
  accepted_as_is: number
  accepted_with_edit: number
  rejected: number
  pending: number
}

export interface MatchingSummary {
  total: number
  matched: number
  unresolved: number
}

export interface UnresolvedMatch {
  pdf_id: string
  filename: string
  outcome: string
  reason: string
  candidates?: string[]
}

export interface RunSummaryFull {
  run_id: string
  status: RunStatus
  operator_status: OperatorRunStatus
  message: string | null
  progress: { stage: string | null; item: string | null }
  config_path: string
  verify_mode: boolean
  provider_name: string | null
  model_name: string | null
  provider_locality: 'local' | 'cloud'
  counts: {
    proposals_generated: number
    reviewed_proposals: number
    accepted_as_is: number
    accepted_with_edit: number
    rejected: number
    pending: number
    changed_cells_exported: number
  }
  pdfs_processed: number
  pdfs_matched: number
  pdfs_unmatched: number
  pdfs_ambiguous: number
  run_status_flags: WarningStatusCategory[]
}

export interface AvailableDownloads {
  run_summary: boolean
  reviewer_summary: boolean
  workbook: boolean
  audit_log: boolean
}

export type DecisionFilter = ReviewDecision | 'all'
