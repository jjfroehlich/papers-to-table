import { useState } from 'react'
import type { ProposalDetail } from '../lib/types'

interface Props {
  detail: ProposalDetail | null
  onDecision: (decision: 'accept' | 'accept_with_edit' | 'reject', editedValue?: string) => void
  onNext: () => void
  onPrevious: () => void
}

export function ProposalDetailPane({ detail, onDecision, onNext, onPrevious }: Props) {
  const [editedValue, setEditedValue] = useState('')
  if (!detail) return <section aria-label="proposal-detail">Select a proposal.</section>
  const { proposal, row_context: rowContext } = detail
  return (
    <section aria-label="proposal-detail">
      <h2>{proposal.column_name}</h2>
      <p>Current value: {proposal.current_value || '∅'}</p>
      <p>Proposed value: {proposal.proposed_value || 'No proposal'}</p>
      <p>Support: {proposal.support_label}</p>
      <p>Rationale: {proposal.rationale || '—'}</p>
      <p>Calculation: {proposal.calculation || '—'}</p>
      <p>Title: {rowContext.Title}</p>
      {proposal.warning_flags.map((warning) => <p key={warning}>Warning: {warning}</p>)}
      <label>
        Edit accepted value
        <input aria-label="edit-value" value={editedValue} onChange={(event) => setEditedValue(event.target.value)} />
      </label>
      <div>
        <button onClick={() => onDecision('accept')}>Accept</button>
        <button onClick={() => onDecision('accept_with_edit', editedValue)}>Accept with edit</button>
        <button onClick={() => onDecision('reject')}>Reject</button>
      </div>
      <div>
        <button onClick={onPrevious}>Previous</button>
        <button onClick={onNext}>Next</button>
      </div>
    </section>
  )
}
