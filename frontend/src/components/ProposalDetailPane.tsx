import { useEffect, useMemo, useState } from 'react'
import type { ProposalDetail } from '../lib/types'
import { isActionableProposal } from '../lib/proposals'

interface Props {
  detail: ProposalDetail | null
  onDecision: (decision: 'accept' | 'accept_with_edit' | 'reject', editedValue?: string) => void
  onNext: () => void
  onPrevious: () => void
}

function supportBadge(detail: ProposalDetail): string {
  if (detail.proposal.proposal_state === 'blocked' || detail.proposal.proposal_state === 'error') return 'badge badge-warning'
  if (detail.proposal.source_mode === 'vision') return 'badge badge-accent'
  if (detail.proposal.support_label === 'Direct evidence') return 'badge badge-success'
  return 'badge badge-neutral'
}

export function ProposalDetailPane({ detail, onDecision, onNext, onPrevious }: Props) {
  const [editedValue, setEditedValue] = useState('')

  useEffect(() => {
    setEditedValue(detail?.proposal.reviewed_value ?? detail?.proposal.proposed_value ?? '')
  }, [detail])

  const uniqueWarnings = useMemo(() => Array.from(new Set(detail?.proposal.warning_flags ?? [])), [detail])

  if (!detail) {
    return (
      <section className="panel" aria-label="proposal-detail">
        <h2 className="section-title">Proposal detail</h2>
        <p className="empty-state">Select a proposal to inspect the row context, rationale, warnings, and review actions.</p>
      </section>
    )
  }

  const { proposal, row_context: rowContext, primary_evidence: primaryEvidence } = detail
  const actionable = isActionableProposal(proposal)
  const baseAcceptedValue = proposal.reviewed_value ?? proposal.proposed_value ?? ''
  const shouldDisableAcceptEdit = !editedValue.trim() || editedValue.trim() === baseAcceptedValue.trim()

  return (
    <section className="panel" aria-label="proposal-detail">
      <div className="section-title-row">
        <div>
          <h2 className="section-title">{proposal.column_name}</h2>
          <p className="section-caption">{rowContext.Title ?? 'Untitled row'} · {proposal.pdf_name}</p>
        </div>
        <div className="badge-row">
          <span className={supportBadge(detail)}>{proposal.support_label}</span>
          <span className={proposal.review_decision === 'no_decision' ? 'badge badge-neutral' : 'badge badge-success'}>
            {proposal.review_decision.replace(/_/g, ' ')}
          </span>
        </div>
      </div>

      <div className="detail-grid">
        <article className="detail-card">
          <span className="detail-label">Current value</span>
          <p className="detail-value">{proposal.current_value || '∅ Empty cell'}</p>
        </article>
        <article className="detail-card">
          <span className="detail-label">Proposed value</span>
          <p className="detail-value detail-value-large">{proposal.proposed_value || 'No proposal available'}</p>
        </article>
        <article className="detail-card">
          <span className="detail-label">Source mode</span>
          <p className="detail-value">{proposal.source_mode === 'vision' ? 'Figure-backed fallback' : 'Text-first extraction'}</p>
        </article>
        <article className="detail-card">
          <span className="detail-label">Evidence</span>
          <p className="detail-value">
            {primaryEvidence ? `Primary evidence on page ${primaryEvidence.page}` : 'No evidence item attached'}
          </p>
        </article>
      </div>

      <div className="stack" style={{ marginTop: '0.9rem' }}>
        <article className="detail-card">
          <span className="detail-label">Rationale</span>
          <p className="detail-value">{proposal.rationale || 'No rationale recorded for this proposal.'}</p>
        </article>
        <article className="detail-card">
          <span className="detail-label">Calculation / derivation</span>
          <p className="detail-value">{proposal.calculation || 'No calculation recorded.'}</p>
        </article>
        <article className="detail-card">
          <span className="detail-label">Row context</span>
          <div className="detail-grid" style={{ marginTop: '0.7rem' }}>
            {Object.entries(rowContext)
              .filter(([key]) => ['Title', 'Authors', 'Publication Year'].includes(key))
              .map(([key, value]) => (
                <div key={key}>
                  <span className="detail-label">{key}</span>
                  <p className="detail-value">{value || '—'}</p>
                </div>
              ))}
          </div>
        </article>
        {uniqueWarnings.length > 0 && (
          <article className="detail-card">
            <span className="detail-label">Warnings</span>
            <ul className="warning-list">
              {uniqueWarnings.map((warning, index) => (
                <li key={index}>{warning.replace(/_/g, ' ')}</li>
              ))}
            </ul>
          </article>
        )}
      </div>

      <div className="stack" style={{ marginTop: '0.95rem' }}>
        <label className="field-group">
          <span className="field-label">Accepted value</span>
          <input
            className="field-input"
            aria-label="edit-value"
            value={editedValue}
            onChange={(event) => setEditedValue(event.target.value)}
            placeholder="Edit the accepted value before saving"
          />
        </label>
        <p className="support-note">Edit the accepted value only when the proposal is close but needs a curator fix. Saving an edited acceptance requires a non-empty value that differs from the proposed value.</p>
        {!actionable && (
          <p className="support-note">
            This record is blocked or missing a proposed value, so accept actions stay disabled. You can still inspect the context and reject it explicitly.
          </p>
        )}
        <div className="action-row">
          <button className="button-primary" onClick={() => onDecision('accept')} disabled={!actionable}>Accept as-is</button>
          <button className="button-secondary" onClick={() => onDecision('accept_with_edit', editedValue)} disabled={!actionable || shouldDisableAcceptEdit}>
            Save edited value
          </button>
          <button className="button-danger" onClick={() => onDecision('reject')}>Reject</button>
        </div>
        <div className="nav-row">
          <p className="support-note">Shortcuts: use the queue to jump around, then previous/next to stay in flow.</p>
          <div className="action-row">
            <button className="button-secondary" onClick={onPrevious}>Previous</button>
            <button className="button-secondary" onClick={onNext}>Next</button>
          </div>
        </div>
      </div>
    </section>
  )
}
