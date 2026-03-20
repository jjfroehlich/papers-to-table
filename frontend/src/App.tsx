import { useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import type { ProposalDetail, ProposalRecord, ReviewerSummary, RunRecord, RunSummary } from './lib/types'
import { ProposalDetailPane } from './components/ProposalDetailPane'
import { ProposalQueue } from './components/ProposalQueue'
import { PdfJsEvidenceViewer } from './components/PdfJsEvidenceViewer'
import { RunSummaryPanel } from './components/RunSummaryPanel'

export function App() {
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [summary, setSummary] = useState<RunSummary | null>(null)
  const [reviewerSummary, setReviewerSummary] = useState<ReviewerSummary | null>(null)
  const [proposals, setProposals] = useState<ProposalRecord[]>([])
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProposalDetail | null>(null)
  const [filter, setFilter] = useState('all')
  const [matchWarnings, setMatchWarnings] = useState<any[]>([])

  useEffect(() => {
    api.listRuns().then((items) => {
      setRuns(items)
      if (items[0]) setSelectedRunId(items[0].run_id)
    }).catch(() => undefined)
  }, [])

  useEffect(() => {
    if (!selectedRunId) return
    Promise.all([
      api.getSummary(selectedRunId),
      api.getReviewerSummary(selectedRunId),
      api.getProposals(selectedRunId),
      api.getMatches(selectedRunId, 'ambiguous'),
    ]).then(([runSummary, reviewer, proposalResponse, matches]) => {
      setSummary(runSummary)
      setReviewerSummary(reviewer)
      setProposals(proposalResponse.proposals)
      setMatchWarnings(matches.matches)
      if (proposalResponse.proposals[0]) setSelectedProposalId(proposalResponse.proposals[0].proposal_id)
    }).catch(() => undefined)
  }, [selectedRunId])

  useEffect(() => {
    if (!selectedRunId || !selectedProposalId) return
    api.getProposal(selectedRunId, selectedProposalId).then(setDetail).catch(() => undefined)
  }, [selectedRunId, selectedProposalId])

  const filteredProposals = useMemo(() => {
    if (filter === 'pending') return proposals.filter((proposal) => proposal.review_decision === 'no_decision')
    if (filter === 'figure') return proposals.filter((proposal) => proposal.source_mode === 'vision')
    if (filter === 'needs_evidence') return proposals.filter((proposal) => proposal.needs_more_evidence)
    return proposals
  }, [filter, proposals])

  const navigate = (delta: number) => {
    const index = filteredProposals.findIndex((proposal) => proposal.proposal_id === selectedProposalId)
    const next = filteredProposals[index + delta]
    if (next) setSelectedProposalId(next.proposal_id)
  }

  const refresh = async () => {
    if (!selectedRunId) return
    const [runSummary, reviewer, proposalResponse] = await Promise.all([
      api.getSummary(selectedRunId),
      api.getReviewerSummary(selectedRunId),
      api.getProposals(selectedRunId),
    ])
    setSummary(runSummary)
    setReviewerSummary(reviewer)
    setProposals(proposalResponse.proposals)
  }

  const handleDecision = async (decision: 'accept' | 'accept_with_edit' | 'reject', editedValue?: string) => {
    if (!selectedRunId || !selectedProposalId) return
    await api.review(selectedRunId, selectedProposalId, decision, editedValue)
    await refresh()
  }

  const handleBulkAccept = async () => {
    if (!selectedRunId) return
    await api.bulkAccept(selectedRunId, filteredProposals.filter((proposal) => proposal.review_decision === 'no_decision').map((proposal) => proposal.proposal_id))
    await refresh()
  }

  return (
    <main>
      <header>
        <h1>Paper Table Agent</h1>
        <label>
          Run
          <select value={selectedRunId ?? ''} onChange={(event) => setSelectedRunId(event.target.value)}>
            {runs.map((run) => <option key={run.run_id} value={run.run_id}>{run.run_id}</option>)}
          </select>
        </label>
      </header>
      <RunSummaryPanel summary={summary} reviewerSummary={reviewerSummary} />
      {matchWarnings.length > 0 && <aside>{matchWarnings.length} ambiguous or blocked PDF records require inspection.</aside>}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', alignItems: 'start' }}>
        <ProposalQueue
          proposals={proposals}
          selectedId={selectedProposalId}
          onSelect={setSelectedProposalId}
          onBulkAccept={handleBulkAccept}
          filter={filter}
          setFilter={setFilter}
        />
        <ProposalDetailPane detail={detail} onDecision={handleDecision} onNext={() => navigate(1)} onPrevious={() => navigate(-1)} />
        <PdfJsEvidenceViewer runId={selectedRunId} detail={detail} />
      </div>
    </main>
  )
}
