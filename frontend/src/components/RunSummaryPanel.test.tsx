import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { RunSummaryPanel } from './RunSummaryPanel'
import type { RunData } from '../types'

const mockGetReviewProgress = vi.fn()
const mockGetMatchingSummary = vi.fn()

vi.mock('../api/client', () => ({
  api: {
    getReviewProgress: (...args: Parameters<typeof mockGetReviewProgress>) => mockGetReviewProgress(...args),
    getMatchingSummary: (...args: Parameters<typeof mockGetMatchingSummary>) => mockGetMatchingSummary(...args),
  },
}))

const baseRun: RunData = {
  run_id: 'run_1',
  status: 'completed_with_warnings',
  config_path: 'config.json',
  table_path: 'table.xlsx',
  schema_path: 'schema.csv',
  pdf_dir: 'pdfs',
  output_dir: './runs',
  verify_mode: false,
  provider_token: 'lm_studio',
  provider_locality: 'local',
  provider_mode: 'live_local',
  provider_text_model_id: 'text-model',
  provider_vision_model_id: null,
  provider_readiness_error: null,
  started_at: null,
  completed_at: null,
  current_stage: null,
  total_rows: 4,
  eligible_cells: 6,
  proposals_generated: 9,
  proposals_reviewed: 0,
  warnings: [
    { category: 'partial_extraction', message: 'Parser fallback used for paper_1.' },
    { category: 'duplicate_row_conflict', message: 'Duplicate row conflict: paper_3' },
    { category: 'fallback_evidence_used', message: '2 proposal(s) require evidence fallback review.' },
  ],
  error_message: null,
  created_at: '2024-01-01T00:00:00Z',
}

describe('RunSummaryPanel', () => {
  beforeEach(() => {
    mockGetReviewProgress.mockReset()
    mockGetMatchingSummary.mockReset()
    mockGetReviewProgress.mockResolvedValue({
      run_id: 'run_1',
      total_proposals: 6,
      reviewed: 2,
      accepted: 1,
      accepted_with_edit: 0,
      confirmed_no_data: 0,
      rejected: 1,
      pending: 4,
    })
    mockGetMatchingSummary.mockResolvedValue({
      run_id: 'run_1',
      total_pdfs: 4,
      matched: 2,
      unmatched: 1,
      ambiguous: 0,
      duplicate_row_conflict: 1,
    })
  })

  it('shows actionable review counts as the primary headline', async () => {
    render(<RunSummaryPanel run={baseRun} outputDir="./runs" />)

    await waitFor(() => {
      expect(screen.getByText(/Actionable review:/i)).toBeInTheDocument()
    })
    expect(screen.getByText('2 / 6')).toBeInTheDocument()
    expect(screen.getByText(/attempted 9/i)).toBeInTheDocument()
  })

  it('surfaces parsing, duplicate-conflict, and evidence-fallback truth', async () => {
    render(<RunSummaryPanel run={baseRun} outputDir="./runs" />)

    await waitFor(() => {
      expect(screen.getByText(/parsing fallback/i)).toBeInTheDocument()
    })
    expect(screen.getByText(/duplicate conflicts/i)).toBeInTheDocument()
    expect(screen.getByText(/evidence fallback/i)).toBeInTheDocument()
  })
})
