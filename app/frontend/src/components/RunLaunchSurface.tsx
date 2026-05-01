import { useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { CreateRunRequest, RunData, RunPreflight } from '../types'

interface Props {
  onRunCreated: (run: RunData) => void
}

function StatusPill({ label, tone }: { label: string; tone: 'neutral' | 'success' | 'warning' | 'danger' }) {
  const className = {
    neutral: 'bg-slate-100 text-slate-700',
    success: 'bg-emerald-100 text-emerald-800',
    warning: 'bg-amber-100 text-amber-800',
    danger: 'bg-rose-100 text-rose-800',
  }[tone]
  return <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${className}`}>{label}</span>
}

function InputPreview({ label, value, locator }: { label: string; value: string | null; locator: string | null }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-slate-900" title={value ?? ''}>{value ?? '—'}</p>
      <p className="mt-1 truncate text-[11px] text-slate-500" title={locator ?? ''}>{locator ?? 'runtime locator unavailable'}</p>
    </div>
  )
}

export function RunLaunchSurface({ onRunCreated }: Props) {
  const [configPath, setConfigPath] = useState('')
  const [tablePath, setTablePath] = useState('')
  const [schemaPath, setSchemaPath] = useState('')
  const [pdfDir, setPdfDir] = useState('')
  const [loading, setLoading] = useState(false)
  const [preflighting, setPreflighting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showOverrides, setShowOverrides] = useState(false)
  const [tableStagedHandle, setTableStagedHandle] = useState<string | null>(null)
  const [schemaStagedHandle, setSchemaStagedHandle] = useState<string | null>(null)
  const [pdfDirStagedHandle, setPdfDirStagedHandle] = useState<string | null>(null)
  const [stagingStatus, setStagingStatus] = useState<string | null>(null)
  const [preflight, setPreflight] = useState<RunPreflight | null>(null)
  const [preflightDirty, setPreflightDirty] = useState(false)

  const configFileRef = useRef<HTMLInputElement>(null)
  const tableFileRef = useRef<HTMLInputElement>(null)
  const schemaFileRef = useRef<HTMLInputElement>(null)
  const pdfDirFileRef = useRef<HTMLInputElement>(null)

  const request = useMemo<CreateRunRequest>(() => {
    const payload: CreateRunRequest = { config_path: configPath.trim() }
    if (tableStagedHandle) payload.table_staged_handle = tableStagedHandle
    else if (tablePath.trim()) payload.table_path = tablePath.trim()
    if (schemaStagedHandle) payload.schema_staged_handle = schemaStagedHandle
    else if (schemaPath.trim()) payload.schema_path = schemaPath.trim()
    if (pdfDirStagedHandle) payload.pdf_dir_staged_handle = pdfDirStagedHandle
    else if (pdfDir.trim()) payload.pdf_dir = pdfDir.trim()
    return payload
  }, [configPath, pdfDir, pdfDirStagedHandle, schemaPath, schemaStagedHandle, tablePath, tableStagedHandle])

  function markDirty() {
    setPreflightDirty(true)
    setPreflight(null)
  }

  async function stageFiles(kind: 'table_path' | 'schema_path' | 'pdf_dir', selected: FileList | null) {
    if (!selected || selected.length === 0) return
    const files = Array.from(selected)
    setError(null)
    setStagingStatus(`Staging ${kind.replace('_path', '')} input…`)
    try {
      const response = await api.stageInputFiles(kind, files)
      if (kind === 'table_path') {
        setTableStagedHandle(response.handle)
        setTablePath(response.logical_source)
      } else if (kind === 'schema_path') {
        setSchemaStagedHandle(response.handle)
        setSchemaPath(response.logical_source)
      } else {
        setPdfDirStagedHandle(response.handle)
        setPdfDir(response.logical_source)
      }
      setStagingStatus(`Staged ${kind.replace('_path', '')}: ${response.logical_source}`)
      markDirty()
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStagingStatus(null)
    }
  }

  async function handlePreflight() {
    if (!configPath.trim()) {
      setError('Config file path is required.')
      return
    }
    setPreflighting(true)
    setError(null)
    try {
      const nextPreflight = await api.preflightRun(request)
      setPreflight(nextPreflight)
      setPreflightDirty(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setPreflight(null)
    } finally {
      setPreflighting(false)
    }
  }

  async function handleCreateRun() {
    if (!preflight || preflightDirty) {
      setError('Run preflight first so the launch context is current.')
      return
    }
    if (!preflight.readiness.ok) {
      setError('Resolve the preflight errors before starting the run.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const resp = await api.createRun(request)
      const runData = await api.getRun(resp.run_id)
      onRunCreated(runData)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const readinessTone = !preflight
    ? 'neutral'
    : preflight.readiness.ok
    ? 'success'
    : 'danger'

  return (
    <div className="space-y-5" data-testid="run-launch-surface">
      <div className="rounded-[28px] border border-slate-200 bg-[linear-gradient(135deg,#0f172a,#1e293b_55%,#334155)] p-5 text-slate-50 shadow-[0_18px_50px_rgba(15,23,42,0.18)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-lg">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-sky-200">Preflight-first launch</p>
            <h3 className="mt-2 text-xl font-semibold tracking-tight">Resolve the run before you start it.</h3>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Confirm the exact table, schema, PDFs, and provider path the backend will use, then launch once the run is ready.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusPill label={preflight ? preflight.run_mode : 'run mode pending'} tone="neutral" />
            <StatusPill label={preflight ? (preflight.readiness.ok ? 'ready to start' : 'needs fixes') : 'run preflight'} tone={readinessTone} />
          </div>
        </div>
      </div>

      <div>
        <label className="mb-1.5 block text-sm font-medium text-slate-700">
          Config file path <span className="text-rose-500">*</span>
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={configPath}
            onChange={(e) => {
              setConfigPath(e.target.value)
              markDirty()
            }}
            placeholder="e.g. config.example.json"
            className="flex-1 rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm shadow-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-200"
          />
          <input
            ref={configFileRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            onChange={(e) => {
              const selected = e.target.files?.[0]
              if (!selected) return
              setConfigPath(selected.webkitRelativePath || selected.name)
              markDirty()
            }}
          />
          <button
            type="button"
            onClick={() => configFileRef.current?.click()}
            className="shrink-0 rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            Browse...
          </button>
        </div>
        <p className="mt-1.5 text-xs text-slate-500">
          The JSON config stays authoritative for advanced settings. Preflight shows the resolved runtime context before launch.
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setShowOverrides(!showOverrides)}
          className="text-sm font-medium text-sky-700 hover:text-sky-800 hover:underline"
        >
          {showOverrides ? '▲ Hide' : '▼ Show'} optional path overrides
        </button>
        {preflightDirty && preflight && (
          <p className="text-xs font-medium text-amber-700">Inputs changed. Refresh preflight before starting the run.</p>
        )}
      </div>

      {showOverrides && (
        <div className="grid gap-3 rounded-3xl border border-slate-200 bg-slate-50/90 p-4">
          <p className="text-xs text-slate-500">
            Use overrides only for a one-run input change. Staged handles are safest when the browser cannot provide backend-readable file paths.
          </p>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Table path override</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={tablePath}
                onChange={(e) => {
                  setTablePath(e.target.value)
                  setTableStagedHandle(null)
                  markDirty()
                }}
                placeholder="e.g. path/to/table.xlsx"
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              />
              <input ref={tableFileRef} type="file" accept=".xlsx,.csv" className="hidden" onChange={(e) => void stageFiles('table_path', e.target.files)} />
              <button type="button" onClick={() => tableFileRef.current?.click()} className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                Stage...
              </button>
            </div>
            {tableStagedHandle && <p className="mt-1 text-xs text-emerald-700">staged handle: {tableStagedHandle}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Schema path override</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={schemaPath}
                onChange={(e) => {
                  setSchemaPath(e.target.value)
                  setSchemaStagedHandle(null)
                  markDirty()
                }}
                placeholder="e.g. path/to/schema.csv"
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              />
              <input ref={schemaFileRef} type="file" accept=".csv" className="hidden" onChange={(e) => void stageFiles('schema_path', e.target.files)} />
              <button type="button" onClick={() => schemaFileRef.current?.click()} className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                Stage...
              </button>
            </div>
            {schemaStagedHandle && <p className="mt-1 text-xs text-emerald-700">staged handle: {schemaStagedHandle}</p>}
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">PDF directory override</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={pdfDir}
                onChange={(e) => {
                  setPdfDir(e.target.value)
                  setPdfDirStagedHandle(null)
                  markDirty()
                }}
                placeholder="e.g. path/to/pdfs"
                className="flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
              />
              <input ref={pdfDirFileRef} type="file" accept=".pdf,application/pdf" multiple className="hidden" onChange={(e) => void stageFiles('pdf_dir', e.target.files)} />
              <button type="button" onClick={() => pdfDirFileRef.current?.click()} className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                Stage PDFs...
              </button>
            </div>
            {pdfDirStagedHandle && <p className="mt-1 text-xs text-emerald-700">staged handle: {pdfDirStagedHandle}</p>}
          </div>
        </div>
      )}

      {stagingStatus && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{stagingStatus}</div>
      )}

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handlePreflight}
          disabled={preflighting || !configPath.trim()}
          className="inline-flex flex-1 items-center justify-center rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {preflighting ? 'Running preflight…' : 'Run preflight'}
        </button>
        <button
          type="button"
          onClick={handleCreateRun}
          disabled={loading || !configPath.trim() || !preflight || preflightDirty || !preflight.readiness.ok}
          className="inline-flex flex-[1.2] items-center justify-center rounded-2xl bg-sky-600 px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Starting run…' : 'Start run'}
        </button>
      </div>

      {preflight && (
        <div className="space-y-4 rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Resolved launch context</p>
              <h4 className="mt-1 text-lg font-semibold text-slate-900">{preflight.readiness.ok ? 'Ready to start' : 'Fix preflight issues before starting'}</h4>
            </div>
            <div className="flex flex-wrap gap-2">
              <StatusPill label={preflight.run_mode} tone="neutral" />
              <StatusPill label={preflight.readiness.provider_mode?.replace(/_/g, ' ') ?? 'provider pending'} tone={preflight.readiness.ok ? 'success' : 'warning'} />
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <InputPreview label="Table" value={preflight.resolved_inputs.table_path?.logical_source ?? null} locator={preflight.resolved_inputs.table_path?.runtime_locator ?? null} />
            <InputPreview label="Schema" value={preflight.resolved_inputs.schema_path?.logical_source ?? null} locator={preflight.resolved_inputs.schema_path?.runtime_locator ?? null} />
            <InputPreview label="PDF scope" value={preflight.resolved_inputs.pdf_dir?.logical_source ?? null} locator={preflight.resolved_inputs.pdf_dir?.runtime_locator ?? null} />
          </div>

          <div className="grid gap-3 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">Scope and readiness</p>
              <div className="mt-3 flex flex-wrap gap-2">
                <StatusPill label={`${preflight.scope.table_rows ?? '—'} table rows`} tone="neutral" />
                <StatusPill label={`${preflight.scope.schema_columns ?? '—'} schema columns`} tone="neutral" />
                <StatusPill label={`${preflight.scope.pdf_count ?? '—'} PDFs`} tone="neutral" />
                <StatusPill label={`text model ${preflight.provider.text_model_id || 'unset'}`} tone={preflight.readiness.ok ? 'success' : 'warning'} />
                {preflight.provider.vision_model_id && <StatusPill label={`vision model ${preflight.provider.vision_model_id}`} tone="neutral" />}
              </div>
              {preflight.readiness.errors.length > 0 && (
                <div className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-3 py-3 text-sm text-rose-700">
                  <p className="font-semibold">Blocking issues</p>
                  <ul className="mt-2 space-y-1 text-xs">
                    {preflight.readiness.errors.map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                </div>
              )}
              {preflight.readiness.warnings.length > 0 && (
                <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-3 text-sm text-amber-800">
                  <p className="font-semibold">Warnings</p>
                  <ul className="mt-2 space-y-1 text-xs">
                    {preflight.readiness.warnings.map((item) => (
                      <li key={item}>• {item}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            <div className="rounded-3xl border border-slate-200 bg-slate-950 p-4 text-slate-50">
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400">What happens next</p>
              <ol className="mt-3 space-y-2 text-sm text-slate-200">
                {preflight.what_happens_next.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-0.5 rounded-full bg-slate-800 px-2 py-0.5 text-[11px] font-semibold text-sky-200">→</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
