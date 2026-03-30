import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { RunStatusBadge } from './RunStatusBadge'

describe('RunStatusBadge', () => {
  it('renders completed status', () => {
    render(<RunStatusBadge status="completed" />)
    expect(screen.getByText('Completed')).toBeTruthy()
  })

  it('renders failed status', () => {
    render(<RunStatusBadge status="failed" />)
    expect(screen.getByText('Failed')).toBeTruthy()
  })

  it('renders running status', () => {
    render(<RunStatusBadge status="running" />)
    expect(screen.getByText('Running')).toBeTruthy()
  })

  it('renders validating status', () => {
    render(<RunStatusBadge status="validating" />)
    expect(screen.getByText('Validating')).toBeTruthy()
  })

  it('renders completed_with_warnings status', () => {
    render(<RunStatusBadge status="completed_with_warnings" />)
    expect(screen.getByText('Completed (warnings)')).toBeTruthy()
  })

  it('renders interrupted status', () => {
    render(<RunStatusBadge status="interrupted" />)
    expect(screen.getByText('Interrupted')).toBeTruthy()
  })
})
