import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { ProposalDetail, EvidenceItem } from '../types'

interface Props {
  proposalId: string | null
  runId: string
  outputDir: string
  selectedEvidenceId: string | null
  onEvidenceSelect: (evidenceId: string) => void
}

function SourceTypeBadge({ sourceType }: { sourceType: string }) {
  const map: Record<string, string> = {
    direct_quote: 'bg-green-100 text-green-700',
    inferred_reasoning: 'bg-yellow-100 text-yellow-700',
    calculation: 'bg-blue-100 text-blue-700',
    approximate_highlight: 'bg-orange-100 text-orange-700',
    quote_plus_page: 'bg-gray-100 text-gray-600',
    caption_grounded_figure_evidence: 'bg-purple-100 text-purple-700',
    visual_interpretation_figure_evidence: 'bg-fuchsia-100 text-fuchsia-700',
  }
  const cls = map[sourceType] ?? 'bg-gray-100 text-gray-600'
  const label = sourceType.replace(/_/g, ' ')
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
  )
}

function EvidenceCard({
  item,
  isSelected,
  onClick,
}: {
  item: EvidenceItem
  isSelected: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded border p-2 space-y-1 transition-colors ${
        isSelected
          ? 'border-blue-400 bg-blue-50'
          : 'border-gray-200 bg-white hover:border-gray-300'
      }`}
    >
      <div className="flex items-center gap-2">
        <SourceTypeBadge sourceType={item.source_type} />
        {item.page_number != null && (
          <span className="text-xs text-gray-500">p.{item.page_number}</span>
        )}
        {item.anchor_confidence != null && (
          <span className="text-xs text-gray-400 ml-auto">
            {Math.round(item.anchor_confidence * 100)}% conf
          </span>
        )}
      </div>
      {item.quote_text && (
        <p className="text-xs text-gray-700 line-clamp-2 italic">"{item.quote_text}"</p>
      )}
      {item.caption_text && !item.quote_text && (
        <p className="text-xs text-gray-600 line-clamp-2">{item.caption_text}</p>
      )}
    </button>
  )
}

export function ProposalDetailPane({
  proposalId,
  runId,
  outputDir,
  selectedEvidenceId,
  onEvidenceSelect,
}: Props) {
  const [detail, setDetail] = useState<ProposalDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [rationaleOpen, setRationaleOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!proposalId) {
        setDetail(null)
        return
      }
      setLoading(true)
      setError(null)
      setRationaleOpen(false)
      try {
        const d = await api.getProposalDetail(runId, proposalId, outputDir)
        if (!cancelled) setDetail(d)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [proposalId, runId, outputDir])

  if (!proposalId) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        Select a proposal from the queue
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        Loading…
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-red-600">
        <strong>Error:</strong> {error}
      </div>
    )
  }

  if (!detail) return null

  const { proposal, evidence } = detail
  const row_context = detail.row_context ?? {}
  const column_definition = detail.column_definition ?? null
  const rowTitle =
    (row_context['Title'] as string | undefined) ??
    (row_context['title'] as string | undefined) ??
    (row_context['paper_title'] as string | undefined) ??
    proposal.row_id
  const rowAuthors =
    (row_context['Authors'] as string | undefined) ??
    (row_context['authors'] as string | undefined)
  const rowYear =
    (row_context['Publication Year'] as string | number | undefined) ??
    (row_context['year'] as string | number | undefined)

  const stateColors: Record<string, string> = {
    found: 'bg-green-100 text-green-700',
    inferred: 'bg-yellow-100 text-yellow-700',
    unclear: 'bg-orange-100 text-orange-700',
    blocked: 'bg-red-100 text-red-700',
    error: 'bg-gray-100 text-gray-600',
    skipped: 'bg-gray-100 text-gray-500',
  }
  const supportColors: Record<string, string> = {
    direct_evidence: 'bg-green-100 text-green-700',
    inferred_from_evidence: 'bg-yellow-100 text-yellow-700',
    weak_evidence: 'bg-orange-100 text-orange-700',
    blocked: 'bg-red-100 text-red-700',
    error: 'bg-gray-100 text-gray-600',
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto p-4 space-y-4">
      {/* Row context */}
      <div className="space-y-0.5">
        <h3 className="text-sm font-semibold text-gray-900 leading-tight">{rowTitle}</h3>
        {(rowAuthors || rowYear) && (
          <p className="text-xs text-gray-500">
            {rowAuthors && <span>{rowAuthors}</span>}
            {rowAuthors && rowYear && <span> · </span>}
            {rowYear && <span>{rowYear}</span>}
          </p>
        )}
      </div>

      {/* Column definition */}
      {column_definition && (
        <div className="rounded bg-gray-50 border border-gray-200 px-3 py-2">
          <p className="text-xs font-medium text-gray-700">
            {column_definition['name'] as string ?? proposal.column_name}
          </p>
          {typeof column_definition['description'] === 'string' && (
            <p className="text-xs text-gray-500 mt-0.5">
              {column_definition['description']}
            </p>
          )}
        </div>
      )}

      {/* State/support badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${stateColors[proposal.state] ?? 'bg-gray-100 text-gray-600'}`}>
          {proposal.state}
        </span>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${supportColors[proposal.support] ?? 'bg-gray-100 text-gray-600'}`}>
          {proposal.support.replace(/_/g, ' ')}
        </span>
        {proposal.provider_mode && (
          <span className="px-2 py-0.5 rounded text-xs bg-slate-100 text-slate-700">
            {proposal.provider_mode.replace(/_/g, ' ')}
          </span>
        )}
        {proposal.is_figure_derived && (
          <span className="px-2 py-0.5 rounded text-xs bg-purple-100 text-purple-700">figure</span>
        )}
        {proposal.is_fallback_evidence && (
          <span className="px-2 py-0.5 rounded text-xs bg-orange-100 text-orange-600">fallback</span>
        )}
        {proposal.warning_flags.length > 0 && (
          <span className="px-2 py-0.5 rounded text-xs bg-amber-100 text-amber-700">
            ⚠ {proposal.warning_flags.length} warning{proposal.warning_flags.length !== 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Proposed value */}
      <div className="rounded border border-gray-200 p-3">
        <p className="text-xs text-gray-500 mb-1 font-medium">{proposal.column_name}</p>
        {proposal.proposed_value ? (
          <p className="text-base font-semibold text-gray-900">{proposal.proposed_value}</p>
        ) : (
          <p className="text-sm italic text-gray-400">No value proposed</p>
        )}
      </div>

      {/* Current vs proposed (verify mode) */}
      {proposal.is_verify_mode && (proposal.existing_value != null || row_context[proposal.column_name] !== undefined) && (
        <div className="rounded border border-purple-200 bg-purple-50 px-3 py-2 text-xs space-y-1">
          <p className="font-medium text-purple-700">Verify mode</p>
          <div className="flex gap-2">
            <span className="text-gray-500">Current:</span>
            <span className="text-gray-800 font-mono">
              {String(proposal.existing_value ?? row_context[proposal.column_name] ?? '—')}
            </span>
          </div>
          <div className="flex gap-2">
            <span className="text-gray-500">Proposed:</span>
            <span className="text-purple-800 font-mono">{proposal.proposed_value ?? '—'}</span>
          </div>
        </div>
      )}

      {/* Rationale */}
      {proposal.rationale && (
        <div className="border border-gray-200 rounded">
          <button
            onClick={() => setRationaleOpen((o) => !o)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs font-medium text-gray-700 hover:bg-gray-50"
          >
            <span>Rationale</span>
            <span>{rationaleOpen ? '▲' : '▼'}</span>
          </button>
          {rationaleOpen && (
            <div className="px-3 pb-3 text-xs text-gray-700 whitespace-pre-wrap border-t border-gray-100 pt-2">
              {proposal.rationale}
            </div>
          )}
        </div>
      )}

      {/* Calculation */}
      {proposal.calculation && (
        <div className="rounded border border-blue-200 bg-blue-50 px-3 py-2">
          <p className="text-xs font-medium text-blue-700 mb-1">Calculation</p>
          <p className="text-xs text-blue-900 font-mono">{proposal.calculation}</p>
        </div>
      )}

      {/* Evidence list */}
      {evidence.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-600 mb-2">Evidence ({evidence.length})</p>
          <div className="space-y-2">
            {evidence.map((item) => (
              <EvidenceCard
                key={item.evidence_id}
                item={item}
                isSelected={selectedEvidenceId === item.evidence_id}
                onClick={() => onEvidenceSelect(item.evidence_id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export type { ProposalDetail }
