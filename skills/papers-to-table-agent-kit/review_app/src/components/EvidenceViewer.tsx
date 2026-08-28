import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import pdfWorkerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'
import type { EvidenceItem } from '../types'
import { api } from '../api/client'

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl

interface HighlightRegion {
  x0: number
  y0: number
  x1: number
  y1: number
  page: number
}

interface HighlightBox {
  x: number
  y: number
  w: number
  h: number
}

interface PageBounds {
  xMin: number
  yMin: number
  width: number
  height: number
}

interface ViewportLike {
  width: number
  height: number
  scale: number
  transform: number[]
}

interface PdfTextItemLike {
  str: string
  transform: number[]
  width: number
  height: number
}

interface TextFragment extends HighlightBox {
  tokenText: string
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

function inferEvidencePage(evidence: EvidenceItem | null): number | null {
  if (!evidence) return null
  if (evidence.page_number && Number.isFinite(evidence.page_number) && evidence.page_number > 0) {
    return evidence.page_number
  }

  const regions = [
    ...(evidence.exact_highlight_regions ?? []),
    ...(evidence.approximate_highlight_regions ?? []),
  ]
  for (const region of regions) {
    if (region.page && Number.isFinite(region.page) && region.page > 0) {
      return region.page
    }
  }
  return null
}

function mapHighlightRegions(
  regions: HighlightRegion[] | null,
  currentPage: number,
  canvasSize: { width: number; height: number },
  pdfPageSize: { width: number; height: number },
  pageBounds: PageBounds | null,
): HighlightBox[] {
  if (!regions || canvasSize.width === 0 || canvasSize.height === 0 || pdfPageSize.width === 0 || pdfPageSize.height === 0) {
    return []
  }
  const boxes: HighlightBox[] = []

  for (const region of regions) {
    if (region.page !== currentPage) continue
    const raw = [region.x0, region.y0, region.x1, region.y1]
    if (raw.some((value) => !Number.isFinite(value))) continue

    const mapped = computeRegionBox(region, canvasSize, pdfPageSize, pageBounds)
    const w = mapped.w
    const h = mapped.h
    if (w <= 0.5 || h <= 0.5) continue

    boxes.push(mapped)
  }

  return boxes
}

function computeRegionBox(
  region: HighlightRegion,
  canvasSize: { width: number; height: number },
  pdfPageSize: { width: number; height: number },
  pageBounds: PageBounds | null,
): HighlightBox {
  const isNormalized =
    Math.max(Math.abs(region.x0), Math.abs(region.x1), Math.abs(region.y0), Math.abs(region.y1)) <= 1.05

  let x: number
  let y: number
  let w: number
  let h: number

  if (isNormalized) {
    const xMin = clamp(Math.min(region.x0, region.x1), 0, 1)
    const xMax = clamp(Math.max(region.x0, region.x1), 0, 1)
    const yMin = clamp(Math.min(region.y0, region.y1), 0, 1)
    const yMax = clamp(Math.max(region.y0, region.y1), 0, 1)
    x = xMin * canvasSize.width
    y = (1 - yMax) * canvasSize.height
    w = (xMax - xMin) * canvasSize.width
    h = (yMax - yMin) * canvasSize.height
  } else {
    const bounds = pageBounds ?? { xMin: 0, yMin: 0, width: pdfPageSize.width, height: pdfPageSize.height }
    const xMin = clamp(Math.min(region.x0, region.x1), bounds.xMin, bounds.xMin + bounds.width)
    const xMax = clamp(Math.max(region.x0, region.x1), bounds.xMin, bounds.xMin + bounds.width)
    const yMin = clamp(Math.min(region.y0, region.y1), bounds.yMin, bounds.yMin + bounds.height)
    const yMax = clamp(Math.max(region.y0, region.y1), bounds.yMin, bounds.yMin + bounds.height)
    const scaleX = canvasSize.width / Math.max(bounds.width, 1)
    const scaleY = canvasSize.height / Math.max(bounds.height, 1)
    x = (xMin - bounds.xMin) * scaleX
    y = ((bounds.yMin + bounds.height) - yMax) * scaleY
    w = (xMax - xMin) * scaleX
    h = (yMax - yMin) * scaleY
  }

  const clampedX = clamp(x, 0, canvasSize.width)
  const clampedY = clamp(y, 0, canvasSize.height)
  const maxWidth = Math.max(0, canvasSize.width - clampedX)
  const maxHeight = Math.max(0, canvasSize.height - clampedY)
  return {
    x: clampedX,
    y: clampedY,
    w: clamp(w, 0, maxWidth),
    h: clamp(h, 0, maxHeight),
  }
}

function isPdfTextItem(value: unknown): value is PdfTextItemLike {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as Partial<PdfTextItemLike>
  return (
    typeof candidate.str === 'string'
    && Array.isArray(candidate.transform)
    && typeof candidate.width === 'number'
    && typeof candidate.height === 'number'
  )
}

function multiplyTransforms(first: number[], second: number[]): number[] {
  return [
    first[0] * second[0] + first[2] * second[1],
    first[1] * second[0] + first[3] * second[1],
    first[0] * second[2] + first[2] * second[3],
    first[1] * second[2] + first[3] * second[3],
    first[0] * second[4] + first[2] * second[5] + first[4],
    first[1] * second[4] + first[3] * second[5] + first[5],
  ]
}

function normalizeSearchText(text: string): string {
  return text
    .normalize('NFKC')
    .toLowerCase()
    .replace(/\u00a0/g, ' ')
    .replace(/[“”„‟«»]/g, '"')
    .replace(/[‘’‚‛]/g, "'")
    .replace(/[‐‑‒–—−]/g, '-')
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function tokenizeSearchText(text: string): string[] {
  const normalized = normalizeSearchText(text)
  return normalized ? normalized.split(' ') : []
}

function extractTextFragments(items: unknown[], viewport: ViewportLike): TextFragment[] {
  const fragments: TextFragment[] = []

  for (const item of items) {
    if (!isPdfTextItem(item)) continue

    const tokenText = normalizeSearchText(item.str)
    if (!tokenText) continue

    const transform = multiplyTransforms(viewport.transform, item.transform)
    const height = Math.max(Math.hypot(transform[2], transform[3]) || Math.abs(item.height * viewport.scale), 1)
    const width = Math.max(Math.abs(item.width * viewport.scale), 1)
    const x = clamp(transform[4], 0, viewport.width)
    const y = clamp(transform[5] - height, 0, viewport.height)
    const w = clamp(width, 0, Math.max(0, viewport.width - x))
    const h = clamp(height, 0, Math.max(0, viewport.height - y))
    if (w <= 0.5 || h <= 0.5) continue

    fragments.push({ x, y, w, h, tokenText })
  }

  return fragments
}

function findTokenSequence(pageTokens: string[], quoteTokens: string[], quoteStart: number, length: number): number {
  const lastStart = pageTokens.length - length
  outer: for (let pageStart = 0; pageStart <= lastStart; pageStart += 1) {
    for (let offset = 0; offset < length; offset += 1) {
      if (pageTokens[pageStart + offset] !== quoteTokens[quoteStart + offset]) {
        continue outer
      }
    }
    return pageStart
  }
  return -1
}

function findBestTokenSpan(pageTokens: string[], quoteTokens: string[]): { start: number; end: number } | null {
  if (pageTokens.length === 0 || quoteTokens.length === 0) return null

  for (let windowLength = quoteTokens.length; windowLength >= 1; windowLength -= 1) {
    for (let quoteStart = 0; quoteStart + windowLength <= quoteTokens.length; quoteStart += 1) {
      const pageStart = findTokenSequence(pageTokens, quoteTokens, quoteStart, windowLength)
      if (pageStart !== -1) {
        return { start: pageStart, end: pageStart + windowLength - 1 }
      }
    }

    if (windowLength <= 6 && quoteTokens.length > 24) {
      break
    }
  }
  return null
}

function mergeFragmentBoxes(fragments: TextFragment[], viewport: { width: number; height: number }): HighlightBox[] {
  if (fragments.length === 0) return []

  const ordered = [...fragments].sort((left, right) => {
    if (Math.abs(left.y - right.y) > 3) return left.y - right.y
    return left.x - right.x
  })

  const merged: HighlightBox[] = []
  for (const fragment of ordered) {
    const current = {
      x: clamp(fragment.x - 2, 0, viewport.width),
      y: clamp(fragment.y - 1, 0, viewport.height),
      w: clamp(fragment.w + 4, 0, viewport.width),
      h: clamp(fragment.h + 2, 0, viewport.height),
    }

    const previous = merged.at(-1)
    if (!previous) {
      merged.push(current)
      continue
    }

    const previousMid = previous.y + previous.h / 2
    const currentMid = current.y + current.h / 2
    const sameLine = Math.abs(previousMid - currentMid) <= Math.max(previous.h, current.h) * 0.7
    const closeEnough = current.x <= previous.x + previous.w + 24

    if (sameLine && closeEnough) {
      const nextX = Math.min(previous.x, current.x)
      const nextY = Math.min(previous.y, current.y)
      const nextRight = Math.max(previous.x + previous.w, current.x + current.w)
      const nextBottom = Math.max(previous.y + previous.h, current.y + current.h)
      merged[merged.length - 1] = {
        x: nextX,
        y: nextY,
        w: clamp(nextRight - nextX, 0, viewport.width - nextX),
        h: clamp(nextBottom - nextY, 0, viewport.height - nextY),
      }
      continue
    }

    merged.push(current)
  }

  return merged
}

function buildQuoteHighlightBoxes(items: unknown[], viewport: ViewportLike, quoteText: string): HighlightBox[] {
  const fragments = extractTextFragments(items, viewport)
  if (fragments.length === 0) return []

  const quoteTokens = tokenizeSearchText(quoteText)
  if (quoteTokens.length === 0) return []

  const pageTokens: Array<{ token: string; fragmentIndex: number }> = []
  fragments.forEach((fragment, fragmentIndex) => {
    const tokens = fragment.tokenText.split(' ').filter(Boolean)
    tokens.forEach((token) => {
      pageTokens.push({ token, fragmentIndex })
    })
  })

  const tokenSpan = findBestTokenSpan(
    pageTokens.map((entry) => entry.token),
    quoteTokens,
  )
  if (!tokenSpan) return []

  const fragmentIndexes = new Set<number>()
  for (let index = tokenSpan.start; index <= tokenSpan.end; index += 1) {
    fragmentIndexes.add(pageTokens[index].fragmentIndex)
  }

  return mergeFragmentBoxes(
    fragments.filter((_, index) => fragmentIndexes.has(index)),
    { width: viewport.width, height: viewport.height },
  )
}

interface Props {
  runId: string
  pdfId: string | null
  evidence: EvidenceItem | null
  evidenceList: EvidenceItem[]
  selectedEvidenceId: string | null
  activeEvidenceIndex: number
  onSelectEvidence: (evidenceId: string) => void
  outputDir: string
}

const DEFAULT_PDF_ZOOM = 1.35

export function EvidenceViewer({
  runId,
  pdfId,
  evidence,
  evidenceList,
  selectedEvidenceId,
  activeEvidenceIndex,
  onSelectEvidence,
  outputDir,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const highlightRef = useRef<HTMLDivElement>(null)
  const [loadedPdf, setLoadedPdf] = useState<{ pdfId: string; doc: pdfjsLib.PDFDocumentProxy } | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [zoom, setZoom] = useState(DEFAULT_PDF_ZOOM)
  const [pageInput, setPageInput] = useState('1')
  const [renderError, setRenderError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 })
  const [pdfPageSize, setPdfPageSize] = useState({ width: 0, height: 0 })
  const [pageBounds, setPageBounds] = useState<PageBounds | null>(null)
  const [quoteHighlights, setQuoteHighlights] = useState<HighlightBox[]>([])
  const [openLocalError, setOpenLocalError] = useState<string | null>(null)
  const [openingLocal, setOpeningLocal] = useState(false)
  const [showFigureFullPage, setShowFigureFullPage] = useState(false)
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null)
  const autoFocusKeyRef = useRef<string | null>(null)
  const renderSequenceRef = useRef(0)
  const evidencePage = useMemo(() => inferEvidencePage(evidence), [evidence])
  const evidenceHighlightText = useMemo(() => (
    evidence?.quote_text ||
    evidence?.table_text ||
    evidence?.evidence_text ||
    evidence?.caption_text ||
    ''
  ), [evidence])
  const pdfDoc = loadedPdf?.pdfId === pdfId ? loadedPdf.doc : null

  useEffect(() => {
    let cancelled = false
    let loadingTask: ReturnType<typeof pdfjsLib.getDocument> | null = null

    async function loadPdf() {
      if (!pdfId) {
        setLoadedPdf(null)
        setTotalPages(0)
        setCurrentPage(1)
        setPageInput('1')
        setLoadError(null)
        setQuoteHighlights([])
        setPageBounds(null)
        return
      }
      if (!api.isServed()) {
        setLoadedPdf(null)
        setTotalPages(0)
        setCurrentPage(1)
        setPageInput('1')
        setLoadError(null)
        setQuoteHighlights([])
        setPageBounds(null)
        return
      }
      setLoadError(null)
      const url = api.getPdfUrl(runId, pdfId, outputDir)
      try {
        if (cancelled) return
        loadingTask = pdfjsLib.getDocument(url)
        const doc = await loadingTask.promise
        if (!cancelled) {
          setLoadedPdf({ pdfId, doc })
          setTotalPages(doc.numPages)
          setCurrentPage(1)
          setPageInput('1')
        }
      } catch (error) {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : String(error))
          setLoadedPdf(null)
        }
      }
    }

    void loadPdf()
    return () => {
      cancelled = true
      if (loadingTask && typeof loadingTask.destroy === 'function') {
        void loadingTask.destroy()
      }
    }
  }, [outputDir, pdfId, runId])

  useEffect(() => {
    if (!evidencePage) return
    const page = totalPages > 0 ? clamp(evidencePage, 1, totalPages) : evidencePage
    setCurrentPage(page)
    setPageInput(String(page))
  }, [evidencePage, totalPages])

  useEffect(() => {
    setShowFigureFullPage(false)
  }, [evidence?.evidence_id])

  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return
    let cancelled = false
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    const sequence = ++renderSequenceRef.current

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel()
    }

    setRenderError(null)

    const safePage = clamp(currentPage, 1, pdfDoc.numPages)
    if (safePage !== currentPage) {
      setCurrentPage(safePage)
      setPageInput(String(safePage))
      return
    }

    Promise.resolve().then(() => {
      if (cancelled || renderSequenceRef.current !== sequence) return null
      return pdfDoc.getPage(safePage)
    }).then((page) => {
      if (!page || cancelled || renderSequenceRef.current !== sequence) return
      const unscaledViewport = page.getViewport({ scale: 1.0 })
      setPdfPageSize({ width: unscaledViewport.width, height: unscaledViewport.height })
      const [xMin, yMin, xMax, yMax] = page.view
      setPageBounds({ xMin, yMin, width: xMax - xMin, height: yMax - yMin })

      const viewport = page.getViewport({ scale: zoom })
      canvas.width = viewport.width
      canvas.height = viewport.height
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`
      setCanvasSize({ width: viewport.width, height: viewport.height })

      const task = page.render({ canvas, canvasContext: ctx, viewport })
      renderTaskRef.current = task
      return task.promise.then(async () => {
        if (cancelled || renderSequenceRef.current !== sequence) return
        if (!evidenceHighlightText || !evidencePage || safePage !== evidencePage) {
          setQuoteHighlights([])
          return
        }
        const textContent = await page.getTextContent()
        if (cancelled || renderSequenceRef.current !== sequence) return
        setQuoteHighlights(buildQuoteHighlightBoxes(textContent.items, viewport as ViewportLike, evidenceHighlightText))
      })
    }).catch((error) => {
      if (cancelled || renderSequenceRef.current !== sequence) return
      if (error?.name !== 'RenderingCancelledException') {
        setRenderError(error instanceof Error ? error.message : String(error))
      }
      setQuoteHighlights([])
    })

    return () => {
      cancelled = true
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel()
      }
    }
  }, [currentPage, evidenceHighlightText, evidencePage, pdfDoc, zoom])

  function goToPage(pageNumber: number) {
    const clamped = Math.max(1, Math.min(pageNumber, totalPages))
    setCurrentPage(clamped)
    setPageInput(String(clamped))
  }

  function handlePageInputBlur() {
    const pageNumber = parseInt(pageInput, 10)
    if (!Number.isNaN(pageNumber)) {
      goToPage(pageNumber)
      return
    }
    setPageInput(String(currentPage))
  }

  async function handleOpenInLocalViewer() {
    if (!pdfId || openingLocal) return
    setOpeningLocal(true)
    setOpenLocalError(null)
    try {
      await api.openPdfInLocalViewer(runId, pdfId, outputDir)
    } catch (error) {
      setOpenLocalError(error instanceof Error ? error.message : String(error))
    } finally {
      setOpeningLocal(false)
    }
  }

  const getHighlights = useCallback((regions: HighlightRegion[] | null) => {
    return mapHighlightRegions(regions, currentPage, canvasSize, pdfPageSize, pageBounds)
  }, [canvasSize, currentPage, pageBounds, pdfPageSize])

  const exactRegions = evidence?.exact_highlight_regions ?? null
  const approxRegions = evidence?.approximate_highlight_regions ?? null
  const exactHighlights = useMemo(() => getHighlights(exactRegions), [exactRegions, getHighlights])
  const approxHighlights = useMemo(() => getHighlights(approxRegions), [approxRegions, getHighlights])
  const usingQuoteHighlights = currentPage === evidencePage && quoteHighlights.length > 0
  const usingExactHighlights = !usingQuoteHighlights && exactHighlights.length > 0
  const usingApproxHighlights = !usingQuoteHighlights && !usingExactHighlights && approxHighlights.length > 0
  const resolvedHighlights = usingQuoteHighlights
    ? quoteHighlights
    : usingExactHighlights
      ? exactHighlights
      : approxHighlights
  const usingApproximateFallbackForQuote =
    usingApproxHighlights &&
    currentPage === evidencePage &&
    Boolean(evidenceHighlightText)
  const showTextFallback =
    evidence?.source_type === 'quote_plus_page' ||
    (!exactRegions && !approxRegions && Boolean(evidenceHighlightText))

  useEffect(() => {
    if (currentPage !== evidencePage) {
      autoFocusKeyRef.current = null
    }
  }, [currentPage, evidencePage])

  useEffect(() => {
    const container = scrollRef.current
    const box = highlightRef.current
    if (!container || !box || resolvedHighlights.length === 0) return

    const focusKey = `${evidence?.evidence_id ?? 'none'}:${currentPage}:${zoom}`
    if (autoFocusKeyRef.current === focusKey) return

    container.scrollTo({
      top: Math.max(box.offsetTop - container.clientHeight * 0.25, 0),
      left: Math.max(box.offsetLeft - container.clientWidth * 0.25, 0),
      behavior: 'smooth',
    })
    autoFocusKeyRef.current = focusKey
  }, [currentPage, evidence?.evidence_id, resolvedHighlights, zoom])

  const isFigureEvidence =
    evidence?.source_type === 'caption_grounded_figure_evidence' ||
    evidence?.source_type === 'visual_interpretation_figure_evidence'

  const canCycleEvidence = evidenceList.length > 1
  const evidenceQualityLabel = isFigureEvidence
    ? 'Figure evidence'
    : quoteHighlights.length > 0
      ? 'Quote-anchored highlight'
    : exactHighlights.length > 0
      ? 'Exact quote highlight'
      : approxHighlights.length > 0
        ? 'Approximate region highlight'
        : showTextFallback
          ? 'Quote + page fallback'
          : 'Paper evidence'

  if (isFigureEvidence && evidence?.figure_ref) {
    const figureUrl = api.getFigureUrl(runId, evidence.pdf_id, evidence.figure_ref, outputDir)
    const figurePageNumber = inferEvidencePage(evidence)
    const hasFullPageContext = Boolean(figurePageNumber)
    const fullPageUrl = hasFullPageContext
      ? api.getPageImageUrl(runId, evidence.pdf_id, figurePageNumber as number, outputDir)
      : null
    return (
      <div className="flex h-full min-h-0 flex-col bg-white">
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2" data-testid="evidence-toolbar">
          <span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-600">{evidenceQualityLabel}</span>
          <span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">
            {evidence.figure_ref}
          </span>
          <span className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600">
            Figure-derived
          </span>
          <div className="ml-auto flex items-center gap-2">
            {hasFullPageContext && (
              <button
                type="button"
                onClick={() => setShowFigureFullPage((value) => !value)}
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                {showFigureFullPage ? 'Hide full page' : 'Show full page'}
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                if (!canCycleEvidence) return
                const previousIndex = activeEvidenceIndex > 0 ? activeEvidenceIndex - 1 : evidenceList.length - 1
                onSelectEvidence(evidenceList[previousIndex].evidence_id)
              }}
              disabled={!canCycleEvidence}
              title="Previous evidence (Ctrl/⌘ + ←)"
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
             >
               Prev
             </button>
            <button
              type="button"
              onClick={() => {
                if (!canCycleEvidence) return
                const nextIndex = activeEvidenceIndex < evidenceList.length - 1 ? activeEvidenceIndex + 1 : 0
                onSelectEvidence(evidenceList[nextIndex].evidence_id)
              }}
              disabled={!canCycleEvidence}
              title="Next evidence (Ctrl/⌘ + →)"
                className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
             >
               Next
             </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto p-4" data-testid="evidence-scroll-region">
          <div className="w-full flex flex-col items-center gap-3">
            <img
              src={figureUrl}
              alt={`Figure ${evidence.figure_ref}`}
              className="max-w-full object-contain shadow-sm"
            />
            {showFigureFullPage && fullPageUrl && (
              <div className="w-full border border-slate-200 rounded bg-white p-2">
                <p className="mb-2 text-xs font-medium text-slate-600">
                  Full-page context (page {figurePageNumber})
                </p>
                <img
                  src={fullPageUrl}
                  alt={`Full page ${figurePageNumber}`}
                  className="max-w-full object-contain shadow-sm"
                />
              </div>
            )}
          </div>
        </div>
        {evidence.caption_text && (
          <div className="px-3 py-2 border-t border-slate-200 bg-white text-xs text-slate-600 italic">
            {evidence.caption_text}
          </div>
        )}
      </div>
    )
  }

  if (!pdfId) {
    return (
      <div className="flex h-full items-center justify-center px-6 text-center text-sm text-slate-400">
        No PDF selected
      </div>
    )
  }

  if (!api.isServed()) {
    return (
      <div className="flex h-full flex-col justify-center gap-3 bg-white p-5 text-sm text-slate-600">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-amber-900">
          PDF rendering and quote highlights require localhost serving. Start serve_review.py for this run, then open the human_review URL.
        </div>
        {evidenceHighlightText && (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3">
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Evidence text</p>
            <p className="text-xs italic text-slate-800">"{evidenceHighlightText}"</p>
          </div>
        )}
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="flex h-full items-center justify-center p-4 text-sm text-red-600">
        PDF load error: {loadError}
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col bg-white">
      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-slate-200 bg-slate-50 px-3 py-2" data-testid="evidence-toolbar">
        <button
          onClick={() => goToPage(currentPage - 1)}
          disabled={currentPage <= 1}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          ‹
        </button>
        <div className="flex items-center gap-1 text-xs text-slate-600">
          <input
            type="number"
            min={1}
            max={totalPages}
            value={pageInput}
            onChange={(event) => setPageInput(event.target.value)}
            onBlur={handlePageInputBlur}
            onKeyDown={(event) => event.key === 'Enter' && handlePageInputBlur()}
            className="w-12 rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-center text-xs text-slate-600"
          />
            <span className="text-slate-400">/ {totalPages || '—'}</span>
        </div>
        <button
          onClick={() => goToPage(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          ›
        </button>
        <div className="h-4 w-px bg-slate-200" />
        <button
          type="button"
          onClick={() => {
            if (!canCycleEvidence) return
            const previousIndex = activeEvidenceIndex > 0 ? activeEvidenceIndex - 1 : evidenceList.length - 1
            onSelectEvidence(evidenceList[previousIndex].evidence_id)
          }}
          disabled={!canCycleEvidence}
          title="Previous evidence (Ctrl/⌘ + ←)"
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          Prev
        </button>
         <span className="text-xs text-slate-500">
           {selectedEvidenceId && activeEvidenceIndex >= 0 ? `${activeEvidenceIndex + 1} / ${evidenceList.length}` : 'No evidence'}
         </span>
        <button
          type="button"
          onClick={() => {
            if (!canCycleEvidence) return
            const nextIndex = activeEvidenceIndex < evidenceList.length - 1 ? activeEvidenceIndex + 1 : 0
            onSelectEvidence(evidenceList[nextIndex].evidence_id)
          }}
          disabled={!canCycleEvidence}
          title="Next evidence (Ctrl/⌘ + →)"
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          Next
        </button>
        <div className="h-4 w-px bg-slate-200" />
        <button
          onClick={() => setZoom((value) => Math.max(0.5, +(value - 0.25).toFixed(2)))}
          disabled={zoom <= 0.5}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          −
        </button>
         <span className="text-xs text-slate-600">{Math.round(zoom * 100)}%</span>
        <button
          onClick={() => setZoom((value) => Math.min(3.0, +(value + 0.25).toFixed(2)))}
          disabled={zoom >= 3.0}
          className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          +
        </button>
        <button
          type="button"
          onClick={handleOpenInLocalViewer}
          disabled={!pdfId || openingLocal}
          className="ml-auto rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-40"
        >
          {openingLocal ? 'Opening…' : 'Open PDF'}
        </button>
      </div>
      <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto p-3" data-testid="evidence-scroll-region">
        {openLocalError && (
          <div className="mb-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            Could not open the local PDF viewer: {openLocalError}
          </div>
        )}
        {renderError && (
          <div className="text-xs text-red-600 mb-2">Render error: {renderError}</div>
        )}
        <div
          className="relative inline-block"
          style={{ width: canvasSize.width || undefined }}
        >
          <canvas ref={canvasRef} className="shadow-md" />
          {resolvedHighlights.map((highlight, index) => (
            <div
              key={`highlight-${index}`}
              ref={index === 0 ? highlightRef : undefined}
              className="absolute pointer-events-none"
              style={{
                left: highlight.x,
                top: highlight.y,
                width: highlight.w,
                height: highlight.h,
                backgroundColor: usingQuoteHighlights
                  ? 'rgba(255, 220, 0, 0.28)'
                  : usingExactHighlights
                    ? 'rgba(59, 130, 246, 0.25)'
                    : 'rgba(234, 88, 12, 0.08)',
                border: usingQuoteHighlights
                  ? '2px solid rgba(200, 160, 0, 0.8)'
                  : usingExactHighlights
                    ? '1px solid rgba(59, 130, 246, 0.7)'
                    : '2px dashed rgba(234, 88, 12, 0.7)',
                boxShadow: usingExactHighlights ? '0 0 0 2px rgba(59, 130, 246, 0.18)' : undefined,
                borderRadius: '2px',
              }}
            >
              {usingApproxHighlights && index === 0 && (
                <span
                  className="absolute -top-4 left-0 text-xs text-orange-600 bg-white px-0.5 rounded"
                  style={{ fontSize: 9, lineHeight: '1rem' }}
                >
                  Approx
                </span>
              )}
            </div>
          ))}
        </div>

        {showTextFallback && evidenceHighlightText && (
          <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-medium text-amber-700 mb-1">
              Text fallback – exact highlighting unavailable
            </p>
            <p className="text-xs text-amber-900 italic">"{evidenceHighlightText}"</p>
          </div>
        )}

        {usingApproximateFallbackForQuote && (
          <p className="mt-2 text-xs text-slate-500">
            Showing an approximate block highlight because the exact quote could not be matched in the rendered page text.
          </p>
        )}
      </div>
    </div>
  )
}
