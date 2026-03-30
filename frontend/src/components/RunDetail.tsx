import type { RunData } from '../types'
import { RunStatusBadge } from './RunStatusBadge'

interface Props {
  run: RunData
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

export function RunDetail({ run }: Props) {
  const PROVIDER_DISPLAY: Record<string, string> = { lm_studio: 'LM Studio' }
  const providerLabel = run.provider_token ? (PROVIDER_DISPLAY[run.provider_token] ?? run.provider_token) : '—'

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <h3 className="font-semibold text-gray-900">Run Details</h3>
        <RunStatusBadge status={run.status} />
      </div>

      <div className="space-y-2">
        <Field label="Run ID" value={run.run_id} />
        <Field label="Provider" value={providerLabel} />
        <Field label="Locality" value={run.provider_locality} />
        <Field label="Verify mode" value={run.verify_mode ? 'Yes' : 'No'} />
        <Field label="Table" value={run.table_path} />
        <Field label="Schema" value={run.schema_path} />
        <Field label="PDF dir" value={run.pdf_dir} />
        <Field label="Output dir" value={run.output_dir} />
        <Field label="Total rows" value={run.total_rows} />
        <Field label="Eligible cells" value={run.eligible_cells} />
        <Field label="Started" value={run.started_at ? new Date(run.started_at).toLocaleString() : null} />
        <Field label="Completed" value={run.completed_at ? new Date(run.completed_at).toLocaleString() : null} />
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
          Run completed. Review functionality will be available in a future update.
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
