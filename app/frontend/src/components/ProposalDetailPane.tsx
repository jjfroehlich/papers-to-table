import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { EvidenceItem, ProposalDetail } from '../types'
import type { SelectedReviewCell } from './ReviewTableView'
import {
  EvidenceSourceTag,
  ProposalStatusTag,
  EvidenceStatusTag,
  ReviewStatusTag,
} from './ReviewTags'
import { formatReasonCode, isPlaceholderValue, proposalConclusionLabel } from './proposalDisplay'

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

function hasAdvancedDiagnostics(proposal: ProposalDetail['proposal']): boolean {
  return Boolean(
      proposal.candidate_answers?.length ||
      proposal.selection_diagnostics ||
      proposal.retrieval_diagnostics ||
      proposal.metadata_diagnostics ||
      proposal.provider_diagnostics ||
      proposal.figure_review_diagnostics ||
      proposal.figure_planner_diagnostics
  )
}

function compactValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'None'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function diagnosticSummary(data: Record<string, unknown> | null | undefined): Array<[string, string]> {
  if (!data) return []
  if (data.attempted === false && data.skip_reason === 'not_needed_or_disabled') {
    const rows: Array<[string, string]> = [['selection step', 'Selection step not run because it was not needed']]
    if (data.candidate_count !== undefined && data.candidate_count !== null) {
      rows.push(['candidate count', compactValue(data.candidate_count)])
    }
    return rows
  }
  const priority = [
    'candidate_count',
    'candidate_values',
    'candidate_sources',
    'attempted',
    'skip_reason',
    'failure_reason',
    'failure_message',
    'chunks_considered',
    'retrieved_chunk_count',
    'front_matter_detected',
    'front_matter_pages',
    'fallback_reasons',
  ]
  return priority
    .filter((key) => data[key] !== undefined && data[key] !== null)
    .map((key) => [key.replace(/_/g, ' '), compactValue(data[key])] as [string, string])
}

function AdvancedDiagnostics({ proposal }: { proposal: ProposalDetail['proposal'] }) {
  if (!hasAdvancedDiagnostics(proposal)) return null

  const candidates = (proposal.candidate_answers ?? []).filter((candidate) => !isPlaceholderValue(candidate.value))
  const metadataCandidates = Array.isArray(proposal.metadata_diagnostics?.candidates)
    ? proposal.metadata_diagnostics.candidates.slice(0, 4)
    : []
  const selectionSummary = diagnosticSummary(proposal.selection_diagnostics)
  const retrievalSummary = diagnosticSummary(proposal.retrieval_diagnostics)
  const metadataSummary = diagnosticSummary(proposal.metadata_diagnostics)

  return (
    <details className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        Advanced diagnostics
      </summary>

      <div className="mt-4 space-y-4">
        {(candidates.length > 0 || metadataCandidates.length > 0) && (
        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-600">Candidate values</p>
          {candidates.map((candidate, index) => (
            <div key={`candidate-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
              <p className="font-medium text-slate-800">{compactValue(candidate.value)}</p>
              <p className="mt-1 text-xs text-slate-500">
                {[compactValue(candidate.candidate_status), compactValue(candidate.source)].filter((item) => item !== 'None').join(' · ')}
              </p>
              {typeof candidate.confidence_rationale === 'string' && (
                <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-slate-500">{candidate.confidence_rationale}</p>
              )}
            </div>
          ))}
          {metadataCandidates.map((candidate, index) => {
            const candidateRecord = candidate as Record<string, unknown>
            return (
              <div key={`metadata-candidate-${index}`} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                <p className="line-clamp-4 font-medium leading-5 text-slate-800">{compactValue(candidateRecord.value)}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {[compactValue(candidateRecord.source), candidateRecord.page_number != null ? `p.${candidateRecord.page_number}` : null]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              </div>
            )
          })}
        </div>
        )}

        {(selectionSummary.length > 0 || retrievalSummary.length > 0 || metadataSummary.length > 0) && (
        <div className="grid gap-3 text-xs text-slate-600">
          {selectionSummary.length > 0 && <DiagnosticList title="Selection diagnostics" rows={selectionSummary} />}
          {retrievalSummary.length > 0 && <DiagnosticList title="Retrieval diagnostics" rows={retrievalSummary} />}
          {metadataSummary.length > 0 && <DiagnosticList title="Metadata diagnostics" rows={metadataSummary} />}
        </div>
        )}
      </div>
    </details>
  )
}

function DiagnosticList({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="font-semibold text-slate-700">{title}</p>
      <dl className="mt-2 space-y-1">
        {rows.map(([key, value]) => (
          <div key={key} className="grid gap-1 sm:grid-cols-[8rem_1fr]">
            <dt className="font-medium text-slate-500">{key}</dt>
            <dd className="break-words text-slate-700">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
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
  const reasonCodes = proposal.reason_codes ?? []
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
                <ProposalStatusTag status={proposal.proposal_status} />
                <EvidenceStatusTag evidenceStatus={proposal.evidence_status} isFallback={proposal.is_fallback_evidence} />
                {reasonCodes.map((code) => {
                  const reason = formatReasonCode(code)
                  return (
                    <span key={code} title={reason.title} className="rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">
                      {reason.label}
                    </span>
                  )
                })}
              </div>
              <p className="mt-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Value</p>
              <p className="mt-1.5 text-xl font-semibold leading-tight text-slate-950">{proposalConclusionLabel(proposal)}</p>
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
              {evidence.length === 0 && (
                <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 text-sm text-slate-500">
                  No formal evidence items were persisted for this proposal.
                </div>
              )}
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

          <AdvancedDiagnostics proposal={proposal} />
        </div>
      </div>
    </div>
  )
}

export type { ProposalDetail }
