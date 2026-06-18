import { ReviewWorkspace } from './components/ReviewWorkspace'
import type { RunData } from './types'

function buildRun(): RunData {
  const pkg = window.__REVIEW_PACKAGE__
  if (!pkg) {
    throw new Error('Missing embedded review package.')
  }
  const reviewable = (pkg.proposals ?? []).filter((proposal) => proposal.review_bucket !== 'diagnostic')
  return {
    run_id: pkg.run_id,
    status: 'completed',
    config_path: null,
    table_path: pkg.source?.source_table_present ? 'source_table.csv' : null,
    schema_path: null,
    pdf_dir: 'pdfs',
    output_dir: '.',
    verify_mode: false,
    eval_mode: false,
    run_mode: 'normal',
    provider_token: null,
    provider_locality: null,
    started_at: pkg.generated_at ?? null,
    completed_at: pkg.generated_at ?? null,
    current_stage: 'review',
    total_rows: pkg.rows?.length ?? 0,
    eligible_cells: reviewable.length,
    proposals_generated: pkg.proposals?.length ?? 0,
    proposals_reviewed: 0,
    warnings: [],
    error_message: null,
    created_at: pkg.generated_at ?? new Date().toISOString(),
  }
}

export function App() {
  return <ReviewWorkspace run={buildRun()} outputDir="" />
}
