/**
 * T084 — Proposal queue pane with filtering, ordering, and stable selection.
 *
 * Ordering rules:
 * 1. Pending/undecided proposals before reviewed proposals.
 * 2. Within undecided: actionable proposals before blocked/unclear/skipped/error.
 * 3. Within same decision-status bucket: stable row order, then column order, then proposal_id.
 *
 * Filters: decision status, support label, figure evidence, ambiguous match, source mode.
 * Selection does NOT record decisions. Stale proposal/detail/evidence state is cleared on run switch.
 */
import { useEffect, useMemo, useState } from 'react'
import type { DecisionFilter, ProposalListItem, WarningStatusCategory } from '../types'
import { flagDisplay, proposalStateDisplay, supportLabelDisplay } from './proposalFormatters'

interface Props {
  proposals: ProposalListItem[]
  selectedId: string | null
  onSelect: (proposalId: string) => void
  onFilterChange?: (filter: QueueFilter) => void
  loading: boolean
}

export interface QueueFilter {
  decision: DecisionFilter
  hasFigureEvidence: boolean | null
  hasAmbiguousMatch: boolean | null
}

const DECISION_ORDER: Record<string, number> = {
  undecided: 0,
  accept: 1,
  accept_with_edit: 1,
  reject: 1,
}

const STATE_ORDER: Record<string, number> = {
  actionable: 0,
  unclear: 1,
  blocked: 2,
  skipped: 3,
  error: 4,
}

function sortProposals(items: ProposalListItem[]): ProposalListItem[] {
  return [...items].sort((a, b) => {
    // 1. Undecided before decided
    const da = DECISION_ORDER[a.latest_decision] ?? 0
    const db = DECISION_ORDER[b.latest_decision] ?? 0
    if (da !== db) return da - db

    // 2. Within undecided: actionable before others
    if (da === 0) {
      const sa = STATE_ORDER[a.proposal_state] ?? 99
      const sb = STATE_ORDER[b.proposal_state] ?? 99
      if (sa !== sb) return sa - sb
    }

    // 3. Stable order: row_id, column_name, proposal_id
    if (a.row_id !== b.row_id) return a.row_id.localeCompare(b.row_id)
    if (a.column_name !== b.column_name) return a.column_name.localeCompare(b.column_name)
    return a.proposal_id.localeCompare(b.proposal_id)
  })
}

function filterProposals(items: ProposalListItem[], filter: QueueFilter): ProposalListItem[] {
  return items.filter((p) => {
    if (filter.decision !== 'all' && p.latest_decision !== filter.decision) return false
    if (filter.hasFigureEvidence === true && !p.status_flags.includes('figure_derived')) return false
    if (filter.hasFigureEvidence === false && p.status_flags.includes('figure_derived')) return false
    if (filter.hasAmbiguousMatch === true && !p.status_flags.includes('ambiguous_match')) return false
    if (filter.hasAmbiguousMatch === false && p.status_flags.includes('ambiguous_match')) return false
    return true
  })
}

function decisionLabel(d: string): string {
  switch (d) {
    case 'undecided': return 'Pending'
    case 'accept': return '✓'
    case 'accept_with_edit': return '✎'
    case 'reject': return '✕'
    default: return d
  }
}

function decisionClass(d: string): string {
  switch (d) {
    case 'accept': return 'decided-accept'
    case 'accept_with_edit': return 'decided-edit'
    case 'reject': return 'decided-reject'
    default: return 'decided-pending'
  }
}

export function ProposalQueue({ proposals, selectedId, onSelect, onFilterChange, loading }: Props) {
  const [filter, setFilter] = useState<QueueFilter>({
    decision: 'all',
    hasFigureEvidence: null,
    hasAmbiguousMatch: null,
  })

  function updateFilter(patch: Partial<QueueFilter>) {
    setFilter((prev) => {
      const next = { ...prev, ...patch }
      onFilterChange?.(next)
      return next
    })
  }

  const sorted = useMemo(() => {
    const filtered = filterProposals(proposals, filter)
    return sortProposals(filtered)
  }, [proposals, filter])

  // Count by decision for counters
  const pendingCount = proposals.filter((p) => p.latest_decision === 'undecided').length
  const decidedCount = proposals.length - pendingCount

  // Auto-select first item when the sorted list changes and nothing is selected
  useEffect(() => {
    if (sorted.length === 0) return
    const selectedIndex = sorted.findIndex((p) => p.proposal_id === selectedId)
    if (selectedIndex === -1) {
      onSelect(sorted[0].proposal_id)
    }
  }, [sorted, selectedId, onSelect])

  return (
    <div className="proposal-queue">
      <div className="queue-header">
        <div className="queue-counters">
          <span className="counter pending">{pendingCount} pending</span>
          <span className="counter decided">{decidedCount} reviewed</span>
          <span className="counter total">/ {proposals.length} total</span>
        </div>
        <div className="queue-filters" role="group" aria-label="Queue filters">
          <label htmlFor="filter-decision">Status</label>
          <select
            id="filter-decision"
            value={filter.decision}
            onChange={(e) => updateFilter({ decision: e.target.value as DecisionFilter })}
          >
            <option value="all">All</option>
            <option value="undecided">Pending</option>
            <option value="accept">Accepted</option>
            <option value="accept_with_edit">Accepted with edit</option>
            <option value="reject">Rejected</option>
          </select>

          <label htmlFor="filter-figure">Figure evidence</label>
          <select
            id="filter-figure"
            value={filter.hasFigureEvidence == null ? 'all' : String(filter.hasFigureEvidence)}
            onChange={(e) => {
              const v = e.target.value
              updateFilter({ hasFigureEvidence: v === 'all' ? null : v === 'true' })
            }}
          >
            <option value="all">Any</option>
            <option value="true">Has figure</option>
            <option value="false">No figure</option>
          </select>

          <label htmlFor="filter-ambiguous">Match</label>
          <select
            id="filter-ambiguous"
            value={filter.hasAmbiguousMatch == null ? 'all' : String(filter.hasAmbiguousMatch)}
            onChange={(e) => {
              const v = e.target.value
              updateFilter({ hasAmbiguousMatch: v === 'all' ? null : v === 'true' })
            }}
          >
            <option value="all">Any</option>
            <option value="false">Matched</option>
            <option value="true">Ambiguous</option>
          </select>
        </div>
      </div>

      {loading && <p className="muted">Loading proposals…</p>}

      {!loading && sorted.length === 0 && (
        <p className="muted">
          {proposals.length === 0
            ? 'No proposals for this run.'
            : 'No proposals match the current filters.'}
        </p>
      )}

      <ul className="queue-list" role="listbox" aria-label="Proposals">
        {sorted.map((p) => {
          const isSelected = p.proposal_id === selectedId
          const flags = p.status_flags as WarningStatusCategory[]
          const hasWarning = flags.some((f) => ['weak_evidence', 'ambiguous_match', 'duplicate_row_conflict'].includes(f))
          const isFigure = flags.includes('figure_derived')

          return (
            <li
              key={p.proposal_id}
              role="option"
              aria-selected={isSelected}
              className={[
                'queue-item',
                isSelected ? 'selected' : '',
                decisionClass(p.latest_decision),
                hasWarning ? 'has-warning' : '',
              ]
                .filter(Boolean)
                .join(' ')}
              onClick={() => onSelect(p.proposal_id)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') onSelect(p.proposal_id) }}
              tabIndex={0}
            >
              <div className="queue-item-main">
                <span className="item-column">{p.column_name}</span>
                <span className="item-row-id muted">{p.row_id}</span>
              </div>
              <div className="queue-item-meta">
                <span className={`decision-badge ${decisionClass(p.latest_decision)}`} title={p.latest_decision}>
                  {decisionLabel(p.latest_decision)}
                </span>
                <span className={`state-chip state-${p.proposal_state}`} title={proposalStateDisplay(p.proposal_state)}>
                  {proposalStateDisplay(p.proposal_state)}
                </span>
                <span className={`support-chip support-${p.support_label}`} title={supportLabelDisplay(p.support_label)}>
                  {p.support_label === 'strong_evidence' ? '●●●' :
                   p.support_label === 'moderate_evidence' ? '●●○' :
                   p.support_label === 'weak_evidence' ? '●○○' : '○○○'}
                </span>
                {isFigure && <span className="badge-fig" title={flagDisplay('figure_derived')}>Fig</span>}
                {hasWarning && !isFigure && <span className="badge-warn" title="Has warnings">⚠</span>}
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
