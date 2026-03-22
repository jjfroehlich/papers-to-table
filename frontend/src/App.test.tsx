import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { App } from './App'

const completedRun = {
  run_id: 'run-1',
  created_at: '2026-03-22T12:00:00Z',
  updated_at: '2026-03-22T12:05:00Z',
  status: 'completed',
  provider_name: 'stub-lmstudio',
  provider_model: 'stub-model',
  provider_locality: 'local',
  verify_mode: true,
  warnings: [],
  config_path: 'my-config.json',
  message: 'Run completed and is ready for review.',
}

const validatingRun = {
  run_id: 'run-2',
  created_at: '2026-03-22T12:10:00Z',
  updated_at: '2026-03-22T12:10:02Z',
  status: 'validating',
  provider_name: 'stub-lmstudio',
  provider_model: 'stub-model',
  provider_locality: 'local',
  verify_mode: true,
  warnings: [],
  config_path: 'my-config.json',
  message: 'Validating config paths and loading table inputs.',
}

const completedRunTwo = {
  run_id: 'run-3',
  created_at: '2026-03-22T12:20:00Z',
  updated_at: '2026-03-22T12:25:00Z',
  status: 'completed',
  provider_name: 'stub-lmstudio',
  provider_model: 'stub-model',
  provider_locality: 'local',
  verify_mode: true,
  warnings: [],
  config_path: 'my-config.json',
  message: 'Second run completed and is ready for review.',
}

const summary = {
  run_id: 'run-1',
  status: 'completed',
  pdfs_processed: 1,
  matched_pdfs: 1,
  unmatched_pdfs: 0,
  ambiguous_pdfs: 0,
  duplicate_conflict_pdfs: 0,
  proposals_generated: 2,
  reviewed_proposals: 0,
  accepted_as_is: 0,
  accepted_with_edit: 0,
  rejected: 0,
  pending: 2,
  changed_cells_exported: 0,
  verify_mode: true,
  provider_name: 'stub-lmstudio',
  provider_model: 'stub-model',
  provider_locality: 'local',
  warnings: [],
}

const reviewerSummary = {
  run_id: 'run-1',
  proposals_generated: 2,
  reviewed_proposals: 0,
  accepted_as_is: 0,
  accepted_with_edit: 0,
  rejected: 0,
  pending: 2,
  changed_cells_exported: 0,
  matched_pdfs: 1,
  unmatched_pdfs: 0,
  ambiguous_pdfs: 0,
  verify_mode: true,
  provider_name: 'stub-lmstudio',
  provider_model: 'stub-model',
  provider_locality: 'local',
  reviewed_verified_cell_count: 0,
  proposal_coverage: 0,
  evidence_coverage: 1,
  anchorable_evidence_rate: 1,
  per_column: [{ column_name: 'Assay', reviewed_verified_cell_count: 0, accepted_as_is: 0, accepted_with_edit: 0, rejected: 0, evidence_coverage: 1, anchorable_evidence_rate: 1 }],
  warnings: ['No reviewed verified cells were available for reviewer-outcome interpretation.'],
}

const proposals = [
  { proposal_id: 'proposal-1', pdf_id: 'pdf-1', row_id: 'row-1', column_name: 'Assay', proposed_value: 'Flow cytometry', proposal_state: 'found', support_label: 'Direct evidence', rationale: 'explicit', calculation: '', needs_more_evidence: false, current_value: '', is_verify_target: false, warning_flags: [], review_decision: 'no_decision', pdf_name: 'paper.pdf', source_mode: 'text' },
  { proposal_id: 'proposal-2', pdf_id: 'pdf-1', row_id: 'row-1', column_name: 'Figure finding', proposed_value: 'Positive signal', proposal_state: 'inferred', support_label: 'Figure-derived evidence', rationale: 'caption', calculation: '', needs_more_evidence: false, current_value: '', is_verify_target: false, warning_flags: ['figure_derived'], review_decision: 'no_decision', pdf_name: 'paper.pdf', source_mode: 'vision' },
  { proposal_id: 'proposal-3', pdf_id: 'pdf-2', row_id: 'row-2', column_name: 'Blocked field', proposed_value: null, proposal_state: 'blocked', support_label: 'Blocked', rationale: '', calculation: '', needs_more_evidence: false, current_value: '', is_verify_target: false, warning_flags: ['ambiguous_match'], review_decision: 'no_decision', pdf_name: 'blocked.pdf', source_mode: 'text' },
  { proposal_id: 'proposal-4', pdf_id: 'pdf-1', row_id: 'row-1', column_name: 'Weak fallback field', proposed_value: 'Fallback value', proposal_state: 'inferred', support_label: 'Weak text evidence', rationale: 'fallback', calculation: '', needs_more_evidence: true, current_value: '', is_verify_target: false, warning_flags: ['quote_page_fallback', 'weak_evidence'], review_decision: 'no_decision', pdf_name: 'paper.pdf', source_mode: 'text' },
]

const proposalsRunTwo = [
  { proposal_id: 'proposal-9', pdf_id: 'pdf-9', row_id: 'row-9', column_name: 'Assay', proposed_value: 'Western blot', proposal_state: 'found', support_label: 'Direct evidence', rationale: 'explicit', calculation: '', needs_more_evidence: false, current_value: '', is_verify_target: false, warning_flags: [], review_decision: 'no_decision', pdf_name: 'paper-2.pdf', source_mode: 'text' },
]

const detail = {
  proposal: proposals[0],
  row_context: { Title: 'Paper title' },
  primary_evidence: { evidence_id: 'e1', page: 1, quote_text: 'Assay: Flow cytometry', highlight: [{ x: 40, y: 80, width: 100, height: 20 }], caption_text: '', crop_path: null, full_page_path: null, anchor_confidence: 0.9, source_type: 'text' },
  secondary_evidence: [],
}

const detailRunTwo = {
  proposal: proposalsRunTwo[0],
  row_context: { Title: 'Second paper title' },
  primary_evidence: { evidence_id: 'e9', page: 3, quote_text: 'Assay: Western blot', highlight: [{ x: 55, y: 95, width: 110, height: 24 }], caption_text: '', crop_path: null, full_page_path: null, anchor_confidence: 0.95, source_type: 'text' },
  secondary_evidence: [],
}

const blockedDetail = { proposal: proposals[2], row_context: { Title: 'Blocked paper title' }, primary_evidence: null, secondary_evidence: [] }
const fallbackDetail = {
  proposal: proposals[3],
  row_context: { Title: 'Paper title' },
  primary_evidence: { evidence_id: 'e2', page: 2, page_width: 612, page_height: 792, quote_text: 'Weakly anchored evidence quote', highlight: [], caption_text: '', crop_path: null, full_page_path: null, anchor_confidence: 0.4, source_type: 'text' },
  secondary_evidence: [],
}

const configSnapshot = {
  paths: {
    table_path: 'tests/fixtures/tables/literature_fixture.csv',
    schema_path: 'tests/fixtures/schema/literature_schema.csv',
    pdf_dir: 'tests/fixtures/papers',
    output_dir: 'artifacts',
  },
  provider: {
    provider: 'stub',
    base_url: 'http://127.0.0.1:1234/v1',
    model: 'stub-model',
    timeout_seconds: 15,
    live_smoke_enabled: false,
  },
  review: {
    verify_mode: true,
    placeholder_values: ['', ' ', 'NA'],
  },
}

const inputSummary = {
  config_path: 'my-config.json',
  table_path: 'tests/fixtures/tables/literature_fixture.csv',
  schema_path: 'tests/fixtures/schema/literature_schema.csv',
  pdf_dir: 'tests/fixtures/papers',
  output_dir: 'artifacts',
  row_count: 8,
  pdf_count: 6,
  target_columns: ['Assay', 'Figure finding'],
  verify_mode: true,
}

describe('App', () => {
  beforeEach(() => {
    let runList = [completedRun, completedRunTwo]
    globalThis.fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      const method = init?.method ?? 'GET'
      if (url.endsWith('/api/runs') && method === 'GET') return Promise.resolve(new Response(JSON.stringify(runList), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/api/runs') && method === 'POST') {
        runList = [validatingRun, ...runList]
        return Promise.resolve(new Response(JSON.stringify(validatingRun), { headers: { 'Content-Type': 'application/json' } }))
      }
      if (url.endsWith('/summary')) return Promise.resolve(new Response(JSON.stringify(summary), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/reviewer-summary')) return Promise.resolve(new Response(JSON.stringify(reviewerSummary), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/config')) return Promise.resolve(new Response(JSON.stringify(configSnapshot), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/input-summary')) return Promise.resolve(new Response(JSON.stringify(inputSummary), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/diagnostics')) return Promise.resolve(new Response(JSON.stringify({}), { headers: { 'Content-Type': 'application/json' } }))
      if (url.includes('/runs/run-3/proposals/proposal-1')) return Promise.reject(new Error('Stale proposal request should not happen.'))
      if (url.includes('/runs/run-3/proposals/proposal-9')) return Promise.resolve(new Response(JSON.stringify(detailRunTwo), { headers: { 'Content-Type': 'application/json' } }))
      if (url.includes('/proposals/proposal-3')) return Promise.resolve(new Response(JSON.stringify(blockedDetail), { headers: { 'Content-Type': 'application/json' } }))
      if (url.includes('/proposals/proposal-4')) return Promise.resolve(new Response(JSON.stringify(fallbackDetail), { headers: { 'Content-Type': 'application/json' } }))
      if (url.includes('/proposals/') && !url.endsWith('/proposals')) return Promise.resolve(new Response(JSON.stringify(detail), { headers: { 'Content-Type': 'application/json' } }))
      if (url.includes('/matches')) return Promise.resolve(new Response(JSON.stringify({ matches: [{ pdf_id: 'pdf-2', pdf_name: 'blocked.pdf', outcome: 'ambiguous', row_id: 'row-2', rationale: 'Title overlap' }] }), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/runs/run-3/proposals')) return Promise.resolve(new Response(JSON.stringify({ proposals: proposalsRunTwo, total: proposalsRunTwo.length }), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/proposals')) return Promise.resolve(new Response(JSON.stringify({ proposals, total: proposals.length }), { headers: { 'Content-Type': 'application/json' } }))
      if (url.endsWith('/reviews') || url.endsWith('/bulk-accept')) return Promise.resolve(new Response(JSON.stringify({ ok: true, summary, reviewer_summary: reviewerSummary }), { headers: { 'Content-Type': 'application/json' } }))
      return Promise.reject(new Error(`Unhandled fetch: ${url}`))
    }) as typeof fetch
  })

  it('does not request stale proposal detail when switching runs', async () => {
    render(<App />)
    await screen.findByText('Assay')
    fireEvent.change(screen.getByLabelText('Current run'), { target: { value: 'run-3' } })
    await screen.findByRole('button', { name: /Western blot/ })
    expect(screen.queryByText(/Stale proposal request should not happen/i)).not.toBeInTheDocument()
  })

  it('renders run setup, summary downloads, and unresolved-match warnings', async () => {
    render(<App />)
    expect(await screen.findByText('Download workbook')).toBeInTheDocument()
    expect(await screen.findByText(/Match inspection/)).toBeInTheDocument()
    expect(await screen.findByText('Run setup')).toBeInTheDocument()
    expect(screen.getByText('my-config.json')).toBeInTheDocument()
  })

  it('filters figure evidence without changing decision state', async () => {
    render(<App />)
    await screen.findByText('Figure finding')
    fireEvent.change(screen.getByLabelText('Filter'), { target: { value: 'figure' } })
    await waitFor(() => {
      expect(screen.getByText('Figure finding')).toBeInTheDocument()
      expect(screen.queryByText('Blocked field')).not.toBeInTheDocument()
    })
  })

  it('disables accept actions for blocked proposals and requires a changed edited value', async () => {
    render(<App />)
    await screen.findByText('Assay')
    expect(screen.getByRole('button', { name: 'Save edited value' })).toBeDisabled()
    fireEvent.click(await screen.findByRole('button', { name: /Blocked field/ }))
    await screen.findByText(/No proposal available/)
    expect(screen.getByRole('button', { name: 'Accept as-is' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Save edited value' })).toBeDisabled()
  })

  it('starts a run from the launcher and shows a validating state before review is ready', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: 'Start run' }))
    await waitFor(() => {
      expect(screen.getAllByText(/validating config paths and loading table inputs/i).length).toBeGreaterThan(0)
      expect(screen.getByText(/review items will appear automatically if validation succeeds/i)).toBeInTheDocument()
    })
  })

  it('shows quote-plus-page fallback messaging when highlight geometry is unavailable', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Weak fallback field/ }))
    await screen.findByText(/quote \+ page fallback/i)
    expect(screen.getByText(/guessed overlay/i)).toBeInTheDocument()
  })
})