import { useState, useCallback, useEffect, useRef } from 'react'
import type { RunData, EvidenceItem, EnrichedProposal } from '../types'
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

// Keyboard help modal
function KeyboardHelpModal({ onClose }: { onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl p-6 w-80 space-y-3"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold text-gray-900">Keyboard Shortcuts</h2>
        <table className="w-full text-xs text-gray-700">
          <tbody className="divide-y divide-gray-100">
            {[
              ['A', 'Accept'],
              ['R', 'Reject'],
              ['] or N', 'Next proposal'],
              ['[ or P', 'Prev proposal'],
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
  const [currentPdfId, setCurrentPdfId] = useState<string | null>(null)
  const [sidePanel, setSidePanel] = useState<SidePanel>('evidence')
  const [showHelp, setShowHelp] = useState(false)
  const [proposalList, setProposalList] = useState<EnrichedProposal[]>([])
  const [decisionVersion, setDecisionVersion] = useState(0)
  const [leftPaneWidth, setLeftPaneWidth] = useState(320)
  const [rightPaneWidth, setRightPaneWidth] = useState(420)
  const [resizeTarget, setResizeTarget] = useState<ResizeTarget>(null)

  // Fetch flat proposal list for navigation
  useEffect(() => {
    api.listProposals(run.run_id, {
      output_dir: outputDir,
      reviewable_only: true,
    })
      .then((resp) => {
        setProposalList(resp.proposals)
        setSelectedProposalId((current) => {
          if (resp.proposals.length === 0) return null
          if (current && resp.proposals.some((proposal) => proposal.proposal_id === current)) {
            return current
          }
          return resp.proposals[0].proposal_id
        })
      })
      .catch(() => {})
  }, [run.run_id, outputDir, decisionVersion])

  const currentIndex = proposalList.findIndex((p) => p.proposal_id === selectedProposalId)

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

  function handleAccept() {
    if (!selectedProposalId) return
    api.recordDecision(run.run_id, selectedProposalId, { decision: 'accepted' }, outputDir)
      .then(() => handleDecisionRecorded())
      .catch(() => {})
  }

  function handleReject() {
    if (!selectedProposalId) return
    api.recordDecision(run.run_id, selectedProposalId, { decision: 'rejected' }, outputDir)
      .then(() => handleDecisionRecorded())
      .catch(() => {})
  }

  const handleDecisionRecorded = useCallback(() => {
    setDecisionVersion((v) => v + 1)
  }, [])

  useReviewKeyboardShortcuts({
    onNext: goNext,
    onPrev: goPrev,
    onAccept: handleAccept,
    onReject: handleReject,
    onFocusEdit: () => {},
    onShowHelp: () => setShowHelp(true),
    enabled: !!selectedProposalId,
  })

  function handleProposalSelect(proposalId: string) {
    setSelectedProposalId(proposalId)
    setSelectedEvidenceId(null)
    setSelectedEvidence(null)
    // pdfId will be set when detail pane loads
  }

  // Load detail to get pdfId and set primary evidence
  useEffect(() => {
    if (!selectedProposalId) return
    api.getProposalDetail(run.run_id, selectedProposalId, outputDir)
      .then((detail) => {
        setCurrentPdfId(detail.proposal.pdf_id)
        const primaryId = detail.proposal.primary_evidence_id
        if (primaryId) {
          setSelectedEvidenceId(primaryId)
          const evItem = detail.evidence.find((e) => e.evidence_id === primaryId) ?? null
          setSelectedEvidence(evItem)
        } else if (detail.evidence.length > 0) {
          setSelectedEvidenceId(detail.evidence[0].evidence_id)
          setSelectedEvidence(detail.evidence[0])
        }
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
    setSelectedEvidenceId(evidenceId)
    // Need to fetch evidence item; we'll look it up from detail
    api.getProposalDetail(run.run_id, selectedProposalId!, outputDir)
      .then((detail) => {
        const evItem = detail.evidence.find((e) => e.evidence_id === evidenceId) ?? null
        setSelectedEvidence(evItem)
      })
      .catch(() => {})
  }

  const currentProposal = proposalList.find((p) => p.proposal_id === selectedProposalId) ?? null

  return (
    <div className="flex flex-col h-[calc(100vh-57px)]">
      {/* Top summary bar */}
      <RunSummaryPanel run={run} outputDir={outputDir} />

      {/* Top secondary bar: unresolved tab */}
      <div className="shrink-0 bg-white border-b border-gray-200 px-4 flex items-center gap-4">
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
        <div className="ml-auto flex items-center gap-2 py-1.5">
          <button
            onClick={() => setShowHelp(true)}
            className="text-xs text-gray-400 hover:text-gray-600"
            title="Keyboard shortcuts (?)"
          >
            ?
          </button>
          <span className="text-xs text-gray-400">
            {currentIndex >= 0
              ? `${currentIndex + 1} / ${proposalList.length}`
              : `${proposalList.length} proposals`}
          </span>
        </div>
      </div>

      {/* Three-pane layout */}
      <div ref={layoutRef} className="flex-1 flex overflow-hidden">
        {/* Left: Queue */}
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

        {/* Center: Detail + actions */}
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

        {/* Right: Evidence viewer / Unresolved */}
        <div
          className="shrink-0 border-l border-gray-200 bg-gray-50 overflow-hidden flex flex-col"
          style={{ width: rightPaneWidth }}
        >
          {sidePanel === 'evidence' ? (
            <EvidenceViewer
              runId={run.run_id}
              pdfId={currentPdfId}
              evidence={selectedEvidence}
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
