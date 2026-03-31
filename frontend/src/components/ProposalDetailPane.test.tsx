import { render, screen, fireEvent } from '@testing-library/react'
import { vi, describe, it, expect, beforeEach } from 'vitest'
import { ProposalDetailPane } from './ProposalDetailPane'
import type { ProposalDetail } from '../types'

// vi.mock factory must not reference outer variables (hoisting)
const mockGetProposalDetail = vi.fn()
vi.mock('../api/client', () => ({
  api: {
    getProposalDetail: (...args: Parameters<typeof mockGetProposalDetail>) => mockGetProposalDetail(...args),
  },
}))

const mockDetail: ProposalDetail = {
  proposal: {
    proposal_id: 'p1',
    run_id: 'r1',
    cell_id: 'c1',
    row_id: 'row-001',
    column_name: 'sample_size',
    pdf_id: 'paper-a',
    state: 'found',
    support: 'direct_evidence',
    proposed_value: '120',
    rationale: 'The sample size of 120 participants was stated in the Methods section.',
    calculation: null,
    primary_evidence_id: 'ev1',
    ordered_supporting_evidence_ids: ['ev1'],
    evidence_ids: ['ev1'],
    warning_flags: [],
    needs_more_evidence: false,
    created_at: '2024-01-01T00:00:00Z',
    latest_decision: null,
    warning_categories: [],
    is_figure_derived: false,
    is_fallback_evidence: false,
  },
  evidence: [
    {
      evidence_id: 'ev1',
      proposal_id: 'p1',
      pdf_id: 'paper-a',
      source_type: 'direct_quote',
      quote_text: 'A total of 120 participants were enrolled.',
      page_number: 3,
      exact_highlight_regions: null,
      approximate_highlight_regions: null,
      figure_ref: null,
      caption_text: null,
      crop_path: null,
      full_page_path: null,
      anchor_confidence: 0.95,
      evidence_rank: 1,
      source_label: 'Direct quote',
    },
    {
      evidence_id: 'ev2',
      proposal_id: 'p1',
      pdf_id: 'paper-a',
      source_type: 'inferred_reasoning',
      quote_text: null,
      page_number: 5,
      exact_highlight_regions: null,
      approximate_highlight_regions: null,
      figure_ref: null,
      caption_text: null,
      crop_path: null,
      full_page_path: null,
      anchor_confidence: null,
      evidence_rank: 2,
      source_label: 'Inferred reasoning',
    },
  ],
  latest_decision: null,
  decision_history: [],
  row_context: {
    title: 'A Study on Cognitive Load',
    authors: 'Smith, J.',
    year: 2022,
  },
  column_definition: {
    name: 'sample_size',
    description: 'Total number of participants',
  },
}

describe('ProposalDetailPane', () => {
  beforeEach(() => {
    mockGetProposalDetail.mockResolvedValue(mockDetail)
  })

  it('shows proposed value prominently', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        onDecisionRecorded={vi.fn()}
      />
    )
    await screen.findByText('120')
    expect(screen.getByText('120')).toBeInTheDocument()
  })

  it('renders rationale collapsed by default', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        onDecisionRecorded={vi.fn()}
      />
    )
    await screen.findByText('Rationale')
    expect(screen.queryByText('The sample size of 120 participants was stated in the Methods section.')).not.toBeInTheDocument()
  })

  it('expands rationale on click', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        onDecisionRecorded={vi.fn()}
      />
    )
    await screen.findByText('Rationale')
    fireEvent.click(screen.getByText('Rationale'))
    expect(screen.getByText('The sample size of 120 participants was stated in the Methods section.')).toBeInTheDocument()
  })

  it('shows evidence list with source type labels', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        onDecisionRecorded={vi.fn()}
      />
    )
    await screen.findByText('direct quote')
    expect(screen.getByText('direct quote')).toBeInTheDocument()
    expect(screen.getByText('inferred reasoning')).toBeInTheDocument()
  })

  it('shows row context (title and year)', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        onDecisionRecorded={vi.fn()}
      />
    )
    await screen.findByText('A Study on Cognitive Load')
    expect(screen.getByText('2022')).toBeInTheDocument()
  })

  it('highlights selected evidence item', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId="ev1"
        onEvidenceSelect={vi.fn()}
        onDecisionRecorded={vi.fn()}
      />
    )
    await screen.findByText('direct quote')
    const quoteCard = screen.getByText('direct quote').closest('button')!
    expect(quoteCard.className).toContain('border-blue-400')
  })

  it('shows placeholder when no proposal is selected', () => {
    render(
      <ProposalDetailPane
        proposalId={null}
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        onDecisionRecorded={vi.fn()}
      />
    )
    expect(screen.getByText('Select a proposal from the queue')).toBeInTheDocument()
  })
})
