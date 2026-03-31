import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ReviewActionArea } from './ReviewActionArea'
import type { EnrichedProposal } from '../types'

// vi.mock factory cannot reference outer variables (hoisted)
const mockRecordDecision = vi.fn()
const mockBulkAccept = vi.fn()
vi.mock('../api/client', () => ({
  api: {
    recordDecision: (...args: Parameters<typeof mockRecordDecision>) => mockRecordDecision(...args),
    bulkAccept: (...args: Parameters<typeof mockBulkAccept>) => mockBulkAccept(...args),
  },
}))

const mockProposal: EnrichedProposal = {
  proposal_id: 'p1',
  run_id: 'r1',
  cell_id: 'c1',
  row_id: 'row-001',
  column_name: 'sample_size',
  pdf_id: 'paper-a',
  state: 'found',
  support: 'direct_evidence',
  proposed_value: '120',
  rationale: null,
  calculation: null,
  primary_evidence_id: null,
  ordered_supporting_evidence_ids: [],
  evidence_ids: [],
  warning_flags: [],
  needs_more_evidence: false,
  created_at: '2024-01-01T00:00:00Z',
  latest_decision: null,
  warning_categories: [],
  is_figure_derived: false,
  is_fallback_evidence: false,
}

describe('ReviewActionArea', () => {
  const onDecisionRecorded = vi.fn()
  const onNext = vi.fn()

  beforeEach(() => {
    onDecisionRecorded.mockClear()
    onNext.mockClear()
    mockRecordDecision.mockClear()
    mockBulkAccept.mockClear()
    mockRecordDecision.mockResolvedValue({ review_decision_id: 'd1' })
    mockBulkAccept.mockResolvedValue({ accepted_count: 2, decisions: [] })
  })

  it('accept button calls recordDecision with accepted', async () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposalIds={['p1', 'p2']}
      />
    )
    const acceptBtn = screen.getByText('Accept')
    fireEvent.click(acceptBtn)
    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('r1', 'p1', { decision: 'accepted' }, './runs')
    })
    expect(onDecisionRecorded).toHaveBeenCalled()
  })

  it('reject button calls recordDecision with rejected', async () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposalIds={['p1']}
      />
    )
    fireEvent.click(screen.getByText('Reject'))
    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('r1', 'p1', { decision: 'rejected' }, './runs')
    })
  })

  it('bulk accept shows confirmation dialog with count', () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposalIds={['p1', 'p2', 'p3']}
      />
    )
    const bulkBtn = screen.getByText(/Bulk accept 2 pending/i)
    fireEvent.click(bulkBtn)
    expect(screen.getByText(/Confirm bulk accept/i)).toBeInTheDocument()
  })

  it('accept-with-edit shows text input when clicked', () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposalIds={['p1']}
      />
    )
    fireEvent.click(screen.getByText('Accept with Edit'))
    expect(screen.getByPlaceholderText(/Enter corrected value/i)).toBeInTheDocument()
  })

  it('accept-with-edit submits edited value on Save', async () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposalIds={['p1']}
      />
    )
    fireEvent.click(screen.getByText('Accept with Edit'))
    const input = screen.getByPlaceholderText(/Enter corrected value/i)
    fireEvent.change(input, { target: { value: '150' } })
    fireEvent.click(screen.getByText('Save'))
    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith(
        'r1',
        'p1',
        { decision: 'accepted_with_edit', edited_value: '150' },
        './runs'
      )
    })
  })

  it('next button calls onNext', () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposalIds={['p1']}
      />
    )
    fireEvent.click(screen.getByText('Next →'))
    expect(onNext).toHaveBeenCalled()
  })
})
