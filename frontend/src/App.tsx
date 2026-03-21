import { useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import type { MatchRecord, ProposalDetail, ProposalRecord, ReviewerSummary, RunRecord, RunSummary } from './lib/types'
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

export function App() {
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [summary, setSummary] = useState<RunSummary | null>(null)
  const [reviewerSummary, setReviewerSummary] = useState<ReviewerSummary | null>(null)
  const [proposals, setProposals] = useState<ProposalRecord[]>([])
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProposalDetail | null>(null)
  const [filter, setFilter] = useState<ProposalFilter>('all')
  const [matchWarnings, setMatchWarnings] = useState<MatchRecord[]>([])
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [loadingRunData, setLoadingRunData] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoadingRuns(true)
    api.listRuns()
      .then((items) => {
        setRuns(items)
        if (items[0]) {
          setSelectedRunId(items[0].run_id)
        }
      })
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : 'Failed to load runs.')
      })
      .finally(() => setLoadingRuns(false))
  }, [])

  useEffect(() => {
    if (!selectedRunId) return
    setLoadingRunData(true)
    setError(null)
    Promise.all([
      api.getSummary(selectedRunId),
      api.getReviewerSummary(selectedRunId),
      api.getProposals(selectedRunId),
      api.getMatches(selectedRunId),
    ])
      .then(([runSummary, reviewer, proposalResponse, matchesResponse]) => {
        setSummary(runSummary)
        setReviewerSummary(reviewer)
        setProposals(proposalResponse.proposals)
        setMatchWarnings(matchesResponse.matches.filter(isMatchWarning))
        setSelectedProposalId((current) => selectProposalId(current, proposalResponse.proposals))
      })
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : 'Failed to load run details.')
      })
      .finally(() => setLoadingRunData(false))
  }, [selectedRunId])

  useEffect(() => {
    if (!selectedRunId || !selectedProposalId) {
      setDetail(null)
      return
    }
    api.getProposal(selectedRunId, selectedProposalId)
      .then(setDetail)
      .catch((requestError) => {
        setError(requestError instanceof Error ? requestError.message : 'Failed to load proposal detail.')
      })
  }, [selectedRunId, selectedProposalId])

  const filteredProposals = useMemo(() => filterProposals(proposals, filter), [filter, proposals])

  const navigate = (delta: number) => {
    const index = filteredProposals.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
    const next = filteredProposals[index + delta]
    if (next) setSelectedProposalId(next.proposal_id)
  }

  const refresh = async () => {
    if (!selectedRunId) return
    const [runSummary, reviewer, proposalResponse, matchesResponse] = await Promise.all([
      api.getSummary(selectedRunId),
      api.getReviewerSummary(selectedRunId),
      api.getProposals(selectedRunId),
      api.getMatches(selectedRunId),
    ])
    setSummary(runSummary)
    setReviewerSummary(reviewer)
    setProposals(proposalResponse.proposals)
    setMatchWarnings(matchesResponse.matches.filter(isMatchWarning))
    setSelectedProposalId((current) => selectProposalId(current, proposalResponse.proposals))
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
            Review proposals in a queue-first workflow with run metrics, row context, PDF evidence, and direct export downloads from the local artifact bundle.
          </p>
        </div>
        <div className="topbar-controls">
          <label className="field-group">
            <span className="field-label">Run</span>
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
          <div className="panel-muted">
            <p className="status-text">{loadingRuns ? 'Loading runs…' : `${runs.length} run${runs.length === 1 ? '' : 's'} available`}</p>
            <p className="status-text">{loadingRunData ? 'Refreshing run data…' : 'Ready for review'}</p>
          </div>
        </div>
      </header>

      {error && (
        <aside className="panel-muted" style={{ borderColor: '#f5c2c7', background: '#fff4f5' }}>
          <strong>Request problem:</strong> {error}
        </aside>
      )}

      <RunSummaryPanel
        summary={summary}
        reviewerSummary={reviewerSummary}
        matchWarnings={matchWarnings}
        runId={selectedRunId}
        downloadAsset={(kind) => selectedRunId ? api.downloadAsset(selectedRunId, kind) : '#'}
      />

      <div className="workspace-grid">
        <ProposalQueue
          proposals={proposals}
          visible={filteredProposals}
          selectedId={selectedProposalId}
          onSelect={setSelectedProposalId}
          onBulkAccept={handleBulkAccept}
          filter={filter}
          setFilter={setFilter}
        />
        <ProposalDetailPane
          detail={detail}
          onDecision={handleDecision}
          onNext={() => navigate(1)}
          onPrevious={() => navigate(-1)}
        />
        <PdfJsEvidenceViewer runId={selectedRunId} detail={detail} />
      </div>
    </main>
  )
}
