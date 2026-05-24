import { useCallback, useEffect, useMemo, useState } from 'react'
import { RunLaunchSurface } from './components/RunLaunchSurface'
import { RunList } from './components/RunList'
import { RunDetail } from './components/RunDetail'
import { ReviewWorkspace } from './components/ReviewWorkspace'
import { api } from './api/client'
import type { RunData, RunStreamEvent } from './types'

type View = 'run' | 'review'

function upsertRun(runs: RunData[], nextRun: RunData): RunData[] {
  return [nextRun, ...runs.filter((run) => run.run_id !== nextRun.run_id)].sort((a, b) =>
    (b.created_at ?? '').localeCompare(a.created_at ?? '')
  )
}

export function App() {
  const [view, setView] = useState<View>('run')
  const [runs, setRuns] = useState<RunData[]>([])
  const [selectedRun, setSelectedRun] = useState<RunData | null>(null)
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [abortingRunId, setAbortingRunId] = useState<string | null>(null)

  const syncSelectedRun = useCallback((nextRuns: RunData[]) => {
    setSelectedRun((current) => {
      if (!current) return current
      return nextRuns.find((run) => run.run_id === current.run_id) ?? current
    })
  }, [])

  const loadRuns = useCallback(async () => {
    try {
      const resp = await api.listRuns()
      setRuns(resp.runs)
      syncSelectedRun(resp.runs)
      setLoadError(null)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingRuns(false)
    }
  }, [syncSelectedRun])

  useEffect(() => {
    void loadRuns()
  }, [loadRuns])

  useEffect(() => {
    if (typeof EventSource === 'undefined') return
    const source = api.createRunEventsSource()

    const handleBootstrap = (event: MessageEvent<string>) => {
      const payload = JSON.parse(event.data) as { runs: RunData[] }
      setRuns(payload.runs)
      syncSelectedRun(payload.runs)
      setLoadingRuns(false)
      setLoadError(null)
    }

    const handleRunUpdated = (event: MessageEvent<string>) => {
      const payload = JSON.parse(event.data) as RunStreamEvent
      if (!payload.run) return
      setRuns((current) => {
        const nextRuns = upsertRun(current, payload.run as RunData)
        syncSelectedRun(nextRuns)
        return nextRuns
      })
      setLoadError(null)
    }

    const handleError = () => {
      void loadRuns()
    }

    source.addEventListener('bootstrap', handleBootstrap as EventListener)
    source.addEventListener('run.updated', handleRunUpdated as EventListener)
    source.onerror = handleError

    return () => {
      source.removeEventListener('bootstrap', handleBootstrap as EventListener)
      source.removeEventListener('run.updated', handleRunUpdated as EventListener)
      source.close()
    }
  }, [loadRuns, syncSelectedRun])

  const handleRunCreated = useCallback((run: RunData) => {
    setRuns((current) => upsertRun(current, run))
    setSelectedRun(run)
    setView('run')
  }, [])

  const handleAbortRun = useCallback(
    async (run: RunData) => {
      setAbortingRunId(run.run_id)
      try {
        await api.abortRun(run.run_id, run.output_dir)
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : String(err))
      } finally {
        setAbortingRunId(null)
      }
    },
    []
  )

  const isReviewable = selectedRun?.status === 'completed' || selectedRun?.status === 'completed_with_warnings'
  const activeRuns = useMemo(
    () => runs.filter((run) => run.status === 'created' || run.status === 'validating' || run.status === 'running'),
    [runs]
  )
  const reviewReadyRuns = useMemo(
    () => runs.filter((run) => run.status === 'completed' || run.status === 'completed_with_warnings').length,
    [runs]
  )

  useEffect(() => {
    if (activeRuns.length === 0) return
    const interval = window.setInterval(() => {
      void loadRuns()
    }, 2000)
    return () => window.clearInterval(interval)
  }, [activeRuns.length, loadRuns])

  return (
    <div className="min-h-screen bg-[#f5f6f7] text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center justify-between gap-4 px-5 py-3">
          <div className="flex min-w-0 items-center gap-3">
            <img src="/logo_1.svg" alt="papers-to-table" className="h-10 w-10 shrink-0 rounded-lg object-contain" />
            <div className="min-w-0">
              <h1 className="text-xl font-semibold tracking-tight text-slate-950">papers-to-table</h1>
              <p className="mt-0.5 text-xs font-medium text-slate-500">Evidence-backed extraction and review</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {activeRuns.length > 0 && (
              <div className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-800 shadow-sm">
                {activeRuns.length} active run{activeRuns.length !== 1 ? 's' : ''}
              </div>
            )}
            <nav className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
              <button
                onClick={() => setView('run')}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${view === 'run' ? 'bg-white text-slate-950 shadow-sm' : 'text-slate-500 hover:text-slate-800'}`}
              >
                Run
              </button>
              <button
                onClick={() => setView('review')}
                disabled={!isReviewable}
                title={!isReviewable ? 'Select a completed run to enable review' : undefined}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  view === 'review' && isReviewable
                    ? 'bg-white text-slate-950 shadow-sm'
                    : !isReviewable
                      ? 'cursor-not-allowed text-slate-300'
                      : 'text-slate-500 hover:text-slate-800'
                }`}
              >
                Review
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className={view === 'review' && isReviewable ? '' : 'mx-auto max-w-screen-2xl px-5 py-5'}>
        {view === 'run' && (
          <div className="space-y-4">
            <div className="grid gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:grid-cols-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Runs</p>
                <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-slate-950">{runs.length}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Review ready</p>
                <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-slate-950">{reviewReadyRuns}</p>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">Active</p>
                <p className="mt-1 font-mono text-2xl font-semibold tabular-nums text-slate-950">{activeRuns.length}</p>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[400px_minmax(0,1fr)]">
              <section className="space-y-4">
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                  <div className="flex items-baseline justify-between gap-3">
                    <h2 className="text-sm font-semibold text-slate-900">Create run</h2>
                    <span className="text-xs text-slate-400">Inputs</span>
                  </div>
                  <div className="mt-4">
                    <RunLaunchSurface onRunCreated={handleRunCreated} />
                  </div>
                </div>

                <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                  <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                    <div>
                      <h2 className="text-sm font-semibold text-slate-900">Runs</h2>
                      <p className="mt-0.5 text-xs text-slate-500">Newest first, live updated.</p>
                    </div>
                    <button onClick={() => void loadRuns()} className="text-xs font-semibold text-sky-700 hover:underline">
                      Refresh
                    </button>
                  </div>
                  {loadingRuns ? (
                    <div className="px-5 py-10 text-center text-sm text-slate-400">Loading runs...</div>
                  ) : loadError ? (
                    <div className="px-5 py-5">
                      <div className="text-sm text-rose-600">
                        <strong>Cannot load runs:</strong> {loadError}
                      </div>
                      <p className="mt-2 text-xs text-slate-500">
                        Start the backend with <code className="rounded bg-slate-100 px-1 py-0.5">bash scripts/run-main-backend.sh</code>.
                      </p>
                    </div>
                  ) : (
                    <RunList runs={runs} selectedRunId={selectedRun?.run_id ?? null} onSelect={setSelectedRun} />
                  )}
                </div>
              </section>

              <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                {selectedRun ? (
                  <RunDetail run={selectedRun} onAbort={handleAbortRun} aborting={abortingRunId === selectedRun.run_id} />
                ) : (
                  <div className="flex min-h-[420px] flex-col items-center justify-center text-center">
                    <h2 className="text-xl font-semibold tracking-tight text-slate-900">No run selected yet</h2>
                    <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">
                      Launch a new run or select an existing run summary on the left.
                    </p>
                  </div>
                )}
              </section>
            </div>
          </div>
        )}

        {view === 'review' && (
          <>
            {isReviewable && selectedRun ? (
              <ReviewWorkspace run={selectedRun} outputDir={selectedRun.output_dir} />
            ) : (
              <div className="rounded-xl border border-slate-200 bg-white p-10 text-center shadow-sm">
                <div className="mx-auto inline-flex rounded-full bg-slate-100 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Review locked</div>
                <h2 className="mt-4 text-xl font-semibold text-slate-800">Select a completed run to enter review</h2>
                <p className="mt-2 text-sm text-slate-500">The review workspace stays gated until a run has completed and persisted reviewable proposals.</p>
                <button onClick={() => setView('run')} className="mt-5 rounded-full bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-700">
                  Go to Run tab
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}

export default App
