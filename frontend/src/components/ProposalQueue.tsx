import type { ProposalRecord } from '../lib/types'
import { isActionableProposal, type ProposalFilter } from '../lib/proposals'

interface Props {
  proposals: ProposalRecord[]
  visible: ProposalRecord[]
  selectedId: string | null
  onSelect: (proposalId: string) => void
  onBulkAccept: () => void
  filter: ProposalFilter
  setFilter: (value: ProposalFilter) => void
}

function badgeClass(proposal: ProposalRecord): string {
  if (proposal.review_decision === 'accept' || proposal.review_decision === 'accept_with_edit') return 'badge badge-success'
  if (proposal.review_decision === 'reject') return 'badge badge-danger'
  if (proposal.proposal_state === 'blocked' || proposal.proposal_state === 'error') return 'badge badge-warning'
  if (proposal.source_mode === 'vision') return 'badge badge-accent'
  return 'badge badge-neutral'
}

function filterLabel(filter: ProposalFilter): string {
  if (filter === 'pending') return 'pending'
  if (filter === 'figure') return 'figure-backed'
  if (filter === 'needs_evidence') return 'needs evidence'
  return 'all'
}

export function ProposalQueue({ proposals, visible, selectedId, onSelect, onBulkAccept, filter, setFilter }: Props) {
  const pendingCount = proposals.filter((proposal) => proposal.review_decision === 'no_decision').length
  const figureCount = proposals.filter((proposal) => proposal.source_mode === 'vision').length
  const needsEvidenceCount = proposals.filter((proposal) => proposal.needs_more_evidence).length
  const actionableVisible = visible.filter((proposal) => proposal.review_decision === 'no_decision' && isActionableProposal(proposal))

  return (
    <section className="panel" aria-labelledby="proposal-queue-heading">
      <div className="section-title-row">
        <div>
          <h2 className="section-title" id="proposal-queue-heading">Proposal queue</h2>
          <p className="section-caption">Stay in the queue, filter down to a review slice, then move cell by cell.</p>
        </div>
        <span className="badge badge-neutral">{visible.length} visible</span>
      </div>
      <div className="queue-toolbar">
        <div className="field-group" style={{ minWidth: '12rem' }}>
          <label className="field-label" htmlFor="proposal-filter">Filter</label>
          <select
            className="field-select"
            id="proposal-filter"
            aria-label="Filter"
            value={filter}
            onChange={(event) => setFilter(event.target.value as ProposalFilter)}
          >
            <option value="all">All proposals ({proposals.length})</option>
            <option value="pending">Pending ({pendingCount})</option>
            <option value="figure">Figure evidence ({figureCount})</option>
            <option value="needs_evidence">Needs more evidence ({needsEvidenceCount})</option>
          </select>
        </div>
        <button className="button-secondary" onClick={onBulkAccept} disabled={actionableVisible.length === 0}>
          Bulk accept {filterLabel(filter)} subset ({actionableVisible.length})
        </button>
      </div>
      <div className="queue-summary">
        <span className="badge badge-neutral">Pending {pendingCount}</span>
        <span className="badge badge-accent">Figure {figureCount}</span>
        <span className="badge badge-warning">Needs evidence {needsEvidenceCount}</span>
      </div>
      <p className="support-note" aria-live="polite" style={{ marginTop: '0.75rem' }}>
        {actionableVisible.length} actionable pending proposal{actionableVisible.length === 1 ? '' : 's'} in the current filter.
      </p>
      <ul aria-label="proposal-queue" className="queue-list">
        {visible.map((proposal) => (
          <li key={proposal.proposal_id}>
            <button
              type="button"
              className="queue-item-button"
              onClick={() => onSelect(proposal.proposal_id)}
              aria-current={selectedId === proposal.proposal_id}
            >
              <div className="queue-item-title">
                <div>
                  <h3 className="queue-item-heading">{proposal.column_name}</h3>
                  <p className="queue-item-meta">{proposal.row_id} · {proposal.pdf_name}</p>
                </div>
                <span className={badgeClass(proposal)}>{proposal.review_decision.replace(/_/g, ' ')}</span>
              </div>
              <div className="badge-row">
                <span className={proposal.proposal_state === 'blocked' ? 'badge badge-warning' : 'badge badge-neutral'}>
                  {proposal.support_label}
                </span>
                <span className={proposal.is_verify_target ? 'badge badge-accent' : 'badge badge-neutral'}>
                  {proposal.is_verify_target ? 'Verify target' : 'Empty target'}
                </span>
                {proposal.needs_more_evidence && <span className="badge badge-warning">Needs evidence</span>}
              </div>
              <p className="queue-item-meta">
                {proposal.proposed_value ? proposal.proposed_value : 'No proposed value; review context only.'}
              </p>
            </button>
          </li>
        ))}
      </ul>
      {visible.length === 0 && <p className="queue-empty">No proposals match the current filter.</p>}
    </section>
  )
}
