import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ReviewWorkspace } from './ReviewWorkspace'
import type { EnrichedProposal, ProposalDetail, ReviewTableData, RunData } from '../types'

const mockListProposals = vi.fn()
const mockGetReviewProgress = vi.fn()
const mockGetProposalDetail = vi.fn()
const mockGetReviewTable = vi.fn()
const mockRecordDecision = vi.fn()
const mockBulkAccept = vi.fn()
const mockTriggerExport = vi.fn()
const mockDownloadDecisions = vi.fn()

vi.mock('../api/client', () => ({
  api: {
    isServed: () => true,
    downloadDecisions: () => mockDownloadDecisions(),
    listProposals: (...args: Parameters<typeof mockListProposals>) => mockListProposals(...args),
    getReviewProgress: (...args: Parameters<typeof mockGetReviewProgress>) => mockGetReviewProgress(...args),
    getProposalDetail: (...args: Parameters<typeof mockGetProposalDetail>) => mockGetProposalDetail(...args),
    getReviewTable: (...args: Parameters<typeof mockGetReviewTable>) => mockGetReviewTable(...args),
    recordDecision: (...args: Parameters<typeof mockRecordDecision>) => mockRecordDecision(...args),
    bulkAccept: (...args: Parameters<typeof mockBulkAccept>) => mockBulkAccept(...args),
    triggerExport: (...args: Parameters<typeof mockTriggerExport>) => mockTriggerExport(...args),
    openPdfInLocalViewer: vi.fn(),
    getPdfUrl: vi.fn().mockReturnValue('/pdf'),
    getFigureUrl: vi.fn().mockReturnValue('/figure'),
    getPageImageUrl: vi.fn().mockReturnValue('/page'),
    getMatchingSummary: vi.fn(),
  },
}))

vi.mock('./EvidenceViewer', () => ({
  EvidenceViewer: ({ evidence }: { evidence: { evidence_id?: string } | null }) => (
    <div data-testid="evidence-viewer">{evidence?.evidence_id ?? 'no-evidence'}</div>
  ),
}))

function makeRun(): RunData {
  return {
    run_id: 'standalone_run',
    status: 'completed',
    config_path: null,
    table_path: null,
    schema_path: null,
    pdf_dir: 'pdfs',
    output_dir: '.',
    verify_mode: false,
    eval_mode: false,
    run_mode: 'normal',
    provider_token: null,
    provider_locality: null,
    started_at: null,
    completed_at: null,
    current_stage: 'review',
    total_rows: 1,
    eligible_cells: 2,
    proposals_generated: 2,
    proposals_reviewed: 0,
    warnings: [],
    error_message: null,
    created_at: '2026-01-01T00:00:00Z',
  }
}

function makeProposal(id: string, columnName: string): EnrichedProposal {
  return {
    proposal_id: id,
    run_id: 'standalone_run',
    cell_id: `${id}_cell`,
    row_id: 'row_1',
    column_name: columnName,
    pdf_id: 'paper_a',
    proposal_status: 'value_proposed',
    evidence_status: 'direct_strong',
    review_bucket: 'review',
    reason_codes: [],
    proposed_value: `${columnName} value`,
    rationale: null,
    calculation: null,
    primary_evidence_id: `${id}_ev`,
    ordered_supporting_evidence_ids: [],
    evidence_ids: [`${id}_ev`],
    needs_more_evidence: false,
    is_verify_mode: false,
    created_at: '2026-01-01T00:00:00Z',
    latest_decision: null,
    is_figure_derived: false,
    is_fallback_evidence: false,
    paper_title: 'Paper A',
    paper_authors: 'Smith, J.',
    paper_year: '2026',
  }
}

function makeDetail(proposal: EnrichedProposal): ProposalDetail {
  return {
    proposal,
    evidence: [
      {
        evidence_id: `${proposal.proposal_id}_ev`,
        proposal_id: proposal.proposal_id,
        pdf_id: proposal.pdf_id,
        source_type: 'direct_quote',
        quote_text: 'quoted support',
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
    ],
    latest_decision: null,
    decision_history: [],
    row_context: { Title: 'Paper A' },
    column_definition: { column_name: proposal.column_name },
  }
}

function makeTable(proposals: EnrichedProposal[]): ReviewTableData {
  return {
    run_id: 'standalone_run',
    columns: [
      { name: 'Title', description: null, field_type: 'text', is_target: false },
      { name: 'Finding', description: null, field_type: 'text', is_target: true },
      { name: 'Outcome', description: null, field_type: 'text', is_target: true },
    ],
    rows: [
      {
        row_id: 'row_1',
        row_index: 0,
        paper_label: 'Paper A',
        title: 'Paper A',
        values: { Title: 'Paper A' },
        cells: {
          Title: { column_name: 'Title', original_value: 'Paper A', display_value: 'Paper A', display_status: 'unchanged', has_proposal: false, proposal: null },
          Finding: { column_name: 'Finding', original_value: '', display_value: proposals[0].proposed_value, display_status: 'pending', has_proposal: true, proposal: proposals[0] },
          Outcome: { column_name: 'Outcome', original_value: '', display_value: proposals[1].proposed_value, display_status: 'pending', has_proposal: true, proposal: proposals[1] },
        },
      },
    ],
    proposal_count: proposals.length,
  }
}

describe('standalone ReviewWorkspace', () => {
  const proposals = [makeProposal('p1', 'Finding'), makeProposal('p2', 'Outcome')]

  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mockListProposals.mockResolvedValue({ run_id: 'standalone_run', count: proposals.length, proposals })
    mockGetReviewProgress.mockResolvedValue({
      run_id: 'standalone_run',
      total_proposals: 2,
      reviewed: 0,
      pending: 2,
      accepted: 0,
      accepted_with_edit: 0,
      confirmed_no_data: 0,
      rejected: 0,
    })
    mockGetProposalDetail.mockImplementation((_runId: string, proposalId: string) => {
      const proposal = proposals.find((item) => item.proposal_id === proposalId) ?? proposals[0]
      return Promise.resolve(makeDetail(proposal))
    })
    mockGetReviewTable.mockResolvedValue(makeTable(proposals))
    mockBulkAccept.mockResolvedValue({ run_id: 'standalone_run', accepted_count: 2, decisions: [] })
    mockRecordDecision.mockResolvedValue({})
    mockTriggerExport.mockResolvedValue({
      run_id: 'standalone_run',
      exported_at: '2026-01-01T00:00:00Z',
      accepted_changes_count: 1,
      workbook_path: 'exports/final_table.csv',
      final_table_path: 'exports/final_table.csv',
      reviewed_bundle_path: 'exports/reviewed_bundle',
      audit_log_path: 'exports/audit_log.json',
      diagnostics_path: 'exports/diagnostics.json',
      unsupported_feature_warnings: [],
      unsupported_feature_warnings_count: 0,
      fidelity_boundary: 'standalone_reviewed_bundle',
    })
  })

  it('renders main review modes, separators, and reviewed bundle export', async () => {
    render(<ReviewWorkspace run={makeRun()} outputDir="" />)

    expect(await screen.findByRole('button', { name: 'By Paper' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'By Column' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'As Table' })).toBeInTheDocument()
    expect(screen.getAllByRole('separator')).toHaveLength(2)
    expect(screen.getByRole('button', { name: 'Download decisions' })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Export reviewed bundle/i }))
    expect(await screen.findByText(/Reviewed bundle: exports\/reviewed_bundle/i)).toBeInTheDocument()
  })

  it('shows guarded bulk accept confirmation for the visible view', async () => {
    render(<ReviewWorkspace run={makeRun()} outputDir="" />)
    fireEvent.click(await screen.findByRole('button', { name: 'By Paper' }))

    fireEvent.click(await screen.findByRole('button', { name: /Bulk accept 1 pending proposal/i }))

    expect(screen.getByText(/decision_source=human_bulk_accept/i)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Confirm bulk accept/i }))

    await waitFor(() => expect(mockBulkAccept).toHaveBeenCalled())
    expect(mockBulkAccept.mock.calls[0][1]).toEqual(['p1', 'p2'])
  })
})
