/**
 * T092 — Unresolved match inspection view.
 *
 * Shows unmatched, ambiguous, and duplicate-row-conflict records in a read-only
 * inspect-only surface. No rematch/reassignment actions (MVP exclusion).
 */
import { useEffect, useState } from 'react'
import { getMatchingSummary, getMatchingUnresolved } from '../api'
import type { MatchingSummary, UnresolvedMatch } from '../types'

interface Props {
  runId: string
}

export function UnresolvedInspection({ runId }: Props) {
  const [summary, setSummary] = useState<MatchingSummary | null>(null)
  const [items, setItems] = useState<UnresolvedMatch[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([
      getMatchingSummary(runId).catch(() => null),
      getMatchingUnresolved(runId).catch(() => []),
    ])
      .then(([s, u]) => {
        setSummary(s)
        setItems(u as UnresolvedMatch[])
        setLoading(false)
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : 'Failed to load unresolved matches')
        setLoading(false)
      })
  }, [runId])

  if (loading) return <p className="muted">Loading unresolved matches…</p>
  if (error) return <p className="error">{error}</p>

  if (!summary || summary.unresolved === 0) {
    return (
      <div className="unresolved-inspection">
        <h4>Unresolved matches</h4>
        <p className="muted">No unmatched, ambiguous, or duplicate-row-conflict PDFs for this run.</p>
      </div>
    )
  }

  return (
    <div className="unresolved-inspection">
      <h4>Unresolved matches ({summary.unresolved})</h4>
      <p className="hint">Inspect-only in MVP. Rematch or reassignment actions are not available.</p>
      <table className="unresolved-table">
        <thead>
          <tr>
            <th>PDF ID</th>
            <th>Filename</th>
            <th>Outcome</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.pdf_id}>
              <td className="mono">{item.pdf_id}</td>
              <td>{item.filename}</td>
              <td>
                <span className={`outcome-badge outcome-${item.outcome}`}>{item.outcome}</span>
              </td>
              <td>{item.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
