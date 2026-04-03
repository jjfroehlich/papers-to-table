import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RunLaunchSurface } from './RunLaunchSurface'

vi.mock('../api/client', () => ({
  api: {
    createRun: vi.fn(),
    getRun: vi.fn(),
  },
}))

describe('RunLaunchSurface', () => {
  it('shows a Browse control next to the config path field', () => {
    render(<RunLaunchSurface onRunCreated={vi.fn()} />)

    expect(screen.getByRole('button', { name: 'Browse...' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/config\.example\.json/i)).toBeInTheDocument()
  })

  it('keeps the config field text-editable after using Browse', () => {
    render(<RunLaunchSurface onRunCreated={vi.fn()} />)

    const input = screen.getByPlaceholderText(/config\.example\.json/i) as HTMLInputElement
    const fileInput = document.querySelector('input[type="file"][accept=".json,application/json"]') as HTMLInputElement

    fireEvent.change(fileInput, {
      target: {
        files: [new File(['{"output_dir":"./runs"}'], 'picked-config.json', { type: 'application/json' })],
      },
    })

    expect(input.value).toBe('picked-config.json')

    fireEvent.change(input, { target: { value: '/tmp/custom-config.json' } })
    expect(input.value).toBe('/tmp/custom-config.json')
  })
})
