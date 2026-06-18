import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { ReviewProgress, ReviewTableData, RunData } from '../types'

interface Props {
  run: RunData
  outputDir: string
}

function DiagnosticBox({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{title}</p>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function DetailRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="grid gap-1 border-b border-slate-100 py-1 last:border-b-0 md:grid-cols-[140px_minmax(0,1fr)] md:gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="min-w-0 break-words text-sm text-slate-800">{value}</span>
    </div>
  )
}

export function RunSummaryPanel({ run }: Props) {
  const [progress, setProgress] = useState<ReviewProgress | null>(null)
  const [reviewTable, setReviewTable] = useState<ReviewTableData | null>(null)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  useEffect(() => {
    api.getReviewProgress(run.run_id).then((value) => { setProgress(value); setSummaryError(null) }).catch((err) => setSummaryError(err instanceof Error ? err.message : String(err)))
    api.getReviewTable(run.run_id).then((value) => { setReviewTable(value); setSummaryError(null) }).catch((err) => setSummaryError(err instanceof Error ? err.message : String(err)))
  }, [run.run_id])

  const proposals = useMemo(() => {
    if (!reviewTable) return []
    const byId = new Map()
    for (const row of reviewTable.rows) {
      for (const cell of Object.values(row.cells)) {
        if (cell.proposal) byId.set(cell.proposal.proposal_id, cell.proposal)
      }
    }
    return Array.from(byId.values())
  }, [reviewTable])

  const attention = proposals.filter((proposal) => (
    proposal.evidence_status !== 'direct_strong' ||
    proposal.proposal_status !== 'value_proposed' ||
    proposal.is_fallback_evidence
  )).length
  const progressPct = progress && progress.total_proposals > 0
    ? Math.round((progress.reviewed / progress.total_proposals) * 100)
    : 0

  return (
    <div className="bg-slate-50 px-5 py-4">
      {summaryError && <div className="mb-3 rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700"><strong>Diagnostics warning:</strong> {summaryError}</div>}
      <div className="grid gap-3 xl:grid-cols-3">
        <DiagnosticBox title="Review">
          <DetailRow label="Reviewed" value={`${progress?.reviewed ?? 0} / ${progress?.total_proposals ?? 0}`} />
          <DetailRow label="Pending" value={progress?.pending ?? 0} />
          <DetailRow label="Accepted" value={progress?.accepted ?? 0} />
          <DetailRow label="Edited" value={progress?.accepted_with_edit ?? 0} />
          <DetailRow label="No data" value={progress?.confirmed_no_data ?? 0} />
          <DetailRow label="Rejected" value={progress?.rejected ?? 0} />
          <div className="mt-3 h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-slate-950 transition-all" style={{ width: `${progressPct}%` }} />
          </div>
        </DiagnosticBox>
        <DiagnosticBox title="Package">
          <DetailRow label="Rows" value={run.total_rows} />
          <DetailRow label="PDFs" value={window.__REVIEW_PACKAGE__?.pdfs?.length ?? 0} />
          <DetailRow label="Columns" value={window.__REVIEW_PACKAGE__?.columns?.length ?? 0} />
          <DetailRow label="Proposals" value={run.proposals_generated} />
          <DetailRow label="Attention" value={attention} />
          <DetailRow label="Generated" value={run.completed_at ? new Date(run.completed_at).toLocaleString() : '—'} />
        </DiagnosticBox>
        <DiagnosticBox title="Standalone">
          <DetailRow label="Mode" value={api.isServed() ? 'localhost writeback' : 'static download'} />
          <DetailRow label="Draft table" value="exports/draft_filled_table.csv" />
          <DetailRow label="Reviewed bundle" value="exports/reviewed_bundle/" />
          <DetailRow label="Inputs" value="excluded from reviewed bundle" />
        </DiagnosticBox>
      </div>
    </div>
  )
}
