/**
 * T094 — Frontend tests for Batch 5 review workspace components.
 *
 * Covers:
 * - Queue filtering and ordering rules
 * - Nonlinear review behavior
 * - Quote+page fallback rendering
 * - Figure-evidence rendering
 * - Run-summary display
 * - Bulk-accept confirmation flow
 */
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'

// API mocks
vi.mock('../api', () => ({
  listProposals: vi.fn(),
  getProposalDetail: vi.fn(),
  recordDecision: vi.fn(),
  bulkAccept: vi.fn(),
  getProgress: vi.fn(),
  getAvailableDownloads: vi.fn(),
  getRunSummaryFull: vi.fn(),
  recomputeSummaries: vi.fn(),
  getMatchingSummary: vi.fn(),
  getMatchingUnresolved: vi.fn(),
  getPdfUrl: vi.fn().mockReturnValue('http://test/pdf'),
  getPageImageUrl: vi.fn().mockReturnValue('http://test/page.png'),
  getFigureCropUrl: vi.fn().mockReturnValue('http://test/crop.png'),
  getRunSummaryDownloadUrl: vi.fn().mockReturnValue('http://test/dl/run-summary'),
  getReviewerSummaryDownloadUrl: vi.fn().mockReturnValue('http://test/dl/reviewer-summary'),
  getWorkbookDownloadUrl: vi.fn().mockReturnValue('http://test/dl/workbook'),
  getAuditLogDownloadUrl: vi.fn().mockReturnValue('http://test/dl/audit-log'),
  createRun: vi.fn(),
  listRuns: vi.fn().mockResolvedValue([]),
  getRunSummary: vi.fn(),
  getInputSummary: vi.fn(),
}))

import {
  getAvailableDownloads,
  getRunSummaryFull,
} from '../api'
import { ProposalQueue } from './ProposalQueue'
import { EvidenceViewer } from './EvidenceViewer'
import { RunSummaryPanel } from './RunSummaryPanel'
import { ReviewActionArea } from './ReviewActionArea'
import type { ProposalListItem, ProposalDetail, EvidenceRecord } from '../types'

// ─── Fixtures ────────────────────────────────────────────────────────────────

function makeProposal(overrides: Partial<ProposalListItem> = {}): ProposalListItem {
  return {
    proposal_id: 'p1',
    run_id: 'run1',
    pdf_id: 'pdf1',
    row_id: 'row1',
    column_name: 'Column A',
    cell_id: 'cell1',
    source_mode: 'text',
    proposal_state: 'actionable',
    support_label: 'moderate_evidence',
    proposed_value: '42',
    status_flags: [],
    latest_decision: 'undecided',
    ...overrides,
  }
}

function makeDetail(overrides: Partial<ProposalDetail> = {}): ProposalDetail {
  return {
    proposal_id: 'p1',
    run_id: 'run1',
    pdf_id: 'pdf1',
    row_id: 'row1',
    column_name: 'Column A',
    cell_id: 'cell1',
    source_mode: 'text',
    proposal_state: 'actionable',
    support_label: 'moderate_evidence',
    proposed_value: '42',
    rationale: 'Found in methods section',
    calculation: null,
    needs_more_evidence: false,
    status_flags: [],
    row_context: { row_id: 'row1', Author: 'Smith' },
    column_definition: { column_name: 'Column A', description: 'Sample size' },
    current_cell_value: null,
    evidence: [],
    latest_decision: 'undecided',
    latest_decision_record: null,
    ...overrides,
  }
}

// ─── ProposalQueue tests ──────────────────────────────────────────────────────

describe('ProposalQueue', () => {
  it('renders proposal list with column name and row id', () => {
    const proposals = [
      makeProposal({ proposal_id: 'p1', column_name: 'Column A', row_id: 'row1' }),
      makeProposal({ proposal_id: 'p2', column_name: 'Column B', row_id: 'row2' }),
    ]
    render(<ProposalQueue proposals={proposals} selectedId={null} onSelect={vi.fn()} loading={false} />)
    expect(screen.getByText('Column A')).toBeInTheDocument()
    expect(screen.getByText('Column B')).toBeInTheDocument()
  })

  it('shows pending and reviewed counters', () => {
    const proposals = [
      makeProposal({ proposal_id: 'p1', latest_decision: 'undecided' }),
      makeProposal({ proposal_id: 'p2', latest_decision: 'accept' }),
    ]
    render(<ProposalQueue proposals={proposals} selectedId={null} onSelect={vi.fn()} loading={false} />)
    expect(screen.getByText(/1 pending/)).toBeInTheDocument()
    expect(screen.getByText(/1 reviewed/)).toBeInTheDocument()
  })

  it('orders undecided proposals before decided ones', () => {
    const proposals = [
      makeProposal({ proposal_id: 'p1', column_name: 'Z Col', latest_decision: 'accept', row_id: 'row1' }),
      makeProposal({ proposal_id: 'p2', column_name: 'A Col', latest_decision: 'undecided', row_id: 'row2' }),
    ]
    render(<ProposalQueue proposals={proposals} selectedId={null} onSelect={vi.fn()} loading={false} />)
    const listbox = screen.getByRole('listbox', { name: 'Proposals' })
    const items = within(listbox).getAllByRole('option')
    // Undecided (p2/A Col) should come before decided (p1/Z Col)
    expect(items[0].textContent).toContain('A Col')
    expect(items[1].textContent).toContain('Z Col')
  })

  it('orders actionable before blocked within undecided', () => {
    const proposals = [
      makeProposal({ proposal_id: 'p1', column_name: 'Blocked', proposal_state: 'blocked', latest_decision: 'undecided', row_id: 'row1' }),
      makeProposal({ proposal_id: 'p2', column_name: 'Actionable', proposal_state: 'actionable', latest_decision: 'undecided', row_id: 'row2' }),
    ]
    render(<ProposalQueue proposals={proposals} selectedId={null} onSelect={vi.fn()} loading={false} />)
    const listbox = screen.getByRole('listbox', { name: 'Proposals' })
    const items = within(listbox).getAllByRole('option')
    expect(items[0].textContent).toContain('Actionable')
    expect(items[1].textContent).toContain('Blocked')
  })

  it('calls onSelect when a proposal is clicked', () => {
    const onSelect = vi.fn()
    const proposals = [makeProposal({ proposal_id: 'p1', column_name: 'Col A' })]
    render(<ProposalQueue proposals={proposals} selectedId={null} onSelect={onSelect} loading={false} />)
    const listbox = screen.getByRole('listbox', { name: 'Proposals' })
    fireEvent.click(within(listbox).getByRole('option'))
    expect(onSelect).toHaveBeenCalledWith('p1')
  })

  it('filters by decision status', () => {
    const proposals = [
      makeProposal({ proposal_id: 'p1', column_name: 'Pending Col', latest_decision: 'undecided' }),
      makeProposal({ proposal_id: 'p2', column_name: 'Accepted Col', latest_decision: 'accept' }),
    ]
    render(<ProposalQueue proposals={proposals} selectedId={null} onSelect={vi.fn()} loading={false} />)
    // Change filter to show only accepted
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'accept' } })
    const listbox = screen.getByRole('listbox', { name: 'Proposals' })
    expect(within(listbox).queryByText('Pending Col')).not.toBeInTheDocument()
    expect(within(listbox).getByText('Accepted Col')).toBeInTheDocument()
  })

  it('shows empty message when no proposals match filter', () => {
    const proposals = [makeProposal({ proposal_id: 'p1', latest_decision: 'reject' })]
    render(<ProposalQueue proposals={proposals} selectedId={null} onSelect={vi.fn()} loading={false} />)
    fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'accept' } })
    expect(screen.getByText(/No proposals match/)).toBeInTheDocument()
  })

  it('shows loading state', () => {
    render(<ProposalQueue proposals={[]} selectedId={null} onSelect={vi.fn()} loading={true} />)
    expect(screen.getByText(/Loading proposals/)).toBeInTheDocument()
  })
})

// ─── EvidenceViewer tests ─────────────────────────────────────────────────────

describe('EvidenceViewer', () => {
  it('shows empty state when no evidence', () => {
    render(<EvidenceViewer runId="run1" evidence={[]} />)
    expect(screen.getByText(/No evidence records/)).toBeInTheDocument()
  })

  it('renders quote+page fallback for text_quote evidence without highlight (T088)', () => {
    const evidence: EvidenceRecord[] = [{
      evidence_id: 'ev1',
      proposal_id: 'p1',
      pdf_id: 'pdf1',
      source_type: 'text_quote',
      page: 5,
      quote_text: 'The sample size was 42 participants.',
      highlight: null,
      figure_ref: null,
      caption_text: null,
      crop_path: null,
      full_page_path: null,
      anchor_confidence: null,
    }]
    render(<EvidenceViewer runId="run1" evidence={evidence} />)
    // Quote fallback shows page ref and quote text
    expect(screen.getByText(/Page 5/)).toBeInTheDocument()
    expect(screen.getByText(/42 participants/)).toBeInTheDocument()
    expect(screen.getByText(/No highlight coordinates/)).toBeInTheDocument()
  })

  it('renders figure evidence crop (T089)', () => {
    const evidence: EvidenceRecord[] = [{
      evidence_id: 'ev1',
      proposal_id: 'p1',
      pdf_id: 'pdf1',
      source_type: 'figure_crop',
      page: 3,
      quote_text: null,
      highlight: null,
      figure_ref: 'Fig. 2',
      caption_text: 'Figure 2: Sample distribution',
      crop_path: '/path/to/crop.png',
      full_page_path: null,
      anchor_confidence: null,
    }]
    render(<EvidenceViewer runId="run1" evidence={evidence} />)
    expect(screen.getByText('Figure: Fig. 2')).toBeInTheDocument()
    expect(screen.getByText(/Sample distribution/)).toBeInTheDocument()
  })

  it('shows tab for each evidence item when multiple exist', () => {
    const evidence: EvidenceRecord[] = [
      {
        evidence_id: 'ev1', proposal_id: 'p1', pdf_id: 'pdf1',
        source_type: 'text_quote', page: 1, quote_text: 'text1', highlight: null,
        figure_ref: null, caption_text: null, crop_path: null, full_page_path: null, anchor_confidence: null,
      },
      {
        evidence_id: 'ev2', proposal_id: 'p1', pdf_id: 'pdf1',
        source_type: 'figure_crop', page: 2, quote_text: null, highlight: null,
        figure_ref: 'Fig. 1', caption_text: 'caption', crop_path: null, full_page_path: null, anchor_confidence: null,
      },
    ]
    render(<EvidenceViewer runId="run1" evidence={evidence} />)
    expect(screen.getByText(/Text p\.1/)).toBeInTheDocument()
    expect(screen.getByText(/Figure Fig\. 1/)).toBeInTheDocument()
  })
})

// ─── ReviewActionArea tests ───────────────────────────────────────────────────

describe('ReviewActionArea', () => {
  const baseProps = {
    onDecision: vi.fn().mockResolvedValue(undefined),
    onNext: vi.fn(),
    onPrev: vi.fn(),
    onBulkAccept: vi.fn().mockResolvedValue(undefined),
    hasPrev: true,
    hasNext: true,
    isBusy: false,
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders accept, reject, and accept-with-edit buttons', () => {
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} />)
    expect(screen.getByLabelText('Accept')).toBeInTheDocument()
    expect(screen.getByLabelText('Reject')).toBeInTheDocument()
    expect(screen.getByLabelText('Accept with edit')).toBeInTheDocument()
  })

  it('disables accept for blocked proposals (T090)', () => {
    render(<ReviewActionArea proposal={makeDetail({ proposal_state: 'blocked' })} {...baseProps} />)
    expect(screen.getByLabelText('Accept')).toBeDisabled()
    expect(screen.getByLabelText('Reject')).not.toBeDisabled()
  })

  it('disables accept when proposed_value is null (T090)', () => {
    render(<ReviewActionArea proposal={makeDetail({ proposed_value: null })} {...baseProps} />)
    expect(screen.getByLabelText('Accept')).toBeDisabled()
  })

  it('calls onDecision with accept when Accept is clicked', async () => {
    const onDecision = vi.fn().mockResolvedValue(undefined)
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} onDecision={onDecision} />)
    fireEvent.click(screen.getByLabelText('Accept'))
    await waitFor(() => expect(onDecision).toHaveBeenCalledWith('accept', undefined))
  })

  it('calls onDecision with reject when Reject is clicked', async () => {
    const onDecision = vi.fn().mockResolvedValue(undefined)
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} onDecision={onDecision} />)
    fireEvent.click(screen.getByLabelText('Reject'))
    await waitFor(() => expect(onDecision).toHaveBeenCalledWith('reject', undefined))
  })

  it('shows bulk accept confirmation dialog (T090a)', async () => {
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} />)
    fireEvent.click(screen.getByText(/Bulk accept visible undecided/))
    expect(await screen.findByText(/Cannot be undone/i)).toBeInTheDocument()
    expect(screen.getByText(/Confirm bulk accept/)).toBeInTheDocument()
    expect(screen.getByText('Cancel')).toBeInTheDocument()
  })

  it('calls onBulkAccept when confirmed (T090a)', async () => {
    const onBulkAccept = vi.fn().mockResolvedValue(undefined)
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} onBulkAccept={onBulkAccept} />)
    fireEvent.click(screen.getByText(/Bulk accept visible undecided/))
    fireEvent.click(await screen.findByText(/Confirm bulk accept/))
    await waitFor(() => expect(onBulkAccept).toHaveBeenCalled())
  })

  it('cancels bulk accept when Cancel is clicked', async () => {
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} />)
    fireEvent.click(screen.getByText(/Bulk accept visible undecided/))
    await screen.findByText(/Confirm bulk accept/)
    fireEvent.click(screen.getByText('Cancel'))
    expect(screen.queryByText(/Confirm bulk accept/)).not.toBeInTheDocument()
  })

  it('shows error when accept-with-edit is clicked without a value (T090a)', async () => {
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} />)
    fireEvent.click(screen.getByLabelText('Accept with edit'))
    expect(await screen.findByText(/Enter an edited value/)).toBeInTheDocument()
  })

  it('calls onDecision with accept_with_edit and edited value', async () => {
    const onDecision = vi.fn().mockResolvedValue(undefined)
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} onDecision={onDecision} />)
    fireEvent.change(screen.getByLabelText('Edited value'), { target: { value: '99' } })
    fireEvent.click(screen.getByLabelText('Accept with edit'))
    await waitFor(() => expect(onDecision).toHaveBeenCalledWith('accept_with_edit', '99'))
  })

  it('disables nav buttons when hasPrev/hasNext are false', () => {
    render(<ReviewActionArea proposal={makeDetail()} {...baseProps} hasPrev={false} hasNext={false} />)
    expect(screen.getByLabelText('Previous proposal')).toBeDisabled()
    expect(screen.getByLabelText('Next proposal')).toBeDisabled()
  })
})

// ─── RunSummaryPanel tests ────────────────────────────────────────────────────

describe('RunSummaryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(getRunSummaryFull as ReturnType<typeof vi.fn>).mockResolvedValue({
      run_id: 'run1',
      status: 'completed',
      operator_status: 'completed',
      message: null,
      progress: { stage: null, item: null },
      config_path: '/path/config.json',
      verify_mode: true,
      provider_name: 'LMStudio',
      model_name: 'mistral',
      provider_locality: 'local',
      counts: {
        proposals_generated: 10,
        reviewed_proposals: 5,
        accepted_as_is: 3,
        accepted_with_edit: 1,
        rejected: 1,
        pending: 5,
        changed_cells_exported: 0,
      },
      pdfs_processed: 4,
      pdfs_matched: 3,
      pdfs_unmatched: 1,
      pdfs_ambiguous: 0,
      run_status_flags: [],
    })
    ;(getAvailableDownloads as ReturnType<typeof vi.fn>).mockResolvedValue({
      run_summary: true,
      reviewer_summary: true,
      workbook: false,
      audit_log: false,
    })
  })

  it('shows PDF and proposal counts (T082)', async () => {
    render(<RunSummaryPanel runId="run1" />)
    expect(await screen.findByText('4')).toBeInTheDocument() // PDFs processed
    expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1) // Matched PDFs and/or accepted
    expect(screen.getByText('10')).toBeInTheDocument() // Proposals generated
  })

  it('shows verify mode and provider info (T082)', async () => {
    render(<RunSummaryPanel runId="run1" />)
    await screen.findByText('On') // Verify mode
    expect(screen.getByText('LMStudio')).toBeInTheDocument()
    expect(screen.getByText('mistral')).toBeInTheDocument()
  })

  it('shows available download links and disabled state for unavailable downloads (T082)', async () => {
    render(<RunSummaryPanel runId="run1" />)
    expect(await screen.findByText('Run summary JSON')).toBeInTheDocument()
    expect(screen.getByText('Reviewer summary JSON')).toBeInTheDocument()
    expect(screen.getByText(/Updated workbook.*export not yet run/)).toBeInTheDocument()
    expect(screen.getByText(/Audit log.*export not yet run/)).toBeInTheDocument()
  })

  it('shows not-yet-available message when summary is unavailable', async () => {
    ;(getRunSummaryFull as ReturnType<typeof vi.fn>).mockResolvedValue(null)
    render(<RunSummaryPanel runId="run1" />)
    expect(await screen.findByText(/not yet available/)).toBeInTheDocument()
  })
})
