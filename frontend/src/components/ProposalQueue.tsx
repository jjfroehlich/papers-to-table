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

export function ProposalQueue({ runId, outputDir, selectedProposalId, onSelect }: Props) {
  const [proposals, setProposals] = useState<EnrichedProposal[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [groupBy, setGroupBy] = useState<GroupBy>('paper')
  const [filter, setFilter] = useState<Filter>('all')
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
  }, [proposals, filter, search])

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
      <div className="p-2 border-b border-gray-100 space-y-2 shrink-0">
        {/* Group toggle */}
        <div className="flex gap-1">
          <button
            onClick={() => setGroupBy('paper')}
            className={`flex-1 py-1 text-xs rounded ${
              groupBy === 'paper'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            By Paper
          </button>
          <button
            onClick={() => setGroupBy('column')}
            className={`flex-1 py-1 text-xs rounded ${
              groupBy === 'column'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            By Column
          </button>
        </div>
        {/* Filter */}
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value as Filter)}
          className="w-full text-xs border border-gray-200 rounded px-2 py-1"
        >
          <option value="all">All</option>
          <option value="pending">Pending</option>
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
          className="w-full text-xs border border-gray-200 rounded px-2 py-1"
        />
      </div>

      {/* Group list */}
      <div className="flex-1 overflow-y-auto">
        {groups.length === 0 && (
          <div className="p-4 text-center text-sm text-gray-400">No proposals match the current filter.</div>
        )}
        {groups.map(([key, items]) => {
          const pendingCount = items.filter(isPending).length
          const isCollapsed = collapsedGroups.has(key)
          const groupLabel = groupBy === 'paper' ? buildPaperGroupLabel(items[0]) : key
          return (
            <div key={key} className="border-b border-gray-100 last:border-b-0">
              {/* Group header */}
              <button
                className="w-full flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 text-left"
                onClick={() => toggleGroup(key)}
              >
                <span className="text-xs font-medium text-gray-700 truncate max-w-52" title={groupLabel}>
                  {groupLabel}
                </span>
                <span className="flex items-center gap-1 shrink-0">
                  {pendingCount > 0 && (
                    <span className="text-xs bg-blue-100 text-blue-700 px-1.5 rounded-full font-medium">
                      {pendingCount}
                    </span>
                  )}
                  <span className="text-xs text-gray-400">{items.length}</span>
                  <span className="text-gray-400 text-xs">{isCollapsed ? '▶' : '▼'}</span>
                </span>
              </button>

              {/* Cards */}
              {!isCollapsed &&
                items.map((p) => (
                  <button
                    key={p.proposal_id}
                    onClick={() => onSelect(p.proposal_id)}
                    className={`w-full text-left px-3 py-2 border-l-4 flex items-start gap-2 hover:bg-gray-50 transition-colors ${stateColor(p)} ${
                      selectedProposalId === p.proposal_id ? 'bg-blue-50' : 'bg-white'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-gray-800 truncate">
                        {p.column_name}
                      </div>
                      <div className="text-xs text-gray-500 truncate">{p.row_id}</div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <SupportBadge support={p.support} />
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
      <div className="px-3 py-1.5 border-t border-gray-100 text-xs text-gray-400 shrink-0">
        {filtered.length} review proposal{filtered.length !== 1 ? 's' : ''}
      </div>
    </div>
  )
}
