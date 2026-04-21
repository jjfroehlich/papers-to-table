import type { RunData } from '../types'
import { RunStatusBadge } from './RunStatusBadge'

interface Props {
  run: RunData
  onAbort?: (run: RunData) => void
  aborting?: boolean
}

function DetailRow({ label, value }: { label: string; value: string | number | boolean | null }) {
  if (value === null || value === undefined) return null
  return (
    <div className="grid gap-1 md:grid-cols-[140px_minmax(0,1fr)] md:gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="break-all text-sm text-slate-800">{String(value)}</span>
    </div>
  )
}

function Chip({ label, tone }: { label: string; tone: 'neutral' | 'success' | 'warning' | 'danger' }) {
  const className = {
    neutral: 'bg-slate-100 text-slate-700',
    success: 'bg-emerald-100 text-emerald-800',
    warning: 'bg-amber-100 text-amber-800',
    danger: 'bg-rose-100 text-rose-700',
  }[tone]
  return <span className={`rounded-full px-3 py-1 text-xs font-semibold ${className}`}>{label}</span>
}

export function RunDetail({ run, onAbort, aborting }: Props) {
  const providerLabel = run.provider_token === 'lm_studio' ? 'LM Studio' : run.provider_token ?? '—'
  const isAbortable = !!onAbort && (run.status === 'created' || run.status === 'validating' || run.status === 'running')
  const resolvedTable = run.resolved_inputs?.table_path
  const resolvedSchema = run.resolved_inputs?.schema_path
  const resolvedPdfDir = run.resolved_inputs?.pdf_dir

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Selected run</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-slate-950">{run.run_id}</h2>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <RunStatusBadge status={run.status} />
            <Chip label={run.run_mode.replace(/_/g, ' ')} tone="neutral" />
            {run.provider_mode && <Chip label={run.provider_mode.replace(/_/g, ' ')} tone={run.provider_mode === 'unavailable' ? 'danger' : 'success'} />}
            <Chip label={providerLabel} tone="neutral" />
          </div>
        </div>
        {isAbortable && (
          <button onClick={() => onAbort?.(run)} disabled={aborting} className="rounded-full border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60">
            {aborting ? 'Aborting…' : 'Abort run'}
          </button>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-[28px] border border-slate-200 bg-slate-50 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Resolved inputs</p>
          <div className="mt-3 space-y-3">
            <DetailRow label="Table source" value={resolvedTable?.logical_source ?? run.table_path} />
            <DetailRow label="Table locator" value={resolvedTable?.runtime_locator ?? null} />
            <DetailRow label="Schema source" value={resolvedSchema?.logical_source ?? run.schema_path} />
            <DetailRow label="Schema locator" value={resolvedSchema?.runtime_locator ?? null} />
            <DetailRow label="PDF source" value={resolvedPdfDir?.logical_source ?? run.pdf_dir} />
            <DetailRow label="PDF locator" value={resolvedPdfDir?.runtime_locator ?? null} />
            <DetailRow label="Output dir" value={run.output_dir} />
          </div>
        </section>

        <section className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Run scope</p>
          <div className="mt-3 grid grid-cols-3 gap-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-center">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Rows</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{run.total_rows}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-center">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Eligible</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{run.eligible_cells}</p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-center">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Proposals</p>
              <p className="mt-2 text-2xl font-semibold text-slate-900">{run.proposals_generated}</p>
            </div>
          </div>
        </section>
      </div>

      <section className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Runtime details</p>
        <div className="mt-3 space-y-3">
          <DetailRow label="Provider" value={providerLabel} />
          <DetailRow label="Text model" value={run.provider_text_model_id ?? null} />
          <DetailRow label="Vision model" value={run.provider_vision_model_id ?? null} />
          <DetailRow label="Structured output" value={run.structured_output_mode?.replace(/_/g, ' ') ?? null} />
          <DetailRow label="Structured reason" value={run.structured_output_reason?.replace(/_/g, ' ') ?? null} />
          <DetailRow label="Readiness reason" value={run.provider_readiness_reason?.replace(/_/g, ' ') ?? null} />
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

      {run.warnings.length > 0 && (
        <div className="rounded-[24px] border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-900">Warnings ({run.warnings.length})</p>
          <ul className="mt-3 space-y-2 text-sm text-amber-800">
            {run.warnings.map((warning, index) => (
              <li key={`${warning.category}-${index}`} className="rounded-2xl border border-amber-200 bg-white px-3 py-2">{warning.message}</li>
            ))}
          </ul>
        </div>
      )}

      {run.status === 'completed' && <div className="rounded-[24px] border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">Run completed. Review and export are available from the Review tab.</div>}
      {run.status === 'completed_with_warnings' && <div className="rounded-[24px] border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">Run completed with warnings. Review is available, but inspect warnings and diagnostics before export.</div>}
    </div>
  )
}
