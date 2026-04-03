import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { RunData, ReviewProgress, MatchingSummary } from '../types'

interface Props {
  run: RunData
  outputDir: string
}

function warningTags(run: RunData) {
  const warnings = run.warnings
  return {
    parsingFallback: warnings.some((warning) => warning.message.toLowerCase().includes('parser fallback') || warning.message.toLowerCase().includes('ocr')),
    duplicateConflicts: warnings.some((warning) => warning.category === 'duplicate_row_conflict'),
    fallbackEvidence: warnings.some((warning) => warning.category === 'fallback_evidence_used'),
  }
}

export function RunSummaryPanel({ run, outputDir }: Props) {
  const [progress, setProgress] = useState<ReviewProgress | null>(null)
  const [matching, setMatching] = useState<MatchingSummary | null>(null)

  useEffect(() => {
    api.getReviewProgress(run.run_id, outputDir).then(setProgress).catch(() => {})
    api.getMatchingSummary(run.run_id, outputDir).then(setMatching).catch(() => {})
  }, [outputDir, run.run_id])

  const actionableReviewed = progress?.reviewed ?? 0
  const actionableTotal = progress?.total_proposals ?? 0
  const progressPct = actionableTotal > 0 ? Math.round((actionableReviewed / actionableTotal) * 100) : 0
  const warnings = useMemo(() => warningTags(run), [run])

  const providerLabel =
    run.provider_token === 'lm_studio' ? 'LM Studio' : (run.provider_token ?? '—')
  const providerMode = run.provider_mode ?? 'unknown'
  const providerModeLabel =
    {
      live_local: 'live local',
      live_cloud: 'live cloud',
      unavailable: 'unavailable',
      disabled: 'disabled',
      stub: 'stub/demo',
      unknown: 'unknown',
    }[providerMode] ?? providerMode.replace(/_/g, ' ')
  const providerModeClass =
    {
      live_local: 'bg-green-100 text-green-700',
      live_cloud: 'bg-blue-100 text-blue-700',
      unavailable: 'bg-red-100 text-red-700',
      disabled: 'bg-gray-100 text-gray-700',
      stub: 'bg-amber-100 text-amber-700',
      unknown: 'bg-gray-100 text-gray-700',
    }[providerMode] ?? 'bg-gray-100 text-gray-700'

  return (
    <div className="bg-white border-b border-gray-200 px-4 py-2 flex flex-wrap items-center gap-4 text-xs text-gray-600">
      <div className="flex items-center gap-1">
        <span className="font-medium text-gray-700">PDFs:</span>
        <span className="text-green-700">{matching?.matched ?? '—'} matched</span>
        {matching && matching.unmatched > 0 && (
          <span className="text-amber-600 ml-1">{matching.unmatched} unmatched</span>
        )}
        {matching && matching.ambiguous > 0 && (
          <span className="text-orange-600 ml-1">{matching.ambiguous} ambiguous</span>
        )}
        {matching && matching.duplicate_row_conflict > 0 && (
          <span className="text-red-600 ml-1">{matching.duplicate_row_conflict} duplicate conflict</span>
        )}
      </div>

      <div className="w-px h-4 bg-gray-200" />

      <div className="flex items-center gap-1">
        <span className="font-medium text-gray-700">Actionable review:</span>
        <span>{actionableReviewed} / {actionableTotal}</span>
        <span className="text-gray-400 ml-1">attempted {run.proposals_generated}</span>
      </div>

      <div className="w-px h-4 bg-gray-200" />

      <div className="flex items-center gap-1.5">
        <span className="font-medium text-gray-700">Provider:</span>
        <span>{providerLabel}</span>
        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${providerModeClass}`}>
          {providerModeLabel}
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

      {(warnings.parsingFallback || warnings.duplicateConflicts || warnings.fallbackEvidence) && (
        <>
          <div className="w-px h-4 bg-gray-200" />
          <div className="flex items-center gap-2">
            {warnings.parsingFallback && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                parsing fallback
              </span>
            )}
            {warnings.duplicateConflicts && (
              <span className="rounded-full bg-red-100 px-2 py-0.5 font-medium text-red-700">
                duplicate conflicts
              </span>
            )}
            {warnings.fallbackEvidence && (
              <span className="rounded-full bg-orange-100 px-2 py-0.5 font-medium text-orange-700">
                evidence fallback
              </span>
            )}
          </div>
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

      {actionableTotal > 0 && (
        <>
          <div className="w-px h-4 bg-gray-200" />
          <div className="flex items-center gap-2 min-w-40">
            <div className="flex-1 bg-gray-100 rounded-full h-2">
              <div
                className="bg-blue-500 h-2 rounded-full transition-all"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <span className="shrink-0 text-gray-500">{progressPct}% actionable reviewed</span>
          </div>
        </>
      )}
    </div>
  )
}
