import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RunsDirectorySelector } from './RunsDirectorySelector'

const mockResolveRunsDirectory = vi.fn()

vi.mock('../api/client', () => ({
  api: {
    resolveRunsDirectory: (...args: Parameters<typeof mockResolveRunsDirectory>) => mockResolveRunsDirectory(...args),
  },
}))

describe('RunsDirectorySelector', () => {
  beforeEach(() => {
    mockResolveRunsDirectory.mockReset()
  })

  it('validates and activates a manually entered directory', async () => {
    const onActivate = vi.fn()
    mockResolveRunsDirectory.mockResolvedValue({ status: 'selected', path: 'C:\\literature\\runs' })
    render(<RunsDirectorySelector activeDirectory="./runs" onActivate={onActivate} onReset={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Runs directory'), { target: { value: 'C:\\literature\\runs' } })
    fireEvent.keyDown(screen.getByLabelText('Runs directory'), { key: 'Enter' })

    await waitFor(() => {
      expect(mockResolveRunsDirectory).toHaveBeenCalledWith('C:\\literature\\runs', false)
      expect(onActivate).toHaveBeenCalledWith('C:\\literature\\runs')
    })
  })

  it('validates and activates a manually entered directory on blur', async () => {
    const onActivate = vi.fn()
    mockResolveRunsDirectory.mockResolvedValue({ status: 'selected', path: 'C:\\literature\\runs' })
    render(<RunsDirectorySelector activeDirectory="./runs" onActivate={onActivate} onReset={vi.fn()} />)

    const input = screen.getByLabelText('Runs directory')
    fireEvent.change(input, { target: { value: 'C:\\literature\\runs' } })
    fireEvent.blur(input)

    await waitFor(() => expect(onActivate).toHaveBeenCalledWith('C:\\literature\\runs'))
  })

  it('activates the directory returned by the native picker', async () => {
    const onActivate = vi.fn()
    mockResolveRunsDirectory.mockResolvedValue({ status: 'selected', path: 'D:\\external-runs' })
    render(<RunsDirectorySelector activeDirectory="./runs" onActivate={onActivate} onReset={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Browse...' }))

    await waitFor(() => {
      expect(mockResolveRunsDirectory).toHaveBeenCalledWith('./runs', true)
      expect(onActivate).toHaveBeenCalledWith('D:\\external-runs')
    })
  })

  it('leaves the active directory unchanged when browsing is cancelled', async () => {
    const onActivate = vi.fn()
    mockResolveRunsDirectory.mockResolvedValue({ status: 'cancelled', path: null })
    render(<RunsDirectorySelector activeDirectory="./runs" onActivate={onActivate} onReset={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'Browse...' }))

    await waitFor(() => expect(mockResolveRunsDirectory).toHaveBeenCalled())
    expect(onActivate).not.toHaveBeenCalled()
    expect(screen.getByLabelText('Runs directory')).toHaveValue('./runs')
  })

  it('shows validation failures without activating the draft directory', async () => {
    const onActivate = vi.fn()
    mockResolveRunsDirectory.mockRejectedValue(new Error('Runs directory does not exist'))
    render(<RunsDirectorySelector activeDirectory="./runs" onActivate={onActivate} onReset={vi.fn()} />)

    fireEvent.change(screen.getByLabelText('Runs directory'), { target: { value: 'Z:\\missing' } })
    fireEvent.keyDown(screen.getByLabelText('Runs directory'), { key: 'Enter' })

    expect(await screen.findByText('Runs directory does not exist')).toBeInTheDocument()
    expect(onActivate).not.toHaveBeenCalled()
  })
})
