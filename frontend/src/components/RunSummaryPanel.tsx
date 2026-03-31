import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { RunData, ReviewProgress, MatchingSummary } from '../types'

interface Props {
  run: RunData
  outputDir: string
}

export function RunSummaryPanel({ run, outputDir }: Props) {
  const [progress, setProgress] = useState<ReviewProgress | null>(null)
  const [matching, setMatching] = useState<MatchingSummary | null>(null)

  useEffect(() => {
    api.getProgress(run.run_id, outputDir).then(setProgress).catch(() => {})
    api.getMatchingSummary(run.run_id, outputDir).then(setMatching).catch(() => {})
  }, [run.run_id, outputDir])

  const reviewed = progress?.reviewed ?? 0
  const total = progress?.total_proposals ?? run.proposals_generated
  const progressPct = total > 0 ? Math.round((reviewed / total) * 100) : 0

  const providerLabel =
    run.provider_token === 'lm_studio' ? 'LM Studio' : (run.provider_token ?? '—')
  const localityLabel = run.provider_locality === 'local' ? 'local' : 'cloud'

  return (
    <div className="bg-white border-b border-gray-200 px-4 py-2 flex flex-wrap items-center gap-4 text-xs text-gray-600">
      {/* PDF matching stats */}
      <div className="flex items-center gap-1">
        <span className="font-medium text-gray-700">PDFs:</span>
        <span className="text-green-700">{matching?.matched ?? '—'} matched</span>
        {matching && matching.unmatched > 0 && (
          <span className="text-amber-600 ml-1">{matching.unmatched} unmatched</span>
        )}
        {matching && matching.ambiguous > 0 && (
          <span className="text-orange-600 ml-1">{matching.ambiguous} ambiguous</span>
        )}
      </div>

      <div className="w-px h-4 bg-gray-200" />

      {/* Proposal stats */}
      <div className="flex items-center gap-1">
        <span className="font-medium text-gray-700">Proposals:</span>
        <span>{total} generated</span>
        {progress && (
          <>
            <span className="text-blue-600 ml-1">{progress.accepted + progress.accepted_with_edit} accepted</span>
            {progress.rejected > 0 && (
              <span className="text-red-500 ml-1">{progress.rejected} rejected</span>
            )}
          </>
        )}
      </div>

      <div className="w-px h-4 bg-gray-200" />

      {/* Provider */}
      <div className="flex items-center gap-1.5">
        <span className="font-medium text-gray-700">Provider:</span>
        <span>{providerLabel}</span>
        <span
          className={`px-1.5 py-0.5 rounded text-xs font-medium ${
            localityLabel === 'local'
              ? 'bg-green-100 text-green-700'
              : 'bg-blue-100 text-blue-700'
          }`}
        >
          {localityLabel}
        </span>
      </div>

      {run.verify_mode && (
        <>
          <div className="w-px h-4 bg-gray-200" />
          <span className="px-1.5 py-0.5 rounded bg-purple-100 text-purple-700 font-medium">
            verify
          </span>
        </>
      )}

      {run.warnings.length > 0 && (
        <>
          <div className="w-px h-4 bg-gray-200" />
          <span className="flex items-center gap-1 text-amber-600">
            <span>⚠</span>
            <span>{run.warnings.length} warning{run.warnings.length !== 1 ? 's' : ''}</span>
          </span>
        </>
      )}

      {/* Progress bar */}
      {total > 0 && (
        <>
          <div className="w-px h-4 bg-gray-200" />
          <div className="flex items-center gap-2 min-w-40">
            <div className="flex-1 bg-gray-100 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="shrink-0 text-gray-500">{progressPct}% reviewed</span>
          </div>
        </>
      )}
    </div>
  )
}
