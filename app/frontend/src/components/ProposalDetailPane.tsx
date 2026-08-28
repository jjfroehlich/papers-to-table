import { useEffect, useState, type ReactNode } from 'react'
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
  detailsOpen?: boolean
  diagnosticsOpen?: boolean
  onDetailsOpenChange?: (open: boolean) => void
  onDiagnosticsOpenChange?: (open: boolean) => void
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

function hasProposalDiagnostics(proposal: ProposalDetail['proposal']): boolean {
  return Boolean(
      proposal.candidate_answers?.length ||
      proposal.selection_diagnostics ||
      proposal.retrieval_diagnostics ||
      proposal.metadata_diagnostics
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

const REVIEWER_LABELS: Record<string, string> = {
  found: 'Found',
  inferred: 'Inferred',
  unclear: 'Unclear',
  first_pass_text: 'Initial text extraction',
  rescued_text: 'Targeted text search',
  evidence_recovery: 'Evidence recovery',
  figure_review: 'Figure review',
  parser_metadata: 'Document metadata',
  front_matter_block: 'Front matter',
  front_matter_conflict: 'Conflicting front matter',
  full_text_fallback: 'Full-text fallback',
  fallback_required: 'Fallback required',
}

function reviewerLabel(value: unknown): string {
  const raw = compactValue(value)
  if (raw === 'None') return ''
  return REVIEWER_LABELS[raw] ?? raw.replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase())
}

function positiveCount(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) && value > 0 ? value : 0
}

function pluralized(count: number, singular: string, plural = `${singular}s`): string {
  return `${count} ${count === 1 ? singular : plural}`
}

const RETRIEVAL_OUTCOMES: Record<string, string> = {
  provider_failure: 'The model provider failed during evidence retrieval.',
  blocked_upstream: 'Evidence retrieval was blocked by an earlier extraction failure.',
  parser_source_gap: 'The parsed paper did not expose the source text needed for this field.',
  retrieval_miss: 'No relevant passage was found for this field.',
  evidence_anchoring_gap: 'Relevant context was found, but its exact location could not be confirmed.',
  retrieval_policy_limit: 'The retrieval limits were reached before decisive evidence was found.',
  reasoning_gap: 'Relevant evidence was found, but it did not support a decisive conclusion.',
}

function evidenceRouteSummary(data: Record<string, unknown> | null | undefined): string | null {
  if (!data) return null
  const parts = [
    [positiveCount(data.exact_evidence_count), 'exact item'],
    [positiveCount(data.approximate_evidence_count), 'approximate item'],
    [positiveCount(data.fallback_evidence_count), 'fallback item'],
    [positiveCount(data.figure_evidence_count), 'figure item'],
  ] as const
  const visible = parts.filter(([count]) => count > 0).map(([count, label]) => pluralized(count, label))
  return visible.length > 0 ? visible.join(' · ') : null
}

function selectionRows(proposal: ProposalDetail['proposal']): Array<[string, string]> {
  const data = proposal.selection_diagnostics
  if (!data) return []
  if (data.failure_reason || data.failure_message) {
    return [
      ['outcome', 'Candidate selection failed'],
      ['reason', reviewerLabel(data.failure_message ?? data.failure_reason)],
    ]
  }
  if (data.attempted !== true) return []
  const candidateCount = proposal.candidate_answers?.length ?? 0
  if (data.selected_candidate_id == null) return [['outcome', 'No candidate could be selected']]
  if (candidateCount > 1) return [['outcome', `Selected from ${pluralized(candidateCount, 'competing candidate')}`]]
  if (data.value_changed === true) return [['outcome', 'Candidate selection changed the proposed value']]
  return []
}

function retrievalRows(proposal: ProposalDetail['proposal']): Array<[string, string]> {
  const data = proposal.retrieval_diagnostics
  if (!data) return []
  const classification = typeof data.classification === 'string' ? data.classification : null
  const rows: Array<[string, string]> = []
  if (classification && classification !== 'not_needed') {
    rows.push(['outcome', RETRIEVAL_OUTCOMES[classification] ?? reviewerLabel(classification)])
    const passages = positiveCount(data.retrieved_chunk_count)
    if (passages > 0) rows.push(['context reviewed', pluralized(passages, 'passage')])
  }
  const route = evidenceRouteSummary(data)
  if (route && (classification !== 'not_needed' || positiveCount(data.approximate_evidence_count) > 0 || positiveCount(data.fallback_evidence_count) > 0 || positiveCount(data.figure_evidence_count) > 0)) {
    rows.push(['evidence used', route])
  }
  return rows
}

function metadataRows(proposal: ProposalDetail['proposal'], candidateCount: number): Array<[string, string]> {
  const data = proposal.metadata_diagnostics
  if (!data) return []
  if (data.failure_reason || data.failure_message) {
    return [
      ['outcome', 'Metadata extraction failed'],
      ['reason', reviewerLabel(data.failure_message ?? data.failure_reason)],
    ]
  }
  if (candidateCount > 1) return [['outcome', `${pluralized(candidateCount, 'metadata candidate')} require comparison`]]
  if (data.front_matter_detected === false) return [['outcome', 'Front matter could not be identified']]
  return []
}

function ProposalDiagnostics({ proposal }: { proposal: ProposalDetail['proposal'] }) {
  if (!hasProposalDiagnostics(proposal)) return null

  const candidates = (proposal.candidate_answers ?? []).filter((candidate) => !isPlaceholderValue(candidate.value))
  const metadataCandidates = Array.isArray(proposal.metadata_diagnostics?.candidates)
    ? proposal.metadata_diagnostics.candidates.slice(0, 4)
    : []
  const showCandidates = candidates.length > 1 || candidates.some((candidate) => {
    const status = compactValue(candidate.candidate_status)
    return status !== 'found' || compactValue(candidate.value) !== compactValue(proposal.proposed_value)
  })
  const showMetadataCandidates = metadataCandidates.length > 1 || metadataCandidates.some((candidate) => {
    const record = candidate as Record<string, unknown>
    return compactValue(record.value) !== compactValue(proposal.proposed_value)
  })
  const selectionSummary = selectionRows(proposal)
  const retrievalSummary = retrievalRows(proposal)
  const metadataSummary = metadataRows(proposal, metadataCandidates.length)

  return (
    <div className="space-y-4">
        {(showCandidates || showMetadataCandidates) && (
        <div className="border-t border-slate-200 pt-3">
          <p className="text-xs font-semibold text-slate-700">Candidates to check</p>
          <div className="mt-2 space-y-2">
          {showCandidates && candidates.map((candidate, index) => (
            <div key={`candidate-${index}`} className="text-sm text-slate-600">
              {!isPlaceholderValue(candidate.value) && compactValue(candidate.value) !== compactValue(proposal.proposed_value) && (
                <p className="font-medium text-slate-800">{compactValue(candidate.value)}</p>
              )}
              <p className="text-xs text-slate-500">
                {[reviewerLabel(candidate.candidate_status), reviewerLabel(candidate.source)].filter(Boolean).join(' · ')}
              </p>
            </div>
          ))}
          {showMetadataCandidates && metadataCandidates.map((candidate, index) => {
            const candidateRecord = candidate as Record<string, unknown>
            return (
              <div key={`metadata-candidate-${index}`} className="text-sm text-slate-600">
                {compactValue(candidateRecord.value) !== compactValue(proposal.proposed_value) && (
                  <p className="line-clamp-4 font-medium leading-5 text-slate-800">{compactValue(candidateRecord.value)}</p>
                )}
                <p className="text-xs text-slate-500">
                  {[reviewerLabel(candidateRecord.source), candidateRecord.page_number != null ? `p.${candidateRecord.page_number}` : null]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              </div>
            )
          })}
          </div>
        </div>
        )}

        {(selectionSummary.length > 0 || retrievalSummary.length > 0 || metadataSummary.length > 0) && (
        <div className="space-y-4 text-xs text-slate-600">
          {selectionSummary.length > 0 && <DiagnosticList title="Selection" rows={selectionSummary} />}
          {retrievalSummary.length > 0 && <DiagnosticList title="Retrieval" rows={retrievalSummary} />}
          {metadataSummary.length > 0 && <DiagnosticList title="Metadata" rows={metadataSummary} />}
        </div>
        )}
    </div>
  )
}

function DiagnosticList({ title, rows }: { title: string; rows: Array<[string, string]> }) {
  return (
    <div className="border-t border-slate-200 pt-3">
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

function Disclosure({
  title,
  open,
  onOpenChange,
  children,
}: {
  title: string
  open?: boolean
  onOpenChange?: (open: boolean) => void
  children: ReactNode
}) {
  const isControlled = open !== undefined && onOpenChange !== undefined
  return (
    <details
      {...(isControlled ? { open } : {})}
      className="group rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <summary
        onClick={(event) => {
          if (!isControlled) return
          event.preventDefault()
          onOpenChange(!open)
        }}
        className="cursor-pointer list-none px-4 py-3.5 marker:hidden"
      >
        <span className="flex items-center gap-2">
          <span aria-hidden="true" className="text-[13px] leading-none text-slate-500 transition-transform duration-200 group-open:rotate-90">▸</span>
          <span className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">{title}</span>
        </span>
      </summary>
      <div className="space-y-4 border-t border-slate-200 px-4 py-4">{children}</div>
    </details>
  )
}

function CellDetail({
  cell,
  detailsOpen,
  diagnosticsOpen,
  onDetailsOpenChange,
  onDiagnosticsOpenChange,
}: {
  cell: SelectedReviewCell
  detailsOpen?: boolean
  diagnosticsOpen?: boolean
  onDetailsOpenChange?: (open: boolean) => void
  onDiagnosticsOpenChange?: (open: boolean) => void
}) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-white">
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5" data-testid="cell-detail-scroll">
        <div className="space-y-4">
          <section className="rounded-xl bg-slate-200 px-4 py-3 text-center ring-1 ring-inset ring-slate-300">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Field</p>
            <p className="mt-1.5 break-words text-base font-semibold text-slate-900">{cell.columnName}</p>
          </section>

          <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Value</p>
            <p className="mt-2 whitespace-pre-wrap break-words text-xl font-semibold leading-snug text-slate-950">
              {formatCellValue(cell.displayValue)}
            </p>
          </section>

          <Disclosure title="Details" open={detailsOpen} onOpenChange={onDetailsOpenChange}>
              <section>
                <p className="text-xs font-semibold text-slate-700">Field and description</p>
                <p className="mt-2 text-sm font-medium text-slate-800">{cell.columnName}</p>
                {cell.columnDescription && <p className="mt-1 text-sm leading-6 text-slate-600">{cell.columnDescription}</p>}
              </section>
              <section>
                <p className="text-xs font-semibold text-slate-700">Paper</p>
                <p className="mt-2 text-sm text-slate-700">{cell.title || cell.paperLabel || cell.rowId}</p>
                <p className="mt-1 text-xs text-slate-500">{cell.paperLabel}</p>
              </section>
          </Disclosure>

          <Disclosure title="Diagnostics" open={diagnosticsOpen} onOpenChange={onDiagnosticsOpenChange}>
            <div className="flex flex-wrap gap-2 text-xs text-slate-500">
              <span className="rounded-md bg-white px-2 py-1 font-medium ring-1 ring-inset ring-slate-200">{cell.displayStatus.replace(/_/g, ' ')}</span>
              {cell.rowIndex != null && <span className="rounded-md bg-white px-2 py-1 font-medium ring-1 ring-inset ring-slate-200">row {cell.rowIndex + 1}</span>}
            </div>
          </Disclosure>
        </div>
      </div>
    </div>
  )
}

export function ProposalDetailPane({ proposalId, runId, outputDir, selectedEvidenceId, onEvidenceSelect, selectedCell, detailsOpen, diagnosticsOpen, onDetailsOpenChange, onDiagnosticsOpenChange }: Props) {
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
    return <CellDetail cell={selectedCell} detailsOpen={detailsOpen} diagnosticsOpen={diagnosticsOpen} onDetailsOpenChange={onDetailsOpenChange} onDiagnosticsOpenChange={onDiagnosticsOpenChange} />
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
          <section className="rounded-xl bg-slate-200 px-4 py-3 text-center ring-1 ring-inset ring-slate-300">
            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Field</p>
            <p className="mt-1.5 break-words text-base font-semibold text-slate-900">
              {typeof columnDefinition?.name === 'string' ? columnDefinition.name : proposal.column_name}
            </p>
          </section>

          <section className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Value</p>
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
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Evidence</p>
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

          <Disclosure title="Details" open={detailsOpen} onOpenChange={onDetailsOpenChange}>
              <section>
                <p className="text-xs font-semibold text-slate-700">Field and description</p>
                <p className="mt-2 text-sm font-medium text-slate-800">
                  {typeof columnDefinition?.name === 'string' ? columnDefinition.name : proposal.column_name}
                </p>
                {typeof columnDefinition?.description === 'string' && (
                  <p className="mt-1 text-sm leading-6 text-slate-600">{columnDefinition.description}</p>
                )}
              </section>

              <section>
                <p className="text-xs font-semibold text-slate-700">Paper</p>
                <h2 className="mt-2 text-sm font-medium text-slate-800">{rowTitle}</h2>
                {(rowAuthors || rowYear) && (
                  <p className="mt-1 text-sm text-slate-500">
                    {rowAuthors}
                    {rowAuthors && rowYear ? ' · ' : ''}
                    {rowYear}
                  </p>
                )}
              </section>
          </Disclosure>

          <Disclosure title="Diagnostics" open={diagnosticsOpen} onOpenChange={onDiagnosticsOpenChange}>
              <section>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <ReviewStatusTag decision={proposal.latest_decision?.decision ?? null} muted />
                  <ProposalStatusTag status={proposal.proposal_status} muted />
                  <EvidenceStatusTag evidenceStatus={proposal.evidence_status} isFallback={proposal.is_fallback_evidence} muted />
                  {reasonCodes.map((code) => {
                    const reason = formatReasonCode(code)
                    return (
                      <span key={code} title={reason.title} className="rounded-md bg-white px-2 py-1 text-[11px] font-semibold text-slate-600 ring-1 ring-inset ring-slate-200">
                        {reason.label}
                      </span>
                    )
                  })}
                </div>
                <div className="mt-3">
                  <ProposalDiagnostics proposal={proposal} />
                </div>
              </section>
          </Disclosure>
        </div>
      </div>
    </div>
  )
}

export type { ProposalDetail }
