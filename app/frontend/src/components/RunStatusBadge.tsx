import type { RunStatus } from '../types'

const STATUS_CONFIG: Record<RunStatus, { label: string; classes: string }> = {
  created: { label: 'Created', classes: 'bg-gray-100 text-gray-700' },
  validating: { label: 'Validating', classes: 'bg-blue-100 text-blue-700 animate-pulse' },
  running: { label: 'Running', classes: 'bg-yellow-100 text-yellow-800 animate-pulse' },
  completed: { label: 'Completed', classes: 'bg-green-100 text-green-800' },
  completed_with_warnings: { label: 'Completed', classes: 'bg-green-100 text-green-800' },
  failed: { label: 'Failed', classes: 'bg-red-100 text-red-700' },
  interrupted: { label: 'Interrupted', classes: 'bg-gray-100 text-gray-600' },
}

interface Props {
  status: RunStatus
}

export function RunStatusBadge({ status }: Props) {
  const { label, classes } = STATUS_CONFIG[status] ?? { label: status, classes: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${classes}`}>
      {label}
    </span>
  )
}
