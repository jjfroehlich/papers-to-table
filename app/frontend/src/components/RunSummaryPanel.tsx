import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { MatchingSummary, ReviewProgress, ReviewTableData, ReviewTableProposal, RunData } from '../types'

interface Props {
  run: RunData
  outputDir: string
}

function formatLabel(value: string | null | undefined) {
  if (!value) return null
  return value.replace(/_/g, ' ')
}

function basename(value: string | null | undefined) {
  if (!value) return null
  const normalized = value.replace(/\\/g, '/')
  const trimmed = normalized.endsWith('/') ? normalized.slice(0, -1) : normalized
  return trimmed.split('/').pop() || trimmed
}

function DiagnosticBox({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-[20px] border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{title}</p>
      <div className="mt-3">{children}</div>
    </section>
  )
}

function DetailRow({ label, value }: { label: string; value: ReactNode | null | undefined }) {
  if (value === null || value === undefined) return null
  return (
    <div className="grid gap-1 border-b border-slate-100 py-1 last:border-b-0 md:grid-cols-[140px_minmax(0,1fr)] md:gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="min-w-0 break-all text-sm text-slate-800">{value}</span>
    </div>
  )
}

function InputRow({
  label,
  source,
  locator,
}: {
  label: string
  source: string | null | undefined
  locator: string | null | undefined
}) {
  if (!source && !locator) return null
  const sourceName = basename(source) ?? source
  const locatorName = basename(locator) ?? locator
  return (
    <div className="grid gap-1 border-b border-slate-100 py-1 last:border-b-0 md:grid-cols-[140px_minmax(0,1fr)_minmax(0,1fr)] md:gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="min-w-0 truncate text-sm text-slate-800" title={source ?? undefined}>
        {sourceName ?? '—'}
      </span>
      <span className="min-w-0 truncate font-mono text-xs text-slate-500" title={locator ?? undefined}>
        {locatorName ?? '—'}
      </span>
    </div>
  )
}

function uniqueProposals(table: ReviewTableData | null): ReviewTableProposal[] {
  if (!table) return []
  const proposals = new Map<string, ReviewTableProposal>()
  for (const row of table.rows) {
    for (const cell of Object.values(row.cells)) {
      if (cell.proposal) proposals.set(cell.proposal.proposal_id, cell.proposal)
    }
  }
  return Array.from(proposals.values())
}

export function RunSummaryPanel({ run, outputDir }: Props) {
  const [progress, setProgress] = useState<ReviewProgress | null>(null)
  const [matching, setMatching] = useState<MatchingSummary | null>(null)
  const [reviewTable, setReviewTable] = useState<ReviewTableData | null>(null)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  useEffect(() => {
    api.getReviewProgress(run.run_id, outputDir).then((value) => { setProgress(value); setSummaryError(null) }).catch((err) => setSummaryError(err instanceof Error ? err.message : String(err)))
    api.getMatchingSummary(run.run_id, outputDir).then((value) => { setMatching(value); setSummaryError(null) }).catch((err) => setSummaryError(err instanceof Error ? err.message : String(err)))
    api.getReviewTable(run.run_id, outputDir).then((value) => { setReviewTable(value); setSummaryError(null) }).catch((err) => setSummaryError(err instanceof Error ? err.message : String(err)))
  }, [outputDir, run.run_id])

  const actionableReviewed = progress?.reviewed ?? 0
  const actionableTotal = progress?.total_proposals ?? 0
  const progressPct = actionableTotal > 0 ? Math.round((actionableReviewed / actionableTotal) * 100) : 0
  const proposals = useMemo(() => uniqueProposals(reviewTable), [reviewTable])
  const proposalStats = useMemo(() => ({
    found: proposals.filter((proposal) => proposal.state === 'found').length,
    inferred: proposals.filter((proposal) => proposal.state === 'inferred').length,
    unclear: proposals.filter((proposal) => proposal.state === 'unclear').length,
    blocked: proposals.filter((proposal) => proposal.state === 'blocked').length,
    weak: proposals.filter((proposal) => proposal.support === 'weak_evidence').length,
    fallback: proposals.filter((proposal) => proposal.is_fallback_evidence).length,
    warnings: proposals.filter((proposal) => proposal.warning_flags.length > 0 || proposal.warning_categories.length > 0).length,
  }), [proposals, run.proposals_generated])

  const providerLabel = run.provider_token === 'lm_studio' ? 'LM Studio' : run.provider_token ?? '—'
  const resolvedTable = run.resolved_inputs?.table_path
  const resolvedSchema = run.resolved_inputs?.schema_path
  const resolvedPdfDir = run.resolved_inputs?.pdf_dir

  return (
    <div className="border-b border-slate-200 bg-slate-50 px-5 py-4">
      {summaryError && <div className="mb-3 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700"><strong>Error:</strong> {summaryError}</div>}
      <div className="grid gap-3 xl:grid-cols-3">
        <DiagnosticBox title="Matching">
          <DetailRow label="PDFs" value={matching?.total_pdfs ?? '—'} />
          <DetailRow label="Matched" value={matching?.matched ?? '—'} />
          <DetailRow label="Unmatched" value={matching?.unmatched ?? '—'} />
          <DetailRow label="Ambiguous" value={matching?.ambiguous ?? '—'} />
          <DetailRow label="Duplicates" value={matching?.duplicate_row_conflict ?? '—'} />
        </DiagnosticBox>

        <DiagnosticBox title="Proposals">
          <DetailRow label="Attempted" value={run.proposals_generated} />
          <DetailRow label="Found" value={proposalStats.found} />
          <DetailRow label="Inferred" value={proposalStats.inferred} />
          <DetailRow label="Blocked" value={proposalStats.blocked} />
          <DetailRow label="Warnings" value={proposalStats.warnings} />
          <DetailRow label="Weak" value={proposalStats.weak} />
          <DetailRow label="Fallback" value={proposalStats.fallback} />
          <DetailRow label="Unclear" value={proposalStats.unclear} />
        </DiagnosticBox>

        <DiagnosticBox title="Review">
          <DetailRow label="Reviewed" value={`${actionableReviewed} / ${actionableTotal}`} />
          <DetailRow label="Accepted" value={progress?.accepted ?? '—'} />
          <DetailRow label="Edited" value={progress?.accepted_with_edit ?? '—'} />
          <DetailRow label="Pending" value={progress?.pending ?? '—'} />
          <DetailRow label="No data" value={progress?.confirmed_no_data ?? '—'} />
          <DetailRow label="Rejected" value={progress?.rejected ?? '—'} />
          <DetailRow label="Progress" value={`${progressPct}%`} />
          <div className="mt-3 h-2 rounded-full bg-slate-100">
            <div className="h-2 rounded-full bg-sky-500 transition-all" style={{ width: `${progressPct}%` }} />
          </div>
        </DiagnosticBox>

      </div>

      <div className="mt-3">
        <section className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Runtime details</p>
          <div className="mt-2">
            <InputRow label="Table" source={resolvedTable?.logical_source ?? run.table_path} locator={resolvedTable?.runtime_locator ?? null} />
            <InputRow label="Schema" source={resolvedSchema?.logical_source ?? run.schema_path} locator={resolvedSchema?.runtime_locator ?? null} />
            <InputRow label="PDFs" source={resolvedPdfDir?.logical_source ?? run.pdf_dir} locator={resolvedPdfDir?.runtime_locator ?? null} />
            <InputRow label="Output directory" source={run.output_dir} locator={null} />
            <DetailRow label="Provider" value={providerLabel} />
            <DetailRow label="Run mode" value={formatLabel(run.run_mode)} />
            <DetailRow label="Provider mode" value={formatLabel(run.provider_mode ?? null)} />
            <DetailRow label="Text model" value={run.provider_text_model_id ?? null} />
            <DetailRow label="Vision model" value={run.provider_vision_model_id ?? null} />
            <DetailRow label="Structured output" value={formatLabel(run.structured_output_mode ?? null)} />
            <DetailRow label="Structured reason" value={formatLabel(run.structured_output_reason ?? null)} />
            <DetailRow label="Readiness reason" value={formatLabel(run.provider_readiness_reason ?? null)} />
            <DetailRow label="Parser" value={run.parser_identity ?? null} />
            <DetailRow label="Gold table source" value={run.eval_artifacts?.gold_table?.source_reference ?? null} />
            <DetailRow label="Gold table snapshot" value={run.eval_artifacts?.gold_table?.snapshot_path ?? null} />
            <DetailRow label="Masked working table" value={run.eval_artifacts?.masked_working_table?.path ?? null} />
            <DetailRow label="Started" value={run.started_at ? new Date(run.started_at).toLocaleString() : null} />
            <DetailRow label="Completed" value={run.completed_at ? new Date(run.completed_at).toLocaleString() : null} />
            <DetailRow label="Current stage" value={run.current_stage ?? null} />
            {run.warnings.length > 0 && <DetailRow label="Run warnings" value={`${run.warnings.length} warning${run.warnings.length === 1 ? '' : 's'}`} />}
          </div>
        </section>
      </div>
    </div>
  )
}
