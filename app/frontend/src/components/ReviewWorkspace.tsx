import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { EvidenceItem, EnrichedProposal, ExportResult, ReviewProgress, RunData } from '../types'
import { RunSummaryPanel } from './RunSummaryPanel'
import { ProposalQueue } from './ProposalQueue'
import { ProposalDetailPane } from './ProposalDetailPane'
import { ReviewActionArea } from './ReviewActionArea'
import { EvidenceViewer } from './EvidenceViewer'
import { UnresolvedInspection } from './UnresolvedInspection'
import { useReviewKeyboardShortcuts } from '../hooks/useReviewKeyboardShortcuts'
import { api } from '../api/client'

interface Props {
  run: RunData
  outputDir: string
}

type ResizeTarget = 'left' | 'right' | null

const LEFT_PANE_MIN = 280
const LEFT_PANE_MAX = 520
const RIGHT_PANE_MIN = 340
const RIGHT_PANE_MAX = 720
const CENTER_PANE_MIN = 480

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function warningHeadline(run: RunData) {
  return {
    hasParsingTruth: run.warnings.some(
      (warning) =>
        warning.category === 'partial_extraction' ||
        warning.message.toLowerCase().includes('parser fallback') ||
        warning.message.toLowerCase().includes('ocr') ||
        warning.message.toLowerCase().includes('low text')
    ),
    hasDuplicateConflict: run.warnings.some((warning) => warning.category === 'duplicate_row_conflict'),
    hasFallbackEvidence: run.warnings.some((warning) => warning.category === 'fallback_evidence_used'),
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

export function ReviewWorkspace({ run, outputDir }: Props) {
  const layoutRef = useRef<HTMLDivElement | null>(null)
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null)
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null)
  const [selectedEvidence, setSelectedEvidence] = useState<EvidenceItem | null>(null)
  const [currentEvidenceList, setCurrentEvidenceList] = useState<EvidenceItem[]>([])
  const [currentPdfId, setCurrentPdfId] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState(false)
  const [showDiagnostics, setShowDiagnostics] = useState(false)
  const [proposalList, setProposalList] = useState<EnrichedProposal[]>([])
  const [reviewProgress, setReviewProgress] = useState<ReviewProgress | null>(null)
  const [decisionVersion, setDecisionVersion] = useState(0)
  const [leftPaneWidth, setLeftPaneWidth] = useState(340)
  const [rightPaneWidth, setRightPaneWidth] = useState(430)
  const [resizeTarget, setResizeTarget] = useState<ResizeTarget>(null)
  const [focusEditSignal, setFocusEditSignal] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportResult, setExportResult] = useState<ExportResult | null>(null)

  const warningTruth = useMemo(() => warningHeadline(run), [run])

  const loadProposalList = useCallback(() => {
    return Promise.all([
      api.listProposals(run.run_id, { output_dir: outputDir, reviewable_only: true }),
      api.getReviewProgress(run.run_id, outputDir),
    ])
      .then(([proposalResponse, progressResponse]) => {
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
      .catch(() => {})
  }, [outputDir, run.run_id])

  useEffect(() => {
    void loadProposalList()
  }, [decisionVersion, loadProposalList])

  const currentIndex = proposalList.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
  const currentProposal = proposalList.find((proposal) => proposal.proposal_id === selectedProposalId) ?? null
  const actionableTotal = reviewProgress?.total_proposals ?? proposalList.length
  const actionableReviewed = reviewProgress?.reviewed ?? proposalList.filter((proposal) => proposal.latest_decision).length
  const attemptedTotal = run.proposals_generated
  const activeEvidenceIndex = currentEvidenceList.findIndex((item) => item.evidence_id === selectedEvidenceId)

  function goNext() {
    if (proposalList.length === 0) return
    const nextIndex = currentIndex < proposalList.length - 1 ? currentIndex + 1 : 0
    setSelectedProposalId(proposalList[nextIndex].proposal_id)
  }

  function goPrev() {
    if (proposalList.length === 0) return
    const previousIndex = currentIndex > 0 ? currentIndex - 1 : proposalList.length - 1
    setSelectedProposalId(proposalList[previousIndex].proposal_id)
  }

  function recordQuickDecision(decision: 'accepted' | 'rejected') {
    if (!selectedProposalId) return
    api.recordDecision(run.run_id, selectedProposalId, { decision }, outputDir)
      .then(() => handleDecisionRecorded({ autoAdvance: true }))
      .catch(() => {})
  }

  const handleDecisionRecorded = useCallback(
    (options?: { autoAdvance?: boolean }) => {
      if (options?.autoAdvance && proposalList.length > 1 && selectedProposalId) {
        const pendingCandidates = proposalList.filter(
          (proposal) => proposal.proposal_id !== selectedProposalId && !proposal.latest_decision
        )
        if (pendingCandidates.length > 0) {
          const currentPendingIndex = proposalList.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
          const ordered = [...proposalList.slice(currentPendingIndex + 1), ...proposalList.slice(0, currentPendingIndex)]
          const nextPending = ordered.find((proposal) => proposal.proposal_id !== selectedProposalId && !proposal.latest_decision)
          setSelectedProposalId(nextPending?.proposal_id ?? pendingCandidates[0].proposal_id)
        }
      }
      setDecisionVersion((version) => version + 1)
    },
    [proposalList, selectedProposalId]
  )

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
    setSelectedProposalId(proposalId)
    setSelectedEvidenceId(null)
    setSelectedEvidence(null)
    setCurrentEvidenceList([])
  }

  useEffect(() => {
    if (!selectedProposalId) return
    api.getProposalDetail(run.run_id, selectedProposalId, outputDir)
      .then((detail) => {
        setCurrentPdfId(detail.proposal.pdf_id)
        setCurrentEvidenceList(detail.evidence)
        const nextEvidence = detail.evidence.find((item) => item.evidence_id === detail.proposal.primary_evidence_id) ?? detail.evidence[0] ?? null
        setSelectedEvidenceId(nextEvidence?.evidence_id ?? null)
        setSelectedEvidence(nextEvidence)
      })
      .catch(() => {})
  }, [decisionVersion, outputDir, run.run_id, selectedProposalId])

  useEffect(() => {
    if (!resizeTarget) return

    function handleMouseMove(event: MouseEvent) {
      const rect = layoutRef.current?.getBoundingClientRect()
      if (!rect) return

      if (resizeTarget === 'left') {
        const maxWidth = Math.min(LEFT_PANE_MAX, rect.width - rightPaneWidth - CENTER_PANE_MIN)
        setLeftPaneWidth(clamp(event.clientX - rect.left, LEFT_PANE_MIN, maxWidth))
        return
      }

      const maxWidth = Math.min(RIGHT_PANE_MAX, rect.width - leftPaneWidth - CENTER_PANE_MIN)
      setRightPaneWidth(clamp(rect.right - event.clientX, RIGHT_PANE_MIN, maxWidth))
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
    try {
      const result = await api.triggerExport(run.run_id, outputDir)
      setExportResult(result)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : String(error))
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-72px)] flex-col px-4 pb-4" data-testid="review-workspace">
      <div className="overflow-hidden rounded-[32px] border border-slate-200 bg-white shadow-[0_28px_70px_rgba(15,23,42,0.1)]">
        <RunSummaryPanel run={run} outputDir={outputDir} />

        <div className="border-b border-slate-200 bg-[linear-gradient(135deg,#f8fafc,#ffffff_60%,#eff6ff)] px-5 py-4" data-testid="review-toolbar">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-[280px]">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">Review workspace</p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
                <span className="rounded-full bg-slate-950 px-3 py-1.5 font-semibold text-white">
                  {actionableReviewed} / {actionableTotal} reviewed
                </span>
                <span className="text-slate-500">{attemptedTotal} attempted proposals</span>
                {currentProposal && <span className="text-slate-700">Reviewing <strong>{currentProposal.column_name}</strong> for <strong>{currentProposal.paper_title ?? currentProposal.row_id}</strong></span>}
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {run.eval_mode && <span className="rounded-full bg-indigo-100 px-3 py-1.5 text-xs font-semibold text-indigo-700">Eval mode</span>}
              {warningTruth.hasParsingTruth && <span className="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-800">parsing fallback</span>}
              {warningTruth.hasDuplicateConflict && <span className="rounded-full bg-rose-100 px-3 py-1.5 text-xs font-semibold text-rose-700">duplicate conflicts</span>}
              {warningTruth.hasFallbackEvidence && <span className="rounded-full bg-orange-100 px-3 py-1.5 text-xs font-semibold text-orange-700">evidence fallback</span>}
              <button
                onClick={() => setShowDiagnostics((value) => !value)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold transition ${showDiagnostics ? 'bg-slate-950 text-white' : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'}`}
              >
                {showDiagnostics ? 'Hide diagnostics' : 'Diagnostics & run inspection'}
              </button>
              <button
                onClick={handleExport}
                disabled={exporting}
                className="rounded-full bg-sky-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-sky-700 disabled:opacity-50"
              >
                {exporting ? 'Exporting…' : 'Export reviewed workbook'}
              </button>
              <button onClick={() => setShowHelp(true)} className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50" title="Keyboard shortcuts (?)">
                ?
              </button>
            </div>
          </div>

          {currentProposal && (
            <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
              <div className="rounded-[24px] border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Current focus</p>
                <div className="mt-2 flex flex-wrap items-center gap-3">
                  <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">{currentProposal.paper_title ?? currentProposal.row_id}</span>
                  <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700">{currentProposal.column_name}</span>
                  <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-700">{currentProposal.proposed_value ?? 'No value proposed'}</span>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <span>{currentIndex >= 0 ? `${currentIndex + 1} / ${proposalList.length}` : `${proposalList.length} actionable`}</span>
                {exportResult && <span className="rounded-full bg-emerald-100 px-3 py-1 font-semibold text-emerald-700">export ready</span>}
              </div>
            </div>
          )}
        </div>

        {(exportError || exportResult) && (
          <div className="border-b border-slate-200 bg-slate-50 px-5 py-3 text-xs" data-testid="export-status">
            {exportError && <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-rose-700"><strong>Export failed:</strong> {exportError}</div>}
            {exportResult && (
              <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-800">
                <span>Export completed at {new Date(exportResult.exported_at).toLocaleString()} with {exportResult.accepted_changes_count} accepted change(s).</span>
                <a href={api.getWorkbookDownloadUrl(run.run_id, outputDir)} className="rounded-full border border-emerald-200 bg-white px-3 py-1 font-semibold text-emerald-800">Workbook</a>
                <a href={api.getAuditLogDownloadUrl(run.run_id, outputDir)} className="rounded-full border border-emerald-200 bg-white px-3 py-1 font-semibold text-emerald-800">Audit log</a>
                <a href={api.getRunSummaryDownloadUrl(run.run_id, outputDir)} className="rounded-full border border-emerald-200 bg-white px-3 py-1 font-semibold text-emerald-800">Run summary</a>
                <a href={api.getReviewerSummaryDownloadUrl(run.run_id, outputDir)} className="rounded-full border border-emerald-200 bg-white px-3 py-1 font-semibold text-emerald-800">Reviewer summary</a>
              </div>
            )}
          </div>
        )}

        <div ref={layoutRef} className="flex flex-1 overflow-hidden">
          <div className="flex shrink-0 flex-col overflow-hidden border-r border-slate-200 bg-slate-50/80" style={{ width: leftPaneWidth }}>
            <ProposalQueue runId={run.run_id} outputDir={outputDir} selectedProposalId={selectedProposalId} onSelect={handleProposalSelect} key={`${run.run_id}-${decisionVersion}`} />
          </div>

          <div role="separator" aria-orientation="vertical" aria-label="Resize proposal queue" onMouseDown={() => setResizeTarget('left')} className={`w-1.5 shrink-0 cursor-col-resize border-r border-slate-200 bg-slate-100 transition hover:bg-sky-200 ${resizeTarget === 'left' ? 'bg-sky-300' : ''}`} />

          <div className="flex min-w-0 flex-1 flex-col overflow-hidden bg-white">
            <div className="flex-1 overflow-hidden">
              <ProposalDetailPane proposalId={selectedProposalId} runId={run.run_id} outputDir={outputDir} selectedEvidenceId={selectedEvidenceId} onEvidenceSelect={handleEvidenceSelect} key={`${selectedProposalId}-${decisionVersion}`} />
            </div>
            {currentProposal && (
              <ReviewActionArea proposal={currentProposal} runId={run.run_id} outputDir={outputDir} onDecisionRecorded={handleDecisionRecorded} onNext={goNext} visibleProposals={proposalList} focusEditSignal={focusEditSignal} />
            )}
          </div>

          <div role="separator" aria-orientation="vertical" aria-label="Resize evidence panel" onMouseDown={() => setResizeTarget('right')} className={`w-1.5 shrink-0 cursor-col-resize border-l border-slate-200 bg-slate-100 transition hover:bg-sky-200 ${resizeTarget === 'right' ? 'bg-sky-300' : ''}`} />

          <div className="flex shrink-0 flex-col overflow-hidden border-l border-slate-200 bg-slate-950/95 text-white" style={{ width: rightPaneWidth }}>
            <EvidenceViewer runId={run.run_id} pdfId={currentPdfId} evidence={selectedEvidence} evidenceList={currentEvidenceList} selectedEvidenceId={selectedEvidenceId} activeEvidenceIndex={activeEvidenceIndex} onSelectEvidence={handleEvidenceSelect} outputDir={outputDir} />
          </div>
        </div>

        {showDiagnostics && (
          <div className="border-t border-slate-200 bg-slate-50 px-5 py-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Diagnostics and run inspection</p>
                <h3 className="mt-1 text-base font-semibold text-slate-900">Keep unresolved matching issues and warnings visible without crowding the evidence panel.</h3>
              </div>
              <button onClick={() => setShowDiagnostics(false)} className="rounded-full border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50">
                Collapse diagnostics
              </button>
            </div>
            <UnresolvedInspection run={run} runId={run.run_id} outputDir={outputDir} />
          </div>
        )}
      </div>

      {showHelp && <KeyboardHelpModal onClose={() => setShowHelp(false)} />}
    </div>
  )
}
