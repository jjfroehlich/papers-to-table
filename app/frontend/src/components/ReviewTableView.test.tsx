import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ReviewTableView } from './ReviewTableView'
import type { ReviewTableData, ReviewTableProposal } from '../types'

const mockGetReviewTable = vi.fn()
vi.mock('../api/client', () => ({
  api: {
    getReviewTable: (...args: Parameters<typeof mockGetReviewTable>) => mockGetReviewTable(...args),
  },
}))

const baseProposal: ReviewTableProposal = {
  proposal_id: 'p1',
  run_id: 'r1',
  cell_id: 'c1',
  row_id: 'row-1',
  column_name: 'field',
  pdf_id: 'paper-1',
  proposal_status: 'value_proposed',
  evidence_status: 'direct_strong',
  review_bucket: 'review',
  reason_codes: [],
  proposed_value: 'value',
  rationale: null,
  calculation: null,
  primary_evidence_id: null,
  ordered_supporting_evidence_ids: [],
  evidence_ids: [],
  warning_flags: [],
  needs_more_evidence: false,
  is_verify_mode: false,
  provider_mode: 'text',
  created_at: '2024-01-01T00:00:00Z',
  latest_decision: null,
  warning_categories: [],
  is_figure_derived: false,
  is_fallback_evidence: false,
}

function tableWith(proposals: ReviewTableProposal[]): ReviewTableData {
  return {
    run_id: 'r1',
    proposal_count: proposals.length,
    columns: proposals.map((proposal) => ({
      name: proposal.column_name,
      description: null,
      field_type: null,
      is_target: true,
    })),
    rows: [
      {
        row_id: 'row-1',
        row_index: 0,
        paper_label: 'paper-1',
        title: 'Paper one',
        values: {},
        cells: Object.fromEntries(
          proposals.map((proposal) => [
            proposal.column_name,
            {
              column_name: proposal.column_name,
              original_value: null,
              display_value: proposal.proposed_value,
              display_status: 'pending',
              has_proposal: true,
              proposal,
            },
          ])
        ),
      },
    ],
  }
}

describe('ReviewTableView', () => {
  beforeEach(() => {
    mockGetReviewTable.mockReset()
  })

  it('renders semantic conclusions instead of blank table values', async () => {
    const proposals: ReviewTableProposal[] = [
      {
        ...baseProposal,
        proposal_id: 'p-no-data',
        cell_id: 'c-no-data',
        column_name: 'no_data_field',
        proposal_status: 'no_data',
        evidence_status: 'direct_strong',
        proposed_value: null,
      },
      {
        ...baseProposal,
        proposal_id: 'p-unresolved',
        cell_id: 'c-unresolved',
        column_name: 'unresolved_field',
        proposal_status: 'unresolved',
        evidence_status: 'no_evidence',
        review_bucket: 'attention',
        proposed_value: 'unclear',
      },
    ]
    mockGetReviewTable.mockResolvedValueOnce(tableWith(proposals))

    render(
      <ReviewTableView
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        filter="all"
        onFilterChange={vi.fn()}
        onSelect={vi.fn()}
      />
    )

    await screen.findByText('No data reported')
    expect(screen.getByText('No value proposed')).toBeInTheDocument()
    expect(screen.queryByText('unclear')).not.toBeInTheDocument()
  })

  it('excludes diagnostic records from reviewable table filters', async () => {
    const diagnosticProposal: ReviewTableProposal = {
      ...baseProposal,
      proposal_id: 'p-diagnostic',
      cell_id: 'c-diagnostic',
      proposal_status: 'unresolved',
      evidence_status: 'no_evidence',
      review_bucket: 'diagnostic',
      reason_codes: ['retrieval_empty'],
      proposed_value: null,
    }
    mockGetReviewTable.mockResolvedValueOnce(tableWith([diagnosticProposal]))

    render(
      <ReviewTableView
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        filter="all"
        onFilterChange={vi.fn()}
        onSelect={vi.fn()}
      />
    )

    await screen.findByText('No rows match this filter.')
    expect(screen.queryByText('No value proposed')).not.toBeInTheDocument()
  })
})
