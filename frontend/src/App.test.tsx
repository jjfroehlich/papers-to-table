import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { App } from './App'

function mockFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (url.endsWith('/api/runs')) {
      return { ok: true, json: async () => [{ run_id: 'run_123', status: 'completed', operator_state: 'completed' }] }
    }
    if (url.includes('/inputs')) {
      return { ok: true, json: async () => ({ pdf_count: 1, row_count: 1 }) }
    }
    if (url.includes('/summaries/run')) {
      return { ok: true, json: async () => ({ proposals_generated: 2, provider_name: 'lm_studio' }) }
    }
    if (url.includes('/summaries/reviewer')) {
      return { ok: true, json: async () => ({ reviewed_proposals: 1 }) }
    }
    if (url.includes('/matching/issues')) {
      return { ok: true, json: async () => ({ unmatched: [], ambiguous: [], duplicate_row_conflicts: [] }) }
    }
    if (url.includes('/downloads')) {
      return { ok: true, json: async () => ({ downloads: { run_summary: { ready: true } } }) }
    }
    if (url.includes('/proposals?')) {
      return {
        ok: true,
        json: async () => ({
          items: [
            {
              proposal_id: 'p2',
              pdf_id: 'pdf_1',
              row_id: 'row_1',
              column_name: 'Material',
              proposal_state: 'found',
              support_label: 'direct_evidence',
              review_decision: 'undecided',
            },
            {
              proposal_id: 'p1',
              pdf_id: 'pdf_1',
              row_id: 'row_0',
              column_name: 'Material',
              proposal_state: 'found',
              support_label: 'direct_evidence',
              review_decision: 'accept',
            },
          ],
          counters: { total: 2, visible: 2, reviewed: 1, pending: 1, undecided_visible: 1 },
          run_warning_categories: ['quote_page_no_highlight'],
        }),
      }
    }
    if (url.includes('/proposals/p2')) {
      return {
        ok: true,
        json: async () => ({
          proposal: {
            proposal_id: 'p2',
            row_id: 'row_1',
            column_name: 'Material',
            proposed_value: 'Steel',
            proposal_state: 'found',
            support_label: 'direct_evidence',
            review_decision: 'undecided',
          },
          row_context: { current_cell_value: '' },
          column_definition: { description: 'Material type' },
          support_label: 'direct_evidence',
          rationale: 'clear quote',
          calculation: '',
          primary_evidence: { evidence_id: 'ev_1', source_type: 'text', page: 1, quote_text: 'steel sample' },
          secondary_evidence: [],
          warning_status_flags: ['quote_page_no_highlight'],
        }),
      }
    }
    return { ok: true, json: async () => ({}) }
  })
  vi.stubGlobal('fetch', fetchMock)
}

describe('App review workspace', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    mockFetch()
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  afterEach(() => cleanup())

  it('shows run launch controls', () => {
    render(<App />)
    expect(screen.getByText('Run Launch and Setup')).toBeTruthy()
    expect(screen.getByText('Start run')).toBeTruthy()
  })

  it('renders review queue with ordering and quote fallback', async () => {
    render(<App />)
    fireEvent.click(screen.getAllByRole('button', { name: 'Review' })[0])
    await waitFor(() => expect(screen.getByText('Review Workspace')).toBeTruthy())
    await waitFor(() => expect(screen.getByText(/row_1 \/ Material/)).toBeTruthy())
    const queueButtons = screen.getAllByRole('button').filter((node) => node.textContent?.includes('row_'))
    expect(queueButtons[0].textContent).toContain('row_1')
    fireEvent.click(queueButtons[0])
    await waitFor(() => expect(screen.getByText('Highlight unavailable. Showing quote + page fallback.')).toBeTruthy())
  })
})
