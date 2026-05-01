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

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,#e0f2fe_0%,#f8fafc_32%,#e2e8f0_100%)] text-slate-900">
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur-xl shadow-[0_10px_35px_rgba(15,23,42,0.06)]">
        <div className="mx-auto flex max-w-screen-2xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div className="flex min-w-0 items-center gap-4">
            <img src="/logo_1.svg" alt="papers-to-table" className="h-12 w-12 shrink-0 rounded-xl object-contain" />
            <div className="min-w-0">
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">papers-to-table</h1>
              <p className="mt-1 text-sm font-medium text-slate-500">Evidence-backed literature extraction and review</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {activeRuns.length > 0 && (
              <div className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-800 shadow-sm">
                {activeRuns.length} active run{activeRuns.length !== 1 ? 's' : ''}
              </div>
            )}
            <nav className="flex rounded-full border border-slate-200 bg-white p-1 shadow-sm">
              <button
                onClick={() => setView('run')}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${view === 'run' ? 'bg-slate-950 text-white shadow-sm' : 'text-slate-600 hover:bg-slate-100'}`}
              >
                Run
              </button>
              <button
                onClick={() => setView('review')}
                disabled={!isReviewable}
                title={!isReviewable ? 'Select a completed run to enable review' : undefined}
                className={`rounded-full px-4 py-2 text-sm font-medium transition ${
                  view === 'review' && isReviewable
                    ? 'bg-slate-950 text-white shadow-sm'
                    : !isReviewable
                    ? 'cursor-not-allowed text-slate-300'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                Review
              </button>
            </nav>
          </div>
        </div>
      </header>

      <main className={view === 'review' && isReviewable ? '' : 'mx-auto max-w-screen-2xl px-5 py-6'}>
        {view === 'run' && (
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-[420px_minmax(0,1fr)]">
            <section className="space-y-6">
              <div className="rounded-[32px] border border-white/70 bg-white/85 p-5 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
                <h2 className="text-base font-semibold text-slate-900">Create run</h2>
                <div className="mt-5">
                  <RunLaunchSurface onRunCreated={handleRunCreated} />
                </div>
              </div>

              <div className="rounded-[32px] border border-white/70 bg-white/85 shadow-[0_20px_60px_rgba(15,23,42,0.08)] backdrop-blur">
                <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                  <div>
                    <h2 className="text-base font-semibold text-slate-900">Runs</h2>
                    <p className="mt-1 text-xs text-slate-500">Newest runs stay at the top and update live while they execute.</p>
                  </div>
                  <button onClick={() => void loadRuns()} className="text-xs font-semibold text-sky-700 hover:underline">
                    Refresh
                  </button>
                </div>
                {loadingRuns ? (
                  <div className="px-5 py-10 text-center text-sm text-slate-400">Loading runs…</div>
                ) : loadError ? (
                  <div className="px-5 py-5">
                    <div className="text-sm text-rose-600">
                      <strong>Cannot load runs:</strong> {loadError}
                    </div>
                    <p className="mt-2 text-xs text-slate-500">Start the backend with <code className="rounded bg-slate-100 px-1 py-0.5">bash scripts/run-main-backend.sh</code>.</p>
                  </div>
                ) : (
                  <RunList runs={runs} selectedRunId={selectedRun?.run_id ?? null} onSelect={setSelectedRun} />
                )}
              </div>
            </section>

            <section className="rounded-[36px] border border-white/70 bg-white/88 p-6 shadow-[0_26px_70px_rgba(15,23,42,0.09)] backdrop-blur">
              {selectedRun ? (
                <RunDetail run={selectedRun} onAbort={handleAbortRun} aborting={abortingRunId === selectedRun.run_id} />
              ) : (
                <div className="flex min-h-[420px] flex-col items-center justify-center text-center">
                  <h2 className="text-2xl font-semibold tracking-tight text-slate-900">No run selected yet</h2>
                  <p className="mt-3 max-w-md text-sm leading-6 text-slate-500">
                    Launch a new run or select an existing run summary on the left.
                  </p>
                </div>
              )}
            </section>
          </div>
        )}

        {view === 'review' && (
          <>
            {isReviewable && selectedRun ? (
              <ReviewWorkspace run={selectedRun} outputDir={selectedRun.output_dir} />
            ) : (
              <div className="rounded-[28px] border border-slate-200 bg-white p-10 text-center shadow-sm">
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
