import { useEffect, useMemo, useState } from 'react'

type RunRecord = {
  run_id: string
  status: string
  operator_state: string
  error?: string
  current_stage?: string
  current_item?: string
}

type ProposalItem = {
  proposal_id: string
  pdf_id: string
  row_id: string
  column_name: string
  proposed_value?: string
  proposal_state: string
  support_label: string
  review_decision: string
  match_outcome?: string
  warning_categories?: string[]
}

type ProposalDetail = {
  proposal: ProposalItem & {
    rationale?: string
    calculation?: string
    primary_evidence_id?: string
  }
  row_context: { row_index?: number; row_values?: Record<string, unknown>; current_cell_value?: unknown }
  column_definition: Record<string, unknown>
  support_label: string
  rationale?: string
  calculation?: string
  primary_evidence?: EvidenceItem | null
  secondary_evidence?: EvidenceItem[]
  warning_status_flags?: string[]
}

type EvidenceItem = {
  evidence_id: string
  source_type?: string
  page?: number
  quote_text?: string
  highlight?: Record<string, unknown>
  caption_text?: string
  crop_path?: string
  full_page_path?: string
}

type Summary = Record<string, unknown>

type FilterState = {
  review_decision: string
  evidence_status: string
  match_status: string
  figure_derived: string
}

const API_ROOT = 'http://localhost:8000'

const FILTER_DEFAULTS: FilterState = {
  review_decision: '',
  evidence_status: '',
  match_status: '',
  figure_derived: '',
}

function figureFilterValue(raw: string): boolean | undefined {
  if (raw === 'true') return true
  if (raw === 'false') return false
  return undefined
}

function queueSort(a: ProposalItem, b: ProposalItem) {
  const decisionRank = (value: string) => (value === 'undecided' ? 0 : 1)
  const actionableRank = (value: string) => (['blocked', 'skipped', 'error'].includes(value) ? 1 : 0)
  const row = (value: string) => Number.parseInt(value.replace('row_', ''), 10)
  return (
    decisionRank(a.review_decision) - decisionRank(b.review_decision) ||
    actionableRank(a.proposal_state) - actionableRank(b.proposal_state) ||
    (Number.isNaN(row(a.row_id)) ? 999999 : row(a.row_id)) - (Number.isNaN(row(b.row_id)) ? 999999 : row(b.row_id)) ||
    a.column_name.localeCompare(b.column_name) ||
    a.proposal_id.localeCompare(b.proposal_id)
  )
}

export function App() {
  const [activeView, setActiveView] = useState<'run' | 'review'>('run')
  const [configPath, setConfigPath] = useState('config.example.json')
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [inputSummary, setInputSummary] = useState<Record<string, unknown> | null>(null)
  const [message, setMessage] = useState('Enter a config path and start a run.')
  const [filters, setFilters] = useState<FilterState>(FILTER_DEFAULTS)
  const [queue, setQueue] = useState<ProposalItem[]>([])
  const [counters, setCounters] = useState<Record<string, number>>({})
  const [runWarnings, setRunWarnings] = useState<string[]>([])
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ProposalDetail | null>(null)
  const [editedValue, setEditedValue] = useState('')
  const [runSummary, setRunSummary] = useState<Summary | null>(null)
  const [reviewerSummary, setReviewerSummary] = useState<Summary | null>(null)
  const [matchingIssues, setMatchingIssues] = useState<Record<string, Array<Record<string, unknown>>>>({})
  const [downloadManifest, setDownloadManifest] = useState<Record<string, unknown> | null>(null)

  async function loadRuns() {
    const res = await fetch(`${API_ROOT}/api/runs`)
    const data = await res.json()
    setRuns(data)
    if (!activeRunId && data.length > 0) {
      setActiveRunId(data[0].run_id)
    }
  }

  async function loadQueue(runId: string) {
    const params = new URLSearchParams()
    if (filters.review_decision) params.set('review_decision', filters.review_decision)
    if (filters.evidence_status) params.set('evidence_status', filters.evidence_status)
    if (filters.match_status) params.set('match_status', filters.match_status)
    const figure = figureFilterValue(filters.figure_derived)
    if (figure !== undefined) params.set('figure_derived', String(figure))

    const res = await fetch(`${API_ROOT}/api/runs/${runId}/proposals?${params.toString()}`)
    const data = await res.json()
    const sorted: ProposalItem[] = (data.items ?? []).slice().sort(queueSort)
    setQueue(sorted)
    setCounters(data.counters ?? {})
    setRunWarnings(data.run_warning_categories ?? [])
    setSelectedProposalId((prev) => {
      if (prev && sorted.some((item) => item.proposal_id === prev)) return prev
      return sorted[0]?.proposal_id ?? null
    })
  }

  async function loadSummaries(runId: string) {
    const [runRes, reviewerRes, issuesRes, downloadsRes] = await Promise.all([
      fetch(`${API_ROOT}/api/runs/${runId}/summaries/run`),
      fetch(`${API_ROOT}/api/runs/${runId}/summaries/reviewer`),
      fetch(`${API_ROOT}/api/runs/${runId}/matching/issues`),
      fetch(`${API_ROOT}/api/runs/${runId}/downloads`),
    ])
    setRunSummary(runRes.ok ? await runRes.json() : null)
    setReviewerSummary(reviewerRes.ok ? await reviewerRes.json() : null)
    setMatchingIssues(issuesRes.ok ? await issuesRes.json() : {})
    setDownloadManifest(downloadsRes.ok ? await downloadsRes.json() : null)
  }

  useEffect(() => {
    loadRuns().catch(() => setMessage('Backend unavailable. Start backend first.'))
    const timer = setInterval(() => loadRuns().catch(() => null), 2000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!activeRunId) {
      setInputSummary(null)
      setQueue([])
      setDetail(null)
      return
    }
    setSelectedProposalId(null)
    setDetail(null)
    fetch(`${API_ROOT}/api/runs/${activeRunId}/inputs`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setInputSummary(data))
      .catch(() => setInputSummary(null))

    loadSummaries(activeRunId).catch(() => {
      setRunSummary(null)
      setReviewerSummary(null)
    })
  }, [activeRunId])

  useEffect(() => {
    if (!activeRunId) return
    const active = runs.find((run) => run.run_id === activeRunId)
    if (!active || !['completed', 'completed_with_warnings'].includes(active.status)) {
      setQueue([])
      return
    }
    loadQueue(activeRunId).catch(() => setQueue([]))
  }, [activeRunId, filters, runs])

  useEffect(() => {
    if (!activeRunId || !selectedProposalId) {
      setDetail(null)
      return
    }
    fetch(`${API_ROOT}/api/runs/${activeRunId}/proposals/${selectedProposalId}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        setDetail(data)
        setEditedValue(data?.proposal?.proposed_value ?? '')
      })
      .catch(() => setDetail(null))
  }, [activeRunId, selectedProposalId])

  const activeRun = useMemo(() => runs.find((r) => r.run_id === activeRunId) ?? null, [runs, activeRunId])

  async function startRun() {
    setMessage('Creating run...')
    const res = await fetch(`${API_ROOT}/api/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config_path: configPath }),
    })
    if (!res.ok) {
      setMessage('Failed to create run.')
      return
    }
    const data = await res.json()
    setActiveRunId(data.run_id)
    setMessage(`Run ${data.run_id} created. Waiting for validation and processing.`)
    await loadRuns()
  }

  async function recordDecision(decision: 'accept' | 'accept_edited' | 'reject') {
    if (!activeRunId || !selectedProposalId) return
    await fetch(`${API_ROOT}/api/runs/${activeRunId}/review/decisions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        proposal_id: selectedProposalId,
        decision,
        edited_value: decision === 'accept_edited' ? editedValue : undefined,
      }),
    })
    await loadQueue(activeRunId)
    await loadSummaries(activeRunId)
  }

  async function bulkAcceptVisible() {
    if (!activeRunId) return
    if (!window.confirm(`Bulk accept visible undecided proposals (${counters.undecided_visible ?? 0})?`)) return
    await fetch(`${API_ROOT}/api/runs/${activeRunId}/review/decisions/bulk-accept-visible`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        review_decision: filters.review_decision || undefined,
        evidence_status: filters.evidence_status || undefined,
        match_status: filters.match_status || undefined,
        figure_derived: figureFilterValue(filters.figure_derived),
      }),
    })
    await loadQueue(activeRunId)
    await loadSummaries(activeRunId)
  }

  function navigate(delta: number) {
    const idx = queue.findIndex((item) => item.proposal_id === selectedProposalId)
    if (idx < 0) return
    const next = queue[idx + delta]
    if (next) setSelectedProposalId(next.proposal_id)
  }

  useEffect(() => {
    function onKeydown(event: KeyboardEvent) {
      if (activeView !== 'review') return
      if (event.key === 'j') navigate(1)
      if (event.key === 'k') navigate(-1)
      if (event.key === 'a') recordDecision('accept').catch(() => null)
      if (event.key === 'r') recordDecision('reject').catch(() => null)
      if (event.key === 'e') {
        const target = document.getElementById('edited-value-input')
        target?.focus()
      }
      if (event.key === 'v') {
        const target = document.getElementById('evidence-viewer')
        target?.scrollIntoView({ behavior: 'smooth' })
      }
    }
    window.addEventListener('keydown', onKeydown)
    return () => window.removeEventListener('keydown', onKeydown)
  }, [activeView, queue, selectedProposalId, editedValue])

  const selectedItem = queue.find((item) => item.proposal_id === selectedProposalId)
  const isBlocked = selectedItem ? ['blocked', 'skipped', 'error'].includes(selectedItem.proposal_state) : true
  const hasProposalValue = Boolean(detail?.proposal?.proposed_value)

  return (
    <main style={{ fontFamily: 'sans-serif', margin: 16 }}>
      <h1>Paper Table Agent</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={() => setActiveView('run')}>Run</button>
        <button onClick={() => setActiveView('review')}>Review</button>
      </div>

      <section style={{ marginBottom: 12 }}>
        <h3>Runs</h3>
        <ul>
          {runs.map((run) => (
            <li key={run.run_id}>
              <button onClick={() => setActiveRunId(run.run_id)}>{run.run_id}</button> — {run.operator_state}
            </li>
          ))}
        </ul>
      </section>

      {activeView === 'run' ? (
        <section>
          <h2>Run Launch and Setup</h2>
          <label>
            Config path:{' '}
            <input style={{ minWidth: 420 }} value={configPath} onChange={(e) => setConfigPath(e.target.value)} />
          </label>{' '}
          <button onClick={() => startRun().catch(() => setMessage('Run creation failed.'))}>Start run</button>
          <p>{message}</p>

          {activeRun ? (
            <div>
              <h3>Lifecycle status</h3>
              <p>
                <strong>{activeRun.operator_state}</strong> ({activeRun.status})
              </p>
              <p>
                Stage: {activeRun.current_stage ?? 'n/a'}
                {activeRun.current_item ? ` — ${activeRun.current_item}` : ''}
              </p>
              {activeRun.error ? <p style={{ color: 'crimson' }}>Failure reason: {activeRun.error}</p> : null}
            </div>
          ) : (
            <p>No run yet. Start a run to begin validation and processing.</p>
          )}

          {inputSummary ? (
            <div>
              <h3>Resolved input summary</h3>
              <pre>{JSON.stringify(inputSummary, null, 2)}</pre>
            </div>
          ) : (
            <p>Input summary appears after validation completes.</p>
          )}
        </section>
      ) : (
        <section>
          <h2>Review Workspace</h2>
          {activeRun ? (
            activeRun.status === 'completed' || activeRun.status === 'completed_with_warnings' ? (
              <div>
                <p>
                  Status: <strong>{activeRun.operator_state}</strong>
                </p>
                {runWarnings.length > 0 ? <p>Warnings: {runWarnings.join(', ')}</p> : null}

                <div style={{ border: '1px solid #ddd', padding: 8, marginBottom: 8 }}>
                  <h3>Run Summary</h3>
                  <pre>{JSON.stringify(runSummary, null, 2)}</pre>
                  <h4>Reviewer Summary</h4>
                  <pre>{JSON.stringify(reviewerSummary, null, 2)}</pre>
                  <p>
                    Downloads:{' '}
                    <a href={`${API_ROOT}/api/runs/${activeRun.run_id}/downloads/run-summary`} target="_blank" rel="noreferrer">
                      run summary
                    </a>{' '}
                    ·{' '}
                    <a href={`${API_ROOT}/api/runs/${activeRun.run_id}/downloads/reviewer-summary`} target="_blank" rel="noreferrer">
                      reviewer summary
                    </a>{' '}
                    ·{' '}
                    <a href={`${API_ROOT}/api/runs/${activeRun.run_id}/downloads/artifacts`} target="_blank" rel="noreferrer">
                      artifacts zip
                    </a>
                  </p>
                  <pre>{JSON.stringify(downloadManifest, null, 2)}</pre>
                </div>

                <div style={{ display: 'flex', gap: 12, marginBottom: 8 }}>
                  <label>
                    Decision:
                    <select
                      value={filters.review_decision}
                      onChange={(e) => setFilters((prev) => ({ ...prev, review_decision: e.target.value }))}
                    >
                      <option value="">All</option>
                      <option value="undecided">Undecided</option>
                      <option value="accept">Accepted</option>
                      <option value="accept_edited">Accepted with edit</option>
                      <option value="reject">Rejected</option>
                    </select>
                  </label>
                  <label>
                    Evidence:
                    <select
                      value={filters.evidence_status}
                      onChange={(e) => setFilters((prev) => ({ ...prev, evidence_status: e.target.value }))}
                    >
                      <option value="">All</option>
                      <option value="strong">Strong</option>
                      <option value="weak">Weak</option>
                    </select>
                  </label>
                  <label>
                    Match:
                    <select
                      value={filters.match_status}
                      onChange={(e) => setFilters((prev) => ({ ...prev, match_status: e.target.value }))}
                    >
                      <option value="">All</option>
                      <option value="matched">Matched</option>
                      <option value="ambiguous">Ambiguous</option>
                      <option value="unmatched">Unmatched</option>
                      <option value="duplicate_row_conflict">Duplicate-row conflict</option>
                    </select>
                  </label>
                  <label>
                    Figure-derived:
                    <select
                      value={filters.figure_derived}
                      onChange={(e) => setFilters((prev) => ({ ...prev, figure_derived: e.target.value }))}
                    >
                      <option value="">All</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  </label>
                  <button onClick={() => bulkAcceptVisible().catch(() => null)}>Bulk accept visible subset</button>
                </div>
                <p>
                  Counters — total: {counters.total ?? 0}, visible: {counters.visible ?? 0}, reviewed: {counters.reviewed ?? 0}, pending:{' '}
                  {counters.pending ?? 0}
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: '28% 32% 40%', gap: 12 }}>
                  <section style={{ border: '1px solid #ddd', padding: 8, minHeight: 360 }}>
                    <h3>Proposal Queue</h3>
                    <ul style={{ maxHeight: 320, overflowY: 'auto', paddingLeft: 18 }}>
                      {queue.map((item) => (
                        <li key={item.proposal_id}>
                          <button onClick={() => setSelectedProposalId(item.proposal_id)}>
                            {item.row_id} / {item.column_name} [{item.review_decision}] [{item.proposal_state}]
                          </button>
                        </li>
                      ))}
                    </ul>
                    <h4>Unresolved match inspection</h4>
                    <pre>{JSON.stringify(matchingIssues, null, 2)}</pre>
                  </section>

                  <section style={{ border: '1px solid #ddd', padding: 8, minHeight: 360 }}>
                    <h3>Proposal Detail</h3>
                    {detail ? (
                      <div>
                        <p>
                          <strong>{detail.proposal.row_id}</strong> — {detail.proposal.column_name}
                        </p>
                        <p>Support: {detail.support_label}</p>
                        <p>Current value (verify mode): {String(detail.row_context.current_cell_value ?? '')}</p>
                        <p>Proposed value: {detail.proposal.proposed_value ?? '(none)'}</p>
                        <p>Rationale: {detail.rationale ?? '(none)'}</p>
                        <p>Calculation: {detail.calculation ?? '(none)'}</p>
                        <p>Warnings: {(detail.warning_status_flags ?? []).join(', ') || '(none)'}</p>
                        <p>Column definition: {String(detail.column_definition.description ?? detail.column_definition.column_name ?? '')}</p>
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <button disabled={isBlocked || !hasProposalValue} onClick={() => recordDecision('accept').catch(() => null)}>
                            Accept
                          </button>
                          <input
                            id="edited-value-input"
                            value={editedValue}
                            onChange={(e) => setEditedValue(e.target.value)}
                            style={{ minWidth: 220 }}
                          />
                          <button disabled={isBlocked || !editedValue} onClick={() => recordDecision('accept_edited').catch(() => null)}>
                            Save edited value
                          </button>
                          <button onClick={() => recordDecision('reject').catch(() => null)}>Reject</button>
                          <button onClick={() => navigate(-1)}>Previous</button>
                          <button onClick={() => navigate(1)}>Next</button>
                        </div>
                      </div>
                    ) : (
                      <p>Select a proposal to inspect details.</p>
                    )}
                  </section>

                  <section id="evidence-viewer" style={{ border: '1px solid #ddd', padding: 8, minHeight: 360 }}>
                    <h3>Evidence Viewer</h3>
                    {detail?.primary_evidence ? (
                      <div>
                        <p>
                          Evidence source: {detail.primary_evidence.source_type ?? 'unknown'} | Page: {detail.primary_evidence.page ?? 'n/a'}
                        </p>
                        {detail.primary_evidence.quote_text ? <blockquote>{detail.primary_evidence.quote_text}</blockquote> : null}
                        {detail.primary_evidence.highlight ? (
                          <pre>Highlight anchor: {JSON.stringify(detail.primary_evidence.highlight, null, 2)}</pre>
                        ) : (
                          <p>Highlight unavailable. Showing quote + page fallback.</p>
                        )}
                        {selectedItem?.pdf_id && detail.primary_evidence.page ? (
                          <img
                            src={`${API_ROOT}/api/runs/${activeRun.run_id}/review/assets/page/${selectedItem.pdf_id}/${detail.primary_evidence.page}`}
                            alt="Evidence page"
                            style={{ maxWidth: '100%' }}
                          />
                        ) : null}
                        {detail.primary_evidence.crop_path ? (
                          <div>
                            <p>Figure crop</p>
                            <img
                              src={`${API_ROOT}/api/runs/${activeRun.run_id}/review/assets/figure?path=${encodeURIComponent(detail.primary_evidence.crop_path)}`}
                              alt="Figure crop"
                              style={{ maxWidth: '100%' }}
                            />
                          </div>
                        ) : null}
                        {detail.primary_evidence.caption_text ? <p>Caption: {detail.primary_evidence.caption_text}</p> : null}
                        {detail.primary_evidence.full_page_path ? (
                          <a
                            href={`${API_ROOT}/api/runs/${activeRun.run_id}/review/assets/figure?path=${encodeURIComponent(detail.primary_evidence.full_page_path)}`}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open full-page evidence image
                          </a>
                        ) : null}
                      </div>
                    ) : (
                      <p>No primary evidence attached.</p>
                    )}
                  </section>
                </div>
              </div>
            ) : (
              <p>
                Review unavailable. Current state: {activeRun.operator_state}. Stage: {activeRun.current_stage ?? 'n/a'}
                {activeRun.current_item ? ` (${activeRun.current_item})` : ''}.
              </p>
            )
          ) : (
            <p>No run selected. Switch to Run view and create a run.</p>
          )}
        </section>
      )}
    </main>
  )
}
