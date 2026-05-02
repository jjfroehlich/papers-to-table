import type { RunData } from '../types'
import { RunStatusBadge } from './RunStatusBadge'

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

function statusSentence(run: RunData, providerLabel: string) {
  const statusLead = {
    completed: 'Run completed',
    completed_with_warnings: 'Run completed with warnings',
    failed: 'Run could not complete',
    interrupted: 'Run interrupted',
    running: 'Run in progress',
    validating: 'Run validating inputs',
    created: 'Run created',
  }[run.status] ?? 'Run ready'

  const reviewLead =
    run.status === 'completed' || run.status === 'completed_with_warnings'
      ? 'Review available'
      : run.status === 'failed'
      ? 'Review unavailable'
      : 'Review locked until completion'

  return `${statusLead} · ${reviewLead} · Local provider: ${providerLabel}`
}

function DetailRow({ label, value }: { label: string; value: string | number | boolean | null }) {
  if (value === null || value === undefined) return null
  return (
    <div className="grid gap-1 md:grid-cols-[140px_minmax(0,1fr)] md:gap-3">
      <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</span>
      <span className="min-w-0 break-all text-sm text-slate-800">{String(value)}</span>
    </div>
  )
}

function ResolvedInputRow({
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
    <div className="rounded-[22px] border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</p>
      {source && (
        <div className="mt-2 min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900" title={source}>
            {sourceName}
          </p>
          {sourceName !== source && (
            <p className="mt-1 truncate text-xs text-slate-500" title={source}>
              {source}
            </p>
          )}
        </div>
      )}
      {locator && (
        <div className="mt-2 min-w-0 text-xs text-slate-500">
          <span className="font-semibold text-slate-600">Locator</span>
          <p className="mt-1 truncate font-mono" title={locator}>
            {locatorName !== locator ? locator : locator}
          </p>
        </div>
      )}
    </div>
  )
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
          <div className="mt-3 flex flex-wrap items-center gap-3">
            <RunStatusBadge status={run.status} />
            <p className="text-sm text-slate-600">{statusSentence(run, providerLabel)}</p>
          </div>
        </div>
        {isAbortable && (
          <button onClick={() => onAbort?.(run)} disabled={aborting} className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-60">
            {aborting ? 'Aborting…' : 'Abort run'}
          </button>
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        <section className="rounded-[28px] border border-slate-200 bg-slate-50 p-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Resolved inputs</p>
          <div className="mt-3 grid gap-3">
            <ResolvedInputRow
              label="Table"
              source={resolvedTable?.logical_source ?? run.table_path}
              locator={resolvedTable?.runtime_locator ?? null}
            />
            <ResolvedInputRow
              label="Schema"
              source={resolvedSchema?.logical_source ?? run.schema_path}
              locator={resolvedSchema?.runtime_locator ?? null}
            />
            <ResolvedInputRow
              label="PDFs"
              source={resolvedPdfDir?.logical_source ?? run.pdf_dir}
              locator={resolvedPdfDir?.runtime_locator ?? null}
            />
            <ResolvedInputRow label="Output directory" source={run.output_dir} locator={null} />
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
