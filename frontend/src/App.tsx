import { useCallback, useEffect, useMemo, useState } from 'react'
import { createRun, getInputSummary, getRunSummary, listRuns } from './api'
import { ReviewWorkspace } from './components/ReviewWorkspace'
import type { InputSummary, RunRecord, RunSummary } from './types'
import './App.css'

type Tab = 'run' | 'review'

const TERMINAL = new Set(['completed', 'completed_with_warnings', 'failed', 'interrupted'])

function guidanceMessage(summary: RunSummary | null, runs: RunRecord[]): string {
  if (runs.length === 0) {
    return 'No runs yet. Enter a config path and create a run to start the workflow.'
  }
  if (!summary) {
    return 'Select a run to view setup context and lifecycle status.'
  }
  if (summary.operator_status === 'validating') {
    return 'Run is validating paths and inputs. Wait for validation to complete.'
  }
  if (summary.operator_status === 'running') {
    const stage = summary.progress.stage
    const item = summary.progress.item
    const detail = stage ? ` — stage: ${stage}${item ? ` (${item})` : ''}` : ''
    return `Run is processing${detail}. Review stays locked until the run reaches a terminal state.`
  }
  if (summary.status === 'failed') {
    return 'Run failed. Inspect the failure message and config/input summary before retrying.'
  }
  if (summary.status === 'completed_with_warnings') {
    return 'Run finished with warnings. Switch to the Review tab to inspect proposals and unresolved matches.'
  }
  if (summary.status === 'completed') {
    return 'Run is complete. Switch to the Review tab to review proposals and export accepted changes.'
  }
  return 'Run is ready.'
}

function App() {
  const [tab, setTab] = useState<Tab>('run')
  const [configPath, setConfigPath] = useState('')
  const [runs, setRuns] = useState<RunRecord[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const [summary, setSummary] = useState<RunSummary | null>(null)
  const [inputSummary, setInputSummary] = useState<InputSummary | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshRuns = useCallback(async () => {
    const records = await listRuns()
    setRuns(records)
    if (!selectedRunId && records.length > 0) {
      setSelectedRunId(records[0].run_id)
    }
  }, [selectedRunId])

  const refreshSelected = useCallback(async (runId: string) => {
    const [runSummary, runInputSummary] = await Promise.all([
      getRunSummary(runId),
      getInputSummary(runId).catch(() => null),
    ])
    setSummary(runSummary)
    setInputSummary(runInputSummary)
  }, [])

  useEffect(() => {
    refreshRuns().catch((err: unknown) => setError(err instanceof Error ? err.message : 'Failed to load runs'))
    const id = window.setInterval(() => {
      refreshRuns().catch(() => undefined)
      if (selectedRunId) {
        refreshSelected(selectedRunId).catch(() => undefined)
      }
    }, 1500)
    return () => window.clearInterval(id)
  }, [refreshRuns, refreshSelected, selectedRunId])

  useEffect(() => {
    if (!selectedRunId) {
      setSummary(null)
      setInputSummary(null)
      return
    }
    refreshSelected(selectedRunId).catch((err: unknown) => {
      setError(err instanceof Error ? err.message : 'Failed to load selected run')
    })
  }, [refreshSelected, selectedRunId])

  const guidance = useMemo(() => guidanceMessage(summary, runs), [summary, runs])

  async function handleCreateRun(event: React.FormEvent) {
    event.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const created = await createRun(configPath)
      setSelectedRunId(created.run_id)
      await refreshRuns()
      await refreshSelected(created.run_id)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Run creation failed')
    } finally {
      setLoading(false)
    }
  }

  const showProgress = summary?.operator_status === 'running' || summary?.operator_status === 'validating'
  const isTerminal = summary ? TERMINAL.has(summary.status) : false
  const isReviewable = isTerminal && summary?.status !== 'failed'

  return (
    <div className="app-shell">
      <header className="header">
        <h1>Paper Table Agent</h1>
        <p className="header-sub">Local-first paper-to-table review system.</p>
      </header>

      <nav className="tabs" aria-label="Primary views">
        <button className={tab === 'run' ? 'active' : ''} onClick={() => setTab('run')}>Run</button>
        <button
          className={tab === 'review' ? 'active' : ''}
          onClick={() => setTab('review')}
        >
          Review{isReviewable ? ' ●' : ''}
        </button>
      </nav>

      {error ? <div className="error">{error}</div> : null}

      {tab === 'run' ? (
        <main className="panel-grid">
          <section className="panel">
            <h2>Start run from config file</h2>
            <form onSubmit={handleCreateRun}>
              <label htmlFor="config-path">Config path</label>
              <input
                id="config-path"
                value={configPath}
                placeholder="/absolute/path/to/config.json"
                onChange={(event) => setConfigPath(event.target.value)}
                required
              />
              <button disabled={loading || configPath.trim().length === 0} type="submit">
                {loading ? 'Creating run…' : 'Create run'}
              </button>
            </form>
            <p className="hint">
              Advanced settings stay in the JSON config file; this UI keeps launch concise.
            </p>
          </section>

          <section className="panel">
            <h2>Runs</h2>
            {runs.length === 0 ? <p>No runs yet.</p> : null}
            <ul>
              {runs.map((run) => (
                <li key={run.run_id}>
                  <button
                    className={selectedRunId === run.run_id ? 'active-row' : ''}
                    onClick={() => setSelectedRunId(run.run_id)}
                  >
                    <span className="run-id-short">{run.run_id.slice(0, 20)}…</span>
                    <span className={`run-status-badge status-${run.status}`}>{run.operator_status}</span>
                  </button>
                </li>
              ))}
            </ul>
          </section>

          <section className="panel full-width">
            <h2>Run setup and lifecycle</h2>
            <p>{guidance}</p>

            {summary ? (
              <dl className="summary-grid">
                <dt>Run ID</dt>
                <dd className="mono">{summary.run_id}</dd>
                <dt>Status</dt>
                <dd>
                  <span className={`run-status-badge status-${summary.status}`}>{summary.operator_status}</span>
                </dd>
                {summary.message ? (<><dt>Message</dt><dd>{summary.message}</dd></>) : null}
                <dt>Config path</dt>
                <dd>{summary.config_path}</dd>
                <dt>Table path</dt>
                <dd>{summary.table_path ?? 'Not available yet'}</dd>
                <dt>Schema path</dt>
                <dd>{summary.schema_path ?? 'Not available yet'}</dd>
                <dt>PDF directory</dt>
                <dd>{summary.pdf_dir ?? 'Not available yet'}</dd>
                <dt>Output directory</dt>
                <dd>{summary.output_dir ?? 'Not available yet'}</dd>
                <dt>Verify mode</dt>
                <dd>{summary.verify_mode ? 'On' : 'Off'}</dd>
                <dt>Provider</dt>
                <dd>
                  {summary.provider_name ?? '—'}
                  {summary.model_name ? ` / ${summary.model_name}` : ''}
                  {' '}({summary.provider_locality ?? 'local'})
                </dd>
                <dt>Target columns</dt>
                <dd>{summary.target_columns.length > 0 ? summary.target_columns.join(', ') : 'Not available yet'}</dd>
              </dl>
            ) : (
              <p>Select or create a run to see setup context.</p>
            )}

            {showProgress && summary ? (
              <div className="progress">
                Current stage: {summary.progress.stage ?? 'unknown'}
                {summary.progress.item ? ` (${summary.progress.item})` : ''}
              </div>
            ) : null}

            {isTerminal && inputSummary ? (
              <div className="input-summary">
                <h3>Input summary</h3>
                <p>Rows: {inputSummary.row_count}</p>
                <p>Eligible missing cells: {inputSummary.eligible_missing_cells}</p>
                <p>Eligible filled cells (Verify mode): {inputSummary.eligible_filled_cells}</p>
                <p>Ineligible cells: {inputSummary.ineligible_cells}</p>
              </div>
            ) : null}

            {isReviewable && (
              <div className="run-action-hint">
                <button onClick={() => setTab('review')}>Go to Review →</button>
              </div>
            )}
          </section>
        </main>
      ) : (
        <main className="review-tab-main">
          {selectedRunId && summary ? (
            <ReviewWorkspace runId={selectedRunId} runSummary={summary} />
          ) : (
            <div className="panel full-width">
              <h2>Review</h2>
              <p>Select or create a run in the Run tab to start reviewing.</p>
            </div>
          )}
        </main>
      )}
    </div>
  )
}

export default App
