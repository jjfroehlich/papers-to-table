import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'

interface Props {
  activeDirectory: string
  onActivate: (path: string) => void
  onReset: () => void
}

export function RunsDirectorySelector({ activeDirectory, onActivate, onReset }: Props) {
  const [draftDirectory, setDraftDirectory] = useState(activeDirectory)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const browseButtonRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    setDraftDirectory(activeDirectory)
  }, [activeDirectory])

  async function activate(path: string) {
    const trimmedPath = path.trim()
    if (!trimmedPath) {
      setError('A runs directory path is required.')
      return
    }
    if (trimmedPath === activeDirectory) {
      setError(null)
      return
    }
    setBusy(true)
    setError(null)
    try {
      const response = await api.resolveRunsDirectory(trimmedPath, false)
      if (response.status === 'selected' && response.path) {
        onActivate(response.path)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  async function browse() {
    setBusy(true)
    setError(null)
    try {
      const response = await api.resolveRunsDirectory(draftDirectory, true)
      if (response.status === 'selected' && response.path) {
        setDraftDirectory(response.path)
        onActivate(response.path)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="border-b border-slate-100 px-4 py-3" data-testid="runs-directory-selector">
      <div className="mb-1 flex items-center justify-between gap-3">
        <label htmlFor="runs-directory" className="block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">
          Runs directory
        </label>
        <button
          type="button"
          onClick={() => {
            setError(null)
            onReset()
          }}
          disabled={busy || activeDirectory === './runs'}
          className="shrink-0 text-xs font-semibold text-sky-700 hover:underline disabled:cursor-not-allowed disabled:text-slate-300 disabled:no-underline"
        >
          Reset to default
        </button>
      </div>
      <div className="flex gap-2">
        <input
          id="runs-directory"
          type="text"
          value={draftDirectory}
          onChange={(event) => setDraftDirectory(event.target.value)}
          onBlur={(event) => {
            if (event.relatedTarget === browseButtonRef.current) return
            void activate(draftDirectory)
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              void activate(draftDirectory)
            }
          }}
          aria-invalid={error ? 'true' : undefined}
          className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
        />
        <button
          ref={browseButtonRef}
          type="button"
          onClick={() => void browse()}
          disabled={busy}
          className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Browse...
        </button>
      </div>
      {error && <p className="mt-1 text-xs text-rose-600">{error}</p>}
    </div>
  )
}
