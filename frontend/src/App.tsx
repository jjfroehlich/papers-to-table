import { FormEvent, useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import type { ConfigSnapshot, InputSummary, MatchRecord, ProposalDetail, ProposalRecord, ReviewerSummary, RunDiagnostics, RunRecord, RunSummary } from './lib/types'
import { filterProposals, isActionableProposal, type ProposalFilter } from './lib/proposals'
import { ProposalDetailPane } from './components/ProposalDetailPane'
import { ProposalQueue } from './components/ProposalQueue'
import { PdfJsEvidenceViewer } from './components/PdfJsEvidenceViewer'
import { RunSummaryPanel } from './components/RunSummaryPanel'

function selectProposalId(current: string | null, nextProposals: ProposalRecord[]): string | null {
  if (current && nextProposals.some((proposal) => proposal.proposal_id === current)) {
    return current
  }
  return nextProposals[0]?.proposal_id ?? null
}

function isMatchWarning(match: MatchRecord): boolean {
  return match.outcome !== 'matched'
}

function isTerminalStatus(status: RunRecord['status'] | null | undefined): boolean {
  return status === 'completed' || status === 'completed_with_warnings' || status === 'failed' || status === 'interrupted'
}

function isReviewReady(status: RunRecord['status'] | null | undefined): boolean {
  return status === 'completed' || status === 'completed_with_warnings'
}

function reviewUnavailableMessage(run: RunRecord | null): string {
  if (!run) {
    return 'No run selected yet. Start a run from the config launcher to populate the review queue.'
  }
  if (run.status === 'failed') {
    return 'This run failed before review became available. Inspect the failure message and diagnostics above, then start a new run after fixing the problem.'
  }
  if (run.status === 'interrupted') {
    return 'This run was interrupted before review became available. Inspect diagnostics and start a new run if you still need proposals.'
  }
  if (run.status === 'validating') {
    return 'This run is validating the config and inputs. Review items will appear automatically if validation succeeds.'
  }
  if (run.status === 'running' || run.status === 'created') {
    return `This run is ${run.status.replace(/_/g, ' ')}. Review items will appear after processing finishes.`
  }
  return 'No proposals match the current filter.'
}

export function App() {
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [summary, setSummary] = useState<RunSummary | null>(null)
  const [reviewerSummary, setReviewerSummary] = useState<ReviewerSummary | null>(null)
  const [inputSummary, setInputSummary] = useState<InputSummary | null>(null)
  const [configSnapshot, setConfigSnapshot] = useState<ConfigSnapshot | null>(null)
  const [diagnostics, setDiagnostics] = useState<RunDiagnostics | null>(null)
  const [proposals, setProposals] = useState<ProposalRecord[]>([])
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProposalDetail | null>(null)
  const [reviewWorkspaceRunId, setReviewWorkspaceRunId] = useState<string | null>(null)
  const [filter, setFilter] = useState<ProposalFilter>('all')
  const [matchWarnings, setMatchWarnings] = useState<MatchRecord[]>([])
  const [configPathInput, setConfigPathInput] = useState('my-config.json')
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [loadingRunData, setLoadingRunData] = useState(false)
  const [startingRun, setStartingRun] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [startError, setStartError] = useState<string | null>(null)

  const selectedRun = useMemo(
    () => runs.find((run) => run.run_id === selectedRunId) ?? null,
    [runs, selectedRunId],
  )

  const refreshRuns = async (preferredRunId?: string | null) => {
    setLoadingRuns(true)
    try {
      const items = await api.listRuns()
      setRuns(items)
      setSelectedRunId((current) => {
        if (preferredRunId && items.some((run) => run.run_id === preferredRunId)) return preferredRunId
        if (current && items.some((run) => run.run_id === current)) return current
        return items[0]?.run_id ?? null
      })
      setError(null)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to load runs.')
    } finally {
      setLoadingRuns(false)
    }
  }

  useEffect(() => {
    void refreshRuns()
  }, [])

  useEffect(() => {
    if (!selectedRunId || !selectedRun) {
      setSummary(null)
      setReviewerSummary(null)
      setInputSummary(null)
      setConfigSnapshot(null)
      setDiagnostics(null)
      setProposals([])
      setMatchWarnings([])
      setSelectedProposalId(null)
      setDetail(null)
      setReviewWorkspaceRunId(null)
      return
    }

    let cancelled = false
    setLoadingRunData(true)
    setDetail(null)
    setReviewWorkspaceRunId(null)

    async function loadRunWorkspace() {
      const setupRequests = await Promise.allSettled([
        api.getConfigSnapshot(selectedRunId),
        api.getInputSummary(selectedRunId),
        api.getDiagnostics(selectedRunId),
      ])

      if (cancelled) return

      setConfigSnapshot(setupRequests[0].status === 'fulfilled' ? setupRequests[0].value : null)
      setInputSummary(setupRequests[1].status === 'fulfilled' ? setupRequests[1].value : null)
      setDiagnostics(setupRequests[2].status === 'fulfilled' ? setupRequests[2].value : null)

      if (!isReviewReady(selectedRun.status)) {
        setSummary(null)
        setReviewerSummary(null)
        setProposals([])
        setMatchWarnings([])
        setSelectedProposalId(null)
        setDetail(null)
        setReviewWorkspaceRunId(null)
        setLoadingRunData(false)
        return
      }

      try {
        const [runSummary, reviewer, proposalResponse, matchesResponse] = await Promise.all([
          api.getSummary(selectedRunId),
          api.getReviewerSummary(selectedRunId),
          api.getProposals(selectedRunId),
          api.getMatches(selectedRunId),
        ])
        if (cancelled) return
        setSummary(runSummary)
        setReviewerSummary(reviewer)
        setProposals(proposalResponse.proposals)
        setMatchWarnings(matchesResponse.matches.filter(isMatchWarning))
        setReviewWorkspaceRunId(selectedRunId)
        setSelectedProposalId((current) => selectProposalId(current, proposalResponse.proposals))
        setError(null)
      } catch (requestError) {
        if (cancelled) return
        setReviewWorkspaceRunId(null)
        setError(requestError instanceof Error ? requestError.message : 'Failed to load run details.')
      } finally {
        if (!cancelled) setLoadingRunData(false)
      }
    }

    void loadRunWorkspace()

    return () => {
      cancelled = true
    }
  }, [selectedRunId, selectedRun?.status, selectedRun?.updated_at])

  useEffect(() => {
    if (!selectedRun || isTerminalStatus(selectedRun.status)) return
    const timer = window.setInterval(() => {
      void refreshRuns(selectedRun.run_id)
    }, 1500)
    return () => window.clearInterval(timer)
  }, [selectedRun?.run_id, selectedRun?.status])

  useEffect(() => {
    const reviewWorkspaceReady = reviewWorkspaceRunId === selectedRunId
    if (!selectedRunId || !selectedProposalId || !isReviewReady(selectedRun?.status) || !reviewWorkspaceReady) {
      setDetail(null)
      return
    }
    api.getProposal(selectedRunId, selectedProposalId)
      .then(setDetail)
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : 'Failed to load proposal detail.')
      })
  }, [reviewWorkspaceRunId, selectedRunId, selectedProposalId, selectedRun?.status])

  const activeReviewWorkspace = reviewWorkspaceRunId === selectedRunId
  const visibleSummary = activeReviewWorkspace ? summary : null
  const visibleReviewerSummary = activeReviewWorkspace ? reviewerSummary : null
  const visibleMatchWarnings = activeReviewWorkspace ? matchWarnings : []
  const visibleProposals = activeReviewWorkspace ? proposals : []
  const visibleDetail = activeReviewWorkspace ? detail : null

  const filteredProposals = useMemo(() => filterProposals(visibleProposals, filter), [filter, visibleProposals])

  const queueEmptyMessage = !selectedRun || !isReviewReady(selectedRun.status)
    ? reviewUnavailableMessage(selectedRun)
    : 'No proposals match the current filter.'

  const navigate = (delta: number) => {
    const index = filteredProposals.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
    const next = filteredProposals[index + delta]
    if (next) setSelectedProposalId(next.proposal_id)
  }

  const handleCreateRun = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setStartingRun(true)
    setStartError(null)
    try {
      const run = await api.createRun(configPathInput.trim())
      await refreshRuns(run.run_id)
      setSelectedRunId(run.run_id)
    } catch (requestError) {
      setStartError(requestError instanceof Error ? requestError.message : 'Failed to start the run.')
    } finally {
      setStartingRun(false)
    }
  }

  const refresh = async () => {
    if (!selectedRunId) return
    await refreshRuns(selectedRunId)
  }

  const handleDecision = async (decision: 'accept' | 'accept_with_edit' | 'reject', editedValue?: string) => {
    if (!selectedRunId || !selectedProposalId) return
    setError(null)
    try {
      await api.review(selectedRunId, selectedProposalId, decision, editedValue)
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to record the review decision.')
    }
  }

  const handleBulkAccept = async () => {
    if (!selectedRunId) return
    const actionableIds = filteredProposals
      .filter((proposal) => proposal.review_decision === 'no_decision' && isActionableProposal(proposal))
      .map((proposal) => proposal.proposal_id)
    if (actionableIds.length === 0) return
    const confirmed = window.confirm(`Accept ${actionableIds.length} visible pending proposal${actionableIds.length === 1 ? '' : 's'}? This only applies to the current filtered subset.`)
    if (!confirmed) return
    setError(null)
    try {
      await api.bulkAccept(selectedRunId, actionableIds)
      await refresh()
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Failed to bulk accept proposals.')
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1 className="app-title">Paper Table Agent</h1>
          <p className="app-subtitle">
            Start runs from a config file, watch them move through validation and extraction, then review proposals in a queue-first workflow with evidence and audited exports.
          </p>
        </div>
        <section className="panel launcher-panel" aria-label="run-launcher">
          <form className="stack" onSubmit={handleCreateRun}>
            <div className="section-title-row" style={{ marginBottom: 0 }}>
              <div>
                <h2 className="section-title">Run launcher</h2>
                <p className="section-caption">Keep the config file as the control surface, but start and monitor runs from the UI.</p>
              </div>
              <span className="badge badge-accent">{startingRun ? 'Starting' : 'Ready'}</span>
            </div>
            <label className="field-group">
              <span className="field-label">Config path</span>
              <input
                className="field-input"
                value={configPathInput}
                onChange={(event) => setConfigPathInput(event.target.value)}
                placeholder="my-config.json"
              />
            </label>
            <div className="quick-actions">
              <button className="button-secondary" type="button" onClick={() => setConfigPathInput('my-config.json')}>Use my-config.json</button>
              <button className="button-secondary" type="button" onClick={() => setConfigPathInput('config.example.json')}>Use config.example.json</button>
            </div>
            <div className="topbar-controls">
              <button className="button-primary" type="submit" disabled={startingRun || !configPathInput.trim()}>
                {startingRun ? 'Starting run…' : 'Start run'}
              </button>
              <button className="button-secondary" type="button" onClick={() => void refreshRuns(selectedRunId)}>
                Refresh runs
              </button>
            </div>
            <div className="topbar-controls">
              <label className="field-group">
                <span className="field-label">Current run</span>
                <select
                  className="field-select"
                  value={selectedRunId ?? ''}
                  onChange={(event) => setSelectedRunId(event.target.value)}
                  disabled={runs.length === 0}
                >
                  {runs.map((run) => (
                    <option key={run.run_id} value={run.run_id}>{run.run_id}</option>
                  ))}
                </select>
              </label>
              <div className="panel-muted status-panel compact-status-panel">
                <p className="status-text">{loadingRuns ? 'Loading runs…' : runs.length === 0 ? 'No runs yet.' : `${runs.length} run${runs.length === 1 ? '' : 's'} available`}</p>
                <p className="status-text">
                  {selectedRun
                    ? `${selectedRun.status.replace(/_/g, ' ')}${selectedRun.message ? ` · ${selectedRun.message}` : ''}`
                    : 'Select or start a run to inspect status.'}
                </p>
              </div>
            </div>
            {startError && <p className="inline-error">{startError}</p>}
          </form>
        </section>
      </header>

      {error && (
        <aside className="panel-muted inline-alert inline-alert-danger">
          <strong>Request problem:</strong> {error}
        </aside>
      )}

      <RunSummaryPanel
        run={selectedRun}
        summary={visibleSummary}
        reviewerSummary={visibleReviewerSummary}
        inputSummary={inputSummary}
        configSnapshot={configSnapshot}
        diagnostics={diagnostics}
        matchWarnings={visibleMatchWarnings}
        runId={selectedRunId}
        loadingRunData={loadingRunData}
        downloadAsset={(kind) => selectedRunId ? api.downloadAsset(selectedRunId, kind) : '#'}
      />

      <div className="workspace-grid">
        <ProposalQueue
          proposals={visibleProposals}
          visible={filteredProposals}
          selectedId={selectedProposalId}
          onSelect={setSelectedProposalId}
          onBulkAccept={handleBulkAccept}
          filter={filter}
          setFilter={setFilter}
          reviewReady={isReviewReady(selectedRun?.status)}
          emptyMessage={queueEmptyMessage}
        />
        <ProposalDetailPane
          detail={visibleDetail}
          onDecision={handleDecision}
          onNext={() => navigate(1)}
          onPrevious={() => navigate(-1)}
        />
        <PdfJsEvidenceViewer runId={selectedRunId} detail={visibleDetail} />
      </div>
    </main>
  )
}
