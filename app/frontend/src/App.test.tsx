import { act, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'

const mockListRuns = vi.fn()
const mockCreateRunEventsSource = vi.fn()

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
    createRunEventsSource: (...args: Parameters<typeof mockCreateRunEventsSource>) => mockCreateRunEventsSource(...args),
  },
}))

vi.mock('./components/RunLaunchSurface', () => ({
  RunLaunchSurface: () => <div>Create run form</div>,
}))

vi.mock('./components/RunDetail', () => ({
  RunDetail: () => <div>Run detail</div>,
}))

vi.mock('./components/RunList', () => ({
  RunList: ({ runs }: { runs: Array<{ run_id: string }> }) => <div>{runs.map((run) => run.run_id).join(',')}</div>,
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
    mockListRuns.mockResolvedValue({ runs: [] })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders the main app shell by default', async () => {
    render(<App />)

    await screen.findByText('Create run form')
    expect(screen.getByText('Review ready')).toBeInTheDocument()
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

    act(() => {
      source.onerror?.()
    })

    await waitFor(() => {
      expect(mockListRuns).toHaveBeenCalledTimes(2)
    })
    expect(screen.queryByText(/Live run updates are disconnected/i)).not.toBeInTheDocument()
  })
})
