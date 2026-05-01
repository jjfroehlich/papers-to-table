import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { EvidenceItem, ProposalDetail } from '../types'

interface Props {
  proposalId: string | null
  runId: string
  outputDir: string
  selectedEvidenceId: string | null
  onEvidenceSelect: (evidenceId: string) => void
}

function SourceTypeBadge({ sourceType }: { sourceType: string }) {
  const map: Record<string, string> = {
    direct_quote: 'bg-emerald-100 text-emerald-800',
    inferred_reasoning: 'bg-amber-100 text-amber-800',
    calculation: 'bg-sky-100 text-sky-800',
    approximate_highlight: 'bg-orange-100 text-orange-700',
    quote_plus_page: 'bg-slate-100 text-slate-700',
    caption_grounded_figure_evidence: 'bg-violet-100 text-violet-800',
    visual_interpretation_figure_evidence: 'bg-fuchsia-100 text-fuchsia-800',
  }
  const label = sourceType.replace(/_/g, ' ')
  return <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${map[sourceType] ?? 'bg-slate-100 text-slate-700'}`}>{label}</span>
}

function EvidenceCard({ item, isSelected, onClick }: { item: EvidenceItem; isSelected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-[22px] border px-3 py-3 text-left transition ${
        isSelected ? 'border-sky-300 bg-sky-50 shadow-sm' : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <SourceTypeBadge sourceType={item.source_type} />
        {item.page_number != null && <span className="text-[11px] font-medium text-slate-500">p.{item.page_number}</span>}
        {item.anchor_confidence != null && (
          <span className="ml-auto text-[11px] font-semibold text-slate-400">{Math.round(item.anchor_confidence * 100)}% confidence</span>
        )}
      </div>
      {item.quote_text && <p className="mt-2 text-sm leading-6 text-slate-700">“{item.quote_text}”</p>}
      {item.caption_text && !item.quote_text && <p className="mt-2 text-sm leading-6 text-slate-600">{item.caption_text}</p>}
    </button>
  )
}

export function ProposalDetailPane({ proposalId, runId, outputDir, selectedEvidenceId, onEvidenceSelect }: Props) {
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
        const nextDetail = await api.getProposalDetail(runId, proposalId, outputDir)
        if (!cancelled) setDetail(nextDetail)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [outputDir, proposalId, runId])

  if (!proposalId) {
    return <div className="flex h-full items-center justify-center text-sm text-slate-400">Select a proposal from the queue.</div>
  }

  if (loading) {
    return <div className="flex h-full items-center justify-center text-sm text-slate-400">Loading proposal detail…</div>
  }

  if (error) {
    return <div className="p-5 text-sm text-rose-600"><strong>Error:</strong> {error}</div>
  }

  if (!detail) return null

  const { proposal, evidence } = detail
  const rowContext = detail.row_context ?? {}
  const columnDefinition = detail.column_definition ?? null
  const rowTitle =
    (rowContext['Title'] as string | undefined) ??
    (rowContext['title'] as string | undefined) ??
    (rowContext['paper_title'] as string | undefined) ??
    proposal.row_id
  const rowAuthors = (rowContext['Authors'] as string | undefined) ?? (rowContext['authors'] as string | undefined)
  const rowYear =
    (rowContext['Publication Year'] as string | number | undefined) ?? (rowContext['year'] as string | number | undefined)

  const badgeClass = {
    found: 'bg-emerald-100 text-emerald-800',
    inferred: 'bg-amber-100 text-amber-800',
    unclear: 'bg-orange-100 text-orange-700',
    blocked: 'bg-rose-100 text-rose-700',
    error: 'bg-slate-100 text-slate-700',
    skipped: 'bg-slate-100 text-slate-500',
  } as const

  const supportClass = {
    direct_evidence: 'bg-emerald-100 text-emerald-800',
    inferred_from_evidence: 'bg-amber-100 text-amber-800',
    weak_evidence: 'bg-orange-100 text-orange-700',
    blocked: 'bg-rose-100 text-rose-700',
    error: 'bg-slate-100 text-slate-700',
  } as const

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-[linear-gradient(180deg,#ffffff,#f8fafc)] px-5 py-5">
      <div className="space-y-5">
        <div className="rounded-[28px] border border-slate-200 bg-slate-950 p-5 text-white shadow-[0_18px_50px_rgba(15,23,42,0.12)]">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-200">Current paper</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight">{rowTitle}</h2>
          {(rowAuthors || rowYear) && <p className="mt-2 text-sm text-slate-300">{rowAuthors}{rowAuthors && rowYear ? ' · ' : ''}{rowYear}</p>}
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${badgeClass[proposal.state] ?? 'bg-slate-100 text-slate-700'}`}>{proposal.state}</span>
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${supportClass[proposal.support] ?? 'bg-slate-100 text-slate-700'}`}>{proposal.support.replace(/_/g, ' ')}</span>
            {proposal.provider_mode && <span className="rounded-full bg-white/10 px-3 py-1 text-xs font-semibold text-slate-200">{proposal.provider_mode.replace(/_/g, ' ')}</span>}
            {proposal.is_figure_derived && <span className="rounded-full bg-violet-400/20 px-3 py-1 text-xs font-semibold text-violet-100">figure evidence</span>}
            {proposal.is_fallback_evidence && <span className="rounded-full bg-orange-400/20 px-3 py-1 text-xs font-semibold text-orange-100">fallback evidence</span>}
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Field under review</p>
            <div className="mt-3 rounded-[24px] border border-slate-200 bg-slate-50 px-4 py-4">
              <p className="text-sm font-semibold text-slate-900">
                {typeof columnDefinition?.name === 'string' ? columnDefinition.name : proposal.column_name}
              </p>
              {typeof columnDefinition?.description === 'string' && <p className="mt-2 text-sm leading-6 text-slate-600">{columnDefinition.description}</p>}
            </div>

            <div className="mt-4 rounded-[24px] border border-slate-200 bg-[linear-gradient(135deg,#eff6ff,#ffffff)] px-4 py-4 shadow-sm">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Proposed value</p>
              <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{proposal.proposed_value ?? 'No value proposed'}</p>
              {detail.support_label_display && <p className="mt-2 text-sm text-slate-600">{detail.support_label_display}</p>}
            </div>

            {proposal.is_verify_mode && (proposal.existing_value != null || rowContext[proposal.column_name] !== undefined) && (
              <div className="mt-4 rounded-[24px] border border-violet-200 bg-violet-50 px-4 py-4 text-sm text-violet-900">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-violet-600">Verify mode</p>
                <div className="mt-2 grid gap-2 md:grid-cols-2">
                  <div>
                    <p className="text-xs font-semibold text-violet-700">Current workbook value</p>
                    <p className="mt-1 font-mono text-sm">{String(proposal.existing_value ?? rowContext[proposal.column_name] ?? '—')}</p>
                  </div>
                  <div>
                    <p className="text-xs font-semibold text-violet-700">Proposed review value</p>
                    <p className="mt-1 font-mono text-sm">{proposal.proposed_value ?? '—'}</p>
                  </div>
                </div>
              </div>
            )}

            {proposal.calculation && (
              <div className="mt-4 rounded-[24px] border border-sky-200 bg-sky-50 px-4 py-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">Calculation</p>
                <p className="mt-2 text-sm font-mono text-sky-900">{proposal.calculation}</p>
              </div>
            )}
          </section>

          <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Evidence stack</p>
              <span className="text-[11px] text-slate-400">{evidence.length} item{evidence.length !== 1 ? 's' : ''}</span>
            </div>
            <p className="mt-2 text-sm text-slate-500">Primary evidence is ranked first. Select an item to sync the document viewer.</p>
            <div className="mt-4 space-y-3">
              {evidence.map((item) => (
                <EvidenceCard key={item.evidence_id} item={item} isSelected={selectedEvidenceId === item.evidence_id} onClick={() => onEvidenceSelect(item.evidence_id)} />
              ))}
            </div>
          </section>
        </div>

        {proposal.rationale && (
          <div className="rounded-[24px] border border-slate-200 bg-white shadow-sm">
            <button onClick={() => setRationaleOpen((open) => !open)} className="flex w-full items-center justify-between px-4 py-3 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50">
              <span>Reviewer-visible rationale</span>
              <span>{rationaleOpen ? '▲' : '▼'}</span>
            </button>
            {rationaleOpen && <div className="border-t border-slate-100 px-4 py-4 text-sm leading-6 text-slate-600 whitespace-pre-wrap">{proposal.rationale}</div>}
          </div>
        )}
      </div>
    </div>
  )
}

export type { ProposalDetail }
