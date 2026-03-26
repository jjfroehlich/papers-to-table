/**
 * T090 + T090a — Review action area.
 *
 * Actions: accept, accept-with-edit, reject, next, previous, bulk-accept.
 * Accept-with-edit is a distinct save-edited-value action (reviewer-safe).
 * Bulk-accept confirms against the currently visible filtered subset.
 * Blocked proposals and proposals without a reviewable value cannot be accepted.
 */
import { useState } from 'react'
import type { ProposalDetail, ReviewDecision } from '../types'

interface Props {
  proposal: ProposalDetail
  onDecision: (decision: ReviewDecision, editedValue?: string) => Promise<void>
  onNext: () => void
  onPrev: () => void
  onBulkAccept: () => Promise<void>
  hasPrev: boolean
  hasNext: boolean
  isBusy: boolean
}

export function ReviewActionArea({
  proposal,
  onDecision,
  onNext,
  onPrev,
  onBulkAccept,
  hasPrev,
  hasNext,
  isBusy,
}: Props) {
  const [editValue, setEditValue] = useState('')
  const [showBulkConfirm, setShowBulkConfirm] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)

  const isBlocked =
    proposal.proposal_state === 'blocked' ||
    proposal.proposal_state === 'error' ||
    proposal.proposal_state === 'skipped'

  const hasProposedValue = proposal.proposed_value != null && proposal.proposed_value.trim() !== ''

  const canAccept = !isBlocked && hasProposedValue && !isBusy
  const canReject = !isBusy
  const currentDecision = proposal.latest_decision

  async function doDecision(decision: ReviewDecision, editedValue?: string) {
    setActionError(null)
    try {
      await onDecision(decision, editedValue)
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Action failed')
    }
  }

  async function handleAccept() {
    await doDecision('accept')
  }

  async function handleAcceptWithEdit() {
    if (editValue.trim() === '') {
      setActionError('Enter an edited value before saving.')
      return
    }
    await doDecision('accept_with_edit', editValue.trim())
    setEditValue('')
  }

  async function handleReject() {
    await doDecision('reject')
  }

  async function handleBulkAccept() {
    setActionError(null)
    setShowBulkConfirm(false)
    try {
      await onBulkAccept()
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Bulk accept failed')
    }
  }

  return (
    <div className="review-action-area" role="region" aria-label="Review actions">
      {actionError && <p className="error">{actionError}</p>}

      {isBlocked && (
        <p className="warning-text">
          ⚠ This proposal is {proposal.proposal_state}. Accept actions are disabled.
        </p>
      )}

      {!hasProposedValue && !isBlocked && (
        <p className="warning-text">⚠ No proposed value — accept is disabled.</p>
      )}

      <div className="action-row primary-actions">
        <button
          className={`btn-action accept ${currentDecision === 'accept' ? 'active-decision' : ''}`}
          onClick={handleAccept}
          disabled={!canAccept}
          title="Accept proposed value (A)"
          aria-label="Accept"
        >
          ✓ Accept
        </button>
        <button
          className={`btn-action reject ${currentDecision === 'reject' ? 'active-decision' : ''}`}
          onClick={handleReject}
          disabled={!canReject}
          title="Reject proposal (R)"
          aria-label="Reject"
        >
          ✕ Reject
        </button>
      </div>

      <div className="edit-accept-row">
        <input
          className="edit-value-input"
          value={editValue}
          onChange={(e) => setEditValue(e.target.value)}
          placeholder={proposal.proposed_value ?? 'Enter edited value'}
          aria-label="Edited value"
          disabled={isBlocked || isBusy}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              if (!isBlocked && !isBusy) void handleAcceptWithEdit()
            }
          }}
        />
        <button
          className={`btn-action accept-edit ${currentDecision === 'accept_with_edit' ? 'active-decision' : ''}`}
          onClick={handleAcceptWithEdit}
          disabled={isBlocked || isBusy}
          title="Save edited value and accept (E)"
          aria-label="Accept with edit"
        >
          ✎ Save edit &amp; accept
        </button>
      </div>

      <div className="action-row nav-actions">
        <button
          className="btn-nav"
          onClick={onPrev}
          disabled={!hasPrev || isBusy}
          title="Previous proposal (←)"
          aria-label="Previous proposal"
        >
          ← Prev
        </button>
        <button
          className="btn-nav"
          onClick={onNext}
          disabled={!hasNext || isBusy}
          title="Next proposal (→)"
          aria-label="Next proposal"
        >
          Next →
        </button>
      </div>

      <div className="bulk-accept-row">
        {!showBulkConfirm ? (
          <button
            className="btn-bulk"
            onClick={() => setShowBulkConfirm(true)}
            disabled={isBusy}
            title="Bulk accept all undecided proposals in the current filtered view"
          >
            Bulk accept visible undecided…
          </button>
        ) : (
          <div className="bulk-confirm">
            <span>Accept all undecided proposals in the current filter? This cannot be undone.</span>
            <button className="btn-action accept" onClick={handleBulkAccept} disabled={isBusy}>
              Confirm bulk accept
            </button>
            <button className="btn-nav" onClick={() => setShowBulkConfirm(false)} disabled={isBusy}>
              Cancel
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
