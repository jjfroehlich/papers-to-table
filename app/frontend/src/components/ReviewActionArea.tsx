import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import type { EnrichedProposal } from '../types'

interface Props {
  proposal: EnrichedProposal
  runId: string
  outputDir: string
  onDecisionRecorded: (options?: { autoAdvance?: boolean }) => void
  onNext: () => void
  visibleProposals: EnrichedProposal[]
  focusEditSignal?: number
}

export function ReviewActionArea({
  proposal,
  runId,
  outputDir,
  onDecisionRecorded,
  onNext,
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
    <div className="shrink-0 border-t border-gray-200 bg-white px-4 py-3 space-y-3">
      {/* Current decision indicator */}
      {isDecided && (
        <div className="text-xs text-gray-500">
          Decision: <strong>{currentDecision?.replace(/_/g, ' ')}</strong>
          {proposal.latest_decision?.edited_value && (
            <span> → <em>{proposal.latest_decision.edited_value}</em></span>
          )}
          <span className="ml-2 text-gray-400">
            {new Date(proposal.latest_decision!.decided_at).toLocaleTimeString()}
          </span>
        </div>
      )}

      {/* Edit input */}
      {showEditInput && (
        <div className="flex gap-2">
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
            className="flex-1 text-sm border border-gray-300 rounded px-2 py-1.5"
          />
          <button
            onClick={() => decide('accepted_with_edit', { edited_value: editValue.trim() })}
            disabled={!editValue.trim() || loading}
            className="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={() => setShowEditInput(false)}
            className="px-3 py-1.5 text-sm rounded border border-gray-200 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Main action buttons */}
      {!showEditInput && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => decide('accepted')}
            disabled={loading}
            title="Accept (A)"
            className="px-3 py-1.5 text-xs rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 font-medium"
          >
            Accept
          </button>
          <button
            onClick={() => setShowEditInput(true)}
            disabled={loading}
            title="Accept with edit"
            className="px-3 py-1.5 text-xs rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 font-medium"
          >
            Accept with Edit
          </button>
          <button
            onClick={() => decide('confirmed_no_data')}
            disabled={loading}
            className="px-3 py-1.5 text-xs rounded bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 font-medium"
          >
            No Data
          </button>
          <button
            onClick={() => decide('rejected')}
            disabled={loading}
            title="Reject (R)"
            className="px-3 py-1.5 text-xs rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50 font-medium"
          >
            Reject
          </button>
          <button
            onClick={onNext}
            disabled={loading}
            title="Next (])"
            className="px-3 py-1.5 text-xs rounded bg-gray-200 text-gray-700 hover:bg-gray-300 disabled:opacity-50 font-medium ml-auto"
          >
            Next →
          </button>
        </div>
      )}

      {/* Bulk accept */}
      {pendingCount > 0 && !showEditInput && (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBulkConfirm(true)}
            disabled={loading}
            className="text-xs text-gray-500 hover:text-gray-700 underline"
          >
            Bulk accept {pendingCount} pending proposal{pendingCount !== 1 ? 's' : ''}…
          </button>
        </div>
      )}

      {/* Bulk confirm dialog */}
      {showBulkConfirm && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3 space-y-2">
          <p className="text-xs font-medium text-amber-800">
            Bulk accept {pendingCount + (proposal.latest_decision ? 0 : 1)} pending proposals?
          </p>
          <p className="text-xs text-amber-700">This will accept all pending proposals in the current view. Review each one after if needed.</p>
          <div className="flex gap-2">
            <button
              onClick={handleBulkAccept}
              className="px-3 py-1 text-xs rounded bg-amber-600 text-white hover:bg-amber-700"
            >
              Confirm bulk accept
            </button>
            <button
              onClick={() => setShowBulkConfirm(false)}
              className="px-3 py-1 text-xs rounded border border-amber-300 hover:bg-amber-100"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="text-xs text-red-600">
          <strong>Error:</strong> {error}
        </div>
      )}
    </div>
  )
}
