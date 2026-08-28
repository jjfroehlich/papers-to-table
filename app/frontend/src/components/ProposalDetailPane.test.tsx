import { fireEvent, render, screen } from '@testing-library/react'
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
    proposal_status: 'value_proposed',
    evidence_status: 'direct_strong',
    review_bucket: 'review',
    reason_codes: [],
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
    is_verify_mode: false,
    existing_value: '84',
    provider_mode: 'text',
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

function renderDetail(detail: ProposalDetail) {
  mockGetProposalDetail.mockResolvedValueOnce(detail)
  render(
    <ProposalDetailPane
      proposalId={detail.proposal.proposal_id}
      runId={detail.proposal.run_id}
      outputDir="./runs"
      selectedEvidenceId={null}
      onEvidenceSelect={vi.fn()}
    />
  )
}

function detailFor(overrides: Partial<ProposalDetail['proposal']>, evidence: ProposalDetail['evidence'] = mockDetail.evidence): ProposalDetail {
  return {
    ...mockDetail,
    proposal: {
      ...mockDetail.proposal,
      ...overrides,
    },
    evidence,
  }
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
        
      />
    )
    await screen.findByText('120')
    expect(screen.getByText('120')).toBeInTheDocument()
  })

  it('does not crash when warning categories are omitted from the payload', async () => {
    const { warning_categories: _warningCategories, ...proposalWithoutWarningCategories } = mockDetail.proposal
    mockGetProposalDetail.mockResolvedValueOnce({
      ...mockDetail,
      proposal: proposalWithoutWarningCategories,
    })

    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )

    await screen.findByText('120')
    expect(screen.getByText('120')).toBeInTheDocument()
  })

  it('renders rationale as a normal reviewer-facing section', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        
      />
    )
    await screen.findByText('Rationale')
    expect(screen.getByText('The sample size of 120 participants was stated in the Methods section.')).toBeInTheDocument()
    expect(screen.queryByText('Context considered')).not.toBeInTheDocument()
  })

  it('uses Value as the section header', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )
    await screen.findByText('Value')
    expect(screen.queryByText('Value or conclusion')).not.toBeInTheDocument()
  })

  it('shows the clear field name before the value and keeps supporting details collapsed', async () => {
    renderDetail(mockDetail)

    const fieldHeading = await screen.findByText('Field')
    const valueHeading = screen.getByText('Value')
    expect(fieldHeading.compareDocumentPosition(valueHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(fieldHeading.closest('section')).toHaveClass('text-center', 'bg-slate-200')
    expect(screen.getAllByText('sample_size')[0]).toBeVisible()
    expect(screen.getByText('Field and description')).not.toBeVisible()
    expect(screen.getByText('Paper')).not.toBeVisible()
    expect(screen.getByText('Diagnostics')).toBeVisible()

    fireEvent.click(screen.getByText('Details'))
    expect(screen.getByText('Field and description')).toBeVisible()
    expect(screen.getByText('Total number of participants')).toBeVisible()
    expect(screen.getByText('Paper')).toBeVisible()
    expect(screen.getByText('Review:')).not.toBeVisible()
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByText('Review:')).toBeVisible()
  })

  it('shows simplified evidence heading', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        
      />
    )
    await screen.findByText('Evidence')
    expect(screen.queryByText('Evidence stack')).not.toBeInTheDocument()
    expect(screen.queryByText(/^[12] items?$/)).not.toBeInTheDocument()
  })

  it('shows evidence list with source type labels', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        
      />
    )
    await screen.findByTitle('Evidence: direct quote')
    expect(screen.getByTitle('Evidence: direct quote')).toBeInTheDocument()
    expect(screen.getByTitle('Evidence: inferred reasoning')).toBeInTheDocument()
  })

  it('shows row context (title and year)', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        
      />
    )
    await screen.findByText('A Study on Cognitive Load')
    expect(screen.getByText(/Smith, J\.\s*·\s*2022/)).toBeInTheDocument()
  })

  it('does not show verify comparison when verify mode is off', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )
    await screen.findByText('120')
    expect(screen.queryByText('Verify mode')).not.toBeInTheDocument()
  })

  it('shows verify comparison only for verify proposals', async () => {
    mockGetProposalDetail.mockResolvedValueOnce({
      ...mockDetail,
      proposal: {
        ...mockDetail.proposal,
        is_verify_mode: true,
      },
    })

    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )
    await screen.findByText('Verify mode')
    expect(screen.getByText('84')).toBeInTheDocument()
    expect(screen.getAllByText('120')).toHaveLength(2)
  })

  it('highlights selected evidence item', async () => {
    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId="ev1"
        onEvidenceSelect={vi.fn()}
        
      />
    )
    await screen.findByTitle('Evidence: direct quote')
    const quoteCard = screen.getByTitle('Evidence: direct quote').closest('button')!
    expect(quoteCard.className).toContain('border-amber-300')
  })

  it('shows placeholder when no proposal is selected', () => {
    render(
      <ProposalDetailPane
        proposalId={null}
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
        
      />
    )
    expect(screen.getByText('Select a proposal from the queue.')).toBeInTheDocument()
  })

  it('does not display unresolved placeholder text as a proposed value', async () => {
    mockGetProposalDetail.mockResolvedValueOnce({
      ...mockDetail,
      proposal: {
        ...mockDetail.proposal,
        proposal_status: 'unresolved',
        evidence_status: 'no_evidence',
        review_bucket: 'attention',
        proposed_value: 'unclear',
        reason_codes: ['insufficient_evidence'],
        rationale: '- Relevant passages were inspected, but none settled the field.',
        evidence_ids: [],
        ordered_supporting_evidence_ids: [],
        primary_evidence_id: null,
        candidate_answers: [
          {
            candidate_id: 'cand_1',
            value: 'unclear',
            candidate_status: 'unclear',
            source: 'first_pass_text',
            confidence_rationale: '- Relevant passages were inspected, but none settled the field.',
          },
        ],
        selection_diagnostics: {
          attempted: false,
          succeeded: false,
          skip_reason: 'not_needed_or_disabled',
          candidate_count: 1,
        },
      },
      evidence: [],
    })

    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )

    await screen.findByText('No value proposed')
    expect(screen.queryByText('unclear')).not.toBeInTheDocument()
    expect(screen.queryByText('No decisive evidence was found for this target cell.')).not.toBeInTheDocument()
    expect(screen.queryByText('No usable evidence found for this target cell.')).not.toBeInTheDocument()
  })

  it('shows rationale by default and retrieval diagnostics directly in collapsed details', async () => {
    mockGetProposalDetail.mockResolvedValueOnce({
      ...mockDetail,
      proposal: {
        ...mockDetail.proposal,
        proposal_status: 'unresolved',
        evidence_status: 'no_evidence',
        review_bucket: 'attention',
        proposed_value: null,
        reason_codes: ['insufficient_evidence'],
        rationale: '- The retrieved passages were relevant but not decisive.',
        evidence_ids: [],
        ordered_supporting_evidence_ids: [],
        primary_evidence_id: null,
        retrieval_diagnostics: {
          classification: 'reasoning_gap',
          retrieved_chunk_count: 5,
          chunks_considered: 5,
        },
      },
      evidence: [],
    })

    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )

    await screen.findByText('Rationale')
    expect(screen.getByText('- The retrieved passages were relevant but not decisive.')).toBeInTheDocument()
    expect(screen.getByText('No formal evidence items were persisted for this proposal.')).toBeInTheDocument()
    expect(screen.getByText('Retrieval')).not.toBeVisible()
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByText('Retrieval')).toBeVisible()
    expect(screen.getByText('Relevant evidence was found, but it did not support a decisive conclusion.')).toBeVisible()
    expect(screen.getByText('5 passages')).toBeVisible()
    expect(screen.queryByText('retrieved chunk count')).not.toBeInTheDocument()
  })

  it('renders readable reason labels with explanatory titles', async () => {
    mockGetProposalDetail.mockResolvedValueOnce({
      ...mockDetail,
      proposal: {
        ...mockDetail.proposal,
        proposal_status: 'unresolved',
        evidence_status: 'no_evidence',
        review_bucket: 'attention',
        proposed_value: null,
        reason_codes: ['conflicting_evidence', 'approximate_anchor', 'retrieval_empty'],
        evidence_ids: [],
        ordered_supporting_evidence_ids: [],
        primary_evidence_id: null,
      },
      evidence: [],
    })

    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )

    await screen.findByText('Conflicting evidence')
    expect(screen.getByTitle('The system found competing or inconsistent candidates.')).toBeInTheDocument()
    expect(screen.getByText('Approximate anchor')).toBeInTheDocument()
    expect(screen.getByText('Retrieval empty')).toBeInTheDocument()
  })

  it('places reason-code chips in the collapsed diagnostics details', async () => {
    renderDetail(
      detailFor({
        proposal_status: 'unresolved',
        evidence_status: 'no_evidence',
        review_bucket: 'attention',
        proposed_value: null,
        reason_codes: ['insufficient_evidence'],
      })
    )

    await screen.findByText('Insufficient evidence')
    const diagnostics = screen.getByText('Diagnostics').closest('details')!
    expect(diagnostics).toContainElement(screen.getByText('Insufficient evidence'))
    expect(screen.getByText('Insufficient evidence')).not.toBeVisible()
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByText('Insufficient evidence')).toBeVisible()
  })

  it('shows metadata conflict candidates directly in collapsed details', async () => {
    mockGetProposalDetail.mockResolvedValueOnce({
      ...mockDetail,
      proposal: {
        ...mockDetail.proposal,
        column_name: 'Journal',
        proposal_status: 'unresolved',
        evidence_status: 'no_evidence',
        review_bucket: 'attention',
        proposed_value: null,
        reason_codes: ['conflicting_evidence'],
        rationale: '- Parser-first metadata/front-matter inspection found conflicting candidates.',
        evidence_ids: [],
        ordered_supporting_evidence_ids: [],
        primary_evidence_id: null,
        metadata_diagnostics: {
          candidate_count: 2,
          candidate_sources: ['front_matter_block', 'front_matter_block'],
          candidates: [
            {
              value: 'Candidate journal title',
              source: 'front_matter_block',
              page_number: 1,
            },
            {
              value: 'Competing journal-like text',
              source: 'front_matter_block',
              page_number: 2,
            },
          ],
        },
      },
      evidence: [],
    })

    render(
      <ProposalDetailPane
        proposalId="p1"
        runId="r1"
        outputDir="./runs"
        selectedEvidenceId={null}
        onEvidenceSelect={vi.fn()}
      />
    )

    await screen.findByText('Candidates to check')
    expect(screen.getByText('Candidates to check')).not.toBeVisible()
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByText('Candidates to check')).toBeVisible()
    expect(screen.getByText('Candidate journal title')).toBeVisible()
    expect(screen.getByText('Competing journal-like text')).toBeVisible()
    expect(screen.getByText('Metadata')).toBeVisible()
    expect(screen.getByText('2 metadata candidates require comparison')).toBeVisible()
    expect(screen.getByText('Front matter · p.1')).toBeVisible()
    expect(screen.getByText('Front matter · p.2')).toBeVisible()
    expect(screen.queryByText('candidate count')).not.toBeInTheDocument()
  })

  it('renders no-data direct evidence as an absence conclusion', async () => {
    renderDetail(
      detailFor({
        proposal_status: 'no_data',
        evidence_status: 'direct_strong',
        review_bucket: 'review',
        proposed_value: null,
        reason_codes: ['explicitly_not_reported'],
        rationale: '- The paper explicitly says the assay was not measured.',
      })
    )

    await screen.findByText('No data reported')
    expect(screen.getByText('Explicitly not reported')).toBeInTheDocument()
    expect(screen.getByTitle('The paper directly says this information was not measured or not reported.')).toBeInTheDocument()
    expect(screen.getByTitle('Evidence: direct strong')).toBeInTheDocument()
  })

  it('renders inferred no-data as no data reported with context', async () => {
    renderDetail(
      detailFor(
        {
          proposal_status: 'no_data',
          evidence_status: 'inferred_weak',
          review_bucket: 'attention',
          proposed_value: null,
          reason_codes: ['not_reported'],
          rationale: '- Relevant sections did not report the field.',
        },
        []
      )
    )

    await screen.findByText('No data reported')
    expect(screen.getByText('Not reported')).toBeInTheDocument()
    expect(screen.getByText('- Relevant sections did not report the field.')).toBeInTheDocument()
    expect(screen.getByText('No formal evidence items were persisted for this proposal.')).toBeInTheDocument()
  })

  it('renders value proposals with inferred strong evidence as a proposed value', async () => {
    renderDetail(
      detailFor({
        proposal_status: 'value_proposed',
        evidence_status: 'inferred_strong',
        review_bucket: 'review',
        proposed_value: 'MPRA',
      })
    )

    await screen.findByText('MPRA')
    expect(screen.getByTitle('Evidence: inferred strong')).toBeInTheDocument()
    expect(screen.getByTitle('Evidence: inferred strong')).not.toBeVisible()
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByTitle('Evidence: inferred strong')).toBeVisible()
    expect(screen.queryByText('Needs attention')).not.toBeInTheDocument()
  })

  it('renders weak direct value proposals with readable reason labels', async () => {
    renderDetail(
      detailFor({
        proposal_status: 'value_proposed',
        evidence_status: 'direct_weak',
        review_bucket: 'attention',
        proposed_value: 'HEK293T',
        reason_codes: ['insufficient_evidence'],
      })
    )

    await screen.findByText('HEK293T')
    expect(screen.getByTitle('Evidence: direct weak')).toBeInTheDocument()
    expect(screen.getByTitle('Evidence: direct weak')).not.toBeVisible()
    expect(screen.getByText('Insufficient evidence')).not.toBeVisible()
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByTitle('Evidence: direct weak')).toBeVisible()
    expect(screen.getByText('Insufficient evidence')).toBeVisible()
  })

  it('renders not-applicable as a conclusion, not a missing proposal', async () => {
    renderDetail(
      detailFor(
        {
          proposal_status: 'not_applicable',
          evidence_status: 'not_applicable',
          review_bucket: 'diagnostic',
          proposed_value: null,
          reason_codes: ['schema_not_applicable'],
        },
        []
      )
    )

    await screen.findAllByText('Not applicable')
    expect(screen.queryByText('No value proposed')).not.toBeInTheDocument()
    expect(screen.getByText('Not applicable by schema')).toBeInTheDocument()
  })

  it('renders errors as extraction errors with reason codes', async () => {
    renderDetail(
      detailFor(
        {
          proposal_status: 'error',
          evidence_status: 'not_applicable',
          review_bucket: 'diagnostic',
          proposed_value: null,
          reason_codes: ['provider_error', 'parser_error', 'invalid_model_output'],
          rationale: 'Provider error: unavailable',
        },
        []
      )
    )

    await screen.findByText('Extraction error')
    expect(screen.getByText('Provider error')).toBeInTheDocument()
    expect(screen.getByText('Parser error')).toBeInTheDocument()
    expect(screen.getByText('Invalid model output')).toBeInTheDocument()
  })

  it('renders not-attempted as a conclusion with its reason', async () => {
    renderDetail(
      detailFor(
        {
          proposal_status: 'not_attempted',
          evidence_status: 'not_applicable',
          review_bucket: 'diagnostic',
          proposed_value: null,
          reason_codes: ['column_excluded'],
        },
        []
      )
    )

    await screen.findByText('Not attempted')
    expect(screen.getByText('column excluded')).toBeInTheDocument()
  })

  it('renders pure retrieval-empty unresolved without implying inspected context', async () => {
    renderDetail(
      detailFor(
        {
          proposal_status: 'unresolved',
          evidence_status: 'no_evidence',
          review_bucket: 'diagnostic',
          proposed_value: null,
          reason_codes: ['retrieval_empty'],
          rationale: null,
          candidate_answers: null,
          selection_diagnostics: null,
          retrieval_diagnostics: null,
        },
        []
      )
    )

    await screen.findByText('No value proposed')
    expect(screen.getAllByText('No formal evidence items were persisted for this proposal.').length).toBeGreaterThan(0)
    expect(screen.queryByText('Context considered')).not.toBeInTheDocument()
    expect(screen.queryByText('No decisive evidence was found for this target cell. Context considered by the system is shown below.')).not.toBeInTheDocument()
  })

  it('falls back gracefully for unknown reason codes', async () => {
    renderDetail(
      detailFor({
        reason_codes: ['future_reason_code'],
      })
    )

    await screen.findByText('future reason code')
    expect(screen.getByTitle('future_reason_code')).toBeInTheDocument()
  })

  it('does not duplicate a matching single candidate in the main pane', async () => {
    renderDetail(
      detailFor({
        proposed_value: '120',
        candidate_answers: [
          {
            candidate_id: 'cand_1',
            value: '120',
            candidate_status: 'found',
            source: 'first_pass_text',
            confidence_rationale: 'The sample size of 120 participants was stated in the Methods section.',
          },
        ],
      })
    )

    expect(await screen.findAllByText('120')).toHaveLength(1)
    expect(screen.queryByText('Candidates to check')).not.toBeInTheDocument()
    expect(screen.getAllByText('The sample size of 120 participants was stated in the Methods section.')).toHaveLength(1)
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.queryByText('Candidates to check')).not.toBeInTheDocument()
    expect(screen.queryByText('found · first_pass_text')).not.toBeInTheDocument()
    expect(screen.getAllByText('120')).toHaveLength(1)
    expect(screen.getAllByText('The sample size of 120 participants was stated in the Methods section.')).toHaveLength(1)
    expect(screen.getByText('Diagnostics').closest('details')?.querySelectorAll('details')).toHaveLength(0)
  })

  it('hides routine not-needed selection diagnostics', async () => {
    renderDetail(
      detailFor({
        selection_diagnostics: {
          attempted: false,
          succeeded: false,
          skip_reason: 'not_needed_or_disabled',
          candidate_count: 1,
        },
      })
    )

    await screen.findByText('Diagnostics')
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.queryByText('Selection')).not.toBeInTheDocument()
    expect(screen.queryByText('Selection step not run because it was not needed')).not.toBeInTheDocument()
    expect(screen.queryByText('succeeded')).not.toBeInTheDocument()
    expect(screen.queryByText('false')).not.toBeInTheDocument()
  })

  it('summarizes competing candidate selection with reviewer-facing source labels', async () => {
    renderDetail(
      detailFor({
        proposed_value: '120',
        candidate_answers: [
          { candidate_id: 'cand_1', value: '120', candidate_status: 'found', source: 'first_pass_text' },
          { candidate_id: 'cand_2', value: '118', candidate_status: 'inferred', source: 'rescued_text' },
        ],
        selection_diagnostics: {
          attempted: true,
          succeeded: true,
          selected_candidate_id: 'cand_1',
          rejected_candidate_ids: ['cand_2'],
          value_changed: false,
        },
      })
    )

    await screen.findByText('Diagnostics')
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByText('Candidates to check')).toBeVisible()
    expect(screen.getByText('Found · Initial text extraction')).toBeVisible()
    expect(screen.getByText('Inferred · Targeted text search')).toBeVisible()
    expect(screen.getByText('Selected from 2 competing candidates')).toBeVisible()
  })

  it('keeps development-only provider and figure telemetry out of reviewer diagnostics', async () => {
    renderDetail(
      detailFor({
        provider_diagnostics: { request_id: 'provider-request-123', elapsed_ms: 8421 },
        figure_review_diagnostics: { raw_model_response: 'figure-review-debug-payload' },
        figure_planner_diagnostics: { planner_query: 'internal-figure-query' },
        retrieval_diagnostics: { classification: 'retrieval_miss', retrieved_chunk_count: 3 },
      })
    )

    await screen.findByText('Diagnostics')
    fireEvent.click(screen.getByText('Diagnostics'))
    expect(screen.getByText('Retrieval')).toBeVisible()
    expect(screen.getByText('No relevant passage was found for this field.')).toBeVisible()
    expect(screen.getByText('3 passages')).toBeVisible()
    expect(screen.queryByText('retrieved chunk count')).not.toBeInTheDocument()
    expect(screen.queryByText('provider-request-123')).not.toBeInTheDocument()
    expect(screen.queryByText('figure-review-debug-payload')).not.toBeInTheDocument()
    expect(screen.queryByText('internal-figure-query')).not.toBeInTheDocument()
  })
})
