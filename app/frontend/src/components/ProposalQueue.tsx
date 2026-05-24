import { useEffect, useState, useMemo } from 'react'
import { api } from '../api/client'
import type { EnrichedProposal, ReviewDecision } from '../types'
import { ReviewTableView, type ReviewFilter, type SelectedReviewCell } from './ReviewTableView'
import {
  ProposalStateIndicator,
  ProposalSupportIndicator,
  ReviewStatusIndicator,
  WarningIndicator,
} from './ReviewTags'

interface Props {
  runId: string
  outputDir: string
  selectedProposalId: string | null
  onSelect: (proposalId: string) => void
  mode: LeftPaneMode
  filter: ReviewFilter
  onModeChange: (mode: LeftPaneMode) => void
  onFilterChange: (filter: ReviewFilter) => void
  onSelectCell?: (cell: SelectedReviewCell) => void
  refreshVersion?: number
}

export type LeftPaneMode = 'paper' | 'column' | 'table'

const DECISION_FILTER_MAP: Record<ReviewFilter, ReviewDecision | 'undecided' | null> = {
  all: null,
  pending: 'undecided',
  needs_attention: null,
  accepted: 'accepted',
  accepted_with_edit: 'accepted_with_edit',
  confirmed_no_data: 'confirmed_no_data',
  rejected: 'rejected',
}

function stateColor(p: EnrichedProposal): string {
  const decision = p.latest_decision?.decision
  if (!decision) {
    if (p.state === 'blocked') return 'border-amber-300'
    return 'border-slate-200'
  }
  switch (decision) {
    case 'accepted':
    case 'accepted_with_edit':
      return 'border-emerald-300'
    case 'confirmed_no_data':
      return 'border-violet-300'
    case 'rejected':
      return 'border-rose-200'
    default:
      return 'border-slate-200'
  }
}

function isPending(p: EnrichedProposal) {
  return !p.latest_decision
}

function getLeadAuthor(authors?: string | null): string | null {
  if (!authors) return null
  const firstAuthor = authors
    .split(/;|,\s+(?=[A-Z][a-z])/)[0]
    ?.trim()
  if (!firstAuthor) return null
  const surname = firstAuthor.split(',')[0]?.trim() || firstAuthor.split(' ').at(-1)?.trim()
  return surname || firstAuthor
}

function buildPaperGroupLabel(proposal: EnrichedProposal): string {
  const author = getLeadAuthor(proposal.paper_authors)
  const year = proposal.paper_year ? String(proposal.paper_year) : null
  const title = proposal.paper_title?.trim()
  const citation = author && year
    ? `${author} et al. ${year}`
    : author || year || proposal.pdf_id
  if (!title) return citation
  const compactTitle = title.length > 56 ? `${title.slice(0, 56).trimEnd()}...` : title
  return `${citation} - ${compactTitle}`
}

function groupStats(items: EnrichedProposal[]) {
  return {
    pending: items.filter(isPending).length,
  }
}

function proposalMatchesFilter(proposal: EnrichedProposal, filter: ReviewFilter) {
  if (filter === 'all') return true
  if (filter === 'pending') return !proposal.latest_decision
  if (filter === 'needs_attention') {
    return (
      proposal.warning_flags.length > 0 ||
      proposal.warning_categories.length > 0 ||
      proposal.support === 'weak_evidence' ||
      proposal.is_fallback_evidence
    )
  }
  return proposal.latest_decision?.decision === filter
}

export function ProposalQueue({
  runId,
  outputDir,
  selectedProposalId,
  onSelect,
  mode,
  filter,
  onModeChange,
  onFilterChange,
  onSelectCell,
  refreshVersion = 0,
}: Props) {
  const [proposals, setProposals] = useState<EnrichedProposal[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    const decisionParam = DECISION_FILTER_MAP[filter]
    async function load() {
      if (mode === 'table') {
        setLoading(false)
        return
      }
      setProposals([])
      setLoading(true)
      setError(null)
      setCollapsedGroups(new Set())
      try {
        const resp = await api.listProposals(runId, {
          output_dir: outputDir,
          reviewable_only: true,
          ...(decisionParam && filter !== 'needs_attention' ? { decision: decisionParam } : {}),
        })
        if (!cancelled) setProposals(resp.proposals)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [runId, outputDir, filter, mode, refreshVersion])

  const filtered = useMemo(() => {
    return proposals.filter((proposal) => proposalMatchesFilter(proposal, filter))
  }, [proposals, filter])

  const groups = useMemo(() => {
    const map = new Map<string, EnrichedProposal[]>()
    for (const p of filtered) {
      const key = mode === 'paper' ? p.pdf_id : p.column_name
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(p)
    }
    // Sort groups: pending groups first
    return Array.from(map.entries()).sort(([, a], [, b]) => {
      const aPending = a.filter(isPending).length
      const bPending = b.filter(isPending).length
      return bPending - aPending
    })
  }, [filtered, mode])

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-gray-400">
        Loading proposals…
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-3 text-sm text-red-600">
        <strong>Error:</strong> {error}
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Controls */}
      <div className="shrink-0 border-b border-slate-200 bg-white px-4 py-4 space-y-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Review list</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            Pick cells by paper, by column, or from the table.
          </p>
        </div>
        {/* Group toggle */}
        <div className="flex gap-1">
          <button
            onClick={() => onModeChange('paper')}
            className={`flex-1 rounded-xl px-3 py-2 text-xs font-medium ${
              mode === 'paper'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'bg-slate-50 text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-100'
            }`}
          >
            By Paper
          </button>
          <button
            onClick={() => onModeChange('column')}
            className={`flex-1 rounded-xl px-3 py-2 text-xs font-medium ${
              mode === 'column'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'bg-slate-50 text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-100'
            }`}
          >
            By Column
          </button>
          <button
            onClick={() => onModeChange('table')}
            className={`flex-1 rounded-xl px-3 py-2 text-xs font-medium ${
              mode === 'table'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'bg-slate-50 text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-100'
            }`}
          >
            As Table
          </button>
        </div>
      </div>

      {mode === 'table' ? (
        <ReviewTableView
          runId={runId}
          outputDir={outputDir}
          selectedProposalId={selectedProposalId}
          filter={filter}
          onFilterChange={onFilterChange}
          onSelect={onSelect}
          onSelectCell={onSelectCell}
          refreshVersion={refreshVersion}
        />
      ) : (
        <>
          <div className="shrink-0 space-y-3 border-b border-slate-200 bg-white px-4 py-3">
        {/* Filter */}
        <select
          value={filter}
          onChange={(e) => onFilterChange(e.target.value as ReviewFilter)}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs text-slate-700"
        >
            <option value="pending">Pending</option>
            <option value="needs_attention">Attention</option>
            <option value="all">All</option>
            <option value="accepted">Reviewed - Accepted</option>
            <option value="accepted_with_edit">Reviewed - Edited</option>
            <option value="confirmed_no_data">Reviewed - No data</option>
            <option value="rejected">Reviewed - Rejected</option>
        </select>
      </div>

      {/* Group list */}
      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3" data-testid="proposal-queue-scroll">
        {groups.length === 0 && (
          <div className="p-4 text-center text-sm text-slate-400">No proposals match the current filter.</div>
        )}
        {groups.map(([key, items]) => {
          const stats = groupStats(items)
          const isCollapsed = collapsedGroups.has(key)
          const groupLabel = mode === 'paper' ? buildPaperGroupLabel(items[0]) : key
          return (
            <div key={key} className="mb-3 overflow-hidden rounded-[18px] border border-slate-300 bg-white last:mb-0">
              {/* Group header */}
              <button
                className="w-full border-b border-slate-200 bg-slate-100 px-3 py-3 text-left hover:bg-slate-200/70"
                onClick={() => toggleGroup(key)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <span className="block truncate text-[13px] font-semibold text-slate-900" title={groupLabel}>
                      {groupLabel}
                    </span>
                    <p className="mt-1 text-[11px] text-slate-500">
                      {stats.pending} pending · {items.length} item{items.length !== 1 ? 's' : ''}
                    </p>
                  </div>
                  <span className="flex items-center gap-2 shrink-0 text-xs text-slate-400">
                    <span>{isCollapsed ? '▶' : '▼'}</span>
                  </span>
                </div>
              </button>

              {/* Cards */}
              {!isCollapsed &&
                <div className="space-y-1 bg-slate-50 px-2 py-2">
                  {items.map((p) => (
                    <button
                      key={p.proposal_id}
                      onClick={() => onSelect(p.proposal_id)}
                      title={p.proposed_value || 'No value proposed'}
                      className={`w-full rounded-xl border px-3 py-2.5 text-left transition-colors ${stateColor(p)} ${
                        selectedProposalId === p.proposal_id
                          ? 'bg-sky-50 shadow-sm ring-1 ring-sky-200'
                          : 'bg-white hover:bg-slate-50'
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="min-w-0 flex-1">
                          {mode !== 'column' && (
                            <div className="truncate text-xs font-semibold text-slate-900">
                              {p.column_name}
                            </div>
                          )}
                          <div className="mt-1 truncate text-sm text-slate-700">
                            {p.proposed_value || 'No value proposed'}
                          </div>
                          {mode === 'column' && (
                            <div className="mt-1 truncate text-[11px] text-slate-400">
                              {buildPaperGroupLabel(p)}
                            </div>
                          )}
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-0">
                          <div className="flex items-center gap-0.5">
                            <ReviewStatusIndicator decision={p.latest_decision?.decision ?? null} size="xs" />
                            <ProposalStateIndicator state={p.state} size="xs" />
                            <ProposalSupportIndicator support={p.support} isFallback={p.is_fallback_evidence} size="xs" />
                          </div>
                          {p.warning_flags.length > 0 && <WarningIndicator size="xs" />}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>}
            </div>
          )
        })}
      </div>

      {/* Footer count */}
      <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-3 text-xs text-slate-500">
        {filtered.length} {filter === 'pending' ? 'pending' : 'review'} proposal{filtered.length !== 1 ? 's' : ''}
      </div>
        </>
      )}
    </div>
  )
}
