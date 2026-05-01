import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunLaunchSurface } from './RunLaunchSurface'

const mockCreateRun = vi.fn()
const mockGetRun = vi.fn()
const mockStageInputFiles = vi.fn()

vi.mock('../api/client', () => ({
  api: {
    createRun: (...args: Parameters<typeof mockCreateRun>) => mockCreateRun(...args),
    getRun: (...args: Parameters<typeof mockGetRun>) => mockGetRun(...args),
    stageInputFiles: (...args: Parameters<typeof mockStageInputFiles>) => mockStageInputFiles(...args),
  },
}))

describe('RunLaunchSurface', () => {
  beforeEach(() => {
    mockCreateRun.mockReset()
    mockGetRun.mockReset()
    mockStageInputFiles.mockReset()
  })

  it('uses staged handles for picker-driven overrides when creating a run', async () => {
    mockStageInputFiles.mockResolvedValueOnce({
      handle: 'staged_table_path_abc123',
      kind: 'table_path',
      logical_source: 'picked-table.xlsx',
      runtime_locator: '/tmp/staged/picked-table.xlsx',
    })
    mockCreateRun.mockResolvedValueOnce({ run_id: 'run_1', status: 'created', resolved_inputs: {} })
    mockGetRun.mockResolvedValueOnce({ run_id: 'run_1' })

    render(<RunLaunchSurface onRunCreated={vi.fn()} />)

    fireEvent.change(screen.getByPlaceholderText(/config\.json/i), {
      target: { value: '/tmp/config.json' },
    })

    const tableFileInput = document.querySelector('input[type="file"][accept=".xlsx,.csv"]') as HTMLInputElement
    fireEvent.change(tableFileInput, {
      target: { files: [new File(['fake'], 'picked-table.xlsx')] },
    })

    await waitFor(() => {
      expect(mockStageInputFiles).toHaveBeenCalledWith('table_path', expect.any(Array), './runs')
    })

    fireEvent.click(screen.getByRole('button', { name: /Start run/i }))

    await waitFor(() => {
      expect(mockCreateRun).toHaveBeenCalledWith(
        expect.objectContaining({
          config_path: '/tmp/config.json',
          table_staged_handle: 'staged_table_path_abc123',
        })
      )
    })

    const request = mockCreateRun.mock.calls[0][0]
    expect(request.table_path).toBeUndefined()
  })

  it('shows Browse controls for selectable inputs', () => {
    render(<RunLaunchSurface onRunCreated={vi.fn()} />)

    expect(screen.getAllByRole('button', { name: 'Browse...' })).toHaveLength(3)
    expect(screen.getByPlaceholderText(/config\.json/i)).toBeInTheDocument()
  })

  it('keeps the config field text-editable', () => {
    render(<RunLaunchSurface onRunCreated={vi.fn()} />)

    const input = screen.getByPlaceholderText(/config\.json/i) as HTMLInputElement

    fireEvent.change(input, { target: { value: '/tmp/custom-config.json' } })
    expect(input.value).toBe('/tmp/custom-config.json')
  })
})
