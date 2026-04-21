import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import type { MatchingSummary, ReviewProgress, RunData } from '../types'

interface Props {
  run: RunData
  outputDir: string
}

function warningTags(run: RunData) {
  return {
    parsingFallback: run.warnings.some(
      (warning) =>
        warning.category === 'partial_extraction' ||
        warning.message.toLowerCase().includes('parser fallback') ||
        warning.message.toLowerCase().includes('ocr')
    ),
    duplicateConflicts: run.warnings.some((warning) => warning.category === 'duplicate_row_conflict'),
    fallbackEvidence: run.warnings.some((warning) => warning.category === 'fallback_evidence_used'),
  }
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 shadow-sm">
      <span className="font-semibold text-slate-800">{label}:</span> {value}
    </div>
  )
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

  const providerLabel = run.provider_token === 'lm_studio' ? 'LM Studio' : run.provider_token ?? '—'
  const providerMode = run.provider_mode ?? 'unknown'
  const providerModeLabel = {
    live_local: 'live local',
    live_cloud: 'live cloud',
    unavailable: 'unavailable',
    disabled: 'disabled',
    stub: 'stub/demo',
    unknown: 'unknown',
  }[providerMode] ?? providerMode.replace(/_/g, ' ')

  return (
    <div className="border-b border-slate-200 bg-[linear-gradient(135deg,#f8fafc,#ffffff_55%,#eff6ff)] px-5 py-4">
      <div className="flex flex-wrap items-center gap-2">
        <SummaryChip label="Provider" value={`${providerLabel} · ${providerModeLabel}`} />
        <SummaryChip label="Actionable review" value={`${actionableReviewed} / ${actionableTotal}`} />
        <SummaryChip label="Attempted" value={`${run.proposals_generated}`} />
        <SummaryChip label="Matched PDFs" value={`${matching?.matched ?? '—'}`} />
        {run.eval_mode && <SummaryChip label="Eval" value="artifact-only review context" />}
        {warnings.parsingFallback && <span className="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-800">parsing fallback</span>}
        {warnings.duplicateConflicts && <span className="rounded-full bg-rose-100 px-3 py-1.5 text-xs font-semibold text-rose-700">duplicate conflicts</span>}
        {warnings.fallbackEvidence && <span className="rounded-full bg-orange-100 px-3 py-1.5 text-xs font-semibold text-orange-700">evidence fallback</span>}
      </div>

      <div className="mt-4 grid gap-3 xl:grid-cols-[1fr_320px]">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Matching</p>
            <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-600">
              <span>{matching?.matched ?? '—'} matched</span>
              <span>{matching?.unmatched ?? '—'} unmatched</span>
              <span>{matching?.ambiguous ?? '—'} ambiguous</span>
              <span>{matching?.duplicate_row_conflict ?? '—'} duplicate conflict</span>
            </div>
          </div>
          <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Run mode</p>
            <p className="mt-3 text-lg font-semibold text-slate-900">{run.run_mode.replace(/_/g, ' ')}</p>
            <p className="mt-1 text-xs text-slate-500">{run.verify_mode ? 'Filled cells are reviewable.' : run.eval_mode ? 'Masked working copy preserved.' : 'Empty target cells only.'}</p>
          </div>
          <div className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Warnings</p>
            <p className="mt-3 text-lg font-semibold text-slate-900">{run.warnings.length}</p>
            <p className="mt-1 text-xs text-slate-500">Warnings stay visible in the diagnostics panel instead of crowding evidence review.</p>
          </div>
        </div>

        <div className="rounded-[24px] border border-slate-200 bg-slate-950 p-4 text-white shadow-sm">
          <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">
            <span>Actionable progress</span>
            <span>{progressPct}%</span>
          </div>
          <div className="mt-4 h-3 rounded-full bg-slate-800">
            <div className="h-3 rounded-full bg-sky-400 transition-all" style={{ width: `${progressPct}%` }} />
          </div>
          <p className="mt-3 text-sm text-slate-300">
            {actionableReviewed} reviewed · {Math.max(actionableTotal - actionableReviewed, 0)} pending
          </p>
        </div>
      </div>
    </div>
  )
}
