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

function makeProposal(overrides: Partial<EnrichedProposal> = {}): EnrichedProposal {
  return {
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
    is_verify_mode: false,
    existing_value: null,
    provider_mode: 'text',
    created_at: '2024-01-01T00:00:00Z',
    latest_decision: null,
    warning_categories: [],
    is_figure_derived: false,
    is_fallback_evidence: false,
    paper_title: 'A sample MPRA paper',
    paper_authors: 'Smith, J.',
    paper_year: '2024',
    ...overrides,
  }
}

const mockProposal = makeProposal()

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
        visibleProposals={[mockProposal, makeProposal({ proposal_id: 'p2' })]}
        focusEditSignal={0}
      />
    )
    const acceptBtn = screen.getByText('Accept')
    fireEvent.click(acceptBtn)
    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('r1', 'p1', { decision: 'accepted' }, './runs')
    })
    expect(onDecisionRecorded).toHaveBeenCalledWith({ autoAdvance: true })
  })

  it('reject button calls recordDecision with rejected', async () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposals={[mockProposal]}
        focusEditSignal={0}
      />
    )
    fireEvent.click(screen.getByText('Reject'))
    await waitFor(() => {
      expect(mockRecordDecision).toHaveBeenCalledWith('r1', 'p1', { decision: 'rejected' }, './runs')
    })
  })

  it('bulk accept shows confirmation dialog with pending count only', () => {
    // p2 is pending, p3 has a decision — bulk count should be 1 (only p2)
    const decidedProposal = makeProposal({
      proposal_id: 'p3',
      latest_decision: {
        review_decision_id: 'd3',
        run_id: 'r1',
        proposal_id: 'p3',
        cell_id: 'c3',
        decision: 'accepted',
        resolution_reason: null,
        edited_value: null,
        reviewer_note: null,
        decided_at: '2024-01-01T00:00:00Z',
      },
    })
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposals={[mockProposal, makeProposal({ proposal_id: 'p2' }), decidedProposal]}
        focusEditSignal={0}
      />
    )
    const bulkBtn = screen.getByText(/Bulk accept 1 pending/i)
    fireEvent.click(bulkBtn)
    expect(screen.getByText(/Confirm bulk accept/i)).toBeInTheDocument()
    expect(screen.getByText(/decision_source=human_bulk_accept/i)).toBeInTheDocument()
  })

  it('accept-with-edit shows text input when clicked', () => {
    render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposals={[mockProposal]}
        focusEditSignal={0}
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
        visibleProposals={[mockProposal]}
        focusEditSignal={0}
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
        visibleProposals={[mockProposal]}
        focusEditSignal={0}
      />
    )
    fireEvent.click(screen.getByText('Next →'))
    expect(onNext).toHaveBeenCalled()
  })

  it('focusEditSignal opens and focuses edit input', async () => {
    const { rerender } = render(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposals={[mockProposal]}
        focusEditSignal={0}
      />
    )

    rerender(
      <ReviewActionArea
        proposal={mockProposal}
        runId="r1"
        outputDir="./runs"
        onDecisionRecorded={onDecisionRecorded}
        onNext={onNext}
        visibleProposals={[mockProposal]}
        focusEditSignal={1}
      />
    )

    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Enter corrected value/i)).toHaveFocus()
    })
  })
})
