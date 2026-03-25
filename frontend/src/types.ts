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
