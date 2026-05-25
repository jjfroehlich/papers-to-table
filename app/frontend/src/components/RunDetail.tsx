import type { ReactNode } from 'react'
import type { RunData } from '../types'

interface Props {
  run: RunData
  onAbort?: (run: RunData) => void
  aborting?: boolean
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

export function RunDetail({ run, onAbort, aborting }: Props) {
  const isAbortable = !!onAbort && (run.status === 'created' || run.status === 'validating' || run.status === 'running')
  const resolvedTable = run.resolved_inputs?.table_path
  const resolvedSchema = run.resolved_inputs?.schema_path
  const resolvedPdfDir = run.resolved_inputs?.pdf_dir
  const providerLabel = run.provider_token === 'lm_studio' ? 'LM Studio' : run.provider_token ?? '—'

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Selected run</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{run.run_id}</h2>
        </div>
        {isAbortable && (
          <button onClick={() => onAbort?.(run)} disabled={aborting} className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60">
            {aborting ? 'Aborting…' : 'Abort run'}
          </button>
        )}
      </div>

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
        </div>
      </section>

      {run.error_message && (
        <div className="rounded-[24px] border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <p className="font-semibold">Run failed</p>
          <p className="mt-2">{run.error_message}</p>
          {run.provider_readiness_error && run.provider_readiness_error !== run.error_message && <p className="mt-2 text-xs text-rose-600">{run.provider_readiness_error}</p>}
        </div>
      )}

    </div>
  )
}
