import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ReviewWorkspace } from './ReviewWorkspace'
import type { EnrichedProposal, ProposalDetail, RunData } from '../types'

const mockListProposals = vi.fn()
const mockGetReviewProgress = vi.fn()
const mockGetProposalDetail = vi.fn()
const mockRecordDecision = vi.fn()
const mockTriggerExport = vi.fn()

vi.mock('../api/client', () => ({
  api: {
    listProposals: (...args: Parameters<typeof mockListProposals>) => mockListProposals(...args),
    getReviewProgress: (...args: Parameters<typeof mockGetReviewProgress>) => mockGetReviewProgress(...args),
    getMatchingSummary: vi.fn().mockResolvedValue({
      run_id: 'run_1',
      total_pdfs: 2,
      matched: 2,
      unmatched: 0,
      ambiguous: 0,
      duplicate_row_conflict: 0,
    }),
    getProposalDetail: (...args: Parameters<typeof mockGetProposalDetail>) => mockGetProposalDetail(...args),
    recordDecision: (...args: Parameters<typeof mockRecordDecision>) => mockRecordDecision(...args),
    triggerExport: (...args: Parameters<typeof mockTriggerExport>) => mockTriggerExport(...args),
    getWorkbookDownloadUrl: vi.fn().mockReturnValue('/downloads/workbook'),
    getAuditLogDownloadUrl: vi.fn().mockReturnValue('/downloads/audit-log'),
    getRunSummaryDownloadUrl: vi.fn().mockReturnValue('/downloads/run-summary'),
    getReviewerSummaryDownloadUrl: vi.fn().mockReturnValue('/downloads/reviewer-summary'),
    openPdfInLocalViewer: vi.fn(),
    getPdfUrl: vi.fn().mockReturnValue('/pdf'),
    getFigureUrl: vi.fn().mockReturnValue('/fig'),
    getUnmatched: vi.fn().mockResolvedValue({ unmatched: [] }),
    getAmbiguous: vi.fn().mockResolvedValue({ ambiguous: [] }),
    getConflicts: vi.fn().mockResolvedValue({ conflicts: [] }),
    bulkAccept: vi.fn(),
  },
}))

vi.mock('./EvidenceViewer', () => ({
  EvidenceViewer: ({ evidence }: { evidence: { evidence_id?: string } | null }) => (
    <div data-testid="evidence-viewer">{evidence?.evidence_id ?? 'no-evidence'}</div>
  ),
}))

function makeProposal(overrides: Partial<EnrichedProposal> = {}): EnrichedProposal {
  return {
    proposal_id: 'p1',
    run_id: 'run_1',
    cell_id: 'c1',
    row_id: 'row-1',
    column_name: 'Outcome',
    pdf_id: 'paper-1',
    state: 'found',
    support: 'direct_evidence',
    proposed_value: 'Positive',
    rationale: null,
    calculation: null,
    primary_evidence_id: 'ev1',
    ordered_supporting_evidence_ids: ['ev2'],
    evidence_ids: ['ev1', 'ev2'],
    warning_flags: [],
    needs_more_evidence: false,
    is_verify_mode: false,
    existing_value: null,
    provider_mode: 'live_local',
    created_at: '2024-01-01T00:00:00Z',
    latest_decision: null,
    warning_categories: [],
    is_figure_derived: false,
    is_fallback_evidence: false,
    paper_title: 'Paper A',
    paper_authors: 'Smith, J.',
    paper_year: '2024',
    ...overrides,
  }
}

function makeDetail(proposal: EnrichedProposal, title: string): ProposalDetail {
  return {
    proposal,
    evidence: [
      {
        evidence_id: 'ev1',
        proposal_id: proposal.proposal_id,
        pdf_id: proposal.pdf_id,
        source_type: 'direct_quote',
        quote_text: `${title} quote`,
        page_number: 1,
        exact_highlight_regions: null,
        approximate_highlight_regions: null,
        figure_ref: null,
        caption_text: null,
        crop_path: null,
        full_page_path: null,
        anchor_confidence: 0.9,
        evidence_rank: 1,
        source_label: 'Direct quote',
      },
      {
        evidence_id: 'ev2',
        proposal_id: proposal.proposal_id,
        pdf_id: proposal.pdf_id,
        source_type: 'quote_plus_page',
        quote_text: `${title} fallback`,
        page_number: 2,
        exact_highlight_regions: null,
        approximate_highlight_regions: null,
        figure_ref: null,
        caption_text: null,
        crop_path: null,
        full_page_path: null,
        anchor_confidence: 0.5,
        evidence_rank: 2,
        source_label: 'Quote + page',
      },
    ],
    latest_decision: proposal.latest_decision,
    decision_history: [],
    row_context: { Title: title, Authors: 'Smith, J.', 'Publication Year': '2024' },
    column_definition: { name: proposal.column_name, description: 'Outcome description' },
  }
}

const baseRun: RunData = {
  run_id: 'run_1',
  status: 'completed_with_warnings',
  config_path: 'config.json',
  table_path: 'table.xlsx',
  schema_path: 'schema.csv',
  pdf_dir: 'pdfs',
  output_dir: './runs',
  verify_mode: false,
  eval_mode: false,
  run_mode: 'normal',
  provider_token: 'lm_studio',
  provider_locality: 'local',
  provider_mode: 'live_local',
  provider_text_model_id: 'text-model',
  provider_vision_model_id: null,
  provider_readiness_error: null,
  started_at: null,
  completed_at: null,
  current_stage: null,
  total_rows: 2,
  eligible_cells: 2,
  proposals_generated: 4,
  proposals_reviewed: 0,
  warnings: [
    { category: 'partial_extraction', message: 'Parser fallback used for paper-1.' },
    { category: 'fallback_evidence_used', message: '1 proposal(s) require evidence fallback review.' },
  ],
  error_message: null,
  created_at: '2024-01-01T00:00:00Z',
}

describe('ReviewWorkspace', () => {
  beforeEach(() => {
    mockListProposals.mockReset()
    mockGetReviewProgress.mockReset()
    mockGetProposalDetail.mockReset()
    mockRecordDecision.mockReset()
    mockTriggerExport.mockReset()

    const proposalA = makeProposal()
    const proposalB = makeProposal({
      proposal_id: 'p2',
      cell_id: 'c2',
      row_id: 'row-2',
      pdf_id: 'paper-2',
      paper_title: 'Paper B',
    })

    mockListProposals.mockResolvedValue({
      run_id: 'run_1',
      count: 2,
      proposals: [proposalA, proposalB],
    })
    mockGetReviewProgress.mockResolvedValue({
      run_id: 'run_1',
      total_proposals: 2,
      reviewed: 0,
      accepted: 0,
      accepted_with_edit: 0,
      confirmed_no_data: 0,
      rejected: 0,
      pending: 2,
    })
    mockGetProposalDetail.mockImplementation(async (_runId: string, proposalId: string) => {
      return proposalId === 'p2' ? makeDetail(proposalB, 'Paper B') : makeDetail(proposalA, 'Paper A')
    })
    mockRecordDecision.mockResolvedValue({ review_decision_id: 'd1' })
    mockTriggerExport.mockResolvedValue({
      run_id: 'run_1',
      exported_at: '2024-01-02T00:00:00Z',
      accepted_changes_count: 1,
      workbook_path: '/tmp/workbook.xlsx',
      audit_log_path: '/tmp/audit.json',
      diagnostics_path: '/tmp/diag.json',
      unsupported_feature_warnings: [],
      unsupported_feature_warnings_count: 0,
      fidelity_boundary: 'content only',
    })
  })

  it('auto-advances to the next proposal after an explicit decision', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    await waitFor(() => {
      expect(screen.getByText('Paper A')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Accept'))

    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('run_1', 'p1', { decision: 'accepted' }, './runs')
    })

    await waitFor(() => {
      expect(screen.getByText('Paper B')).toBeInTheDocument()
    })
  })

  it('triggers export explicitly and shows download links', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(screen.getByRole('button', { name: /Export reviewed workbook/i }))

    await waitFor(() => {
      expect(mockTriggerExport).toHaveBeenCalledWith('run_1', './runs')
    })

    expect(await screen.findByRole('link', { name: 'Workbook' })).toHaveAttribute('href', '/downloads/workbook')
    expect(screen.getByRole('link', { name: 'Audit log' })).toHaveAttribute('href', '/downloads/audit-log')
  })

  it('shows eval context in the toolbar without implying in-app scoring', async () => {
    const evalRun: RunData = {
      ...baseRun,
      eval_mode: true,
      run_mode: 'eval',
      eval_artifacts: {
        gold_table: {
          snapshot_path: 'inputs/gold_table.xlsx',
        },
        masked_working_table: {
          path: 'inputs/masked_working_table.xlsx',
        },
      },
    }

    render(<ReviewWorkspace run={evalRun} outputDir="./runs" />)

    await waitFor(() => {
      expect(screen.getByText(/Eval mode/i)).toBeInTheDocument()
    })

    expect(screen.getByText(/artifact-only, no in-app scoring/i)).toBeInTheDocument()
    expect(screen.getByText(/gold: inputs\/gold_table.xlsx/i)).toBeInTheDocument()
    expect(screen.getByText(/masked: inputs\/masked_working_table.xlsx/i)).toBeInTheDocument()
  })

  it('surfaces duplicate-conflict warning truth in the toolbar', async () => {
    const warningRun: RunData = {
      ...baseRun,
      warnings: [
        ...baseRun.warnings,
        { category: 'duplicate_row_conflict', message: 'Two rows matched the same PDF.' },
      ],
    }

    render(<ReviewWorkspace run={warningRun} outputDir="./runs" />)

    await waitFor(() => {
      expect(screen.getAllByText(/duplicate conflicts/i).length).toBeGreaterThan(0)
    })
  })

  it('shows export failure status without implying a completed export', async () => {
    mockTriggerExport.mockRejectedValueOnce(new Error('disk full'))

    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(screen.getByRole('button', { name: /Export reviewed workbook/i }))

    expect(await screen.findByText(/Export failed:/i)).toBeInTheDocument()
    expect(screen.getByText(/disk full/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Workbook' })).not.toBeInTheDocument()
  })

  it('shows the unresolved inspection empty state when toggled', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(screen.getByRole('button', { name: 'Unresolved' }))

    expect(await screen.findByText(/No unresolved matching issues/i)).toBeInTheDocument()
  })
})
