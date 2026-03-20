import type { ProposalRecord } from '../lib/types'

interface Props {
  proposals: ProposalRecord[]
  selectedId: string | null
  onSelect: (proposalId: string) => void
  onBulkAccept: () => void
  filter: string
  setFilter: (value: string) => void
}

export function ProposalQueue({ proposals, selectedId, onSelect, onBulkAccept, filter, setFilter }: Props) {
  const visible = proposals.filter((proposal) => {
    if (filter === 'pending') return proposal.review_decision === 'no_decision'
    if (filter === 'figure') return proposal.source_mode === 'vision'
    if (filter === 'needs_evidence') return proposal.needs_more_evidence
    return true
  })

  return (
    <section>
      <div>
        <label>
          Filter
          <select value={filter} onChange={(event) => setFilter(event.target.value)}>
            <option value="all">All</option>
            <option value="pending">Pending</option>
            <option value="figure">Figure evidence</option>
            <option value="needs_evidence">Needs more evidence</option>
          </select>
        </label>
        <button onClick={onBulkAccept}>Bulk accept visible subset</button>
      </div>
      <ul aria-label="proposal-queue">
        {visible.map((proposal) => (
          <li key={proposal.proposal_id}>
            <button
              type="button"
              onClick={() => onSelect(proposal.proposal_id)}
              aria-current={selectedId === proposal.proposal_id}
            >
              {proposal.row_id} · {proposal.column_name} · {proposal.support_label} · {proposal.review_decision}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
