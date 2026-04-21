import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { RunData } from '../types'

interface Props {
  run: RunData
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

function Card({ title, tone, children }: { title: string; tone: 'slate' | 'amber' | 'orange' | 'rose'; children: ReactNode }) {
  const className = {
    slate: 'border-slate-200 bg-white',
    amber: 'border-amber-200 bg-amber-50',
    orange: 'border-orange-200 bg-orange-50',
    rose: 'border-rose-200 bg-rose-50',
  }[tone]
  return (
    <section className={`rounded-3xl border p-4 shadow-sm ${className}`}>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      <div className="mt-3 space-y-2 text-sm text-slate-600">{children}</div>
    </section>
  )
}

function ItemField({ label, value }: { label: string; value: unknown }) {
  if (value === undefined || value === null) return null
  return (
    <p className="text-xs text-slate-600">
      <span className="font-semibold text-slate-700">{label}:</span>{' '}
      {Array.isArray(value) ? value.join(', ') : String(value)}
    </p>
  )
}

export function UnresolvedInspection({ run, runId, outputDir }: Props) {
  const [unmatched, setUnmatched] = useState<UnmatchedItem[]>([])
  const [ambiguous, setAmbiguous] = useState<AmbiguousItem[]>([])
  const [conflicts, setConflicts] = useState<ConflictItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      const [u, a, c] = await Promise.allSettled([
        api.getUnmatched(runId, outputDir),
        api.getAmbiguous(runId, outputDir),
        api.getConflicts(runId, outputDir),
      ])
      if (cancelled) return
      if (u.status === 'fulfilled') setUnmatched(u.value.unmatched as UnmatchedItem[])
      if (a.status === 'fulfilled') setAmbiguous(a.value.ambiguous as AmbiguousItem[])
      if (c.status === 'fulfilled') setConflicts(c.value.conflicts as ConflictItem[])
      const errs = [u, a, c]
        .filter((result) => result.status === 'rejected')
        .map((result) => (result as PromiseRejectedResult).reason?.message ?? 'Unknown error')
      setError(errs.length > 0 ? errs.join('; ') : null)
      setLoading(false)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [outputDir, runId])

  const warningGroups = useMemo(() => {
    const grouped = new Map<string, string[]>()
    for (const warning of run.warnings) {
      const current = grouped.get(warning.category) ?? []
      current.push(warning.message)
      grouped.set(warning.category, current)
    }
    return Array.from(grouped.entries())
  }, [run.warnings])

  if (loading) {
    return <div className="rounded-3xl border border-slate-200 bg-white px-4 py-6 text-sm text-slate-400 shadow-sm">Loading diagnostics…</div>
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
      <Card title="Run warnings" tone="slate">
        {warningGroups.length === 0 ? (
          <p className="text-sm text-slate-500">No persisted warnings for this run.</p>
        ) : (
          warningGroups.map(([category, messages]) => (
            <div key={category} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{category.replace(/_/g, ' ')}</p>
              <ul className="mt-2 space-y-1 text-xs text-slate-700">
                {messages.map((message) => (
                  <li key={message}>• {message}</li>
                ))}
              </ul>
            </div>
          ))
        )}
        {error && <p className="text-xs text-rose-700">Diagnostics request warning: {error}</p>}
      </Card>

      <div className="space-y-4">
        <Card title={`Unmatched PDFs (${unmatched.length})`} tone="amber">
          {unmatched.length === 0 ? (
            <p className="text-sm text-slate-500">No unmatched PDFs in this run.</p>
          ) : (
            unmatched.map((item, index) => (
              <div key={`${item.pdf_id ?? item.filename ?? index}`} className="rounded-2xl border border-amber-200 bg-white px-3 py-3">
                <p className="text-sm font-semibold text-slate-900">{item.filename ?? item.pdf_id ?? `Item ${index + 1}`}</p>
                <ItemField label="Reason" value={item.reason} />
              </div>
            ))
          )}
        </Card>

        <Card title={`Ambiguous matches (${ambiguous.length})`} tone="orange">
          {ambiguous.length === 0 ? (
            <p className="text-sm text-slate-500">No ambiguous-match records.</p>
          ) : (
            ambiguous.map((item, index) => (
              <div key={`${item.pdf_id ?? item.filename ?? index}`} className="rounded-2xl border border-orange-200 bg-white px-3 py-3">
                <p className="text-sm font-semibold text-slate-900">{item.filename ?? item.pdf_id ?? `Item ${index + 1}`}</p>
                <ItemField label="Score" value={item.score != null ? item.score.toFixed(2) : undefined} />
                <ItemField label="Matched rows" value={item.matches} />
              </div>
            ))
          )}
        </Card>

        <Card title={`Duplicate row conflicts (${conflicts.length})`} tone="rose">
          {conflicts.length === 0 ? (
            <p className="text-sm text-slate-500">No duplicate-row conflicts in this run.</p>
          ) : (
            conflicts.map((item, index) => (
              <div key={`${item.pdf_id ?? index}`} className="rounded-2xl border border-rose-200 bg-white px-3 py-3">
                <p className="text-sm font-semibold text-slate-900">{item.pdf_id ?? `Item ${index + 1}`}</p>
                <ItemField label="Row IDs" value={item.row_ids} />
              </div>
            ))
          )}
        </Card>
      </div>
    </div>
  )
}
