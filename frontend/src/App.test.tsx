import { act, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { App } from './App'

const mockListRuns = vi.fn()

vi.mock('./api/client', () => ({
  api: {
    listRuns: (...args: Parameters<typeof mockListRuns>) => mockListRuns(...args),
    abortRun: vi.fn(),
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
  it('surfaces stale auto-refresh truth when active-run polling fails', async () => {
    mockListRuns
      .mockResolvedValueOnce({
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
      .mockRejectedValueOnce(new Error('backend offline'))

    render(<App />)

    await waitFor(() => {
      expect(screen.getByText(/run_active/i)).toBeInTheDocument()
    })

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 2200))
    })

    await waitFor(() => {
      expect(screen.getByText(/Active run status may be stale/i)).toBeInTheDocument()
    })
  }, 10000)
})
