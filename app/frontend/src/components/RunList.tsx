import { RunStatusBadge } from './RunStatusBadge'
import type { RunData } from '../types'

interface Props {
  runs: RunData[]
  selectedRunId: string | null
  onSelect: (run: RunData) => void
}

function formatDate(iso: string | null) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function RunList({ runs, selectedRunId, onSelect }: Props) {
  if (runs.length === 0) {
    return (
      <div className="text-sm text-gray-500 text-center py-8">
        No runs yet. Create your first run above.
      </div>
    )
  }
  return (
    <ul className="divide-y divide-slate-100">
      {runs.map((run) => (
        <li
          key={run.run_id}
          data-testid="run-item"
          className={`cursor-pointer px-4 py-3 transition-colors hover:bg-slate-50 ${
            selectedRunId === run.run_id ? 'border-l-2 border-slate-900 bg-slate-50' : ''
          }`}
          onClick={() => onSelect(run)}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="flex-1 truncate font-mono text-xs text-slate-700">{run.run_id}</span>
            <RunStatusBadge status={run.status} />
          </div>
          <div className="mt-1 text-xs text-slate-500">
            {run.current_stage ? (
              <span className="text-slate-700">Stage: {run.current_stage}</span>
            ) : (
              <span>{formatDate(run.created_at)}</span>
            )}
          </div>
          {run.error_message && (
            <div className="mt-1 text-xs text-red-600 truncate">{run.error_message}</div>
          )}
        </li>
      ))}
    </ul>
  )
}
