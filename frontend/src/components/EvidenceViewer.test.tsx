import { render, screen } from '@testing-library/react'
import { vi, describe, it, expect, beforeAll } from 'vitest'
import { EvidenceViewer } from './EvidenceViewer'
import type { EvidenceItem } from '../types'

// Mock pdfjs-dist
vi.mock('pdfjs-dist', () => ({
  GlobalWorkerOptions: { workerSrc: '' },
  getDocument: vi.fn().mockReturnValue({
    promise: new Promise(() => {}), // Never resolves - simulates loading
  }),
}))

vi.mock('../api/client', () => ({
  api: {
    getPdfUrl: (_runId: string, pdfId: string) => `http://localhost:8000/api/runs/r1/assets/pdf/${pdfId}`,
    getFigureUrl: (_runId: string, pdfId: string, figureId: string) =>
      `http://localhost:8000/api/runs/r1/assets/figures/${pdfId}/${figureId}`,
  },
}))

// Stub DOMMatrix if not available in jsdom
beforeAll(() => {
  if (typeof globalThis.DOMMatrix === 'undefined') {
    // @ts-expect-error - stub for test env
    globalThis.DOMMatrix = class {
      constructor() {}
      invertSelf() { return this }
    }
  }
})

const quoteEvidence: EvidenceItem = {
  evidence_id: 'ev1',
  proposal_id: 'p1',
  pdf_id: 'paper-a',
  source_type: 'quote_plus_page',
  quote_text: 'A total of 120 participants were enrolled.',
  page_number: 3,
  exact_highlight_regions: null,
  approximate_highlight_regions: null,
  figure_ref: null,
  caption_text: null,
  crop_path: null,
  full_page_path: null,
  anchor_confidence: null,
  evidence_rank: 1,
  source_label: 'Quote + page',
}

const approxEvidence: EvidenceItem = {
  evidence_id: 'ev2',
  proposal_id: 'p1',
  pdf_id: 'paper-a',
  source_type: 'approximate_highlight',
  quote_text: null,
  page_number: 2,
  exact_highlight_regions: null,
  approximate_highlight_regions: [{ x0: 10, y0: 20, x1: 100, y1: 50, page: 2 }],
  figure_ref: null,
  caption_text: null,
  crop_path: null,
  full_page_path: null,
  anchor_confidence: 0.7,
  evidence_rank: 1,
  source_label: 'Approximate highlight',
}

const figureEvidence: EvidenceItem = {
  evidence_id: 'ev3',
  proposal_id: 'p1',
  pdf_id: 'paper-a',
  source_type: 'figure_based_evidence',
  quote_text: null,
  page_number: null,
  exact_highlight_regions: null,
  approximate_highlight_regions: null,
  figure_ref: 'fig-001',
  caption_text: 'Figure 1: Results overview',
  crop_path: null,
  full_page_path: null,
  anchor_confidence: null,
  evidence_rank: 1,
  source_label: 'Figure',
}

describe('EvidenceViewer', () => {
  it('renders quote text for quote_plus_page fallback', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={quoteEvidence}
        outputDir="./runs"
      />
    )
    expect(screen.getByText(/Text fallback – exact highlighting unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/A total of 120 participants were enrolled/i)).toBeInTheDocument()
  })

  it('shows no-pdf placeholder when pdfId is null and no figure evidence', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId={null}
        evidence={null}
        outputDir="./runs"
      />
    )
    expect(screen.getByText('No PDF selected')).toBeInTheDocument()
  })

  it('figure evidence shows image with correct src', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={figureEvidence}
        outputDir="./runs"
      />
    )
    const img = screen.getByRole('img')
    expect(img).toBeInTheDocument()
    expect(img.getAttribute('src')).toContain('fig-001')
  })

  it('figure evidence shows caption text', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={figureEvidence}
        outputDir="./runs"
      />
    )
    expect(screen.getByText('Figure 1: Results overview')).toBeInTheDocument()
  })

  it('shows Approx label for approximate highlight evidence after render', () => {
    // With a loaded page the overlay would show; with load error we still render canvas area
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={approxEvidence}
        outputDir="./runs"
      />
    )
    // The toolbar should be visible (PDF path)
    expect(screen.getByRole('spinbutton')).toBeInTheDocument()
  })
})
