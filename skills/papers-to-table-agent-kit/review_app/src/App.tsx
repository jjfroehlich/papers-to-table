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
  const run = buildRun()

  return (
    <div className="min-h-screen bg-[#f5f6f7] text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center justify-between gap-4 px-5 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <img src="./logo_1.svg" alt="papers-to-table" className="h-10 w-10 shrink-0 rounded-lg object-contain" />
            <div className="min-w-0">
              <h1 className="text-xl font-semibold tracking-tight text-slate-950">papers-to-table</h1>
              <p className="mt-0.5 text-xs font-medium text-slate-500">Evidence-backed extraction and review</p>
            </div>
          </div>

          <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
            <span className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-slate-950 shadow-sm">
              Agent skill review
            </span>
          </div>
        </div>
      </header>

      <main>
        <ReviewWorkspace run={run} outputDir="" />
      </main>
    </div>
  )
}
