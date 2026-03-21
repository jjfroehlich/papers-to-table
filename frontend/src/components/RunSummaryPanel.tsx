import type { MatchRecord, ReviewerSummary, RunSummary } from '../lib/types'

interface Props {
  summary: RunSummary | null
  reviewerSummary: ReviewerSummary | null
  matchWarnings: MatchRecord[]
  runId: string | null
  downloadAsset: (kind: 'workbook' | 'audit-log' | 'run-summary' | 'reviewer-summary') => string
}

function warningLabel(match: MatchRecord): string {
  if (match.outcome === 'duplicate_row_conflict') return 'Duplicate row conflict'
  if (match.outcome === 'ambiguous') return 'Ambiguous match'
  return 'Unmatched PDF'
}

export function RunSummaryPanel({ summary, reviewerSummary, matchWarnings, runId, downloadAsset }: Props) {
  if (!summary) {
    return (
      <section className="panel" aria-label="run-summary">
        <h2 className="section-title">Run summary</h2>
        <p className="empty-state">Select a run to inspect the summary, reviewer outcomes, and export downloads.</p>
      </section>
    )
  }

  return (
    <section className="stack" aria-label="run-summary">
      <div className="panel">
        <div className="section-title-row">
          <div>
            <h2 className="section-title">Run summary</h2>
            <p className="section-caption">Run {summary.run_id} · {summary.provider_name} / {summary.provider_model} · {summary.provider_locality}</p>
          </div>
          <div className="badge-row">
            <span className={summary.status === 'completed' ? 'badge badge-success' : 'badge badge-warning'}>{summary.status.replace(/_/g, ' ')}</span>
            <span className="badge badge-neutral">{summary.verify_mode ? 'Verify mode on' : 'Verify mode off'}</span>
          </div>
        </div>
        <div className="metric-grid">
          <article className="metric-card">
            <span className="metric-label">PDFs</span>
            <span className="metric-value">{summary.pdfs_processed}</span>
            <span className="metric-footnote">{summary.matched_pdfs} matched / {summary.unmatched_pdfs} unmatched / {summary.ambiguous_pdfs} ambiguous</span>
          </article>
          <article className="metric-card">
            <span className="metric-label">Queue</span>
            <span className="metric-value">{summary.proposals_generated}</span>
            <span className="metric-footnote">{summary.pending} pending / {summary.reviewed_proposals} reviewed</span>
          </article>
          <article className="metric-card">
            <span className="metric-label">Accepted</span>
            <span className="metric-value">{summary.accepted_as_is + summary.accepted_with_edit}</span>
            <span className="metric-footnote">{summary.accepted_as_is} as-is / {summary.accepted_with_edit} edited</span>
          </article>
          <article className="metric-card">
            <span className="metric-label">Exported cells</span>
            <span className="metric-value">{summary.changed_cells_exported}</span>
            <span className="metric-footnote">{summary.rejected} rejected proposals</span>
          </article>
        </div>
      </div>

      <div className="panel">
        <div className="section-title-row">
          <div>
            <h2 className="section-title">Reviewer outcomes</h2>
            <p className="section-caption">Coverage and evidence quality stay visible while you review verify-mode targets.</p>
          </div>
        </div>
        {reviewerSummary ? (
          <div className="stack">
            <div className="metric-grid">
              <article className="metric-card">
                <span className="metric-label">Reviewed verify targets</span>
                <span className="metric-value">{reviewerSummary.reviewed_verified_cell_count}</span>
              </article>
              <article className="metric-card">
                <span className="metric-label">Proposal coverage</span>
                <span className="metric-value">{Math.round(reviewerSummary.proposal_coverage * 100)}%</span>
              </article>
              <article className="metric-card">
                <span className="metric-label">Evidence coverage</span>
                <span className="metric-value">{Math.round(reviewerSummary.evidence_coverage * 100)}%</span>
              </article>
              <article className="metric-card">
                <span className="metric-label">Anchorable evidence</span>
                <span className="metric-value">{Math.round(reviewerSummary.anchorable_evidence_rate * 100)}%</span>
              </article>
            </div>
            {reviewerSummary.warnings.length > 0 && (
              <ul className="warning-list">
                {reviewerSummary.warnings.map((warning, index) => (
                  <li key={index}>{warning}</li>
                ))}
              </ul>
            )}
            {reviewerSummary.per_column.length > 0 && (
              <div className="detail-card">
                <span className="detail-label">Per-column verify coverage</span>
                <ul className="column-summary-list">
                  {reviewerSummary.per_column.map((column) => (
                    <li key={column.column_name}>
                      {column.column_name}: {column.reviewed_verified_cell_count} reviewed · {Math.round(column.evidence_coverage * 100)}% evidence coverage
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="empty-state">Reviewer outcome metrics are unavailable for this run.</p>
        )}
      </div>

      {matchWarnings.length > 0 && (
        <aside className="panel-muted">
          <div className="section-title-row">
            <div>
              <h2 className="section-title">Blocked or unresolved PDFs</h2>
              <p className="section-caption">Keep these visible so row matching problems do not get buried under actionable review work.</p>
            </div>
            <span className="badge badge-warning">{matchWarnings.length} flagged</span>
          </div>
          <ul className="match-warning-list">
            {matchWarnings.map((match, index) => (
              <li key={index}>
                <strong>{warningLabel(match)}:</strong> {match.pdf_name}
                {match.row_id ? ` → ${match.row_id}` : ''}
                {match.rationale ? ` — ${match.rationale}` : ''}
              </li>
            ))}
          </ul>
        </aside>
      )}

      {runId && (
        <section className="panel">
          <div className="section-title-row">
            <div>
              <h2 className="section-title">Exports and artifacts</h2>
              <p className="section-caption">Download the current content-only export, audit log, or summary JSON directly from the run bundle.</p>
            </div>
          </div>
          <div className="downloads">
            <a className="download-link" href={downloadAsset('workbook')}>Download workbook</a>
            <a className="download-link" href={downloadAsset('audit-log')}>Download audit log</a>
            <a className="download-link" href={downloadAsset('run-summary')}>Run summary JSON</a>
            <a className="download-link" href={downloadAsset('reviewer-summary')}>Reviewer summary JSON</a>
          </div>
        </section>
      )}
    </section>
  )
}
