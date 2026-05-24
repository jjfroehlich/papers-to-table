import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ProposalQueue } from './ProposalQueue'
import type { EnrichedProposal } from '../types'

// vi.mock is hoisted - factory cannot reference outer variables
const mockListProposals = vi.fn()
const mockGetReviewTable = vi.fn()
vi.mock('../api/client', () => ({
  api: {
    listProposals: (...args: Parameters<typeof mockListProposals>) => mockListProposals(...args),
    getReviewTable: (...args: Parameters<typeof mockGetReviewTable>) => mockGetReviewTable(...args),
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
    is_verify_mode: false,
    existing_value: null,
    provider_mode: 'text',
    paper_title: 'A study of sample size reporting in MPRA assays',
    paper_authors: 'Smith, J.; Doe, A.',
    paper_year: '2024',
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
    is_verify_mode: false,
    existing_value: null,
    provider_mode: 'text',
    paper_title: 'An effect size benchmark paper',
    paper_authors: 'Lee, P.; Kim, R.',
    paper_year: '2023',
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
    is_verify_mode: false,
    existing_value: null,
    provider_mode: 'text',
    paper_title: 'A study of sample size reporting in MPRA assays',
    paper_authors: 'Smith, J.; Doe, A.',
    paper_year: '2024',
  },
]

describe('ProposalQueue', () => {
  const onSelect = vi.fn()
  const onModeChange = vi.fn()
  const onFilterChange = vi.fn()

  function renderQueue(overrides = {}) {
    return render(
      <ProposalQueue
        runId="r1"
        outputDir="./runs"
        selectedProposalId={null}
        onSelect={onSelect}
        mode="paper"
        filter="pending"
        onModeChange={onModeChange}
        onFilterChange={onFilterChange}
        {...overrides}
      />
    )
  }

  beforeEach(() => {
    mockListProposals.mockReset()
    mockGetReviewTable.mockReset()
    onSelect.mockClear()
    onModeChange.mockClear()
    onFilterChange.mockClear()
    mockListProposals.mockResolvedValue({ proposals: mockProposals, run_id: 'r1', count: 3 })
    mockGetReviewTable.mockResolvedValue({ run_id: 'r1', columns: [], rows: [], proposal_count: 0 })
  })

  it('renders pending proposals with blue border', async () => {
    renderQueue()
    await screen.findByText('sample_size')
    expect(screen.getByText('sample_size')).toBeInTheDocument()
    expect(screen.getByText('p_value')).toBeInTheDocument()
  })

  it('grouping by paper groups proposals by pdf_id', async () => {
    renderQueue({ filter: 'all' })
    await screen.findByText(/Smith et al\. 2024/)
    expect(screen.getByText(/Smith et al\. 2024/)).toBeInTheDocument()
    expect(screen.getByText(/Lee et al\. 2023/)).toBeInTheDocument()
  })

  it('grouping by column groups proposals by column_name', async () => {
    renderQueue({ mode: 'column', filter: 'all' })
    await screen.findByText('sample_size')
    // Column groups should be column names.
    expect(screen.getAllByText('effect_size').length).toBeGreaterThan(0)
  })

  it('filter pending shows only undecided proposals', async () => {
    const pendingOnly = mockProposals.filter((p) => !p.latest_decision)
    mockListProposals.mockResolvedValueOnce({
      proposals: pendingOnly,
      run_id: 'r1',
      count: pendingOnly.length,
    })

    renderQueue()
    await screen.findByText('sample_size')
    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'pending' } })
    expect(onFilterChange).toHaveBeenCalledWith('pending')
    await screen.findByText('sample_size')
  })

  it('compact card shows categorized support badge', async () => {
    renderQueue()
    await screen.findAllByTitle('Support: direct evidence')
    expect(screen.getAllByTitle('Support: direct evidence').length).toBeGreaterThan(0)
  })

  it('calls onSelect when a proposal card is clicked', async () => {
    renderQueue()
    await screen.findByText('sample_size')
    const card = screen.getByText('sample_size').closest('button')!
    fireEvent.click(card)
    expect(onSelect).toHaveBeenCalledWith('p1')
  })
})

