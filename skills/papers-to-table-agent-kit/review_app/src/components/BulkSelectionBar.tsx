import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { EnrichedProposal } from '../types'

type BulkDecision = 'accepted' | 'rejected' | 'confirmed_no_data'

interface Props {
  proposals: EnrichedProposal[]
  runId: string
  outputDir: string
  onApplied: () => void
  onClear: () => void
}

const LABELS: Record<BulkDecision, string> = {
  accepted: 'Accept',
  rejected: 'Reject',
  confirmed_no_data: 'No data',
}

export function BulkSelectionBar({ proposals, runId, outputDir, onApplied, onClear }: Props) {
  const [pendingDecision, setPendingDecision] = useState<BulkDecision | null>(null)
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pendingCount = useMemo(() => proposals.filter((proposal) => !proposal.latest_decision).length, [proposals])
  const reviewedCount = proposals.length - pendingCount
  const targetCount = replaceExisting ? proposals.length : pendingCount

  async function applyDecision() {
    if (!pendingDecision || targetCount === 0) return
    setLoading(true)
    setError(null)
    try {
      await api.bulkDecision(
        runId,
        proposals.map((proposal) => proposal.proposal_id),
        pendingDecision,
        replaceExisting,
        outputDir,
      )
      onApplied()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="shrink-0 border-t border-sky-200 bg-sky-50 px-4 py-3" data-testid="bulk-selection-bar">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-sky-950">{proposals.length} cells selected</p>
          <p className="text-xs text-sky-700">{pendingCount} pending · {reviewedCount} already reviewed</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => setPendingDecision('rejected')} disabled={loading} className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50">
            Reject
          </button>
          <button onClick={() => setPendingDecision('confirmed_no_data')} disabled={loading} className="rounded-md border border-violet-300 bg-white px-3 py-1.5 text-sm font-medium text-violet-800 hover:bg-violet-50 disabled:opacity-50">
            No data
          </button>
          <button onClick={() => setPendingDecision('accepted')} disabled={loading} className="rounded-md border border-emerald-600 bg-emerald-600 px-3.5 py-1.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">
            Accept
          </button>
          <button onClick={onClear} disabled={loading} className="rounded-md px-2 py-1.5 text-xs font-semibold text-sky-700 hover:bg-sky-100 disabled:opacity-50">
            Clear
          </button>
        </div>
      </div>

      {pendingDecision && (
        <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-semibold text-amber-900">
            {LABELS[pendingDecision]} {targetCount} selected proposal{targetCount === 1 ? '' : 's'}?
          </p>
          <p className="mt-1 text-xs text-amber-800">
            This records decision_source=human_bulk_selection. Selected cells without proposals are never included.
          </p>
          {reviewedCount > 0 && (
            <label className="mt-2 flex items-center gap-2 text-xs font-medium text-amber-900">
              <input
                type="checkbox"
                checked={replaceExisting}
                onChange={(event) => setReplaceExisting(event.target.checked)}
              />
              Replace the existing decision for {reviewedCount} reviewed cell{reviewedCount === 1 ? '' : 's'}
            </label>
          )}
          <div className="mt-3 flex gap-2">
            <button onClick={applyDecision} disabled={loading || targetCount === 0} className="rounded-lg bg-amber-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-800 disabled:opacity-50">
              {loading ? 'Applying…' : 'Confirm selected cells'}
            </button>
            <button onClick={() => { setPendingDecision(null); setReplaceExisting(false) }} disabled={loading} className="rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-50">
              Cancel
            </button>
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-xs text-rose-700"><strong>Bulk action failed:</strong> {error}</p>}
    </div>
  )
}

