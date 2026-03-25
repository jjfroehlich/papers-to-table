import { useEffect, useMemo, useState } from 'react'

type RunRecord = {
  run_id: string
  status: string
  operator_state: string
  error?: string
}

export function App() {
  const [activeView, setActiveView] = useState<'run' | 'review'>('run')
  const [configPath, setConfigPath] = useState('config.example.json')
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [inputSummary, setInputSummary] = useState<Record<string, unknown> | null>(null)
  const [message, setMessage] = useState('Enter a config path and start a run.')

  async function loadRuns() {
    const res = await fetch('http://localhost:8000/api/runs')
    const data = await res.json()
    setRuns(data)
    if (!activeRunId && data.length > 0) {
      setActiveRunId(data[0].run_id)
    }
  }

  useEffect(() => {
    loadRuns().catch(() => setMessage('Backend unavailable. Start backend first.'))
    const timer = setInterval(() => loadRuns().catch(() => null), 2000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!activeRunId) {
      setInputSummary(null)
      return
    }
    fetch(`http://localhost:8000/api/runs/${activeRunId}/inputs`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setInputSummary(data))
      .catch(() => setInputSummary(null))
  }, [activeRunId, runs])

  const activeRun = useMemo(() => runs.find((r) => r.run_id === activeRunId) ?? null, [runs, activeRunId])

  async function startRun() {
    setMessage('Creating run...')
    const res = await fetch('http://localhost:8000/api/runs', {
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

  return (
    <main style={{ fontFamily: 'sans-serif', margin: 24 }}>
      <h1>Paper Table Agent</h1>
      <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
        <button onClick={() => setActiveView('run')}>Run</button>
        <button onClick={() => setActiveView('review')}>Review</button>
      </div>

      {activeView === 'run' ? (
        <section>
          <h2>Run Launch and Setup</h2>
          <label>
            Config path:{' '}
            <input style={{ minWidth: 400 }} value={configPath} onChange={(e) => setConfigPath(e.target.value)} />
          </label>{' '}
          <button onClick={() => startRun().catch(() => setMessage('Run creation failed.'))}>Start run</button>
          <p>{message}</p>

          {activeRun ? (
            <div>
              <h3>Lifecycle status</h3>
              <p>
                <strong>{activeRun.operator_state}</strong> ({activeRun.status})
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
          <h2>Review</h2>
          {activeRun ? (
            activeRun.status === 'completed' || activeRun.status === 'completed_with_warnings' ? (
              <p>Run is reviewable. Proposal queue arrives in Batch 5.</p>
            ) : (
              <p>Review unavailable. Current state: {activeRun.operator_state}. Wait for terminal state.</p>
            )
          ) : (
            <p>No run selected. Switch to Run view and create a run.</p>
          )}
        </section>
      )}

      <section>
        <h3>Runs</h3>
        <ul>
          {runs.map((run) => (
            <li key={run.run_id}>
              <button onClick={() => setActiveRunId(run.run_id)}>{run.run_id}</button> — {run.operator_state}
            </li>
          ))}
        </ul>
      </section>
    </main>
  )
}
