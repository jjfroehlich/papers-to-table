import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { RunList } from './RunList'
import type { RunData } from '../types'

const mockRun: RunData = {
  run_id: 'run_20240315_143022_abc123',
  status: 'completed',
  config_path: 'config.json',
  table_path: 'tests/fixtures/tables/literature_fixture.xlsx',
  schema_path: null,
  pdf_dir: 'tests/fixtures/papers',
  output_dir: './runs',
  verify_mode: false,
  eval_mode: false,
  run_mode: 'normal',
  provider_token: 'lm_studio',
  provider_locality: 'local',
  provider_mode: 'live_local',
  started_at: '2024-03-15T14:30:22Z',
  completed_at: '2024-03-15T14:35:00Z',
  current_stage: null,
  total_rows: 10,
  eligible_cells: 50,
  proposals_generated: 0,
  proposals_reviewed: 0,
  warnings: [],
  error_message: null,
  created_at: '2024-03-15T14:30:22Z',
}

describe('RunList', () => {
  it('shows empty state when no runs', () => {
    render(<RunList runs={[]} selectedRunId={null} onSelect={vi.fn()} />)
    expect(screen.getByText(/No runs yet/)).toBeTruthy()
  })

  it('renders run items', () => {
    render(<RunList runs={[mockRun]} selectedRunId={null} onSelect={vi.fn()} />)
    expect(screen.getByText('run_20240315_143022_abc123')).toBeTruthy()
  })

  it('calls onSelect when clicked', () => {
    const onSelect = vi.fn()
    render(<RunList runs={[mockRun]} selectedRunId={null} onSelect={onSelect} />)
    fireEvent.click(screen.getByText('run_20240315_143022_abc123'))
    expect(onSelect).toHaveBeenCalledWith(mockRun)
  })

  it('highlights selected run', () => {
    const { container } = render(
      <RunList runs={[mockRun]} selectedRunId={mockRun.run_id} onSelect={vi.fn()} />
    )
    expect(container.innerHTML).toContain('border-l-4')
  })

  it('shows error message for failed runs', () => {
    const failedRun = { ...mockRun, status: 'failed' as const, error_message: 'Provider unreachable' }
    render(<RunList runs={[failedRun]} selectedRunId={null} onSelect={vi.fn()} />)
    expect(screen.getByText('Provider unreachable')).toBeTruthy()
  })
})
