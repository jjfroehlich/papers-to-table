import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi } from 'vitest'
import { App } from './App'

const runs = [{ run_id: 'run-1', status: 'completed', provider_name: 'stub-lmstudio', provider_model: 'stub-model', provider_locality: 'local', verify_mode: true, warnings: [], message: '' }]
const summary = { run_id: 'run-1', status: 'completed', pdfs_processed: 1, matched_pdfs: 1, unmatched_pdfs: 0, ambiguous_pdfs: 0, duplicate_conflict_pdfs: 0, proposals_generated: 2, reviewed_proposals: 0, accepted_as_is: 0, accepted_with_edit: 0, rejected: 0, pending: 2, changed_cells_exported: 0, verify_mode: true, provider_name: 'stub-lmstudio', provider_model: 'stub-model', provider_locality: 'local', warnings: [] }
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
  warnings: [],
}
const proposals = [
  { proposal_id: 'proposal-1', pdf_id: 'pdf-1', row_id: 'row-1', column_name: 'Assay', proposed_value: 'Flow cytometry', proposal_state: 'found', support_label: 'Direct evidence', rationale: 'explicit', calculation: '', needs_more_evidence: false, current_value: '', is_verify_target: false, warning_flags: [], review_decision: 'no_decision', pdf_name: 'paper.pdf', source_mode: 'text' },
  { proposal_id: 'proposal-2', pdf_id: 'pdf-1', row_id: 'row-1', column_name: 'Figure finding', proposed_value: 'Positive signal', proposal_state: 'inferred', support_label: 'Figure-derived evidence', rationale: 'caption', calculation: '', needs_more_evidence: false, current_value: '', is_verify_target: false, warning_flags: ['figure_derived'], review_decision: 'no_decision', pdf_name: 'paper.pdf', source_mode: 'vision' },
  { proposal_id: 'proposal-3', pdf_id: 'pdf-2', row_id: 'row-2', column_name: 'Blocked field', proposed_value: null, proposal_state: 'blocked', support_label: 'Blocked', rationale: '', calculation: '', needs_more_evidence: false, current_value: '', is_verify_target: false, warning_flags: ['ambiguous_match'], review_decision: 'no_decision', pdf_name: 'blocked.pdf', source_mode: 'text' },
]
const detail = { proposal: proposals[0], row_context: { Title: 'Paper title' }, primary_evidence: { evidence_id: 'e1', page: 1, quote_text: 'Assay: Flow cytometry', highlight: [{ x: 40, y: 80, width: 100, height: 20 }], caption_text: '', crop_path: null, full_page_path: null, anchor_confidence: 0.9, source_type: 'text' }, secondary_evidence: [] }
const blockedDetail = { proposal: proposals[2], row_context: { Title: 'Blocked paper title' }, primary_evidence: null, secondary_evidence: [] }

describe('App', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      if (url.endsWith('/api/runs')) return Promise.resolve(new Response(JSON.stringify(runs)))
      if (url.endsWith('/summary')) return Promise.resolve(new Response(JSON.stringify(summary)))
      if (url.endsWith('/reviewer-summary')) return Promise.resolve(new Response(JSON.stringify(reviewerSummary)))
      if (url.includes('/proposals/proposal-3')) return Promise.resolve(new Response(JSON.stringify(blockedDetail)))
      if (url.includes('/proposals/') && !url.endsWith('/proposals')) return Promise.resolve(new Response(JSON.stringify(detail)))
      if (url.includes('/matches')) return Promise.resolve(new Response(JSON.stringify({ matches: [{ pdf_id: 'pdf-2', pdf_name: 'blocked.pdf', outcome: 'ambiguous', row_id: 'row-2', rationale: 'Title overlap' }] })))
      if (url.endsWith('/proposals')) return Promise.resolve(new Response(JSON.stringify({ proposals, total: proposals.length })))
      if (url.endsWith('/reviews') || url.endsWith('/bulk-accept')) return Promise.resolve(new Response(JSON.stringify({ ok: true, summary, reviewer_summary: reviewerSummary })))
      return Promise.reject(new Error(`Unhandled fetch: ${url}`))
    }) as typeof fetch
  })

  it('renders summary, downloads, and unresolved-match warnings', async () => {
    render(<App />)
    expect(await screen.findByText('Download workbook')).toBeInTheDocument()
    expect(await screen.findByText(/Blocked or unresolved PDFs/)).toBeInTheDocument()
    expect(screen.getByText('Paper Table Agent')).toBeInTheDocument()
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

  it('disables accept actions for blocked proposals', async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole('button', { name: /Blocked field/ }))
    await screen.findByText(/No proposal available/)
    expect(screen.getByRole('button', { name: 'Accept as-is' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Accept with edit' })).toBeDisabled()
  })
})
