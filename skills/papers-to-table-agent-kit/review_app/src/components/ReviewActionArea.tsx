import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { EnrichedProposal } from '../types'

interface Props {
  proposal: EnrichedProposal
  runId: string
  outputDir: string
  onDecisionRecorded: (options?: { autoAdvance?: boolean }) => void
  onNext: () => void
  onPrev: () => void
  visibleProposals: EnrichedProposal[]
  focusEditSignal?: number
}

export function ReviewActionArea({
  proposal,
  runId,
  outputDir,
  onDecisionRecorded,
  onNext,
  onPrev,
  visibleProposals,
  focusEditSignal = 0,
}: Props) {
  const [editValue, setEditValue] = useState('')
  const [showEditInput, setShowEditInput] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showBulkConfirm, setShowBulkConfirm] = useState(false)
  const editInputRef = useRef<HTMLInputElement | null>(null)

  // Only count proposals that have not yet been decided (pending)
  const pendingProposals = visibleProposals.filter(
    (p) => p.proposal_id !== proposal.proposal_id && !p.latest_decision
  )
  const pendingCount = pendingProposals.length

  useEffect(() => {
    if (focusEditSignal === 0) return
    setShowEditInput(true)
  }, [focusEditSignal])

  useEffect(() => {
    if (!showEditInput) return
    editInputRef.current?.focus()
    editInputRef.current?.select()
  }, [showEditInput, focusEditSignal])

  async function decide(
    decision: string,
    extras?: { edited_value?: string; reviewer_note?: string }
  ) {
    setLoading(true)
    setError(null)
    try {
      await api.recordDecision(runId, proposal.proposal_id, { decision, ...extras }, outputDir)
      setShowEditInput(false)
      setEditValue('')
      onDecisionRecorded({ autoAdvance: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  async function handleBulkAccept() {
    setShowBulkConfirm(false)
    setLoading(true)
    setError(null)
    try {
      // Include the current proposal if not yet decided
      const ids = proposal.latest_decision
        ? pendingProposals.map((p) => p.proposal_id)
        : [proposal.proposal_id, ...pendingProposals.map((p) => p.proposal_id)]
      await api.bulkAccept(runId, ids, outputDir)
      onDecisionRecorded()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const isDecided = !!proposal.latest_decision
  const currentDecision = proposal.latest_decision?.decision

  return (
    <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-2.5" data-testid="review-action-area">
      {/* Current decision indicator */}
      {isDecided && (
        <div className="mb-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Decision: <strong>{currentDecision?.replace(/_/g, ' ')}</strong>
          {proposal.latest_decision?.edited_value && (
            <span> → <em>{proposal.latest_decision.edited_value}</em></span>
          )}
          <span className="ml-2 text-slate-400">
            {new Date(proposal.latest_decision!.decided_at).toLocaleTimeString()}
          </span>
        </div>
      )}

      {/* Edit input */}
      {showEditInput && (
        <div className="flex flex-wrap gap-2">
          <input
            ref={editInputRef}
            autoFocus
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && editValue.trim()) {
                decide('accepted_with_edit', { edited_value: editValue.trim() })
              } else if (e.key === 'Escape') {
                setShowEditInput(false)
              }
            }}
            placeholder="Enter corrected value…"
            className="min-w-[220px] flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
          <button
            onClick={() => decide('accepted_with_edit', { edited_value: editValue.trim() })}
            disabled={!editValue.trim() || loading}
            className="rounded-lg bg-slate-950 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={() => setShowEditInput(false)}
            className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Main action buttons */}
      {!showEditInput && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="mr-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Decision</span>
          <button
            onClick={onPrev}
            disabled={loading}
            title="Previous ([)"
            aria-label="Previous proposal"
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            ←
          </button>
          <button
            onClick={() => decide('rejected')}
            disabled={loading}
            title="Reject (R)"
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Reject
          </button>
          <button
            onClick={() => setShowEditInput(true)}
            disabled={loading}
            title="Edit proposed value (E)"
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Edit
          </button>
          <button
            onClick={() => decide('confirmed_no_data')}
            disabled={loading}
            className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            No Data
          </button>
          <button
            onClick={() => decide('accepted')}
            disabled={loading}
            title="Accept (A)"
            className="rounded-md border border-emerald-600 bg-emerald-600 px-3.5 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
          >
            Accept
          </button>
          <button
            onClick={onNext}
            disabled={loading}
            title="Next (])"
            aria-label="Next proposal"
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-50"
          >
            →
          </button>
        </div>
      )}

      {/* Bulk accept */}
      {pendingCount > 0 && !showEditInput && (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBulkConfirm(true)}
            disabled={loading}
            className="text-xs text-slate-500 underline hover:text-slate-700"
          >
            Bulk accept {pendingCount} pending proposal{pendingCount !== 1 ? 's' : ''}…
          </button>
        </div>
      )}

      {/* Bulk confirm dialog */}
      {showBulkConfirm && (
        <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50 p-3">
          <p className="text-xs font-medium text-amber-800">
            Bulk accept {pendingCount + (proposal.latest_decision ? 0 : 1)} pending proposals?
          </p>
          <p className="text-xs text-amber-700">This will accept all pending proposals in the current view and record decision_source=human_bulk_accept. These cells are not individually reviewed decisions.</p>
          <div className="flex gap-2">
            <button
              onClick={handleBulkAccept}
              className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700"
            >
              Confirm bulk accept
            </button>
            <button
              onClick={() => setShowBulkConfirm(false)}
              className="rounded-lg border border-amber-300 px-3 py-1.5 text-xs font-semibold text-amber-900 hover:bg-amber-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-xs text-rose-600">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  )
}
