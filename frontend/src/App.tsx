import { useState, useEffect, useCallback } from 'react'
import { RunLaunchSurface } from './components/RunLaunchSurface'
import { RunList } from './components/RunList'
import { RunDetail } from './components/RunDetail'
import { api } from './api/client'
import type { RunData } from './types'

type View = 'run' | 'review'

export function App() {
  const [view, setView] = useState<View>('run')
  const [runs, setRuns] = useState<RunData[]>([])
  const [selectedRun, setSelectedRun] = useState<RunData | null>(null)
  const [loadingRuns, setLoadingRuns] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [pollingInterval, setPollingInterval] = useState<ReturnType<typeof setInterval> | null>(null)

  const loadRuns = useCallback(async () => {
    try {
      const resp = await api.listRuns()
      setRuns(resp.runs)
      setLoadError(null)
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

  // Poll for active runs
  useEffect(() => {
    const hasActiveRun = runs.some((r) =>
      r.status === 'created' || r.status === 'validating' || r.status === 'running'
    )
    if (hasActiveRun && !pollingInterval) {
      const id = setInterval(loadRuns, 2000)
      setPollingInterval(id)
    } else if (!hasActiveRun && pollingInterval) {
      clearInterval(pollingInterval)
      setPollingInterval(null)
    }
    return () => {
      if (pollingInterval) clearInterval(pollingInterval)
    }
  }, [runs, loadRuns]) // eslint-disable-line react-hooks/exhaustive-deps

  function handleRunCreated(run: RunData) {
    setRuns((prev) => [run, ...prev.filter((r) => r.run_id !== run.run_id)])
    setSelectedRun(run)
  }

  const isReviewable = selectedRun?.status === 'completed' || selectedRun?.status === 'completed_with_warnings'

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-screen-xl mx-auto px-4 py-3 flex items-center justify-between">
          <h1 className="text-lg font-bold text-gray-900">Paper Table Agent</h1>
          <nav className="flex gap-2">
            <button
              onClick={() => setView('run')}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                view === 'run'
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              Run
            </button>
            <button
              onClick={() => setView('review')}
              disabled={!isReviewable}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                view === 'review' && isReviewable
                  ? 'bg-blue-600 text-white'
                  : !isReviewable
                  ? 'text-gray-300 cursor-not-allowed'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
              title={!isReviewable ? 'Select a completed run to enable review' : undefined}
            >
              Review
            </button>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-screen-xl mx-auto px-4 py-6">
        {view === 'run' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Launch + run list */}
            <div className="lg:col-span-1 space-y-6">
              {/* Launch surface */}
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5">
                <h2 className="text-base font-semibold text-gray-900 mb-4">Create Run</h2>
                <RunLaunchSurface onRunCreated={handleRunCreated} />
              </div>

              {/* Run list */}
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm">
                <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                  <h2 className="text-base font-semibold text-gray-900">
                    Runs {runs.length > 0 && <span className="text-gray-400 text-sm">({runs.length})</span>}
                  </h2>
                  <button
                    onClick={loadRuns}
                    className="text-xs text-blue-600 hover:underline"
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
              <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-5 min-h-64">
                {selectedRun ? (
                  <RunDetail run={selectedRun} />
                ) : (
                  <div className="flex flex-col items-center justify-center h-48 text-center">
                    <div className="text-gray-400 text-4xl mb-3">📋</div>
                    <h3 className="text-base font-medium text-gray-700">No run selected</h3>
                    <p className="mt-1 text-sm text-gray-500 max-w-sm">
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
          <div className="bg-white rounded-lg border border-gray-200 shadow-sm p-8 text-center">
            {isReviewable ? (
              <>
                <div className="text-gray-400 text-4xl mb-3">🔍</div>
                <h2 className="text-lg font-semibold text-gray-900">Review</h2>
                <p className="mt-2 text-sm text-gray-500">
                  Proposal review workspace — available in Batch 2.
                </p>
                <p className="mt-1 text-xs text-gray-400">
                  Selected run: <code className="bg-gray-100 px-1 rounded">{selectedRun?.run_id}</code>
                </p>
              </>
            ) : (
              <>
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
              </>
            )}
          </div>
        )}
      </main>
    </div>
  )
}

export default App
