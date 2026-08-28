import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ReviewWorkspace } from './ReviewWorkspace'
import type { EnrichedProposal, ProposalDetail, ReviewTableData, RunData } from '../types'

const mockListProposals = vi.fn()
const mockGetReviewProgress = vi.fn()
const mockGetProposalDetail = vi.fn()
const mockRecordDecision = vi.fn()
const mockTriggerExport = vi.fn()
const mockGetReviewTable = vi.fn()
const mockBulkAccept = vi.fn()
const mockBulkDecision = vi.fn()

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
    getReviewTable: (...args: Parameters<typeof mockGetReviewTable>) => mockGetReviewTable(...args),
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
    bulkAccept: (...args: Parameters<typeof mockBulkAccept>) => mockBulkAccept(...args),
    bulkDecision: (...args: Parameters<typeof mockBulkDecision>) => mockBulkDecision(...args),
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
    proposal_status: 'value_proposed',
    evidence_status: 'direct_strong',
    review_bucket: 'review',
    reason_codes: [],
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

function makeReviewTable(proposals: EnrichedProposal[]): ReviewTableData {
  const byRow = new Map<string, EnrichedProposal>()
  for (const proposal of proposals) byRow.set(proposal.row_id, proposal)
  return {
    run_id: 'run_1',
    proposal_count: proposals.length,
    columns: [
      { name: 'Title', description: null, field_type: null, is_target: false },
      { name: 'Outcome', description: 'Outcome description', field_type: 'text', is_target: true },
      { name: 'Notes', description: null, field_type: null, is_target: false },
    ],
    rows: ['row-1', 'row-2'].map((rowId, index) => {
      const proposal = byRow.get(rowId) ?? null
      return {
        row_id: rowId,
        row_index: index,
        paper_label: index === 0 ? 'Paper A' : 'Paper B',
        title: index === 0 ? 'Paper A' : 'Paper B',
        values: {
          Title: index === 0 ? 'Paper A' : 'Paper B',
          Outcome: '',
          Notes: 'unchanged note',
        },
        cells: {
          Title: {
            column_name: 'Title',
            original_value: index === 0 ? 'Paper A' : 'Paper B',
            display_value: index === 0 ? 'Paper A' : 'Paper B',
            display_status: 'unchanged',
            has_proposal: false,
            proposal: null,
          },
          Outcome: {
            column_name: 'Outcome',
            original_value: '',
            display_value: proposal?.latest_decision?.edited_value ?? proposal?.proposed_value ?? '',
            display_status: proposal?.latest_decision?.decision ?? 'pending',
            has_proposal: !!proposal,
            proposal: proposal ? { ...proposal, evidence_summary: { count: 2, primary_evidence_id: 'ev1', primary_source_type: 'direct_quote', primary_page_number: 1, primary_quote_text: 'quote' } } : null,
          },
          Notes: {
            column_name: 'Notes',
            original_value: 'unchanged note',
            display_value: 'unchanged note',
            display_status: 'unchanged',
            has_proposal: false,
            proposal: null,
          },
        },
      }
    }),
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
    window.localStorage.clear()
    mockListProposals.mockReset()
    mockGetReviewProgress.mockReset()
    mockGetProposalDetail.mockReset()
    mockRecordDecision.mockReset()
    mockTriggerExport.mockReset()
    mockGetReviewTable.mockReset()
    mockBulkAccept.mockReset()
    mockBulkDecision.mockReset()

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
    mockGetReviewTable.mockResolvedValue(makeReviewTable([proposalA, proposalB]))
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
    mockBulkAccept.mockResolvedValue({ run_id: 'run_1', accepted_count: 2, decisions: [] })
    mockBulkDecision.mockResolvedValue({ run_id: 'run_1', decision: 'rejected', recorded_count: 2, skipped_count: 0, skipped_proposal_ids: [], decisions: [] })
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

    fireEvent.click(await screen.findByTestId('review-table-cell-p1'))

    fireEvent.click(screen.getByText('Accept'))

    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('run_1', 'p1', { decision: 'accepted' }, './runs')
    })

    await waitFor(() => {
      expect(mockGetProposalDetail).toHaveBeenCalledWith('run_1', 'p2', './runs')
    })
  })

  it('opens in table mode by default and selects proposal cells for evidence inspection', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    expect(await screen.findByTestId('review-table-view')).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Table filter' })).toHaveValue('pending')
    fireEvent.click(await screen.findByTestId('review-table-cell-p1'))

    await waitFor(() => {
      expect(mockGetProposalDetail).toHaveBeenCalledWith('run_1', 'p1', './runs')
    })
    await waitFor(() => {
      expect(screen.getByTestId('evidence-viewer')).toHaveTextContent('ev1')
    })
  })

  it('applies a guarded action to an explicit Ctrl multi-cell selection', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(await screen.findByTestId('review-table-cell-p1'))
    fireEvent.click(screen.getByTestId('review-table-cell-p2'), { ctrlKey: true })

    expect(await screen.findByText('2 cells selected')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
    expect(screen.getByText(/decision_source=human_bulk_selection/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Confirm selected cells' }))

    await waitFor(() => {
      expect(mockBulkDecision).toHaveBeenCalledWith('run_1', ['p1', 'p2'], 'rejected', false, './runs')
    })
  })

  it('keeps details and diagnostics open while navigating between proposals', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(await screen.findByTestId('review-table-cell-p1'))
    const detailsSummary = await screen.findByText('Details')
    const diagnosticsSummary = screen.getAllByText('Diagnostics').find((element) => element.closest('details'))!
    fireEvent.click(detailsSummary)
    fireEvent.click(diagnosticsSummary)

    expect(detailsSummary.closest('details')).toHaveAttribute('open')
    expect(diagnosticsSummary.closest('details')).toHaveAttribute('open')

    fireEvent.click(screen.getByRole('button', { name: 'Next proposal' }))
    await waitFor(() => {
      expect(mockGetProposalDetail).toHaveBeenCalledWith('run_1', 'p2', './runs')
    })

    await waitFor(() => {
      expect(screen.getByText('Details').closest('details')).toHaveAttribute('open')
      expect(screen.getAllByText('Diagnostics').find((element) => element.closest('details'))?.closest('details')).toHaveAttribute('open')
    })
  })

  it('navigates in the active table order instead of the API proposal order', async () => {
    const proposalA = makeProposal({ proposal_id: 'p1', row_id: 'row-1', column_name: 'Outcome', proposed_value: 'A' })
    const proposalB = makeProposal({ proposal_id: 'p2', row_id: 'row-2', column_name: 'Outcome', proposed_value: 'B' })
    const proposalC = makeProposal({ proposal_id: 'p3', row_id: 'row-1', column_name: 'Notes', proposed_value: 'C' })

    function cellFor(proposal: EnrichedProposal) {
      return {
        column_name: proposal.column_name,
        original_value: '',
        display_value: proposal.proposed_value,
        display_status: 'pending',
        has_proposal: true,
        proposal: {
          ...proposal,
          evidence_summary: {
            count: 1,
            primary_evidence_id: 'ev1',
            primary_source_type: 'direct_quote',
            primary_page_number: 1,
            primary_quote_text: 'quote',
          },
        },
      }
    }

    mockListProposals.mockResolvedValue({
      run_id: 'run_1',
      count: 3,
      proposals: [proposalA, proposalB, proposalC],
    })
    mockGetReviewTable.mockResolvedValue({
      run_id: 'run_1',
      proposal_count: 3,
      columns: [
        { name: 'Title', description: null, field_type: null, is_target: false },
        { name: 'Outcome', description: null, field_type: null, is_target: true },
        { name: 'Notes', description: null, field_type: null, is_target: true },
      ],
      rows: [
        {
          row_id: 'row-1',
          row_index: 0,
          paper_label: 'Paper A',
          title: 'Paper A',
          values: { Title: 'Paper A', Outcome: '', Notes: '' },
          cells: {
            Title: {
              column_name: 'Title',
              original_value: 'Paper A',
              display_value: 'Paper A',
              display_status: 'unchanged',
              has_proposal: false,
              proposal: null,
            },
            Outcome: cellFor(proposalA),
            Notes: cellFor(proposalC),
          },
        },
        {
          row_id: 'row-2',
          row_index: 1,
          paper_label: 'Paper B',
          title: 'Paper B',
          values: { Title: 'Paper B', Outcome: '', Notes: '' },
          cells: {
            Title: {
              column_name: 'Title',
              original_value: 'Paper B',
              display_value: 'Paper B',
              display_status: 'unchanged',
              has_proposal: false,
              proposal: null,
            },
            Outcome: cellFor(proposalB),
            Notes: {
              column_name: 'Notes',
              original_value: '',
              display_value: '',
              display_status: 'unchanged',
              has_proposal: false,
              proposal: null,
            },
          },
        },
      ],
    } satisfies ReviewTableData)
    mockGetProposalDetail.mockImplementation(async (_runId: string, proposalId: string) => {
      const proposal = proposalId === 'p3' ? proposalC : proposalId === 'p2' ? proposalB : proposalA
      return makeDetail(proposal, proposal.proposed_value ?? proposal.proposal_id)
    })

    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(await screen.findByTestId('review-table-cell-p1'))
    fireEvent.click(screen.getByRole('button', { name: 'Next proposal' }))

    await waitFor(() => {
      expect(mockGetProposalDetail).toHaveBeenCalledWith('run_1', 'p3', './runs')
    })
  })

  it('switches left pane modes and persists the choice', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    expect(await screen.findByTestId('review-table-view')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'By Paper' }))

    await waitFor(() => {
      expect(screen.getByTestId('proposal-queue-scroll')).toBeInTheDocument()
    })
    expect(window.localStorage.getItem('papersToTable.review.leftPaneMode')).toBe('paper')
  })

  it('restores persisted left pane mode and filter', async () => {
    window.localStorage.setItem('papersToTable.review.leftPaneMode', 'paper')
    window.localStorage.setItem('papersToTable.review.leftPaneFilter', 'all')

    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    await waitFor(() => {
      expect(screen.getByTestId('proposal-queue-scroll')).toBeInTheDocument()
    })
    expect(screen.getByRole('combobox')).toHaveValue('all')
  })

  it('records a decision from a selected table cell and refreshes the grid', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(await screen.findByTestId('review-table-cell-p1'))
    fireEvent.click(await screen.findByRole('button', { name: 'Accept' }))

    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('run_1', 'p1', { decision: 'accepted' }, './runs')
    })
    await waitFor(() => {
      expect(mockGetReviewTable).toHaveBeenCalledTimes(2)
    })
  })

  it('accept keyboard shortcut works after selecting a table cell', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(await screen.findByTestId('review-table-cell-p1'))
    fireEvent.keyDown(document, { key: 'w' })

    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('run_1', 'p1', { decision: 'accepted' }, './runs')
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

  it('shows eval mode context in the toolbar', async () => {
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
  })

  it('renders contained scroll regions for queue, detail, evidence, and actions', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(await screen.findByRole('button', { name: 'By Paper' }))

    await waitFor(() => {
      expect(screen.getByTestId('proposal-queue-scroll')).toBeInTheDocument()
      expect(screen.getByTestId('proposal-detail-scroll')).toBeInTheDocument()
      expect(screen.getByTestId('evidence-viewer')).toBeInTheDocument()
      expect(screen.getByTestId('review-action-area')).toBeInTheDocument()
    })
  })

  it('moves warning count into diagnostics', async () => {
    const warningRun: RunData = {
      ...baseRun,
      warnings: [
        ...baseRun.warnings,
        { category: 'duplicate_row_conflict', message: 'Two rows matched the same PDF.' },
      ],
    }

    render(<ReviewWorkspace run={warningRun} outputDir="./runs" />)

    expect(screen.queryByText('3 warnings')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Diagnostics' }))
    expect(await screen.findByText('Run warnings')).toBeInTheDocument()
    expect(screen.getByText('3 warnings')).toBeInTheDocument()
  })

  it('shows export failure status without implying a completed export', async () => {
    mockTriggerExport.mockRejectedValueOnce(new Error('disk full'))

    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(screen.getByRole('button', { name: /Export reviewed workbook/i }))

    expect(await screen.findByText(/Export failed:/i)).toBeInTheDocument()
    expect(screen.getByText(/disk full/i)).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Workbook' })).not.toBeInTheDocument()
  })

  it('shows diagnostics summary when toggled', async () => {
    render(<ReviewWorkspace run={baseRun} outputDir="./runs" />)

    fireEvent.click(screen.getByRole('button', { name: 'Diagnostics' }))

    expect(await screen.findByText('Matching')).toBeInTheDocument()
    expect(screen.queryByText(/No unmatched PDFs in this run/i)).not.toBeInTheDocument()
  })
})
