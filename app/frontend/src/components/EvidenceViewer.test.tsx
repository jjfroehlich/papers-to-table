import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { vi, describe, it, expect, beforeAll, beforeEach } from 'vitest'
import * as pdfjsLib from 'pdfjs-dist'
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
    getPageImageUrl: (_runId: string, pdfId: string, pageNumber: number) =>
      `http://localhost:8000/api/runs/r1/assets/pages/${pdfId}/${pageNumber}`,
    openPdfInLocalViewer: vi.fn().mockResolvedValue({ status: 'opened' }),
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

  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => {
    return {} as CanvasRenderingContext2D
  })

  if (!('scrollTo' in HTMLElement.prototype)) {
    Object.defineProperty(HTMLElement.prototype, 'scrollTo', {
      value: vi.fn(),
      configurable: true,
      writable: true,
    })
  } else {
    vi.spyOn(HTMLElement.prototype, 'scrollTo').mockImplementation(() => {})
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

const approxEvidenceWithoutPageNumber: EvidenceItem = {
  ...approxEvidence,
  evidence_id: 'ev4',
  page_number: null,
  approximate_highlight_regions: [{ x0: 10, y0: 20, x1: 100, y1: 50, page: 7 }],
}

const figureEvidence: EvidenceItem = {
  evidence_id: 'ev3',
  proposal_id: 'p1',
  pdf_id: 'paper-a',
  source_type: 'caption_grounded_figure_evidence',
  quote_text: null,
  page_number: 4,
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

function mockResolvedPdf(options?: {
  textItems?: Array<{ str: string; transform: number[]; width: number; height: number }>
  numPages?: number
}) {
  const textItems = options?.textItems ?? []
  const page = {
    view: [0, 0, 600, 800],
    getViewport: ({ scale }: { scale: number }) => ({
      width: 600 * scale,
      height: 800 * scale,
      scale,
      transform: [scale, 0, 0, scale, 0, 0],
    }),
    render: vi.fn().mockReturnValue({
      promise: Promise.resolve(),
      cancel: vi.fn(),
    }),
    getTextContent: vi.fn().mockResolvedValue({ items: textItems }),
  }

  const doc = {
    numPages: options?.numPages ?? 1,
    getPage: vi.fn().mockResolvedValue(page),
  }

  const getDocument = pdfjsLib.getDocument as unknown as ReturnType<typeof vi.fn>
  getDocument.mockReturnValue({
    promise: Promise.resolve(doc),
    destroy: vi.fn().mockResolvedValue(undefined),
  })
}

describe('EvidenceViewer', () => {
  const onSelectEvidence = vi.fn()

  beforeEach(() => {
    onSelectEvidence.mockClear()
    const getDocument = pdfjsLib.getDocument as unknown as ReturnType<typeof vi.fn>
    getDocument.mockReset()
    getDocument.mockReturnValue({
      promise: new Promise(() => {}),
    })
  })

  it('shows local-viewer action', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={null}
        evidenceList={[]}
        selectedEvidenceId={null}
        activeEvidenceIndex={-1}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )
    expect(screen.queryByText(/optimized for evidence highlights/i)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Open PDF/i })).toBeInTheDocument()
  })

  it('renders quote text for quote_plus_page fallback', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={quoteEvidence}
        evidenceList={[quoteEvidence]}
        selectedEvidenceId="ev1"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )
    expect(screen.getByText(/Text fallback – exact highlighting unavailable/i)).toBeInTheDocument()
    expect(screen.getByText(/A total of 120 participants were enrolled/i)).toBeInTheDocument()
  })

  it('opens the local PDF viewer on demand', async () => {
    const { api } = await import('../api/client')
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={null}
        evidenceList={[]}
        selectedEvidenceId={null}
        activeEvidenceIndex={-1}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )
    fireEvent.click(screen.getByRole('button', { name: /Open PDF/i }))
    await waitFor(() => {
      expect(api.openPdfInLocalViewer).toHaveBeenCalledWith('r1', 'paper-a', './runs')
    })
  })

  it('shows no-pdf placeholder when pdfId is null and no figure evidence', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId={null}
        evidence={null}
        evidenceList={[]}
        selectedEvidenceId={null}
        activeEvidenceIndex={-1}
        onSelectEvidence={onSelectEvidence}
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
        evidenceList={[figureEvidence]}
        selectedEvidenceId="ev3"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
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
        evidenceList={[figureEvidence]}
        selectedEvidenceId="ev3"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )
    expect(screen.getByText('Figure 1: Results overview')).toBeInTheDocument()
  })

  it('figure evidence can toggle full-page context and shows figure-derived marker', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={figureEvidence}
        evidenceList={[figureEvidence]}
        selectedEvidenceId="ev3"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )

    expect(screen.getByText(/Figure-derived/i)).toBeInTheDocument()

    const toggle = screen.getByRole('button', { name: /Show full page/i })
    fireEvent.click(toggle)

    expect(screen.getByText(/Full-page context \(page 4\)/i)).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Full page 4/i })).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Hide full page/i }))
    expect(screen.queryByText(/Full-page context \(page 4\)/i)).not.toBeInTheDocument()
  })

  it('shows Approx label for approximate highlight evidence after render', () => {
    // With a loaded page the overlay would show; with load error we still render canvas area
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={approxEvidence}
        evidenceList={[approxEvidence]}
        selectedEvidenceId="ev2"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )
    // The toolbar should be visible (PDF path)
    expect(screen.getByRole('spinbutton')).toBeInTheDocument()
  })

  it('infers page input from highlight regions when page_number is missing', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={approxEvidenceWithoutPageNumber}
        evidenceList={[approxEvidenceWithoutPageNumber]}
        selectedEvidenceId="ev4"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )

    expect(screen.getByRole('spinbutton')).toHaveValue(7)
  })

  it('cycles to the next evidence item from the toolbar', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={quoteEvidence}
        evidenceList={[quoteEvidence, approxEvidence]}
        selectedEvidenceId="ev1"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )

    fireEvent.click(screen.getByRole('button', { name: 'Next' }))
    expect(onSelectEvidence).toHaveBeenCalledWith('ev2')
  })

  it('does not render a destroyed PDF document while switching papers', async () => {
    const page = {
      view: [0, 0, 600, 800],
      getViewport: ({ scale }: { scale: number }) => ({
        width: 600 * scale,
        height: 800 * scale,
        scale,
        transform: [scale, 0, 0, scale, 0, 0],
      }),
      render: vi.fn().mockReturnValue({ promise: Promise.resolve(), cancel: vi.fn() }),
      getTextContent: vi.fn().mockResolvedValue({ items: [] }),
    }
    let firstDestroyed = false
    let callsAfterDestroy = 0
    const firstDoc = {
      numPages: 5,
      getPage: vi.fn(() => {
        if (firstDestroyed) {
          callsAfterDestroy += 1
          throw new TypeError("Cannot read properties of null (reading 'sendWithPromise')")
        }
        return Promise.resolve(page)
      }),
    }
    const secondDoc = { numPages: 5, getPage: vi.fn().mockResolvedValue(page) }
    const getDocument = pdfjsLib.getDocument as unknown as ReturnType<typeof vi.fn>
    getDocument
      .mockReturnValueOnce({
        promise: Promise.resolve(firstDoc),
        destroy: vi.fn(() => {
          firstDestroyed = true
          return Promise.resolve()
        }),
      })
      .mockReturnValueOnce({ promise: Promise.resolve(secondDoc), destroy: vi.fn().mockResolvedValue(undefined) })

    const { rerender } = render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={quoteEvidence}
        evidenceList={[quoteEvidence]}
        selectedEvidenceId="ev1"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )
    await waitFor(() => expect(firstDoc.getPage).toHaveBeenCalled())

    const secondEvidence = { ...approxEvidence, pdf_id: 'paper-b' }
    rerender(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-b"
        evidence={secondEvidence}
        evidenceList={[secondEvidence]}
        selectedEvidenceId="ev2"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )

    await waitFor(() => expect(secondDoc.getPage).toHaveBeenCalled())
    expect(callsAfterDestroy).toBe(0)
    expect(screen.getByTestId('evidence-toolbar')).toBeInTheDocument()
  })

  it('renders quote-anchored overlay rectangles from resolved PDF text content', async () => {
    mockResolvedPdf({
      numPages: 5,
      textItems: [
        {
          str: 'A total of 120 participants were enrolled.',
          transform: [1, 0, 0, 1, 10, 30],
          width: 120,
          height: 12,
        },
      ],
    })

    const { container } = render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={quoteEvidence}
        evidenceList={[quoteEvidence]}
        selectedEvidenceId="ev1"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )

    await waitFor(() => {
      const overlays = container.querySelectorAll('div.absolute.pointer-events-none')
      expect(overlays.length).toBeGreaterThan(0)
      expect((overlays[0] as HTMLDivElement).style.left).toMatch(/px$/)
      expect((overlays[0] as HTMLDivElement).style.top).toMatch(/px$/)
      expect((overlays[0] as HTMLDivElement).style.border).toContain('rgba(200, 160, 0')
    })
  })

  it('shows approximate fallback note when quote matching fails and approximate region is used', async () => {
    mockResolvedPdf({
      numPages: 5,
      textItems: [
        {
          str: 'This text does not include the evidence quote.',
          transform: [1, 0, 0, 1, 12, 28],
          width: 100,
          height: 10,
        },
      ],
    })

    const quoteWithApprox: EvidenceItem = {
      ...quoteEvidence,
      evidence_id: 'ev-quote-approx',
      approximate_highlight_regions: [{ x0: 0.1, y0: 0.2, x1: 0.35, y1: 0.28, page: 3 }],
    }

    const { container } = render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={quoteWithApprox}
        evidenceList={[quoteWithApprox]}
        selectedEvidenceId="ev-quote-approx"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )

    await waitFor(() => {
      expect(
        screen.getByText(/approximate block highlight because the exact quote could not be matched/i)
      ).toBeInTheDocument()
      const overlays = container.querySelectorAll('div.absolute.pointer-events-none')
      expect(overlays.length).toBeGreaterThan(0)
      expect((overlays[0] as HTMLDivElement).style.border).toContain('dashed')
    })
  })

  it('defaults to 135% zoom for readability', () => {
    render(
      <EvidenceViewer
        runId="r1"
        pdfId="paper-a"
        evidence={quoteEvidence}
        evidenceList={[quoteEvidence]}
        selectedEvidenceId="ev1"
        activeEvidenceIndex={0}
        onSelectEvidence={onSelectEvidence}
        outputDir="./runs"
      />
    )

    expect(screen.getByText('135%')).toBeInTheDocument()
  })
})
