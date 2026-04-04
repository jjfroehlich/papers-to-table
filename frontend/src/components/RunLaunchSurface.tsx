import { useState, useRef } from 'react'
import { api } from '../api/client'
import type { CreateRunRequest, RunData } from '../types'

interface Props {
  onRunCreated: (run: RunData) => void
}

export function RunLaunchSurface({ onRunCreated }: Props) {
  const [configPath, setConfigPath] = useState('')
  const [tablePath, setTablePath] = useState('')
  const [schemaPath, setSchemaPath] = useState('')
  const [pdfDir, setPdfDir] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showOverrides, setShowOverrides] = useState(false)
  const [tableStagedHandle, setTableStagedHandle] = useState<string | null>(null)
  const [schemaStagedHandle, setSchemaStagedHandle] = useState<string | null>(null)
  const [pdfDirStagedHandle, setPdfDirStagedHandle] = useState<string | null>(null)
  const [stagingStatus, setStagingStatus] = useState<string | null>(null)

  const configFileRef = useRef<HTMLInputElement>(null)
  const tableFileRef = useRef<HTMLInputElement>(null)
  const schemaFileRef = useRef<HTMLInputElement>(null)
  const pdfDirFileRef = useRef<HTMLInputElement>(null)

  async function stageFiles(
    kind: 'table_path' | 'schema_path' | 'pdf_dir',
    selected: FileList | null,
  ) {
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
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStagingStatus(null)
    }
  }

  async function handleCreateRun() {
    if (!configPath.trim()) {
      setError('Config file path is required.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const req: CreateRunRequest = { config_path: configPath.trim() }
      if (tableStagedHandle) req.table_staged_handle = tableStagedHandle
      else if (tablePath.trim()) req.table_path = tablePath.trim()
      if (schemaStagedHandle) req.schema_staged_handle = schemaStagedHandle
      else if (schemaPath.trim()) req.schema_path = schemaPath.trim()
      if (pdfDirStagedHandle) req.pdf_dir_staged_handle = pdfDirStagedHandle
      else if (pdfDir.trim()) req.pdf_dir = pdfDir.trim()

      const resp = await api.createRun(req)
      const runData = await api.getRun(resp.run_id)
      onRunCreated(runData)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4" data-testid="run-launch-surface">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Config file path <span className="text-red-500">*</span>
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={configPath}
            onChange={(e) => setConfigPath(e.target.value)}
            placeholder="e.g. config.example.json"
            className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
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
            }}
          />
          <button
            type="button"
            onClick={() => configFileRef.current?.click()}
            className="shrink-0 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50"
          >
            Browse...
          </button>
        </div>
        <p className="mt-1 text-xs text-gray-500">
          Enter the backend-readable path to your JSON run configuration file. The browse control can prefill a selected file name, but you may still need to edit the exact path. See{' '}
          <code className="bg-gray-100 px-1 rounded">config.example.json</code> for the format.
        </p>
      </div>

      <div>
        <button
          type="button"
          onClick={() => setShowOverrides(!showOverrides)}
          className="text-sm text-blue-600 hover:underline"
        >
          {showOverrides ? '▲ Hide' : '▼ Show'} optional path overrides
        </button>
      </div>

      {showOverrides && (
        <div className="space-y-3 rounded-md border border-gray-200 bg-gray-50 p-4">
          <p className="text-xs text-gray-500">
            Override paths from the config file. You can enter a backend-readable path manually or stage picker-selected files into app-owned handles for this run.
          </p>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Table path override</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={tablePath}
                onChange={(e) => {
                  setTablePath(e.target.value)
                  setTableStagedHandle(null)
                }}
                placeholder="e.g. path/to/table.xlsx"
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
              <input ref={tableFileRef} type="file" accept=".xlsx,.csv" className="hidden"
                onChange={(e) => void stageFiles('table_path', e.target.files)} />
              <button
                type="button"
                onClick={() => tableFileRef.current?.click()}
                className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50"
              >
                Stage...
              </button>
            </div>
            {tableStagedHandle && (
              <p className="mt-1 text-xs text-emerald-700">
                staged handle: {tableStagedHandle}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Schema path override</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={schemaPath}
                onChange={(e) => {
                  setSchemaPath(e.target.value)
                  setSchemaStagedHandle(null)
                }}
                placeholder="e.g. path/to/schema.csv"
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
              <input ref={schemaFileRef} type="file" accept=".csv" className="hidden"
                onChange={(e) => void stageFiles('schema_path', e.target.files)} />
              <button
                type="button"
                onClick={() => schemaFileRef.current?.click()}
                className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50"
              >
                Stage...
              </button>
            </div>
            {schemaStagedHandle && (
              <p className="mt-1 text-xs text-emerald-700">
                staged handle: {schemaStagedHandle}
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">PDF directory override</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={pdfDir}
                onChange={(e) => {
                  setPdfDir(e.target.value)
                  setPdfDirStagedHandle(null)
                }}
                placeholder="e.g. path/to/pdfs"
                className="flex-1 rounded-md border border-gray-300 px-3 py-2 text-sm"
              />
              <input
                ref={pdfDirFileRef}
                type="file"
                accept=".pdf,application/pdf"
                multiple
                className="hidden"
                onChange={(e) => void stageFiles('pdf_dir', e.target.files)}
              />
              <button
                type="button"
                onClick={() => pdfDirFileRef.current?.click()}
                className="rounded-md border border-gray-300 bg-white px-3 py-2 text-sm hover:bg-gray-50"
              >
                Stage PDFs...
              </button>
            </div>
            {pdfDirStagedHandle && (
              <p className="mt-1 text-xs text-emerald-700">
                staged handle: {pdfDirStagedHandle}
              </p>
            )}
          </div>
        </div>
      )}

      {stagingStatus && (
        <div className="rounded-md bg-emerald-50 border border-emerald-200 p-2 text-xs text-emerald-700">
          {stagingStatus}
        </div>
      )}

      {error && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          <strong>Error:</strong> {error}
        </div>
      )}

      <button
        type="button"
        onClick={handleCreateRun}
        disabled={loading || !configPath.trim()}
        className="w-full rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {loading ? 'Creating run…' : 'Create Run'}
      </button>
    </div>
  )
}
