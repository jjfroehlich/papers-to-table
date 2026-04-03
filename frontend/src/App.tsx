import { useState, useEffect, useCallback } from 'react'
import { RunLaunchSurface } from './components/RunLaunchSurface'
import { RunList } from './components/RunList'
import { RunDetail } from './components/RunDetail'
import { ReviewWorkspace } from './components/ReviewWorkspace'
import { api } from './api/client'
import type { RunData } from './types'

type View = 'run' | 'review'

export function App() {
  const [view, setView] = useState<View>('run')
  const [runs, setRuns] = useState<RunData[]>([])
  const [selectedRun, setSelectedRun] = useState<RunData | null>(null)
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [abortingRunId, setAbortingRunId] = useState<string | null>(null)
  const [lastSuccessfulRefreshAt, setLastSuccessfulRefreshAt] = useState<string | null>(null)

  const loadRuns = useCallback(async () => {
    try {
      const resp = await api.listRuns()
      setRuns(resp.runs)
      setLoadError(null)
      setLastSuccessfulRefreshAt(new Date().toISOString())
      if (selectedRun) {
        const updated = resp.runs.find((r) => r.run_id === selectedRun.run_id)
        if (updated) setSelectedRun(updated)
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingRuns(false)
    }
  }, [selectedRun])

  useEffect(() => {
    loadRuns()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const hasActiveRun = runs.some((r) =>
      r.status === 'created' || r.status === 'validating' || r.status === 'running'
    )
    if (!hasActiveRun) return
    const timeoutId = window.setTimeout(() => {
      void loadRuns()
    }, 2000)
    return () => window.clearTimeout(timeoutId)
  }, [runs, loadRuns])

  const hasActiveRun = runs.some((run) =>
    run.status === 'created' || run.status === 'validating' || run.status === 'running'
  )
  const activeRunRefreshStale = hasActiveRun && !!loadError

  function handleRunCreated(run: RunData) {
    setRuns((prev) => [run, ...prev.filter((r) => r.run_id !== run.run_id)])
    setSelectedRun(run)
  }

  const handleAbortRun = useCallback(async (run: RunData) => {
    setAbortingRunId(run.run_id)
    try {
      await api.abortRun(run.run_id, run.output_dir)
      await loadRuns()
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    } finally {
      setAbortingRunId(null)
    }
  }, [loadRuns])

  const isReviewable = selectedRun?.status === 'completed' || selectedRun?.status === 'completed_with_warnings'

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-950 text-slate-50 shadow-lg">
        <div className="max-w-screen-xl mx-auto px-4 py-4 flex items-center justify-between gap-6">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">Paper Table Agent</h1>
            <p className="mt-1 text-xs text-slate-300">
              Evidence-first scientific review workstation for paper-backed table curation.
            </p>
          </div>
          <nav className="flex gap-2">
            <button
              onClick={() => setView('run')}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                view === 'run'
                  ? 'bg-blue-500 text-white shadow-sm'
                  : 'text-slate-300 hover:bg-slate-800'
              }`}
            >
              Run
            </button>
            <button
              onClick={() => setView('review')}
              disabled={!isReviewable}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                view === 'review' && isReviewable
                  ? 'bg-blue-500 text-white shadow-sm'
                  : !isReviewable
                  ? 'text-slate-600 cursor-not-allowed'
                  : 'text-slate-300 hover:bg-slate-800'
              }`}
              title={!isReviewable ? 'Select a completed run to enable review' : undefined}
            >
              Review
            </button>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className={view === 'review' && isReviewable ? '' : 'max-w-screen-xl mx-auto px-4 py-6'}>
        {activeRunRefreshStale && (
          <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 shadow-sm">
            Live status refresh failed. Active run status may be stale until the backend connection recovers.
            {lastSuccessfulRefreshAt && (
              <span className="ml-1 text-amber-800">
                Last successful refresh: {new Date(lastSuccessfulRefreshAt).toLocaleTimeString()}.
              </span>
            )}
            <button
              onClick={() => void loadRuns()}
              className="ml-3 text-xs font-semibold text-amber-900 underline"
            >
              Refresh now
            </button>
          </div>
        )}

        {view === 'run' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left: Launch + run list */}
              <div className="lg:col-span-1 space-y-6">
                {/* Launch surface */}
                <div className="rounded-2xl border border-slate-200 bg-white/95 shadow-sm p-5">
                  <h2 className="text-base font-semibold text-slate-900 mb-1">Create Run</h2>
                  <p className="mb-4 text-xs text-slate-500">
                    Launch one evidence-backed curation run from a config file, then review only explicit proposals.
                  </p>
                  <RunLaunchSurface onRunCreated={handleRunCreated} />
                </div>

                {/* Run list */}
                <div className="rounded-2xl border border-slate-200 bg-white/95 shadow-sm">
                  <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
                    <h2 className="text-base font-semibold text-slate-900">
                      Runs {runs.length > 0 && <span className="text-slate-400 text-sm">({runs.length})</span>}
                    </h2>
                    <button
                      onClick={loadRuns}
                      className="text-xs font-medium text-blue-700 hover:underline"
                    >
                      Refresh
                    </button>
                </div>
                {loadingRuns ? (
                  <div className="px-5 py-8 text-sm text-gray-400 text-center">Loading runs…</div>
                ) : loadError ? (
                  <div className="px-5 py-4">
                    <div className="text-sm text-red-600">
                      <strong>Cannot load runs:</strong> {loadError}
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      Make sure the backend is running: <code className="bg-gray-100 px-1 rounded">uvicorn backend.app.main:app --reload</code>
                    </p>
                  </div>
                ) : (
                  <RunList
                    runs={runs}
                    selectedRunId={selectedRun?.run_id ?? null}
                    onSelect={setSelectedRun}
                  />
                )}
              </div>
            </div>

            {/* Right: Run detail / next-action guidance */}
            <div className="lg:col-span-2">
              <div className="rounded-2xl border border-slate-200 bg-white/95 shadow-sm p-5 min-h-64">
                {selectedRun ? (
                  <RunDetail
                    run={selectedRun}
                    onAbort={handleAbortRun}
                    aborting={abortingRunId === selectedRun.run_id}
                  />
                ) : (
                    <div className="flex flex-col items-center justify-center h-48 text-center">
                      <div className="text-slate-400 text-4xl mb-3">📋</div>
                      <h3 className="text-base font-medium text-slate-700">No run selected</h3>
                      <p className="mt-1 text-sm text-slate-500 max-w-sm">
                        Create a run using the form on the left, or select an existing run from the list to see its details.
                      </p>
                    {runs.length === 0 && (
                      <p className="mt-3 text-sm text-blue-600">
                        To start: enter the path to your <code className="bg-blue-50 px-1 rounded">config.json</code> file and click Create Run.
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {view === 'review' && (
          <>
            {isReviewable && selectedRun ? (
              <ReviewWorkspace run={selectedRun} outputDir={selectedRun.output_dir} />
            ) : (
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-8 text-center">
                <div className="text-gray-300 text-4xl mb-3">🔒</div>
                <h2 className="text-lg font-semibold text-gray-700">Review unavailable</h2>
                <p className="mt-2 text-sm text-gray-500">
                  Select a completed run from the Run tab to enable review.
                </p>
                <button
                  onClick={() => setView('run')}
                  className="mt-4 px-4 py-2 rounded-md bg-blue-600 text-white text-sm hover:bg-blue-700"
                >
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
