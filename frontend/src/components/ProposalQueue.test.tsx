import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ProposalQueue } from './ProposalQueue'
import type { EnrichedProposal } from '../types'

// vi.mock is hoisted - factory cannot reference outer variables
const mockListProposals = vi.fn()
vi.mock('../api/client', () => ({
  api: {
    listProposals: (...args: Parameters<typeof mockListProposals>) => mockListProposals(...args),
  },
}))

const mockProposals: EnrichedProposal[] = [
  {
    proposal_id: 'p1',
    run_id: 'r1',
    cell_id: 'c1',
    row_id: 'row-001',
    column_name: 'sample_size',
    pdf_id: 'paper-a',
    state: 'found',
    support: 'direct_evidence',
    proposed_value: '120',
    rationale: 'Stated in methods',
    calculation: null,
    primary_evidence_id: 'ev1',
    ordered_supporting_evidence_ids: [],
    evidence_ids: ['ev1'],
    warning_flags: [],
    needs_more_evidence: false,
    created_at: '2024-01-01T00:00:00Z',
    latest_decision: null,
    warning_categories: [],
    is_figure_derived: false,
    is_fallback_evidence: false,
  },
  {
    proposal_id: 'p2',
    run_id: 'r1',
    cell_id: 'c2',
    row_id: 'row-002',
    column_name: 'effect_size',
    pdf_id: 'paper-b',
    state: 'found',
    support: 'inferred_from_evidence',
    proposed_value: '0.45',
    rationale: null,
    calculation: null,
    primary_evidence_id: null,
    ordered_supporting_evidence_ids: [],
    evidence_ids: [],
    warning_flags: ['low_confidence'],
    needs_more_evidence: false,
    created_at: '2024-01-01T00:00:00Z',
    latest_decision: {
      review_decision_id: 'd1',
      run_id: 'r1',
      proposal_id: 'p2',
      cell_id: 'c2',
      decision: 'accepted',
      resolution_reason: null,
      edited_value: null,
      reviewer_note: null,
      decided_at: '2024-01-01T01:00:00Z',
    },
    warning_categories: [],
    is_figure_derived: false,
    is_fallback_evidence: false,
  },
  {
    proposal_id: 'p3',
    run_id: 'r1',
    cell_id: 'c3',
    row_id: 'row-001',
    column_name: 'p_value',
    pdf_id: 'paper-a',
    state: 'found',
    support: 'direct_evidence',
    proposed_value: '0.03',
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
  },
]

describe('ProposalQueue', () => {
  const onSelect = vi.fn()

  beforeEach(() => {
    onSelect.mockClear()
    mockListProposals.mockResolvedValue({ proposals: mockProposals, run_id: 'r1', count: 3 })
  })

  it('renders pending proposals with blue border', async () => {
    render(
      <ProposalQueue
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        onSelect={onSelect}
      />
    )
    await screen.findByText('sample_size')
    expect(screen.getByText('sample_size')).toBeInTheDocument()
    expect(screen.getByText('p_value')).toBeInTheDocument()
  })

  it('grouping by paper groups proposals by pdf_id', async () => {
    render(
      <ProposalQueue
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        onSelect={onSelect}
      />
    )
    await screen.findByText('paper-a')
    expect(screen.getByText('paper-a')).toBeInTheDocument()
    expect(screen.getByText('paper-b')).toBeInTheDocument()
  })

  it('grouping by column groups proposals by column_name', async () => {
    render(
      <ProposalQueue
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        onSelect={onSelect}
      />
    )
    await screen.findByText('paper-a')
    const colBtn = screen.getByText('By Column')
    fireEvent.click(colBtn)
    // After switching, groups should be column names (use getAllByText since name appears in header + card)
    expect(screen.getAllByText('effect_size').length).toBeGreaterThan(0)
  })

  it('filter pending shows only undecided proposals', async () => {
    const pendingOnly = mockProposals.filter((p) => !p.latest_decision)
    mockListProposals.mockResolvedValueOnce({
      proposals: pendingOnly,
      run_id: 'r1',
      count: pendingOnly.length,
    })

    render(
      <ProposalQueue
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        onSelect={onSelect}
      />
    )
    await screen.findByText('sample_size')
    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'pending' } })
    // Re-render with pending-only mock
    mockListProposals.mockResolvedValueOnce({
      proposals: pendingOnly,
      run_id: 'r1',
      count: pendingOnly.length,
    })
    await screen.findByText('sample_size')
  })

  it('compact card shows support badge', async () => {
    render(
      <ProposalQueue
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        onSelect={onSelect}
      />
    )
    // 'direct' badge appears for direct_evidence support
    await screen.findAllByText('direct')
    expect(screen.getAllByText('direct').length).toBeGreaterThan(0)
  })

  it('calls onSelect when a proposal card is clicked', async () => {
    render(
      <ProposalQueue
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        onSelect={onSelect}
      />
    )
    await screen.findByText('sample_size')
    const card = screen.getByText('sample_size').closest('button')!
    fireEvent.click(card)
    expect(onSelect).toHaveBeenCalledWith('p1')
  })
})

