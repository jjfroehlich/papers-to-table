import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface Props {
  runId: string
  outputDir: string
}

interface UnmatchedItem {
  pdf_id?: string
  filename?: string
  reason?: string
  [key: string]: unknown
}

interface AmbiguousItem {
  pdf_id?: string
  filename?: string
  matches?: unknown[]
  score?: number
  [key: string]: unknown
}

interface ConflictItem {
  pdf_id?: string
  row_ids?: string[]
  [key: string]: unknown
}

function ItemField({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null) return null
  return (
    <span className="text-xs text-gray-500">
      <span className="font-medium">{label}:</span>{' '}
      {Array.isArray(value) ? value.join(', ') : String(value)}
    </span>
  )
}

export function UnresolvedInspection({ runId, outputDir }: Props) {
  const [unmatched, setUnmatched] = useState<UnmatchedItem[]>([])
  const [ambiguous, setAmbiguous] = useState<AmbiguousItem[]>([])
  const [conflicts, setConflicts] = useState<ConflictItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    Promise.allSettled([
      api.getUnmatched(runId, outputDir),
      api.getAmbiguous(runId, outputDir),
      api.getConflicts(runId, outputDir),
    ]).then(([u, a, c]) => {
      if (u.status === 'fulfilled') setUnmatched(u.value.unmatched as UnmatchedItem[])
      if (a.status === 'fulfilled') setAmbiguous(a.value.ambiguous as AmbiguousItem[])
      if (c.status === 'fulfilled') setConflicts(c.value.conflicts as ConflictItem[])
      const errs = [u, a, c]
        .filter((r) => r.status === 'rejected')
        .map((r) => (r as PromiseRejectedResult).reason?.message ?? 'Unknown error')
      if (errs.length) setError(errs.join('; '))
    }).finally(() => setLoading(false))
  }, [runId, outputDir])

  if (loading) {
    return <div className="p-4 text-sm text-gray-400">Loading unresolved items…</div>
  }

  const hasAny = unmatched.length + ambiguous.length + conflicts.length > 0

  return (
    <div className="p-4 space-y-4">
      {error && (
        <div className="text-xs text-red-600">
          <strong>Warning:</strong> {error}
        </div>
      )}

      {!hasAny && (
        <div className="text-sm text-gray-500 text-center py-8">
          No unresolved matching issues.
        </div>
      )}

      {unmatched.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2">
            Unmatched PDFs ({unmatched.length})
          </h3>
          <div className="space-y-1">
            {unmatched.map((item, i) => (
              <div key={i} className="rounded border border-amber-200 bg-amber-50 px-3 py-2">
                <div className="text-xs font-medium text-gray-800">
                  {item.filename ?? item.pdf_id ?? `Item ${i + 1}`}
                </div>
                <ItemField label="Reason" value={item.reason} />
              </div>
            ))}
          </div>
        </section>
      )}

      {ambiguous.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2">
            Ambiguous Matches ({ambiguous.length})
          </h3>
          <div className="space-y-1">
            {ambiguous.map((item, i) => (
              <div key={i} className="rounded border border-orange-200 bg-orange-50 px-3 py-2 space-y-1">
                <div className="text-xs font-medium text-gray-800">
                  {item.filename ?? item.pdf_id ?? `Item ${i + 1}`}
                </div>
                <ItemField label="Score" value={item.score != null ? item.score.toFixed(2) : undefined} />
                <ItemField label="Matched rows" value={item.matches} />
              </div>
            ))}
          </div>
        </section>
      )}

      {conflicts.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-gray-800 mb-2">
            Duplicate Row Conflicts ({conflicts.length})
          </h3>
          <div className="space-y-1">
            {conflicts.map((item, i) => (
              <div key={i} className="rounded border border-red-200 bg-red-50 px-3 py-2 space-y-1">
                <div className="text-xs font-medium text-gray-800">
                  {item.pdf_id ?? `Item ${i + 1}`}
                </div>
                <ItemField label="Row IDs" value={item.row_ids} />
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
