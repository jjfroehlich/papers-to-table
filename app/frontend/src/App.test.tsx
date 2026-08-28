import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const mockListRuns = vi.fn()
const mockCreateRunEventsSource = vi.fn()
const mockResolveRunsDirectory = vi.fn()

class MockEventSource {
  listeners = new Map<string, EventListener[]>()
  onerror: (() => void) | null = null
  close = vi.fn()

  addEventListener(type: string, listener: EventListener) {
    const current = this.listeners.get(type) ?? []
    current.push(listener)
    this.listeners.set(type, current)
  }

  removeEventListener(type: string, listener: EventListener) {
    const current = this.listeners.get(type) ?? []
    this.listeners.set(type, current.filter((item) => item !== listener))
  }

  emit(type: string, payload: unknown) {
    for (const listener of this.listeners.get(type) ?? []) {
      listener({ data: JSON.stringify(payload) } as MessageEvent)
    }
  }
}

vi.mock('./api/client', () => ({
  api: {
    listRuns: (...args: Parameters<typeof mockListRuns>) => mockListRuns(...args),
    abortRun: vi.fn(),
    resolveRunsDirectory: (...args: Parameters<typeof mockResolveRunsDirectory>) => mockResolveRunsDirectory(...args),
    createRunEventsSource: (...args: Parameters<typeof mockCreateRunEventsSource>) => mockCreateRunEventsSource(...args),
  },
}))

vi.mock('./components/RunLaunchSurface', () => ({
  RunLaunchSurface: () => (
    <div>
      Create run form
      <label htmlFor="new-run-output">Output directory</label>
      <input id="new-run-output" defaultValue="./runs" />
    </div>
  ),
}))

vi.mock('./components/RunDetail', () => ({
  RunDetail: ({ run, onStartReview }: { run: { run_id: string }; onStartReview?: (run: { run_id: string }) => void }) => (
    <div>
      Run detail
      <button onClick={() => onStartReview?.(run)}>Start human review</button>
    </div>
  ),
}))

vi.mock('./components/RunList', () => ({
  RunList: ({ runs, onSelect }: { runs: Array<{ run_id: string }>; onSelect: (run: { run_id: string }) => void }) => (
    <div>
      {runs.map((run) => (
        <button key={run.run_id} onClick={() => onSelect(run)}>{run.run_id}</button>
      ))}
    </div>
  ),
}))

vi.mock('./components/ReviewWorkspace', () => ({
  ReviewWorkspace: () => <div>Review workspace</div>,
}))

describe('App', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
    window.localStorage.clear()
    vi.unstubAllGlobals()
    mockListRuns.mockReset()
    mockCreateRunEventsSource.mockReset()
    mockResolveRunsDirectory.mockReset()
    mockListRuns.mockResolvedValue({ runs: [] })
    mockResolveRunsDirectory.mockImplementation(async (path: string) => ({ status: 'selected', path }))
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.unstubAllEnvs()
  })

  it('renders the main app shell by default', async () => {
    render(<App />)

    await screen.findByText('Create run form')
    expect(screen.getByText('Review ready')).toBeInTheDocument()
    expect(mockListRuns).toHaveBeenCalledWith('./runs')
  })

  it('opens human review from the selected-run action', async () => {
    mockListRuns.mockResolvedValue({
      runs: [{
        run_id: 'run_completed',
        status: 'completed',
        output_dir: 'D:\\external-runs',
      }],
    })
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'run_completed' }))
    fireEvent.click(screen.getByRole('button', { name: 'Start human review' }))

    expect(await screen.findByText('Review workspace')).toBeInTheDocument()
  })

  it('restores the last successfully selected runs directory', async () => {
    window.localStorage.setItem('papers-to-table.runs-directory', 'C:\\saved-runs')

    render(<App />)

    await waitFor(() => expect(mockListRuns).toHaveBeenCalledWith('C:\\saved-runs'))
    expect(screen.getByLabelText('Runs directory')).toHaveValue('C:\\saved-runs')
  })

  it('gives the startup runs directory precedence over saved browser state', async () => {
    vi.stubEnv('VITE_DEFAULT_RUNS_DIR', 'D:\\startup-runs')
    window.localStorage.setItem('papers-to-table.runs-directory', 'C:\\saved-runs')

    render(<App />)

    await waitFor(() => expect(mockListRuns).toHaveBeenCalledWith('D:\\startup-runs'))
    expect(screen.getByLabelText('Runs directory')).toHaveValue('D:\\startup-runs')
  })

  it('switches and persists the review directory without changing new-run output', async () => {
    mockResolveRunsDirectory.mockResolvedValue({ status: 'selected', path: 'C:\\external-runs' })
    render(<App />)

    fireEvent.change(screen.getByLabelText('Runs directory'), { target: { value: 'C:\\external-runs' } })
    fireEvent.keyDown(screen.getByLabelText('Runs directory'), { key: 'Enter' })

    await waitFor(() => expect(mockListRuns).toHaveBeenCalledWith('C:\\external-runs'))
    expect(window.localStorage.getItem('papers-to-table.runs-directory')).toBe('C:\\external-runs')
    expect(screen.getByLabelText('Output directory')).toHaveValue('./runs')
  })

  it('resets review discovery to the default without changing new-run output', async () => {
    window.localStorage.setItem('papers-to-table.runs-directory', 'C:\\saved-runs')
    render(<App />)

    fireEvent.click(await screen.findByRole('button', { name: 'Reset to default' }))

    await waitFor(() => expect(mockListRuns).toHaveBeenCalledWith('./runs'))
    expect(window.localStorage.getItem('papers-to-table.runs-directory')).toBeNull()
    expect(screen.getByLabelText('Output directory')).toHaveValue('./runs')
  })

  it('refreshes runs quietly when the event stream reports an error', async () => {
    const source = new MockEventSource()
    vi.stubGlobal('EventSource', MockEventSource)
    mockCreateRunEventsSource.mockReturnValue(source)
    mockListRuns.mockResolvedValue({
      runs: [
        {
          run_id: 'run_active',
          status: 'running',
          config_path: 'config.json',
          table_path: 'table.xlsx',
          schema_path: 'schema.csv',
          pdf_dir: 'pdfs',
          output_dir: './runs',
          verify_mode: false,
          eval_mode: false,
          run_mode: 'normal',
          provider_token: 'lm_studio',
          provider_locality: 'local',
          provider_mode: 'live_local',
          provider_text_model_id: 'text-model',
          provider_vision_model_id: null,
          provider_readiness_error: null,
          started_at: null,
          completed_at: null,
          current_stage: 'parse',
          total_rows: 0,
          eligible_cells: 0,
          proposals_generated: 0,
          proposals_reviewed: 0,
          warnings: [],
          error_message: null,
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
    })

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/run_active/i)).toBeInTheDocument()
    })
    expect(mockCreateRunEventsSource).toHaveBeenCalledWith('./runs')

    act(() => {
      source.onerror?.()
    })

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledTimes(2)
    })
    expect(screen.queryByText(/Live run updates are disconnected/i)).not.toBeInTheDocument()
  })
})
