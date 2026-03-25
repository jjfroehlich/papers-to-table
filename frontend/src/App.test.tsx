import { render, screen } from '@testing-library/react'
import { vi } from 'vitest'

import App from './App'

vi.mock('./api', () => ({
  listRuns: vi.fn().mockResolvedValue([]),
  createRun: vi.fn(),
  getRunSummary: vi.fn(),
  getInputSummary: vi.fn(),
}))

describe('App', () => {
  it('shows run-launch baseline and empty-state guidance', async () => {
    render(<App />)

    expect(await screen.findByText('Start run from config file')).toBeInTheDocument()
    expect(screen.getByText(/No runs yet\. Enter a config path and create a run/)).toBeInTheDocument()
  })
})
