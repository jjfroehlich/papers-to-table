/**
 * T083 — Three-pane review workspace.
 *
 * Left pane:   Proposal queue (T084)
 * Center pane: Proposal detail (T085) + Review actions (T090)
 * Right pane:  Evidence viewer (T086-T089)
 *
 * Also surfaces:
 * - T082: Run summary context at top
 * - T091: Keyboard shortcuts for navigation and decisions
 * - T092: Unresolved match inspection (accessible via "Unresolved" tab)
 * - T093: Warnings/statuses, run-summary fields, provider/model consistently shown
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import {
  bulkAccept,
  getProgress,
  getProposalDetail,
  listProposals,
  recordDecision,
} from '../api'
import type {
  ProposalDetail,
  ProposalListItem,
  ProposalProgress,
  ReviewDecision,
  RunSummary,
} from '../types'
import { EvidenceViewer } from './EvidenceViewer'
import { ProposalDetailPane } from './ProposalDetailPane'
import { ProposalQueue, type QueueFilter } from './ProposalQueue'
import { ReviewActionArea } from './ReviewActionArea'
import { RunSummaryPanel } from './RunSummaryPanel'
import { UnresolvedInspection } from './UnresolvedInspection'
import { useReviewKeyboardShortcuts } from '../hooks/useReviewKeyboardShortcuts'

type WorkspaceTab = 'review' | 'summary' | 'unresolved'

interface Props {
  runId: string
  runSummary: RunSummary
}

const TERMINAL = new Set(['completed', 'completed_with_warnings', 'failed', 'interrupted'])

export function ReviewWorkspace({ runId, runSummary }: Props) {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('review')
  const [proposals, setProposals] = useState<ProposalListItem[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProposalDetail | null>(null)
  const [progress, setProgress] = useState<ProposalProgress | null>(null)
  const [loadingProposals, setLoadingProposals] = useState(false)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [isBusy, setIsBusy] = useState(false)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [, setActiveFilter] = useState<QueueFilter>({
    decision: 'all',
    hasFigureEvidence: null,
    hasAmbiguousMatch: null,
  })

  const evidenceRef = useRef<HTMLDivElement>(null)

  const isTerminal = TERMINAL.has(runSummary.status)
  const isReviewable = isTerminal && runSummary.status !== 'failed'

  // Load proposals on run change
  useEffect(() => {
    setProposals([])
    setSelectedId(null)
    setDetail(null)
    setProgress(null)
    setWorkspaceError(null)

    if (!isReviewable) return

    setLoadingProposals(true)
    Promise.all([
      listProposals(runId),
      getProgress(runId).catch(() => null),
    ])
      .then(([items, prog]) => {
        setProposals(items)
        setProgress(prog)
      })
      .catch((err: unknown) => {
        setWorkspaceError(err instanceof Error ? err.message : 'Failed to load proposals')
      })
      .finally(() => setLoadingProposals(false))
  }, [runId, isReviewable])

  // Load detail when selection changes
  useEffect(() => {
    if (!selectedId) {
      setDetail(null)
      return
    }
    setLoadingDetail(true)
    getProposalDetail(runId, selectedId)
      .then(setDetail)
      .catch((err: unknown) => {
        setWorkspaceError(err instanceof Error ? err.message : 'Failed to load proposal detail')
      })
      .finally(() => setLoadingDetail(false))
  }, [runId, selectedId])

  // Refresh progress after decisions
  const refreshProgress = useCallback(() => {
    getProgress(runId)
      .then(setProgress)
      .catch(() => undefined)
  }, [runId])

  // Refresh proposals after decisions (to update decision badges)
  const refreshProposals = useCallback(() => {
    listProposals(runId)
      .then(setProposals)
      .catch(() => undefined)
  }, [runId])

  // Navigation helpers (operate on sorted+filtered order from ProposalQueue)
  const sortedIds = proposals.map((p) => p.proposal_id)
  const selectedIndex = selectedId ? sortedIds.indexOf(selectedId) : -1
  const hasPrev = selectedIndex > 0
  const hasNext = selectedIndex < sortedIds.length - 1

  function goNext() {
    if (hasNext) setSelectedId(sortedIds[selectedIndex + 1])
  }

  function goPrev() {
    if (hasPrev) setSelectedId(sortedIds[selectedIndex - 1])
  }

  async function handleDecision(decision: ReviewDecision, editedValue?: string) {
    if (!selectedId) return
    setIsBusy(true)
    try {
      await recordDecision(runId, selectedId, decision, editedValue)
      // Refresh proposals and detail to reflect new decision
      await Promise.all([
        listProposals(runId).then(setProposals),
        getProposalDetail(runId, selectedId).then(setDetail),
      ])
      refreshProgress()
      // Auto-advance to next pending proposal
      if (decision !== 'undecided') {
        const pending = proposals.filter(
          (p) => p.proposal_id !== selectedId && p.latest_decision === 'undecided',
        )
        if (pending.length > 0) {
          setSelectedId(pending[0].proposal_id)
        }
      }
    } finally {
      setIsBusy(false)
    }
  }

  async function handleBulkAccept() {
    setIsBusy(true)
    try {
      // Bulk accept scoped to current filter context (no pdf_id filter for now — accept all undecided visible)
      await bulkAccept(runId)
      await listProposals(runId).then(setProposals)
      refreshProgress()
      // Reload current detail if it changed
      if (selectedId) {
        await getProposalDetail(runId, selectedId).then(setDetail).catch(() => undefined)
      }
    } finally {
      setIsBusy(false)
    }
  }

  // Keyboard shortcut handlers (T091)
  const focusEdit = useCallback(() => {
    const el = document.querySelector<HTMLElement>('.edit-value-input')
    el?.focus()
  }, [])

  const focusEvidence = useCallback(() => {
    evidenceRef.current?.focus()
    evidenceRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useReviewKeyboardShortcuts({
    onPrev: goPrev,
    onNext: goNext,
    onAccept: () => { if (detail && !isBusy) void handleDecision('accept') },
    onReject: () => { if (detail && !isBusy) void handleDecision('reject') },
    onFocusEdit: focusEdit,
    onFocusEvidence: focusEvidence,
    enabled: activeTab === 'review',
  })

  const verifyMode = runSummary.verify_mode

  // Pre-review state guidance
  if (!isReviewable) {
    return (
      <div className="review-preguidance">
        <h2>Review</h2>
        {runSummary.status === 'failed' && (
          <p>Run failed. Fix config/input issues and start a new run before reviewing.</p>
        )}
        {!isTerminal && (
          <p>Run is {runSummary.operator_status}. Review is gated until the run reaches a terminal state.</p>
        )}
        {runSummary.status === 'created' && (
          <p>Run is not yet started. Switch to the Run tab to launch it.</p>
        )}
      </div>
    )
  }

  return (
    <div className="review-workspace">
      {/* T093: Provider/model/verify-mode context bar */}
      <div className="workspace-context-bar">
        <span className="ctx-item">
          <span className="ctx-label">Run:</span>
          <span className="ctx-val mono">{runId.slice(0, 16)}…</span>
        </span>
        <span className="ctx-item">
          <span className="ctx-label">Verify mode:</span>
          <span className="ctx-val">{verifyMode ? 'On' : 'Off'}</span>
        </span>
        {runSummary.provider_name && (
          <span className="ctx-item">
            <span className="ctx-label">Provider:</span>
            <span className="ctx-val">{runSummary.provider_name} ({runSummary.model_name ?? '—'})</span>
          </span>
        )}
        <span className={`ctx-item locality-${runSummary.provider_locality}`}>
          {runSummary.provider_locality === 'local' ? '🏠 Local' : '☁ Cloud'}
        </span>
        {progress && (
          <span className="ctx-item progress-summary">
            {progress.pending} pending / {progress.total} total
            {progress.accepted_as_is + progress.accepted_with_edit > 0 &&
              ` · ${progress.accepted_as_is + progress.accepted_with_edit} accepted`}
            {progress.rejected > 0 && ` · ${progress.rejected} rejected`}
          </span>
        )}
      </div>

      {/* Workspace tabs */}
      <div className="workspace-tabs" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === 'review'}
          className={activeTab === 'review' ? 'active' : ''}
          onClick={() => setActiveTab('review')}
        >
          Review queue
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'summary'}
          className={activeTab === 'summary' ? 'active' : ''}
          onClick={() => setActiveTab('summary')}
        >
          Run summary
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'unresolved'}
          className={activeTab === 'unresolved' ? 'active' : ''}
          onClick={() => setActiveTab('unresolved')}
        >
          Unresolved
        </button>
      </div>

      {workspaceError && <p className="error">{workspaceError}</p>}

      {activeTab === 'summary' && <RunSummaryPanel runId={runId} />}
      {activeTab === 'unresolved' && <UnresolvedInspection runId={runId} />}

      {activeTab === 'review' && (
        <div className="three-pane-workspace">
          {/* Left pane: proposal queue */}
          <div className="pane pane-queue">
            <h3 className="pane-title">Proposals</h3>
            <ProposalQueue
              proposals={proposals}
              selectedId={selectedId}
              onSelect={(id) => {
                setSelectedId(id)
                refreshProposals()
              }}
              onFilterChange={setActiveFilter}
              loading={loadingProposals}
            />
          </div>

          {/* Center pane: detail + actions */}
          <div className="pane pane-detail">
            <h3 className="pane-title">Detail</h3>
            {loadingDetail && <p className="muted">Loading…</p>}
            {!selectedId && !loadingDetail && (
              <p className="muted">Select a proposal from the queue.</p>
            )}
            {detail && !loadingDetail && (
              <>
                <ProposalDetailPane proposal={detail} verifyMode={verifyMode} />
                <ReviewActionArea
                  proposal={detail}
                  onDecision={handleDecision}
                  onNext={goNext}
                  onPrev={goPrev}
                  onBulkAccept={handleBulkAccept}
                  hasPrev={hasPrev}
                  hasNext={hasNext}
                  isBusy={isBusy}
                />
              </>
            )}
          </div>

          {/* Right pane: evidence viewer */}
          <div className="pane pane-evidence" ref={evidenceRef} tabIndex={-1}>
            <h3 className="pane-title">Evidence</h3>
            {detail ? (
              <EvidenceViewer
                key={detail.proposal_id}
                runId={runId}
                evidence={detail.evidence}
              />
            ) : (
              <p className="muted">Select a proposal to view evidence.</p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'review' && (
        <p className="keyboard-hint muted">
          Keyboard: ←/p prev · →/n next · a accept · r reject · e edit · v evidence
        </p>
      )}
    </div>
  )
}
