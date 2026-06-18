import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import type { RunData } from './types'

vi.mock('./components/ReviewWorkspace', () => ({
  ReviewWorkspace: ({ run }: { run: RunData }) => <div data-testid="review-workspace">{run.run_id}</div>,
}))

describe('standalone App shell', () => {
  afterEach(() => {
    window.__REVIEW_PACKAGE__ = undefined
  })

  it('renders the main app brand header with standalone review title', () => {
    window.__REVIEW_PACKAGE__ = {
      schema_version: 'papers_to_table.review_package.v1',
      run_id: 'agent_review',
      source: { source_table_present: true },
      rows: [],
      columns: [],
      pdfs: [],
      proposals: [],
    }

    render(<App />)

    expect(screen.getByRole('img', { name: 'papers-to-table' })).toHaveAttribute('src', './logo_1.svg')
    expect(screen.getByRole('heading', { name: 'papers-to-table' })).toBeInTheDocument()
    expect(screen.getByText('Evidence-backed extraction and review')).toBeInTheDocument()
    expect(screen.getByText('Agent skill review')).toBeInTheDocument()
    expect(screen.getByTestId('review-workspace')).toHaveTextContent('agent_review')
  })
})
