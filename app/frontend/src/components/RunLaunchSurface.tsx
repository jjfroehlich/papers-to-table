import { useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { CreateRunRequest, RunData } from '../types'

interface Props {
  onRunCreated: (run: RunData) => void
}

function PathField({
  label,
  value,
  placeholder,
  buttonLabel,
  accept,
  multiple,
  onText,
  onPick,
  stagedHandle,
}: {
  label: string
  value: string
  placeholder: string
  buttonLabel: string
  accept?: string
  multiple?: boolean
  onText: (value: string) => void
  onPick: (files: FileList | null) => void
  stagedHandle?: string | null
}) {
  const fileRef = useRef<HTMLInputElement>(null)
  return (
    <div>
      <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">{label}</label>
      <div className="flex gap-2">
        <input
          type="text"
          value={value}
          onChange={(event) => onText(event.target.value)}
          placeholder={placeholder}
          className="min-w-0 flex-1 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
        />
        <input
          ref={fileRef}
          type="file"
          accept={accept}
          multiple={multiple}
          className="hidden"
          onChange={(event) => onPick(event.target.files)}
        />
        <button
          type="button"
          onClick={() => fileRef.current?.click()}
          className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
        >
          {buttonLabel}
        </button>
      </div>
      {stagedHandle && <p className="mt-1 text-xs text-emerald-700">Staged handle: {stagedHandle}</p>}
    </div>
  )
}

export function RunLaunchSurface({ onRunCreated }: Props) {
  const [configPath, setConfigPath] = useState('config.json')
  const [tablePath, setTablePath] = useState('')
  const [schemaPath, setSchemaPath] = useState('')
  const [pdfDir, setPdfDir] = useState('')
  const [outputDir, setOutputDir] = useState('./runs')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [tableStagedHandle, setTableStagedHandle] = useState<string | null>(null)
  const [schemaStagedHandle, setSchemaStagedHandle] = useState<string | null>(null)
  const [pdfDirStagedHandle, setPdfDirStagedHandle] = useState<string | null>(null)
  const [stagingStatus, setStagingStatus] = useState<string | null>(null)

  const request = useMemo<CreateRunRequest>(() => {
    const payload: CreateRunRequest = {
      config_path: configPath.trim() || 'config.json',
      output_dir: outputDir.trim() || './runs',
    }
    if (tableStagedHandle) payload.table_staged_handle = tableStagedHandle
    else if (tablePath.trim()) payload.table_path = tablePath.trim()
    if (schemaStagedHandle) payload.schema_staged_handle = schemaStagedHandle
    else if (schemaPath.trim()) payload.schema_path = schemaPath.trim()
    if (pdfDirStagedHandle) payload.pdf_dir_staged_handle = pdfDirStagedHandle
    else if (pdfDir.trim()) payload.pdf_dir = pdfDir.trim()
    return payload
  }, [configPath, outputDir, pdfDir, pdfDirStagedHandle, schemaPath, schemaStagedHandle, tablePath, tableStagedHandle])

  async function stageFiles(kind: 'table_path' | 'schema_path' | 'pdf_dir', selected: FileList | null) {
    if (!selected || selected.length === 0) return
    const files = Array.from(selected)
    setError(null)
    setStagingStatus(`Staging ${kind.replace('_path', '')} input...`)
    try {
      const response = await api.stageInputFiles(kind, files, outputDir.trim() || './runs')
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
      setStagingStatus(`Staged ${response.logical_source}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStagingStatus(null)
    }
  }

  async function handleCreateRun() {
    setLoading(true)
    setError(null)
    try {
      const resp = await api.createRun(request)
      const runData = await api.getRun(resp.run_id, outputDir.trim() || './runs')
      onRunCreated(runData)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4" data-testid="run-launch-surface">
      <PathField
        label="Table"
        value={tablePath}
        placeholder="Select a table file or enter a backend-readable path"
        buttonLabel="Browse..."
        accept=".xlsx,.csv"
        onText={(value) => {
          setTablePath(value)
          setTableStagedHandle(null)
        }}
        onPick={(files) => void stageFiles('table_path', files)}
        stagedHandle={tableStagedHandle}
      />

      <PathField
        label="Schema"
        value={schemaPath}
        placeholder="Select a schema CSV or enter a backend-readable path"
        buttonLabel="Browse..."
        accept=".csv"
        onText={(value) => {
          setSchemaPath(value)
          setSchemaStagedHandle(null)
        }}
        onPick={(files) => void stageFiles('schema_path', files)}
        stagedHandle={schemaStagedHandle}
      />

      <PathField
        label="PDFs"
        value={pdfDir}
        placeholder="Select PDFs or enter a backend-readable PDF folder"
        buttonLabel="Browse..."
        accept=".pdf,application/pdf"
        multiple
        onText={(value) => {
          setPdfDir(value)
          setPdfDirStagedHandle(null)
        }}
        onPick={(files) => void stageFiles('pdf_dir', files)}
        stagedHandle={pdfDirStagedHandle}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Output directory</label>
          <input
            type="text"
            value={outputDir}
            onChange={(event) => {
              setOutputDir(event.target.value)
            }}
            placeholder="./runs"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Config file</label>
          <input
            type="text"
            value={configPath}
            onChange={(event) => {
              setConfigPath(event.target.value)
            }}
            placeholder="config.json"
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none transition focus:border-slate-400 focus:ring-2 focus:ring-slate-100"
          />
        </div>
      </div>

      {stagingStatus && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{stagingStatus}</div>
      )}

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="flex">
        <button
          type="button"
          onClick={handleCreateRun}
          disabled={loading}
          className="inline-flex w-full items-center justify-center rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? 'Starting...' : 'Start run'}
        </button>
      </div>
    </div>
  )
}
