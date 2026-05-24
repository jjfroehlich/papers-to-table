import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { EvidenceItem, ProposalDetail } from '../types'
import type { SelectedReviewCell } from './ReviewTableView'
import {
  EvidenceSourceTag,
  FigureTag,
  ProposalStateTag,
  ProposalSupportTag,
  ReviewStatusTag,
  WarningTag,
} from './ReviewTags'

interface Props {
  proposalId: string | null
  runId: string
  outputDir: string
  selectedEvidenceId: string | null
  onEvidenceSelect: (evidenceId: string) => void
  selectedCell?: SelectedReviewCell | null
}

function EvidenceCard({ item, isSelected, onClick }: { item: EvidenceItem; isSelected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`w-full rounded-lg border px-3 py-2.5 text-left transition ${
        isSelected ? 'border-amber-300 bg-amber-50 shadow-sm ring-1 ring-amber-100' : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <EvidenceSourceTag sourceType={item.source_type} />
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

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Blank'
  return String(value)
}

function CellDetail({ cell }: { cell: SelectedReviewCell }) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-white">
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5" data-testid="cell-detail-scroll">
        <div className="space-y-4">
          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Cell value</p>
            <p className="mt-2 whitespace-pre-wrap break-words text-xl font-semibold leading-snug text-slate-950">
              {formatCellValue(cell.displayValue)}
            </p>
            <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-md bg-slate-100 px-2 py-1 font-medium">{cell.displayStatus.replace(/_/g, ' ')}</span>
              {cell.rowIndex != null && <span className="rounded-md bg-slate-100 px-2 py-1 font-medium">row {cell.rowIndex + 1}</span>}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Field</p>
            <p className="mt-2 text-sm text-slate-700">{cell.columnName}</p>
            {cell.columnDescription && <p className="mt-2 text-sm leading-6 text-slate-600">{cell.columnDescription}</p>}
          </section>

          <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Paper</p>
            <p className="mt-2 text-sm text-slate-700">{cell.title || cell.paperLabel || cell.rowId}</p>
            <p className="mt-2 text-xs text-slate-500">{cell.paperLabel}</p>
          </section>
        </div>
      </div>
    </div>
  )
}

export function ProposalDetailPane({ proposalId, runId, outputDir, selectedEvidenceId, onEvidenceSelect, selectedCell }: Props) {
  const [detail, setDetail] = useState<ProposalDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      if (!proposalId) {
        setDetail(null)
        return
      }
      setLoading(true)
      setError(null)
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

  if (!proposalId && selectedCell) {
    return <CellDetail cell={selectedCell} />
  }

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

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-white">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4" data-testid="proposal-detail-scroll">
        <div className="space-y-3">
          <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <ReviewStatusTag decision={proposal.latest_decision?.decision ?? null} />
                <ProposalStateTag state={proposal.state} />
                <ProposalSupportTag support={proposal.support} isFallback={proposal.is_fallback_evidence} />
                {proposal.warning_flags.length > 0 && <WarningTag />}
                {proposal.is_figure_derived && <FigureTag />}
              </div>
              <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Proposed value</p>
              <p className="mt-1.5 text-xl font-semibold leading-tight text-slate-950">{proposal.proposed_value ?? 'No value proposed'}</p>
          </section>

          {proposal.is_verify_mode && (proposal.existing_value != null || rowContext[proposal.column_name] !== undefined) && (
              <section className="rounded-xl border border-violet-200 bg-violet-50 p-4 text-sm text-violet-900">
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
              </section>
            )}

            {proposal.calculation && (
              <section className="rounded-xl border border-sky-200 bg-sky-50 p-4">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-sky-700">Calculation</p>
                <p className="mt-2 text-sm font-mono text-sky-900">{proposal.calculation}</p>
              </section>
            )}

            {proposal.rationale && (
              <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Rationale</p>
                <div className="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-600">{proposal.rationale}</div>
              </section>
            )}

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Evidence</p>
              </div>
              <span className="rounded-md bg-slate-100 px-2 py-1 text-[11px] font-semibold text-slate-600">
                {evidence.length} item{evidence.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="mt-4 space-y-3">
              {evidence.map((item) => (
                <EvidenceCard key={item.evidence_id} item={item} isSelected={selectedEvidenceId === item.evidence_id} onClick={() => onEvidenceSelect(item.evidence_id)} />
              ))}
            </div>
          </section>

          <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Field</p>
            <p className="mt-2 text-sm text-slate-700">
              {typeof columnDefinition?.name === 'string' ? columnDefinition.name : proposal.column_name}
            </p>
            {typeof columnDefinition?.description === 'string' && (
              <p className="mt-2 text-sm leading-6 text-slate-600">{columnDefinition.description}</p>
            )}
          </section>

          <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Paper</p>
            <h2 className="mt-2 text-sm text-slate-700">{rowTitle}</h2>
            {(rowAuthors || rowYear) && (
              <p className="mt-2 text-sm text-slate-500">
                {rowAuthors}
                {rowAuthors && rowYear ? ' · ' : ''}
                {rowYear}
              </p>
            )}
          </section>
        </div>
      </div>
    </div>
  )
}

export type { ProposalDetail }
