import type { ReviewerSummary, RunSummary } from '../lib/types'

interface Props {
  summary: RunSummary | null
  reviewerSummary: ReviewerSummary | null
}

export function RunSummaryPanel({ summary, reviewerSummary }: Props) {
  if (!summary) return <section aria-label="run-summary">Select a run.</section>
  return (
    <section aria-label="run-summary">
      <h2>Run Summary</h2>
      <ul>
        <li>PDFs processed: {summary.pdfs_processed}</li>
        <li>Matched / Unmatched / Ambiguous: {summary.matched_pdfs} / {summary.unmatched_pdfs} / {summary.ambiguous_pdfs}</li>
        <li>Proposals generated: {summary.proposals_generated}</li>
        <li>Reviewed proposals: {summary.reviewed_proposals}</li>
        <li>Accepted as-is: {summary.accepted_as_is}</li>
        <li>Accepted with edit: {summary.accepted_with_edit}</li>
        <li>Rejected: {summary.rejected}</li>
        <li>Changed cells exported: {summary.changed_cells_exported}</li>
        <li>Verify mode: {summary.verify_mode ? 'On' : 'Off'}</li>
        <li>Provider: {summary.provider_name} / {summary.provider_model} ({summary.provider_locality})</li>
      </ul>
      {reviewerSummary && (
        <div>
          <h3>Reviewer Outcomes</h3>
          <p>Reviewed verified cells: {reviewerSummary.reviewed_verified_cell_count}</p>
          <p>Proposal coverage: {Math.round(reviewerSummary.proposal_coverage * 100)}%</p>
          <p>Evidence coverage: {Math.round(reviewerSummary.evidence_coverage * 100)}%</p>
          <p>Anchorable evidence rate: {Math.round(reviewerSummary.anchorable_evidence_rate * 100)}%</p>
          {reviewerSummary.warnings.map((warning) => <p key={warning}>{warning}</p>)}
        </div>
      )}
    </section>
  )
}
