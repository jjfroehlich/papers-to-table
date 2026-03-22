import type { ConfigSnapshot, InputSummary, MatchRecord, ReviewerSummary, RunDiagnostics, RunRecord, RunSummary } from '../lib/types'

interface Props {
  run: RunRecord | null
  summary: RunSummary | null
  reviewerSummary: ReviewerSummary | null
  inputSummary: InputSummary | null
  configSnapshot: ConfigSnapshot | null
  diagnostics: RunDiagnostics | null
  matchWarnings: MatchRecord[]
  runId: string | null
  loadingRunData: boolean
  downloadAsset: (kind: 'workbook' | 'audit-log' | 'run-summary' | 'reviewer-summary' | 'config-snapshot') => string
}

function warningLabel(match: MatchRecord): string {
  if (match.outcome === 'duplicate_row_conflict') return 'Duplicate row conflict'
  if (match.outcome === 'ambiguous') return 'Ambiguous match'
  return 'Unmatched PDF'
}

function statusBadgeClass(status: RunRecord['status'] | RunSummary['status']): string {
  if (status === 'completed') return 'badge badge-success'
  if (status === 'completed_with_warnings' || status === 'validating' || status === 'running') return 'badge badge-warning'
  if (status === 'failed' || status === 'interrupted') return 'badge badge-danger'
  return 'badge badge-neutral'
}

function hasReviewSummary(run: RunRecord | null, summary: RunSummary | null): boolean {
  return Boolean(run && summary && (run.status === 'completed' || run.status === 'completed_with_warnings'))
}

function processingMessage(run: RunRecord): string {
  if (run.status === 'failed') {
    return 'This run failed before review became available. Use the status message, diagnostics, and config snapshot above, then fix the inputs or config and start a new run.'
  }
  if (run.status === 'interrupted') {
    return 'This run was interrupted before review became available. Inspect diagnostics and start a new run if you still need proposals.'
  }
  return 'The review queue and aggregate metrics become available once proposal generation and summary writing finish.'
}

export function RunSummaryPanel({
  run,
  summary,
  reviewerSummary,
  inputSummary,
  configSnapshot,
  diagnostics,
  matchWarnings,
  runId,
  loadingRunData,
  downloadAsset,
}: Props) {
  if (!run) {
    return (
      <section className="panel" aria-label="run-summary">
        <h2 className="section-title">Run summary</h2>
        <p className="empty-state">No runs are available yet. Start one from the config launcher, then use this area to confirm the setup, status, review metrics, and exports.</p>
      </section>
    )
  }

  return (
    <section className="stack" aria-label="run-summary">
      <div className="panel">
        <div className="section-title-row">
          <div>
            <h2 className="section-title">Run status</h2>
            <p className="section-caption">{run.run_id} · {run.provider_name} / {run.provider_model} · {run.provider_locality}</p>
          </div>
          <div className="badge-row">
            <span className={statusBadgeClass(summary?.status ?? run.status)}>{(summary?.status ?? run.status).replace(/_/g, ' ')}</span>
            <span className="badge badge-neutral">{run.verify_mode ? 'Verify mode on' : 'Verify mode off'}</span>
          </div>
        </div>
        <p className="status-lead">{run.message || 'Run metadata is available.'}</p>
        {loadingRunData && <p className="support-note">Refreshing run workspace…</p>}
        {diagnostics?.error && <p className="inline-error">{diagnostics.error}</p>}
      </div>

      <div className="panel">
        <div className="section-title-row">
          <div>
            <h2 className="section-title">Run setup</h2>
            <p className="section-caption">Show the config source and resolved inputs without turning the UI into a full advanced settings editor.</p>
          </div>
          <a className="download-link" href={downloadAsset('config-snapshot')}>Download config snapshot</a>
        </div>
        <div className="detail-grid">
          <article className="detail-card">
            <span className="detail-label">Config path</span>
            <p className="detail-value">{inputSummary?.config_path || run.config_path || 'Inline request payload'}</p>
          </article>
          <article className="detail-card">
            <span className="detail-label">Table and schema</span>
            <p className="detail-value">{inputSummary?.table_path || configSnapshot?.paths.table_path || 'Pending validation'}</p>
            <p className="detail-value subtle-detail">{inputSummary?.schema_path || configSnapshot?.paths.schema_path || 'Workbook schema or not available yet'}</p>
          </article>
          <article className="detail-card">
            <span className="detail-label">PDF directory</span>
            <p className="detail-value">{inputSummary?.pdf_dir || configSnapshot?.paths.pdf_dir || 'Pending validation'}</p>
          </article>
          <article className="detail-card">
            <span className="detail-label">Artifact root</span>
            <p className="detail-value">{inputSummary?.output_dir || configSnapshot?.paths.output_dir || 'Pending validation'}</p>
          </article>
          <article className="detail-card">
            <span className="detail-label">Input volume</span>
            <p className="detail-value">{inputSummary ? `${inputSummary.pdf_count} PDFs · ${inputSummary.row_count} rows` : 'Visible after validation'}</p>
          </article>
          <article className="detail-card">
            <span className="detail-label">Target columns</span>
            <p className="detail-value">{inputSummary ? inputSummary.target_columns.join(', ') : 'Visible after validation'}</p>
          </article>
        </div>
      </div>

      {hasReviewSummary(run, summary) ? (
        <div className="panel">
          <div className="section-title-row">
            <div>
              <h2 className="section-title">Run summary</h2>
              <p className="section-caption">Keep queue health, acceptance progress, and export scope visible while you review.</p>
            </div>
          </div>
          <div className="metric-grid">
            <article className="metric-card">
              <span className="metric-label">PDFs</span>
              <span className="metric-value">{summary?.pdfs_processed}</span>
              <span className="metric-footnote">{summary?.matched_pdfs} matched / {summary?.unmatched_pdfs} unmatched / {summary?.ambiguous_pdfs} ambiguous</span>
            </article>
            <article className="metric-card">
              <span className="metric-label">Queue</span>
              <span className="metric-value">{summary?.proposals_generated}</span>
              <span className="metric-footnote">{summary?.pending} pending / {summary?.reviewed_proposals} reviewed</span>
            </article>
            <article className="metric-card">
              <span className="metric-label">Accepted</span>
              <span className="metric-value">{(summary?.accepted_as_is ?? 0) + (summary?.accepted_with_edit ?? 0)}</span>
              <span className="metric-footnote">{summary?.accepted_as_is} as-is / {summary?.accepted_with_edit} edited</span>
            </article>
            <article className="metric-card">
              <span className="metric-label">Exported cells</span>
              <span className="metric-value">{summary?.changed_cells_exported}</span>
              <span className="metric-footnote">{summary?.rejected} rejected proposals</span>
            </article>
          </div>
        </div>
      ) : (
        <div className="panel-muted status-panel">
          <strong>Processing state:</strong> {run.status.replace(/_/g, ' ')}
          <p className="status-text">{processingMessage(run)}</p>
        </div>
      )}

      <div className="panel">
        <div className="section-title-row">
          <div>
            <h2 className="section-title">Reviewer outcomes</h2>
            <p className="section-caption">Verify-mode reporting should stay honest, especially when coverage is low or not yet meaningful.</p>
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
            {reviewerSummary.reviewed_verified_cell_count === 0 && reviewerSummary.per_column.length > 0 && (
              <p className="support-note">Per-column lines below show evidence coverage for verify-mode targets, but there are no reviewed verified cells yet, so they should not be read as outcome scores.</p>
            )}
            {reviewerSummary.per_column.length > 0 && (
              <div className="detail-card">
                <span className="detail-label">Per-column verify coverage</span>
                <ul className="column-summary-list">
                  {reviewerSummary.per_column.map((column) => (
                    <li key={column.column_name}>
                      {column.column_name}: {column.reviewed_verified_cell_count === 0 ? 'no verified reviews yet' : `${column.reviewed_verified_cell_count} reviewed`} · {Math.round(column.evidence_coverage * 100)}% evidence coverage
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="empty-state">Reviewer outcome metrics will appear after the run finishes and verify-mode summaries are written.</p>
        )}
      </div>

      {matchWarnings.length > 0 && (
        <aside className="panel-muted">
          <div className="section-title-row">
            <div>
              <h2 className="section-title">Match inspection</h2>
              <p className="section-caption">Keep unresolved PDFs visible with their outcomes and rationales so row-matching problems do not disappear behind actionable review work.</p>
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
              <p className="section-caption">Pull files straight from the run bundle, but only when the run has actually written them.</p>
            </div>
          </div>
          <div className="downloads">
            <a className="download-link" href={downloadAsset('config-snapshot')}>Config snapshot JSON</a>
            {hasReviewSummary(run, summary) ? (
              <>
                <a className="download-link" href={downloadAsset('workbook')}>Download workbook</a>
                <a className="download-link" href={downloadAsset('audit-log')}>Download audit log</a>
                <a className="download-link" href={downloadAsset('run-summary')}>Run summary JSON</a>
                <a className="download-link" href={downloadAsset('reviewer-summary')}>Reviewer summary JSON</a>
              </>
            ) : (
              <p className="support-note">Workbook, audit-log, and summary downloads appear after the run reaches a reviewable completed state.</p>
            )}
          </div>
        </section>
      )}
    </section>
  )
}