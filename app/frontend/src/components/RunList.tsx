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
    <ul className="divide-y divide-gray-200">
      {runs.map((run) => (
        <li
          key={run.run_id}
          data-testid="run-item"
          className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
            selectedRunId === run.run_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
          }`}
          onClick={() => onSelect(run)}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-mono text-gray-700 truncate flex-1">{run.run_id}</span>
            <RunStatusBadge status={run.status} />
          </div>
          <div className="mt-1 text-xs text-gray-500">
            {run.current_stage ? (
              <span className="text-blue-600">Stage: {run.current_stage}</span>
            ) : (
              <span>{formatDate(run.created_at)}</span>
            )}
          </div>
          {run.error_message && (
            <div className="mt-1 text-xs text-red-600 truncate">{run.error_message}</div>
          )}
          {run.warnings.length > 0 && (
            <div className="mt-1 text-xs text-amber-600">{run.warnings.length} warning(s)</div>
          )}
        </li>
      ))}
    </ul>
  )
}
