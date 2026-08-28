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
    proposal_status: 'value_proposed',
    evidence_status: 'direct_strong',
    review_bucket: 'review',
    reason_codes: [],
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
    proposal_status: 'value_proposed',
    evidence_status: 'inferred_strong',
    review_bucket: 'review',
    reason_codes: [],
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
    proposal_status: 'value_proposed',
    evidence_status: 'direct_strong',
    review_bucket: 'review',
    reason_codes: [],
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
  {
    proposal_id: 'p4',
    run_id: 'r1',
    cell_id: 'c4',
    row_id: 'row-003',
    column_name: 'integration_site',
    pdf_id: 'paper-c',
    proposal_status: 'unresolved',
    evidence_status: 'no_evidence',
    review_bucket: 'attention',
    reason_codes: ['insufficient_evidence'],
    proposed_value: null,
    rationale: 'Relevant chunks were inspected but were not decisive.',
    calculation: null,
    primary_evidence_id: null,
    ordered_supporting_evidence_ids: [],
    evidence_ids: [],
    warning_flags: [],
    needs_more_evidence: false,
    created_at: '2024-01-01T00:00:00Z',
    latest_decision: null,
    warning_categories: ['weak_evidence'],
    is_figure_derived: false,
    is_fallback_evidence: false,
    is_verify_mode: false,
    existing_value: null,
    provider_mode: 'text',
    paper_title: 'A paper with an unresolved target cell',
    paper_authors: 'Nolan, M.',
    paper_year: '2022',
  },
  {
    proposal_id: 'p5',
    run_id: 'r1',
    cell_id: 'c5',
    row_id: 'row-004',
    column_name: 'architecture_figure',
    pdf_id: 'paper-d',
    proposal_status: 'value_proposed',
    evidence_status: 'inferred_strong',
    review_bucket: 'review',
    reason_codes: [],
    proposed_value: 'Fig. 2 architecture',
    rationale: null,
    calculation: null,
    primary_evidence_id: 'ev5',
    ordered_supporting_evidence_ids: [],
    evidence_ids: ['ev5'],
    warning_flags: ['figure_derived'],
    needs_more_evidence: false,
    created_at: '2024-01-01T00:00:00Z',
    latest_decision: null,
    warning_categories: [],
    is_figure_derived: true,
    is_fallback_evidence: false,
    is_verify_mode: false,
    existing_value: null,
    provider_mode: 'text',
    paper_title: 'A paper with figure evidence',
    paper_authors: 'Patel, S.',
    paper_year: '2021',
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
        selectedProposalIds={[]}
        onSelect={onSelect}
        onSelectionChange={vi.fn()}
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
    mockListProposals.mockResolvedValue({ proposals: mockProposals, run_id: 'r1', count: mockProposals.length })
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

  it('compact card shows categorized evidence badge', async () => {
    renderQueue()
    await screen.findAllByTitle('Evidence: direct strong')
    expect(screen.getAllByTitle('Evidence: direct strong').length).toBeGreaterThan(0)
  })

  it('shows unresolved no-evidence target cells in reviewable pending queue', async () => {
    renderQueue()
    await screen.findByText('integration_site')
    expect(screen.getByText('No value proposed')).toBeInTheDocument()
  })

  it('shows semantic conclusions on compact cards', async () => {
    const conclusionProposals: EnrichedProposal[] = [
      { ...mockProposals[0], proposal_id: 'p-no-data', cell_id: 'c-no-data', column_name: 'assay_absence', proposal_status: 'no_data', evidence_status: 'direct_strong', review_bucket: 'review', proposed_value: null },
      { ...mockProposals[0], proposal_id: 'p-na', cell_id: 'c-na', column_name: 'schema_scope', proposal_status: 'not_applicable', evidence_status: 'not_applicable', review_bucket: 'attention', proposed_value: null },
      { ...mockProposals[0], proposal_id: 'p-error', cell_id: 'c-error', column_name: 'provider_result', proposal_status: 'error', evidence_status: 'not_applicable', review_bucket: 'attention', proposed_value: null },
    ]
    mockListProposals.mockResolvedValueOnce({
      proposals: conclusionProposals,
      run_id: 'r1',
      count: conclusionProposals.length,
    })

    renderQueue({ filter: 'all' })

    await screen.findByText('No data reported')
    expect(screen.getByText('Not applicable')).toBeInTheDocument()
    expect(screen.getByText('Extraction error')).toBeInTheDocument()
  })

  it('does not show proposal-level warning or figure icons on compact cards', async () => {
    renderQueue({ filter: 'all' })
    await screen.findByText('architecture_figure')
    expect(screen.queryByLabelText('Evidence: figure or vision')).toBeNull()
    expect(screen.queryByLabelText('Warning present')).toBeNull()
  })

  it('renders inferred strong evidence with the green compact dot', async () => {
    renderQueue({ filter: 'all' })
    const inferredStrongDots = await screen.findAllByTitle('Evidence: inferred strong')
    expect(inferredStrongDots[0].querySelector('.bg-emerald-500')).not.toBeNull()
  })

  it('attention filter is driven by non-green proposal or evidence dots', async () => {
    const categoryOnlyProposal: EnrichedProposal = {
      ...mockProposals[0],
      proposal_id: 'p-warning-category-only',
      cell_id: 'c-warning-category-only',
      column_name: 'warning_category_only',
      review_bucket: 'review',
      warning_categories: ['weak_evidence'],
    }
    const attentionProposal: EnrichedProposal = {
      ...mockProposals[0],
      proposal_id: 'p-attention',
      cell_id: 'c-attention',
      column_name: 'attention_bucket',
      evidence_status: 'direct_weak',
      review_bucket: 'review',
      warning_categories: [],
    }
    mockListProposals.mockResolvedValueOnce({
      proposals: [categoryOnlyProposal, attentionProposal],
      run_id: 'r1',
      count: 2,
    })

    renderQueue({ filter: 'needs_attention' })
    await screen.findByText('attention_bucket')
    expect(screen.queryByText('warning_category_only')).toBeNull()
  })

  it('does not keep the selected proposal visible when it does not match the active filter', async () => {
    const pendingProposal = {
      ...mockProposals[0],
      proposal_id: 'p-selected',
      column_name: 'selected_pending',
      latest_decision: null,
    }
    mockListProposals.mockResolvedValueOnce({
      proposals: [pendingProposal],
      run_id: 'r1',
      count: 1,
    })

    renderQueue({ selectedProposalId: 'p-selected', filter: 'accepted' })

    await screen.findByText('No proposals match the current filter.')
    expect(screen.queryByText('selected_pending')).toBeNull()
  })

  it('calls onSelect when a proposal card is clicked', async () => {
    renderQueue()
    await screen.findByText('sample_size')
    const card = screen.getByText('sample_size').closest('button')!
    fireEvent.click(card)
    expect(onSelect).toHaveBeenCalledWith('p1')
  })
})

