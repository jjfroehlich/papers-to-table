import { useEffect, useState, useMemo } from 'react'
import { api } from '../api/client'
import type { EnrichedProposal, ReviewDecision } from '../types'

interface Props {
  runId: string
  outputDir: string
  selectedProposalId: string | null
  onSelect: (proposalId: string) => void
}

type GroupBy = 'paper' | 'column'
type Filter = 'all' | 'pending' | 'accepted' | 'no_data' | 'rejected'

const DECISION_FILTER_MAP: Record<Filter, ReviewDecision | 'undecided' | null> = {
  all: null,
  pending: 'undecided',
  accepted: 'accepted',
  no_data: 'confirmed_no_data',
  rejected: 'rejected',
}

function stateColor(p: EnrichedProposal): string {
  const decision = p.latest_decision?.decision
  if (!decision) {
    if (p.state === 'blocked') return 'border-orange-400'
    return 'border-blue-400'
  }
  switch (decision) {
    case 'accepted':
    case 'accepted_with_edit':
      return 'border-green-500'
    case 'confirmed_no_data':
      return 'border-purple-500'
    case 'rejected':
      return 'border-gray-400'
    default:
      return 'border-blue-400'
  }
}

function SupportBadge({ support }: { support: EnrichedProposal['support'] }) {
  const map: Record<string, { label: string; cls: string }> = {
    direct_evidence: { label: 'direct', cls: 'bg-green-100 text-green-700' },
    inferred_from_evidence: { label: 'inferred', cls: 'bg-yellow-100 text-yellow-700' },
    weak_evidence: { label: 'weak', cls: 'bg-orange-100 text-orange-700' },
    blocked: { label: 'blocked', cls: 'bg-red-100 text-red-700' },
    error: { label: 'error', cls: 'bg-gray-100 text-gray-600' },
  }
  const info = map[support] ?? { label: support, cls: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`px-1 py-0.5 rounded text-xs font-medium ${info.cls}`}>
      {info.label}
    </span>
  )
}

function DecisionBadge({ decision }: { decision: ReviewDecision }) {
  const map: Record<ReviewDecision, { label: string; cls: string }> = {
    accepted: { label: '✓', cls: 'bg-green-100 text-green-700' },
    accepted_with_edit: { label: '✓e', cls: 'bg-teal-100 text-teal-700' },
    confirmed_no_data: { label: 'ND', cls: 'bg-purple-100 text-purple-700' },
    rejected: { label: '✕', cls: 'bg-gray-100 text-gray-600' },
  }
  const info = map[decision]
  return (
    <span className={`px-1 py-0.5 rounded text-xs font-medium ${info.cls}`}>
      {info.label}
    </span>
  )
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
    direct: items.filter((item) => item.support === 'direct_evidence').length,
    weak: items.filter((item) => item.support === 'weak_evidence').length,
    fallback: items.filter((item) => item.is_fallback_evidence).length,
  }
}

export function ProposalQueue({ runId, outputDir, selectedProposalId, onSelect }: Props) {
  const [proposals, setProposals] = useState<EnrichedProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [groupBy, setGroupBy] = useState<GroupBy>('paper')
  const [filter, setFilter] = useState<Filter>('pending')
  const [search, setSearch] = useState('')
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set())

  useEffect(() => {
    let cancelled = false
    const decisionParam = DECISION_FILTER_MAP[filter]
    async function load() {
      setProposals([])
      setLoading(true)
      setError(null)
      setCollapsedGroups(new Set())
      try {
        const resp = await api.listProposals(runId, {
          output_dir: outputDir,
          reviewable_only: true,
          ...(decisionParam ? { decision: decisionParam } : {}),
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
  }, [runId, outputDir, filter])

  const filtered = useMemo(() => {
    let list = proposals
    if (search.trim()) {
      const q = search.toLowerCase()
      list = list.filter(
        (p) =>
          (p.paper_title ?? '').toLowerCase().includes(q) ||
          (p.paper_authors ?? '').toLowerCase().includes(q) ||
          p.column_name.toLowerCase().includes(q) ||
          p.row_id.toLowerCase().includes(q) ||
          (p.proposed_value ?? '').toLowerCase().includes(q)
      )
    }
    return list
  }, [proposals, search])

  const groups = useMemo(() => {
    const map = new Map<string, EnrichedProposal[]>()
    for (const p of filtered) {
      const key = groupBy === 'paper' ? p.pdf_id : p.column_name
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(p)
    }
    // Sort groups: pending groups first
    return Array.from(map.entries()).sort(([, a], [, b]) => {
      const aPending = a.filter(isPending).length
      const bPending = b.filter(isPending).length
      return bPending - aPending
    })
  }, [filtered, groupBy])

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
    <div className="flex flex-col h-full">
      {/* Controls */}
      <div className="shrink-0 border-b border-slate-200 bg-slate-50/80 p-3 space-y-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Queue</p>
          <p className="mt-1 text-xs text-slate-600">
            Triage by paper or column, keep pending items first, and jump directly into evidence review.
          </p>
        </div>
        {/* Group toggle */}
        <div className="flex gap-1">
          <button
            onClick={() => setGroupBy('paper')}
            className={`flex-1 rounded-full px-3 py-1.5 text-xs font-medium ${
              groupBy === 'paper'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-100'
            }`}
          >
            By Paper
          </button>
          <button
            onClick={() => setGroupBy('column')}
            className={`flex-1 rounded-full px-3 py-1.5 text-xs font-medium ${
              groupBy === 'column'
                ? 'bg-slate-900 text-white shadow-sm'
                : 'bg-white text-slate-600 ring-1 ring-inset ring-slate-200 hover:bg-slate-100'
            }`}
          >
            By Column
          </button>
        </div>
        {/* Filter */}
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as Filter)}
          className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-700"
        >
            <option value="pending">Pending</option>
            <option value="all">All reviewable</option>
            <option value="accepted">Accepted</option>
            <option value="no_data">No Data</option>
            <option value="rejected">Rejected</option>
        </select>
        {/* Search */}
        <input
          type="search"
          placeholder="Search…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-lg border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-700"
        />
      </div>

      {/* Group list */}
      <div className="flex-1 overflow-y-auto">
        {groups.length === 0 && (
          <div className="p-4 text-center text-sm text-slate-400">No proposals match the current filter.</div>
        )}
        {groups.map(([key, items]) => {
          const stats = groupStats(items)
          const isCollapsed = collapsedGroups.has(key)
          const groupLabel = groupBy === 'paper' ? buildPaperGroupLabel(items[0]) : key
          return (
            <div key={key} className="border-b border-slate-100 last:border-b-0">
              {/* Group header */}
              <button
                className="w-full px-3 py-2.5 bg-slate-50 hover:bg-slate-100 text-left"
                onClick={() => toggleGroup(key)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <span className="block truncate text-xs font-semibold text-slate-800" title={groupLabel}>
                      {groupLabel}
                    </span>
                    <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                      {stats.pending > 0 && (
                        <span className="rounded-full bg-blue-100 px-2 py-0.5 font-medium text-blue-700">
                          {stats.pending} pending
                        </span>
                      )}
                      {stats.direct > 0 && (
                        <span className="rounded-full bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700">
                          {stats.direct} direct
                        </span>
                      )}
                      {stats.weak > 0 && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-700">
                          {stats.weak} weak
                        </span>
                      )}
                      {stats.fallback > 0 && (
                        <span className="rounded-full bg-orange-100 px-2 py-0.5 font-medium text-orange-700">
                          {stats.fallback} fallback
                        </span>
                      )}
                    </div>
                  </div>
                  <span className="flex items-center gap-2 shrink-0 text-xs text-slate-400">
                    <span>{items.length}</span>
                    <span>{isCollapsed ? '▶' : '▼'}</span>
                  </span>
                </div>
              </button>

              {/* Cards */}
              {!isCollapsed &&
                items.map((p) => (
                  <button
                    key={p.proposal_id}
                    onClick={() => onSelect(p.proposal_id)}
                    className={`w-full border-l-4 px-3 py-2.5 text-left flex items-start gap-3 transition-colors ${stateColor(p)} ${
                      selectedProposalId === p.proposal_id ? 'bg-blue-50/80' : 'bg-white hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-semibold text-slate-800 truncate">
                        {p.column_name}
                      </div>
                      <div className="mt-0.5 text-[11px] text-slate-500 truncate">
                        {groupBy === 'paper'
                          ? (p.proposed_value || p.row_id)
                          : (p.paper_title || p.row_id)}
                      </div>
                      <div className="mt-1 text-[11px] text-slate-400 truncate">{p.row_id}</div>
                    </div>
                    <div className="flex flex-wrap items-center justify-end gap-1 shrink-0">
                      <SupportBadge support={p.support} />
                      {p.is_figure_derived && (
                        <span className="rounded-full bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-700">
                          fig
                        </span>
                      )}
                      {p.is_fallback_evidence && (
                        <span className="rounded-full bg-orange-100 px-1.5 py-0.5 text-[10px] font-medium text-orange-700">
                          fallback
                        </span>
                      )}
                      {p.latest_decision && (
                        <DecisionBadge decision={p.latest_decision.decision} />
                      )}
                      {p.warning_flags.length > 0 && (
                        <span className="text-amber-500 text-xs" title="Has warnings">⚠</span>
                      )}
                    </div>
                  </button>
                ))}
            </div>
          )
        })}
      </div>

      {/* Footer count */}
      <div className="shrink-0 border-t border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
        {filtered.length} {filter === 'pending' ? 'pending' : 'review'} proposal{filtered.length !== 1 ? 's' : ''}
      </div>
    </div>
  )
}
