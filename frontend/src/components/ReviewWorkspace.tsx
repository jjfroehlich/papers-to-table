import { useState, useCallback, useEffect, useMemo, useRef } from 'react'
import type { RunData, EvidenceItem, EnrichedProposal, ExportResult, ReviewProgress } from '../types'
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

type SidePanel = 'evidence' | 'unresolved'
type ResizeTarget = 'left' | 'right' | null

const LEFT_PANE_MIN = 260
const LEFT_PANE_MAX = 520
const RIGHT_PANE_MIN = 320
const RIGHT_PANE_MAX = 720
const CENTER_PANE_MIN = 420

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max)
}

function warningHeadline(run: RunData) {
  const messages = run.warnings.map((warning) => warning.message.toLowerCase())
  return {
    hasParsingTruth: messages.some((message) => message.includes('parser fallback') || message.includes('ocr') || message.includes('low text')),
    hasDuplicateConflict: run.warnings.some((warning) => warning.category === 'duplicate_row_conflict'),
    hasFallbackEvidence: run.warnings.some((warning) => warning.category === 'fallback_evidence_used'),
  }
}

function KeyboardHelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl p-6 w-96 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold text-gray-900">Keyboard Shortcuts</h2>
        <table className="w-full text-xs text-gray-700">
          <tbody className="divide-y divide-gray-100">
            {[
              ['A', 'Accept'],
              ['R', 'Reject'],
              ['] or N', 'Next proposal'],
              ['[ or P', 'Previous proposal'],
              ['Alt+N', 'Next evidence'],
              ['Alt+P', 'Previous evidence'],
              ['E', 'Focus edit input'],
              ['?', 'This help'],
            ].map(([key, desc]) => (
              <tr key={key}>
                <td className="py-1.5 pr-4">
                  <kbd className="bg-gray-100 border border-gray-200 rounded px-1.5 py-0.5 font-mono text-xs">
                    {key}
                  </kbd>
                </td>
                <td className="py-1.5">{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <button
          onClick={onClose}
          className="w-full py-1.5 text-xs rounded bg-gray-100 hover:bg-gray-200 text-gray-700"
        >
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
  const [sidePanel, setSidePanel] = useState<SidePanel>('evidence')
  const [showHelp, setShowHelp] = useState(false)
  const [proposalList, setProposalList] = useState<EnrichedProposal[]>([])
  const [reviewProgress, setReviewProgress] = useState<ReviewProgress | null>(null)
  const [decisionVersion, setDecisionVersion] = useState(0)
  const [leftPaneWidth, setLeftPaneWidth] = useState(320)
  const [rightPaneWidth, setRightPaneWidth] = useState(420)
  const [resizeTarget, setResizeTarget] = useState<ResizeTarget>(null)
  const [focusEditSignal, setFocusEditSignal] = useState(0)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exportResult, setExportResult] = useState<ExportResult | null>(null)

  const warningTruth = useMemo(() => warningHeadline(run), [run])

  const loadProposalList = useCallback(() => {
    return Promise.all([
      api.listProposals(run.run_id, {
        output_dir: outputDir,
        reviewable_only: true,
      }),
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
          return proposalResponse.proposals.find((proposal) => !proposal.latest_decision)?.proposal_id
            ?? proposalResponse.proposals[0].proposal_id
        })
      })
      .catch(() => {})
  }, [outputDir, run.run_id])

  useEffect(() => {
    void loadProposalList()
  }, [loadProposalList, decisionVersion])

  const currentIndex = proposalList.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
  const currentProposal = proposalList.find((proposal) => proposal.proposal_id === selectedProposalId) ?? null
  const actionableTotal = reviewProgress?.total_proposals ?? proposalList.length
  const actionableReviewed = reviewProgress?.reviewed ?? proposalList.filter((proposal) => proposal.latest_decision).length
  const attemptedTotal = run.proposals_generated

  function goNext() {
    if (proposalList.length === 0) return
    const nextIdx = currentIndex < proposalList.length - 1 ? currentIndex + 1 : 0
    setSelectedProposalId(proposalList[nextIdx].proposal_id)
  }

  function goPrev() {
    if (proposalList.length === 0) return
    const prevIdx = currentIndex > 0 ? currentIndex - 1 : proposalList.length - 1
    setSelectedProposalId(proposalList[prevIdx].proposal_id)
  }

  function recordQuickDecision(decision: 'accepted' | 'rejected') {
    if (!selectedProposalId) return
    api.recordDecision(run.run_id, selectedProposalId, { decision }, outputDir)
      .then(() => handleDecisionRecorded({ autoAdvance: true }))
      .catch(() => {})
  }

  const handleDecisionRecorded = useCallback((options?: { autoAdvance?: boolean }) => {
    if (options?.autoAdvance && proposalList.length > 1 && selectedProposalId) {
      const pendingCandidates = proposalList.filter(
        (proposal) => proposal.proposal_id !== selectedProposalId && !proposal.latest_decision
      )
      if (pendingCandidates.length > 0) {
        const currentPendingIndex = proposalList.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
        const ordered = [
          ...proposalList.slice(currentPendingIndex + 1),
          ...proposalList.slice(0, currentPendingIndex),
        ]
        const nextPending = ordered.find((proposal) => proposal.proposal_id !== selectedProposalId && !proposal.latest_decision)
        setSelectedProposalId(nextPending?.proposal_id ?? pendingCandidates[0].proposal_id)
      }
    }
    setDecisionVersion((version) => version + 1)
  }, [proposalList, selectedProposalId])

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
        const nextEvidence = detail.evidence.find((item) => item.evidence_id === detail.proposal.primary_evidence_id)
          ?? detail.evidence[0]
          ?? null
        setSelectedEvidenceId(nextEvidence?.evidence_id ?? null)
        setSelectedEvidence(nextEvidence)
      })
      .catch(() => {})
  }, [selectedProposalId, run.run_id, outputDir, decisionVersion])

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

  const activeEvidenceIndex = currentEvidenceList.findIndex((item) => item.evidence_id === selectedEvidenceId)

  return (
    <div className="flex flex-col h-[calc(100vh-57px)]">
      <RunSummaryPanel run={run} outputDir={outputDir} />

      <div className="shrink-0 bg-white border-b border-gray-200 px-4 py-2 flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setSidePanel('evidence')}
            className={`py-2 text-xs font-medium border-b-2 transition-colors ${
              sidePanel === 'evidence'
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Evidence
          </button>
          <button
            onClick={() => setSidePanel('unresolved')}
            className={`py-2 text-xs font-medium border-b-2 transition-colors ${
              sidePanel === 'unresolved'
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Unresolved
          </button>
        </div>

        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="font-medium text-gray-700">Actionable review</span>
          <span>{actionableReviewed} / {actionableTotal}</span>
          <span className="text-gray-400">· attempted {attemptedTotal}</span>
        </div>

        <div className="flex items-center gap-2 text-xs">
          {warningTruth.hasParsingTruth && (
            <span className="rounded-full bg-amber-100 px-2 py-1 font-medium text-amber-800">
              parsing fallback
            </span>
          )}
          {warningTruth.hasDuplicateConflict && (
            <span className="rounded-full bg-red-100 px-2 py-1 font-medium text-red-700">
              duplicate conflicts
            </span>
          )}
          {warningTruth.hasFallbackEvidence && (
            <span className="rounded-full bg-orange-100 px-2 py-1 font-medium text-orange-700">
              evidence fallback
            </span>
          )}
        </div>

        <div className="ml-auto flex items-center gap-2 py-1.5">
          <button
            onClick={handleExport}
            disabled={exporting}
            className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {exporting ? 'Exporting…' : 'Export reviewed workbook'}
          </button>
          {exportResult && (
            <>
              <a
                href={api.getWorkbookDownloadUrl(run.run_id, outputDir)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Workbook
              </a>
              <a
                href={api.getAuditLogDownloadUrl(run.run_id, outputDir)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Audit log
              </a>
              <a
                href={api.getRunSummaryDownloadUrl(run.run_id, outputDir)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Run summary
              </a>
              <a
                href={api.getReviewerSummaryDownloadUrl(run.run_id, outputDir)}
                className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
              >
                Reviewer summary
              </a>
            </>
          )}
          <button
            onClick={() => setShowHelp(true)}
            className="text-xs text-gray-400 hover:text-gray-600"
            title="Keyboard shortcuts (?)"
          >
            ?
          </button>
          <span className="text-xs text-gray-400">
            {currentIndex >= 0 ? `${currentIndex + 1} / ${proposalList.length}` : `${proposalList.length} actionable`}
          </span>
        </div>
      </div>

      {(exportError || exportResult) && (
        <div className="shrink-0 border-b border-gray-200 bg-gray-50 px-4 py-2 text-xs">
          {exportError && (
            <div className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700">
              <strong>Export failed:</strong> {exportError}
            </div>
          )}
          {exportResult && (
            <div className="rounded border border-green-200 bg-green-50 px-3 py-2 text-green-800">
              Export completed at {new Date(exportResult.exported_at).toLocaleString()} with {exportResult.accepted_changes_count} accepted change(s).
            </div>
          )}
        </div>
      )}

      <div ref={layoutRef} className="flex-1 flex overflow-hidden">
        <div
          className="shrink-0 border-r border-gray-200 bg-white overflow-hidden flex flex-col"
          style={{ width: leftPaneWidth }}
        >
          <ProposalQueue
            runId={run.run_id}
            outputDir={outputDir}
            selectedProposalId={selectedProposalId}
            onSelect={handleProposalSelect}
            key={`${run.run_id}-${decisionVersion}`}
          />
        </div>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize proposal queue"
          onMouseDown={() => setResizeTarget('left')}
          className={`w-1.5 shrink-0 cursor-col-resize border-r border-gray-200 bg-gray-100 transition-colors hover:bg-blue-200 ${
            resizeTarget === 'left' ? 'bg-blue-300' : ''
          }`}
        />

        <div className="flex-1 min-w-0 flex flex-col overflow-hidden bg-white">
          <div className="flex-1 overflow-hidden">
            <ProposalDetailPane
              proposalId={selectedProposalId}
              runId={run.run_id}
              outputDir={outputDir}
              selectedEvidenceId={selectedEvidenceId}
              onEvidenceSelect={handleEvidenceSelect}
              key={`${selectedProposalId}-${decisionVersion}`}
            />
          </div>
          {currentProposal && (
            <ReviewActionArea
              proposal={currentProposal}
              runId={run.run_id}
              outputDir={outputDir}
              onDecisionRecorded={handleDecisionRecorded}
              onNext={goNext}
              visibleProposals={proposalList}
              focusEditSignal={focusEditSignal}
            />
          )}
        </div>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize evidence panel"
          onMouseDown={() => setResizeTarget('right')}
          className={`w-1.5 shrink-0 cursor-col-resize border-l border-gray-200 bg-gray-100 transition-colors hover:bg-blue-200 ${
            resizeTarget === 'right' ? 'bg-blue-300' : ''
          }`}
        />

        <div
          className="shrink-0 border-l border-gray-200 bg-gray-50 overflow-hidden flex flex-col"
          style={{ width: rightPaneWidth }}
        >
          {sidePanel === 'evidence' ? (
            <EvidenceViewer
              runId={run.run_id}
              pdfId={currentPdfId}
              evidence={selectedEvidence}
              evidenceList={currentEvidenceList}
              selectedEvidenceId={selectedEvidenceId}
              activeEvidenceIndex={activeEvidenceIndex}
              onSelectEvidence={handleEvidenceSelect}
              outputDir={outputDir}
            />
          ) : (
            <div className="flex-1 overflow-y-auto">
              <UnresolvedInspection runId={run.run_id} outputDir={outputDir} />
            </div>
          )}
        </div>
      </div>

      {showHelp && <KeyboardHelpModal onClose={() => setShowHelp(false)} />}
    </div>
  )
}
