import type { RunData } from '../types'
import { RunStatusBadge } from './RunStatusBadge'

interface Props {
  run: RunData
  onAbort?: (run: RunData) => void
  aborting?: boolean
}

function Field({ label, value }: { label: string; value: string | number | boolean | null }) {
  if (value === null || value === undefined) return null
  return (
    <div className="flex gap-2 text-sm">
      <span className="font-medium text-gray-600 min-w-32">{label}:</span>
      <span className="text-gray-900 font-mono text-xs break-all">{String(value)}</span>
    </div>
  )
}

export function RunDetail({ run, onAbort, aborting }: Props) {
  const PROVIDER_DISPLAY: Record<string, string> = { lm_studio: 'LM Studio' }
  const providerLabel = run.provider_token ? (PROVIDER_DISPLAY[run.provider_token] ?? run.provider_token) : '—'
  const providerMode =
    run.provider_mode == null ? null : run.provider_mode.replace(/_/g, ' ')
  const structuredOutputMode =
    run.structured_output_mode == null ? null : run.structured_output_mode.replace(/_/g, ' ')
  const readinessReason =
    run.provider_readiness_reason == null ? null : run.provider_readiness_reason.replace(/_/g, ' ')
  const runModeLabel = run.run_mode.replace(/_/g, ' ')
  const isAbortable =
    !!onAbort && (run.status === 'created' || run.status === 'validating' || run.status === 'running')

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h3 className="font-semibold text-gray-900">Run Details</h3>
        <RunStatusBadge status={run.status} />
        {isAbortable && (
          <button
            onClick={() => onAbort?.(run)}
            disabled={aborting}
            className="ml-auto rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 transition-colors hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {aborting ? 'Aborting…' : 'Abort Run'}
          </button>
        )}
      </div>

      <div className="space-y-2">
        <Field label="Run ID" value={run.run_id} />
        <Field label="Provider" value={providerLabel} />
        <Field label="Locality" value={run.provider_locality} />
        <Field label="Provider mode" value={providerMode} />
        <Field label="Run mode" value={runModeLabel} />
        <Field label="Text model" value={run.provider_text_model_id ?? null} />
        <Field label="Vision model" value={run.provider_vision_model_id ?? null} />
        <Field label="Structured output" value={structuredOutputMode} />
        <Field
          label="Structured fallback used"
          value={
            run.structured_output_fallback_used == null
              ? null
              : (run.structured_output_fallback_used ? 'Yes' : 'No')
          }
        />
        <Field label="Readiness reason" value={readinessReason} />
        <Field label="Verify mode" value={run.verify_mode ? 'Yes' : 'No'} />
        <Field label="Eval mode" value={run.eval_mode ? 'Yes' : 'No'} />
        <Field label="Table" value={run.table_path} />
        <Field label="Schema" value={run.schema_path} />
        <Field label="PDF dir" value={run.pdf_dir} />
        <Field label="Table source" value={run.resolved_inputs?.table_path?.logical_source ?? null} />
        <Field label="Table locator" value={run.resolved_inputs?.table_path?.runtime_locator ?? null} />
        <Field label="Schema source" value={run.resolved_inputs?.schema_path?.logical_source ?? null} />
        <Field label="Schema locator" value={run.resolved_inputs?.schema_path?.runtime_locator ?? null} />
        <Field label="PDF source" value={run.resolved_inputs?.pdf_dir?.logical_source ?? null} />
        <Field label="PDF locator" value={run.resolved_inputs?.pdf_dir?.runtime_locator ?? null} />
        <Field label="Output dir" value={run.output_dir} />
        <Field label="Prompt hash" value={run.prompt_hash ?? null} />
        <Field label="Schema hash" value={run.schema_hash ?? null} />
        <Field label="Config hash" value={run.config_hash ?? null} />
        <Field label="Parser" value={run.parser_identity ?? null} />
        <Field label="Total rows" value={run.total_rows} />
        <Field label="Eligible cells" value={run.eligible_cells} />
        <Field label="Started" value={run.started_at ? new Date(run.started_at).toLocaleString() : null} />
        <Field label="Completed" value={run.completed_at ? new Date(run.completed_at).toLocaleString() : null} />
        {run.eval_artifacts?.gold_table?.source_reference && (
          <Field label="Gold table source" value={run.eval_artifacts.gold_table.source_reference} />
        )}
        {run.eval_artifacts?.gold_table?.snapshot_path && (
          <Field label="Gold table snapshot" value={run.eval_artifacts.gold_table.snapshot_path} />
        )}
        {run.eval_artifacts?.masked_working_table?.path && (
          <Field label="Masked working table" value={run.eval_artifacts.masked_working_table.path} />
        )}
        {run.current_stage && (
          <div className="text-sm text-blue-600">
            <span className="font-medium">Current stage:</span> {run.current_stage}
          </div>
        )}
      </div>

      {run.error_message && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3">
          <p className="text-sm font-medium text-red-700">Run failed</p>
          <p className="mt-1 text-sm text-red-600">{run.error_message}</p>
          {run.provider_readiness_error && run.provider_readiness_error !== run.error_message && (
            <p className="mt-1 text-xs text-red-500">{run.provider_readiness_error}</p>
          )}
        </div>
      )}

      {run.warnings.length > 0 && (
        <div className="rounded-md bg-amber-50 border border-amber-200 p-3">
          <p className="text-sm font-medium text-amber-800">Warnings ({run.warnings.length})</p>
          <ul className="mt-1 space-y-1">
            {run.warnings.map((w, i) => (
              <li key={i} className="text-xs text-amber-700">{w.message}</li>
            ))}
          </ul>
        </div>
      )}

      {run.status === 'completed' && (
        <div className="rounded-md bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          Run completed. Review and export are available from the Review tab.
        </div>
      )}

      {run.status === 'completed_with_warnings' && (
        <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-700">
          Run completed with warnings. Check warnings above before proceeding to review.
        </div>
      )}
    </div>
  )
}
