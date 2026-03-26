/**
 * T082 — Concise run summary view.
 *
 * Shows PDFs processed/matched/unmatched/ambiguous, proposal counts, decision
 * breakdown, verify mode, provider/model, and download links.
 */
import { useEffect, useState } from 'react'
import {
  getAvailableDownloads,
  getAuditLogDownloadUrl,
  getReviewerSummaryDownloadUrl,
  getRunSummaryDownloadUrl,
  getRunSummaryFull,
  getWorkbookDownloadUrl,
  recomputeSummaries,
} from '../api'
import type { AvailableDownloads, RunSummaryFull } from '../types'

interface Props {
  runId: string
}

export function RunSummaryPanel({ runId }: Props) {
  const [summary, setSummary] = useState<RunSummaryFull | null>(null)
  const [downloads, setDownloads] = useState<AvailableDownloads | null>(null)
  const [recomputing, setRecomputing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function load() {
    Promise.all([
      getRunSummaryFull(runId).catch(() => null),
      getAvailableDownloads(runId).catch(() => null),
    ]).then(([s, d]) => {
      setSummary(s)
      setDownloads(d)
    }).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Failed to load run summary')
    })
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId])

  async function handleRecompute() {
    setRecomputing(true)
    setError(null)
    try {
      await recomputeSummaries(runId)
      load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Recompute failed')
    } finally {
      setRecomputing(false)
    }
  }

  if (error) return <p className="error">{error}</p>
  if (!summary) return <p className="muted">Run summary not yet available for this run.</p>

  const flags = summary.run_status_flags ?? []
  const counts = summary.counts ?? {}

  return (
    <div className="run-summary-panel">
      <div className="run-summary-header">
        <h3>Run summary</h3>
        <button className="btn-sm" onClick={handleRecompute} disabled={recomputing} title="Recompute summaries from current artifacts">
          {recomputing ? 'Recomputing…' : 'Recompute'}
        </button>
      </div>

      {flags.length > 0 && (
        <div className="flag-list">
          {flags.map((f) => (
            <span key={f} className={`flag flag-${f}`}>{formatFlag(f)}</span>
          ))}
        </div>
      )}

      <div className="summary-grid two-col">
        <div className="summary-section">
          <h4>PDFs</h4>
          <dl className="kv-list">
            <dt>Processed</dt><dd>{summary.pdfs_processed}</dd>
            <dt>Matched</dt><dd>{summary.pdfs_matched}</dd>
            <dt>Unmatched</dt><dd>{summary.pdfs_unmatched ?? 0}</dd>
            <dt>Ambiguous</dt><dd>{summary.pdfs_ambiguous ?? 0}</dd>
          </dl>
        </div>

        <div className="summary-section">
          <h4>Proposals</h4>
          <dl className="kv-list">
            <dt>Generated</dt><dd>{counts.proposals_generated ?? 0}</dd>
            <dt>Reviewed</dt><dd>{counts.reviewed_proposals ?? 0}</dd>
            <dt>Accepted as-is</dt><dd>{counts.accepted_as_is ?? 0}</dd>
            <dt>Accepted with edit</dt><dd>{counts.accepted_with_edit ?? 0}</dd>
            <dt>Rejected</dt><dd>{counts.rejected ?? 0}</dd>
            <dt>Pending</dt><dd>{counts.pending ?? 0}</dd>
            <dt>Exported cells</dt><dd>{counts.changed_cells_exported ?? 0}</dd>
          </dl>
        </div>

        <div className="summary-section">
          <h4>Configuration</h4>
          <dl className="kv-list">
            <dt>Verify mode</dt><dd>{summary.verify_mode ? 'On' : 'Off'}</dd>
            <dt>Provider</dt><dd>{summary.provider_name ?? '—'}</dd>
            <dt>Model</dt><dd>{summary.model_name ?? '—'}</dd>
            <dt>Locality</dt><dd>{summary.provider_locality ?? 'local'}</dd>
          </dl>
        </div>

        <div className="summary-section">
          <h4>Downloads</h4>
          {downloads ? (
            <ul className="download-list">
              <li>
                {downloads.run_summary ? (
                  <a href={getRunSummaryDownloadUrl(runId)} download>Run summary JSON</a>
                ) : (
                  <span className="muted">Run summary — not yet written</span>
                )}
              </li>
              <li>
                {downloads.reviewer_summary ? (
                  <a href={getReviewerSummaryDownloadUrl(runId)} download>Reviewer summary JSON</a>
                ) : (
                  <span className="muted">Reviewer summary — not yet written</span>
                )}
              </li>
              <li>
                {downloads.workbook ? (
                  <a href={getWorkbookDownloadUrl(runId)} download>Updated workbook (XLSX)</a>
                ) : (
                  <span className="muted">Updated workbook — export not yet run</span>
                )}
              </li>
              <li>
                {downloads.audit_log ? (
                  <a href={getAuditLogDownloadUrl(runId)} download>Audit log (CSV)</a>
                ) : (
                  <span className="muted">Audit log — export not yet run</span>
                )}
              </li>
            </ul>
          ) : (
            <p className="muted">Loading downloads…</p>
          )}
        </div>
      </div>
    </div>
  )
}

function formatFlag(flag: string): string {
  return flag.replace(/_/g, ' ')
}
