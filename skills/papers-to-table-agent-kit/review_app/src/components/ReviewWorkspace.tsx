import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { EvidenceItem, EnrichedProposal, ExportResult, ReviewProgress, RunData } from '../types'
import { RunSummaryPanel } from './RunSummaryPanel'
import { ProposalQueue } from './ProposalQueue'
import { ProposalDetailPane } from './ProposalDetailPane'
import { ReviewActionArea } from './ReviewActionArea'
import { EvidenceViewer } from './EvidenceViewer'
import { useReviewKeyboardShortcuts } from '../hooks/useReviewKeyboardShortcuts'
import { api } from '../api/client'
import type { LeftPaneMode } from './ProposalQueue'
import type { ReviewFilter, SelectedReviewCell } from './ReviewTableView'

interface Props {
  run: RunData
  outputDir: string
}

type ResizeTarget = 'left' | 'right' | null
const LEFT_PANE_MIN = 200
const LEFT_PANE_MAX = 760
const RIGHT_PANE_MIN = 240
const RIGHT_PANE_MAX = 960
const CENTER_PANE_MIN = 280

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function readStoredNumber(key: string, fallback: number) {
  try {
    const raw = window.localStorage.getItem(key)
    if (!raw) return fallback
    const value = Number(raw)
    return Number.isFinite(value) ? value : fallback
  } catch {
    return fallback
  }
}

function readStoredValue<T extends string>(key: string, fallback: T, allowed: readonly T[]) {
  try {
    const raw = window.localStorage.getItem(key)
    return allowed.includes(raw as T) ? (raw as T) : fallback
  } catch {
    return fallback
  }
}

function storeValue(key: string, value: string | number) {
  try {
    window.localStorage.setItem(key, String(value))
  } catch {
    // Ignore storage failures; review workflow should remain usable.
  }
}

function KeyboardHelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/40 backdrop-blur-sm" onClick={onClose}>
      <div className="w-[420px] space-y-4 rounded-[28px] border border-slate-200 bg-white p-6 shadow-2xl" onClick={(event) => event.stopPropagation()}>
        <h2 className="text-sm font-semibold text-slate-900">Keyboard shortcuts</h2>
        <table className="w-full text-xs text-slate-700">
          <tbody className="divide-y divide-slate-100">
            {[
              ['A', 'Accept'],
              ['R', 'Reject'],
              ['] or N', 'Next proposal'],
              ['[ or P', 'Previous proposal'],
              ['Alt+N', 'Next evidence'],
              ['Alt+P', 'Previous evidence'],
              ['E', 'Focus edit input'],
              ['?', 'This help'],
            ].map(([key, description]) => (
              <tr key={key}>
                <td className="py-2 pr-4">
                  <kbd className="rounded-lg border border-slate-200 bg-slate-100 px-2 py-1 font-mono text-[11px]">{key}</kbd>
                </td>
                <td className="py-2">{description}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <button onClick={onClose} className="w-full rounded-2xl bg-slate-100 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200">
          Close
        </button>
      </div>
    </div>
  )
}

function DiagnosticsDrawer({
  run,
  outputDir,
  onClose,
}: {
  run: RunData
  outputDir: string
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-40 bg-slate-950/30 backdrop-blur-sm" onClick={onClose}>
      <div
        className="ml-auto flex h-full w-full max-w-4xl flex-col overflow-hidden border-l border-slate-200 bg-white shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Diagnostics</p>
            <h2 className="mt-1 text-lg font-semibold text-slate-950">Run diagnostics</h2>
          </div>
          <button onClick={onClose} className="rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50">
            Close
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          <RunSummaryPanel run={run} outputDir={outputDir} />
        </div>
      </div>
    </div>
  )
}

export function ReviewWorkspace({ run, outputDir }: Props) {
  const layoutRef = useRef<HTMLDivElement | null>(null)
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null)
  const [selectedCell, setSelectedCell] = useState<SelectedReviewCell | null>(null)
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null)
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null)
  const [currentEvidenceList, setCurrentEvidenceList] = useState<EvidenceItem[]>([])
  const [currentPdfId, setCurrentPdfId] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [showDiagnostics, setShowDiagnostics] = useState(false)
  const [proposalList, setProposalList] = useState<EnrichedProposal[]>([])
  const [visibleProposalOrder, setVisibleProposalOrder] = useState<string[]>([])
  const [reviewProgress, setReviewProgress] = useState<ReviewProgress | null>(null)
  const [decisionVersion, setDecisionVersion] = useState(0)
  const [leftPaneWidth, setLeftPaneWidth] = useState(() => readStoredNumber('papersToTable.review.leftPaneWidth', 340))
  const [rightPaneWidth, setRightPaneWidth] = useState(() => readStoredNumber('papersToTable.review.rightPaneWidth', 430))
  const [resizeTarget, setResizeTarget] = useState<ResizeTarget>(null)
  const [focusEditSignal, setFocusEditSignal] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportResult, setExportResult] = useState<ExportResult | null>(null)
  const [exportNotice, setExportNotice] = useState<string | null>(null)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [leftPaneMode, setLeftPaneMode] = useState<LeftPaneMode>(() =>
    readStoredValue<LeftPaneMode>('papersToTable.review.leftPaneMode', 'table', ['paper', 'column', 'table'])
  )
  const [leftPaneFilter, setLeftPaneFilter] = useState<ReviewFilter>(() =>
    readStoredValue<ReviewFilter>('papersToTable.review.leftPaneFilter', 'pending', [
      'pending',
      'needs_attention',
      'all',
      'accepted',
      'accepted_with_edit',
      'confirmed_no_data',
      'rejected',
    ])
  )
  const loadProposalList = useCallback(() => {
    return Promise.all([
      api.listProposals(run.run_id, { output_dir: outputDir, reviewable_only: true }),
      api.getReviewProgress(run.run_id, outputDir),
    ])
      .then(([proposalResponse, progressResponse]) => {
        setWorkspaceError(null)
        setProposalList(proposalResponse.proposals)
        setReviewProgress(progressResponse)
        setSelectedProposalId((current) => {
          if (proposalResponse.proposals.length === 0) return null
          if (current && proposalResponse.proposals.some((proposal) => proposal.proposal_id === current)) {
            return current
          }
          return (
            proposalResponse.proposals.find((proposal) => !proposal.latest_decision)?.proposal_id ??
            proposalResponse.proposals[0].proposal_id
          )
        })
      })
      .catch((err) => { setWorkspaceError(err instanceof Error ? err.message : String(err)) })
  }, [outputDir, run.run_id])

  useEffect(() => {
    void loadProposalList()
  }, [decisionVersion, loadProposalList])

  const navigationProposals = useMemo(() => {
    if (visibleProposalOrder.length === 0) return proposalList
    const proposalById = new Map(proposalList.map((proposal) => [proposal.proposal_id, proposal]))
    const ordered = visibleProposalOrder
      .map((proposalId) => proposalById.get(proposalId))
      .filter((proposal): proposal is EnrichedProposal => !!proposal)
    return ordered.length > 0 ? ordered : proposalList
  }, [proposalList, visibleProposalOrder])
  const currentIndex = navigationProposals.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
  const currentProposal = proposalList.find((proposal) => proposal.proposal_id === selectedProposalId) ?? null
  const actionableTotal = reviewProgress?.total_proposals ?? proposalList.length
  const actionableReviewed = reviewProgress?.reviewed ?? proposalList.filter((proposal) => proposal.latest_decision).length
  const actionablePending = Math.max(actionableTotal - actionableReviewed, 0)
  const progressPct = actionableTotal > 0 ? Math.round((actionableReviewed / actionableTotal) * 100) : 0
  const activeEvidenceIndex = currentEvidenceList.findIndex((item) => item.evidence_id === selectedEvidenceId)

  function goNext() {
    if (navigationProposals.length === 0) return
    const nextIndex = currentIndex >= 0 && currentIndex < navigationProposals.length - 1 ? currentIndex + 1 : 0
    setSelectedProposalId(navigationProposals[nextIndex].proposal_id)
    setSelectedCell(null)
  }

  function goPrev() {
    if (navigationProposals.length === 0) return
    const previousIndex = currentIndex > 0 ? currentIndex - 1 : navigationProposals.length - 1
    setSelectedProposalId(navigationProposals[previousIndex].proposal_id)
    setSelectedCell(null)
  }

  function recordQuickDecision(decision: 'accepted' | 'rejected') {
    if (!selectedProposalId) return
    api.recordDecision(run.run_id, selectedProposalId, { decision }, outputDir)
      .then(() => handleDecisionRecorded({ autoAdvance: true }))
      .catch((err) => { setWorkspaceError(err instanceof Error ? err.message : String(err)) })
  }

  const handleDecisionRecorded = useCallback(
    (options?: { autoAdvance?: boolean }) => {
      if (options?.autoAdvance && navigationProposals.length > 1 && selectedProposalId) {
        const pendingCandidates = navigationProposals.filter(
          (proposal) => proposal.proposal_id !== selectedProposalId && !proposal.latest_decision
        )
        if (pendingCandidates.length > 0) {
          const currentPendingIndex = navigationProposals.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
          const ordered = currentPendingIndex >= 0
            ? [...navigationProposals.slice(currentPendingIndex + 1), ...navigationProposals.slice(0, currentPendingIndex)]
            : navigationProposals
          const nextPending = ordered.find((proposal) => proposal.proposal_id !== selectedProposalId && !proposal.latest_decision)
          setSelectedProposalId(nextPending?.proposal_id ?? pendingCandidates[0].proposal_id)
          setSelectedCell(null)
        }
      }
      setDecisionVersion((version) => version + 1)
    },
    [navigationProposals, selectedProposalId]
  )

  const handleVisibleProposalOrderChange = useCallback((proposalIds: string[]) => {
    setVisibleProposalOrder((current) => {
      if (current.length === proposalIds.length && current.every((proposalId, index) => proposalId === proposalIds[index])) {
        return current
      }
      return proposalIds
    })
  }, [])

  useReviewKeyboardShortcuts({
    onNext: goNext,
    onPrev: goPrev,
    onNextEvidence: () => {
      if (currentEvidenceList.length <= 1) return
      const currentEvidenceIndex = currentEvidenceList.findIndex((item) => item.evidence_id === selectedEvidenceId)
      const nextIndex = currentEvidenceIndex < currentEvidenceList.length - 1 ? currentEvidenceIndex + 1 : 0
      const nextEvidence = currentEvidenceList[nextIndex]
      setSelectedEvidenceId(nextEvidence.evidence_id)
      setSelectedEvidence(nextEvidence)
    },
    onPrevEvidence: () => {
      if (currentEvidenceList.length <= 1) return
      const currentEvidenceIndex = currentEvidenceList.findIndex((item) => item.evidence_id === selectedEvidenceId)
      const nextIndex = currentEvidenceIndex > 0 ? currentEvidenceIndex - 1 : currentEvidenceList.length - 1
      const previousEvidence = currentEvidenceList[nextIndex]
      setSelectedEvidenceId(previousEvidence.evidence_id)
      setSelectedEvidence(previousEvidence)
    },
    onAccept: () => recordQuickDecision('accepted'),
    onReject: () => recordQuickDecision('rejected'),
    onFocusEdit: () => setFocusEditSignal((signal) => signal + 1),
    onShowHelp: () => setShowHelp(true),
    enabled: !!selectedProposalId,
  })

  function handleProposalSelect(proposalId: string) {
    if (proposalId === selectedProposalId) return
    setSelectedProposalId(proposalId)
    setSelectedCell(null)
    setSelectedEvidenceId(null)
    setSelectedEvidence(null)
    setCurrentEvidenceList([])
    setCurrentPdfId(null)
  }

  function handleCellSelect(cell: SelectedReviewCell) {
    setSelectedCell(cell)
    setSelectedProposalId(null)
    setSelectedEvidenceId(null)
    setSelectedEvidence(null)
    setCurrentEvidenceList([])
    setCurrentPdfId(null)
  }

  function handleLeftPaneModeChange(mode: LeftPaneMode) {
    setLeftPaneMode(mode)
    storeValue('papersToTable.review.leftPaneMode', mode)
  }

  function handleLeftPaneFilterChange(filter: ReviewFilter) {
    setLeftPaneFilter(filter)
    storeValue('papersToTable.review.leftPaneFilter', filter)
  }

  useEffect(() => {
    if (!selectedProposalId) return
    let cancelled = false
    setCurrentPdfId(null)
    setCurrentEvidenceList([])
    setSelectedEvidenceId(null)
    setSelectedEvidence(null)
    api.getProposalDetail(run.run_id, selectedProposalId, outputDir)
      .then((detail) => {
        if (cancelled) return
        setWorkspaceError(null)
        setCurrentPdfId(detail.proposal.pdf_id)
        setCurrentEvidenceList(detail.evidence)
        const nextEvidence = detail.evidence.find((item) => item.evidence_id === detail.proposal.primary_evidence_id) ?? detail.evidence[0] ?? null
        setSelectedEvidenceId(nextEvidence?.evidence_id ?? null)
        setSelectedEvidence(nextEvidence)
      })
      .catch((err) => {
        if (!cancelled) setWorkspaceError(err instanceof Error ? err.message : String(err))
      })
    return () => {
      cancelled = true
    }
  }, [decisionVersion, outputDir, run.run_id, selectedProposalId])

  useEffect(() => {
    if (!resizeTarget) return

    function handleMouseMove(event: MouseEvent) {
      const rect = layoutRef.current?.getBoundingClientRect()
      if (!rect) return

      if (resizeTarget === 'left') {
        const maxWidth = Math.min(LEFT_PANE_MAX, rect.width - rightPaneWidth - CENTER_PANE_MIN)
        const nextWidth = clamp(event.clientX - rect.left, LEFT_PANE_MIN, maxWidth)
        setLeftPaneWidth(nextWidth)
        storeValue('papersToTable.review.leftPaneWidth', nextWidth)
        return
      }

      const maxWidth = Math.min(RIGHT_PANE_MAX, rect.width - leftPaneWidth - CENTER_PANE_MIN)
      const nextWidth = clamp(rect.right - event.clientX, RIGHT_PANE_MIN, maxWidth)
      setRightPaneWidth(nextWidth)
      storeValue('papersToTable.review.rightPaneWidth', nextWidth)
    }

    function handleMouseUp() {
      setResizeTarget(null)
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => {
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      window.removeEventListener('mousemove', handleMouseMove)
      window.removeEventListener('mouseup', handleMouseUp)
    }
  }, [leftPaneWidth, resizeTarget, rightPaneWidth])

  function handleEvidenceSelect(evidenceId: string) {
    const evidenceItem = currentEvidenceList.find((item) => item.evidence_id === evidenceId) ?? null
    setSelectedEvidenceId(evidenceId)
    setSelectedEvidence(evidenceItem)
  }

  async function handleExport() {
    setExporting(true)
    setExportError(null)
    setExportNotice(null)
    try {
      if (!api.isServed()) {
        await api.downloadDecisions()
        setExportResult(null)
        setExportNotice('Review decisions downloaded. To create the root reviewed CSV, run apply_review_decisions.py with the downloaded_decisions.json file for this review run.')
        return
      }
      const result = await api.triggerExport(run.run_id, outputDir)
      setExportResult(result)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : String(error))
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-73px)] min-h-0 flex-col bg-slate-100 px-3 pb-3 pt-3" data-testid="review-workspace">
      <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="shrink-0 border-b border-slate-200 bg-white px-4 py-3" data-testid="review-toolbar">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Review</p>
              <div className="inline-flex max-w-full flex-col">
                <div className="mt-1 flex max-w-full flex-wrap items-center gap-2 text-sm">
                  <h2 className="max-w-[28rem] truncate text-base font-semibold tracking-tight text-slate-950" title={run.run_id}>
                    {run.run_id}
                  </h2>
                  <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                    {actionableReviewed} / {actionableTotal} reviewed
                  </span>
                  <span className="rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-800">
                    {actionablePending} pending
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-3">
                  <div className="h-1.5 min-w-48 flex-1 overflow-hidden rounded-full bg-slate-100">
                    <div className="h-full rounded-full bg-slate-950 transition-all" style={{ width: `${progressPct}%` }} />
                  </div>
                  <span className="font-mono text-xs font-semibold tabular-nums text-slate-500">{progressPct}%</span>
                </div>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {run.eval_mode && <span className="rounded-md bg-indigo-100 px-2 py-1 text-xs font-semibold text-indigo-700">Eval mode</span>}
              <button
                onClick={() => setShowDiagnostics((value) => !value)}
                aria-expanded={showDiagnostics}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${showDiagnostics ? 'bg-slate-950 text-white' : 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50'}`}
              >
                Diagnostics
              </button>
              <button
                onClick={handleExport}
                disabled={exporting}
                title={api.isServed() ? 'Write the root reviewed CSV from accepted decisions.' : 'Finish this static review by downloading decisions for the export script.'}
                className="rounded-lg bg-slate-950 px-3 py-1.5 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
              >
                {exporting ? 'Finishing…' : api.isServed() ? 'Export reviewed table' : 'Finish review'}
              </button>
              <button onClick={() => setShowHelp(true)} className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-500 hover:bg-slate-50" title="Keyboard shortcuts (?)">
                ?
              </button>
            </div>
          </div>
        </div>

        {(exportError || exportResult || exportNotice) && (
          <div className="border-b border-slate-200 bg-slate-50 px-5 py-3 text-xs" data-testid="export-status">
            {exportError && <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-rose-700"><strong>Export failed:</strong> {exportError}</div>}
            {exportNotice && <div className="rounded-2xl border border-sky-200 bg-sky-50 px-3 py-2 text-sky-800"><strong>Decisions downloaded:</strong> {exportNotice}</div>}
            {exportResult && (
              <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">
                <span>Export completed at {new Date(exportResult.exported_at).toLocaleString()} with {exportResult.accepted_changes_count} accepted change(s).</span>
                {exportResult.reviewed_table_path && <span className="rounded-xl border border-emerald-200 bg-white px-3 py-1.5 font-semibold text-emerald-800">Reviewed table: {exportResult.reviewed_table_path}</span>}
              </div>
            )}
          </div>
        )}
        {workspaceError && (
          <div className="border-b border-rose-200 bg-rose-50 px-5 py-3 text-xs text-rose-800" data-testid="workspace-error-banner">
            <strong>Workspace action failed:</strong> {workspaceError}
          </div>
        )}

        <div ref={layoutRef} className="flex min-h-0 flex-1 overflow-hidden">
            <div className="flex min-h-0 shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-slate-50" style={{ width: leftPaneWidth }}>
              <ProposalQueue
                runId={run.run_id}
                outputDir={outputDir}
                selectedProposalId={selectedProposalId}
                onSelect={handleProposalSelect}
                onVisibleProposalOrderChange={handleVisibleProposalOrderChange}
                mode={leftPaneMode}
                filter={leftPaneFilter}
                onModeChange={handleLeftPaneModeChange}
                onFilterChange={handleLeftPaneFilterChange}
                onSelectCell={handleCellSelect}
                refreshVersion={decisionVersion}
              />
            </div>

            <div role="separator" aria-orientation="vertical" aria-label="Resize proposal queue" onMouseDown={() => setResizeTarget('left')} className={`w-1 shrink-0 cursor-col-resize border-r border-slate-200 bg-slate-100 transition hover:bg-slate-300 ${resizeTarget === 'left' ? 'bg-slate-400' : ''}`} />

            <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-white">
              <div className="min-h-0 flex-1 overflow-hidden">
                <ProposalDetailPane proposalId={selectedProposalId} selectedCell={selectedCell} runId={run.run_id} outputDir={outputDir} selectedEvidenceId={selectedEvidenceId} onEvidenceSelect={handleEvidenceSelect} key={`${selectedProposalId ?? selectedCell?.rowId ?? 'none'}-${selectedCell?.columnName ?? ''}-${decisionVersion}`} />
              </div>
              {currentProposal && (
                <ReviewActionArea proposal={currentProposal} runId={run.run_id} outputDir={outputDir} onDecisionRecorded={handleDecisionRecorded} onNext={goNext} onPrev={goPrev} visibleProposals={navigationProposals} focusEditSignal={focusEditSignal} />
              )}
            </div>

            <div role="separator" aria-orientation="vertical" aria-label="Resize evidence panel" onMouseDown={() => setResizeTarget('right')} className={`w-1 shrink-0 cursor-col-resize border-l border-slate-200 bg-slate-100 transition hover:bg-slate-300 ${resizeTarget === 'right' ? 'bg-slate-400' : ''}`} />

            <div className="flex min-h-0 shrink-0 flex-col overflow-hidden border-l border-slate-200 bg-white" style={{ width: rightPaneWidth }}>
              <EvidenceViewer runId={run.run_id} pdfId={currentPdfId} evidence={selectedEvidence} evidenceList={currentEvidenceList} selectedEvidenceId={selectedEvidenceId} activeEvidenceIndex={activeEvidenceIndex} onSelectEvidence={handleEvidenceSelect} outputDir={outputDir} />
            </div>
          </div>
      </div>

      {showDiagnostics && <DiagnosticsDrawer run={run} outputDir={outputDir} onClose={() => setShowDiagnostics(false)} />}
      {showHelp && <KeyboardHelpModal onClose={() => setShowHelp(false)} />}
    </div>
  )
}
