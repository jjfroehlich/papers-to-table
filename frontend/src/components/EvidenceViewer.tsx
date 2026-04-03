import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import type { EvidenceItem } from '../types'
import { api } from '../api/client'

pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url
).href

interface HighlightRegion {
  x0: number
  y0: number
  x1: number
  y1: number
  page: number
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
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null)
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [zoom, setZoom] = useState(1.0)
  const [pageInput, setPageInput] = useState('1')
  const [renderError, setRenderError] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [canvasSize, setCanvasSize] = useState({ width: 0, height: 0 })
  const [pdfPageSize, setPdfPageSize] = useState({ width: 0, height: 0 })
  const [openLocalError, setOpenLocalError] = useState<string | null>(null)
  const [openingLocal, setOpeningLocal] = useState(false)
  const renderTaskRef = useRef<pdfjsLib.RenderTask | null>(null)

  useEffect(() => {
    let cancelled = false
    let loadingTask: ReturnType<typeof pdfjsLib.getDocument> | null = null

    async function loadPdf() {
      if (!pdfId) {
        setPdfDoc(null)
        setTotalPages(0)
        setCurrentPage(1)
        setPageInput('1')
        setLoadError(null)
        return
      }
      setLoadError(null)
      const url = api.getPdfUrl(runId, pdfId, outputDir)
      try {
        loadingTask = pdfjsLib.getDocument(url)
        const doc = await loadingTask.promise
        if (!cancelled) {
          setPdfDoc(doc)
          setTotalPages(doc.numPages)
          setCurrentPage(1)
          setPageInput('1')
        }
      } catch (error) {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : String(error))
          setPdfDoc(null)
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
    if (evidence?.page_number == null) return
    const page = evidence.page_number
    setCurrentPage(page)
    setPageInput(String(page))
  }, [evidence])

  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    if (renderTaskRef.current) {
      renderTaskRef.current.cancel()
    }

    setRenderError(null)

    pdfDoc.getPage(currentPage).then((page) => {
      const unscaledViewport = page.getViewport({ scale: 1.0 })
      setPdfPageSize({ width: unscaledViewport.width, height: unscaledViewport.height })

      const viewport = page.getViewport({ scale: zoom })
      canvas.width = viewport.width
      canvas.height = viewport.height
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`
      setCanvasSize({ width: viewport.width, height: viewport.height })

      const task = page.render({ canvas, canvasContext: ctx, viewport })
      renderTaskRef.current = task
      return task.promise
    }).catch((error) => {
      if (error?.name !== 'RenderingCancelledException') {
        setRenderError(error instanceof Error ? error.message : String(error))
      }
    })
  }, [currentPage, pdfDoc, zoom])

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
    if (!regions || canvasSize.width === 0 || pdfPageSize.width === 0) return []
    const scaleX = canvasSize.width / pdfPageSize.width
    const scaleY = canvasSize.height / pdfPageSize.height
    return regions
      .filter((region) => region.page === currentPage)
      .map((region) => {
        const x = region.x0 * scaleX
        const y = (pdfPageSize.height - region.y1) * scaleY
        const w = (region.x1 - region.x0) * scaleX
        const h = (region.y1 - region.y0) * scaleY
        return { x, y, w, h }
      })
  }, [canvasSize.height, canvasSize.width, currentPage, pdfPageSize.height, pdfPageSize.width])

  const exactRegions = evidence?.exact_highlight_regions ?? null
  const approxRegions = evidence?.approximate_highlight_regions ?? null
  const exactHighlights = useMemo(() => getHighlights(exactRegions), [exactRegions, getHighlights])
  const approxHighlights = useMemo(() => getHighlights(approxRegions), [approxRegions, getHighlights])
  const activeHighlights = exactHighlights.length > 0 ? exactHighlights : approxHighlights
  const showTextFallback =
    evidence?.source_type === 'quote_plus_page' ||
    (!exactRegions && !approxRegions && evidence?.quote_text)

  useEffect(() => {
    const highlight = activeHighlights[0]
    const container = scrollRef.current
    if (!container || !highlight) return
    container.scrollTo({
      top: Math.max(0, highlight.y - container.clientHeight / 2 + highlight.h / 2),
      left: Math.max(0, highlight.x - container.clientWidth / 2 + highlight.w / 2),
      behavior: 'smooth',
    })
  }, [activeHighlights, evidence?.evidence_id, zoom])

  const isFigureEvidence =
    evidence?.source_type === 'caption_grounded_figure_evidence' ||
    evidence?.source_type === 'visual_interpretation_figure_evidence'

  const canCycleEvidence = evidenceList.length > 1

  if (isFigureEvidence && evidence?.figure_ref) {
    const figureUrl = api.getFigureUrl(runId, evidence.pdf_id, evidence.figure_ref, outputDir)
    return (
      <div className="flex flex-col h-full bg-gray-50">
        <div className="px-3 py-2 border-b border-gray-200 bg-white flex items-center gap-2">
          <span className="text-xs font-medium text-gray-600">Figure</span>
          <span className="text-xs text-purple-600 bg-purple-100 px-1.5 rounded">
            {evidence.figure_ref}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                if (!canCycleEvidence) return
                const previousIndex = activeEvidenceIndex > 0 ? activeEvidenceIndex - 1 : evidenceList.length - 1
                onSelectEvidence(evidenceList[previousIndex].evidence_id)
              }}
              disabled={!canCycleEvidence}
              className="rounded border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 disabled:opacity-40"
            >
              Previous evidence
            </button>
            <button
              type="button"
              onClick={() => {
                if (!canCycleEvidence) return
                const nextIndex = activeEvidenceIndex < evidenceList.length - 1 ? activeEvidenceIndex + 1 : 0
                onSelectEvidence(evidenceList[nextIndex].evidence_id)
              }}
              disabled={!canCycleEvidence}
              className="rounded border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-100 disabled:opacity-40"
            >
              Next evidence
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-auto flex items-start justify-center p-4">
          <img
            src={figureUrl}
            alt={`Figure ${evidence.figure_ref}`}
            className="max-w-full object-contain shadow-sm"
          />
        </div>
        {evidence.caption_text && (
          <div className="px-3 py-2 border-t border-gray-200 bg-white text-xs text-gray-600 italic">
            {evidence.caption_text}
          </div>
        )}
      </div>
    )
  }

  if (!pdfId) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-400">
        No PDF selected
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="flex items-center justify-center h-full p-4 text-sm text-red-600">
        PDF load error: {loadError}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="shrink-0 px-2 py-1.5 border-b border-gray-200 bg-white flex items-center gap-2 flex-wrap">
        <button
          onClick={() => goToPage(currentPage - 1)}
          disabled={currentPage <= 1}
          className="px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-100 disabled:opacity-40"
        >
          ‹
        </button>
        <div className="flex items-center gap-1 text-xs">
          <input
            type="number"
            min={1}
            max={totalPages}
            value={pageInput}
            onChange={(event) => setPageInput(event.target.value)}
            onBlur={handlePageInputBlur}
            onKeyDown={(event) => event.key === 'Enter' && handlePageInputBlur()}
            className="w-10 border border-gray-200 rounded px-1 py-0.5 text-center text-xs"
          />
          <span className="text-gray-400">/ {totalPages || '—'}</span>
        </div>
        <button
          onClick={() => goToPage(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-100 disabled:opacity-40"
        >
          ›
        </button>
        <div className="w-px h-4 bg-gray-200" />
        <button
          type="button"
          onClick={() => {
            if (!canCycleEvidence) return
            const previousIndex = activeEvidenceIndex > 0 ? activeEvidenceIndex - 1 : evidenceList.length - 1
            onSelectEvidence(evidenceList[previousIndex].evidence_id)
          }}
          disabled={!canCycleEvidence}
          className="px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-100 disabled:opacity-40"
        >
          Previous evidence
        </button>
        <span className="text-xs text-gray-500">
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
          className="px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-100 disabled:opacity-40"
        >
          Next evidence
        </button>
        <div className="w-px h-4 bg-gray-200" />
        <button
          onClick={() => setZoom((value) => Math.max(0.5, +(value - 0.25).toFixed(2)))}
          disabled={zoom <= 0.5}
          className="px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-100 disabled:opacity-40"
        >
          −
        </button>
        <span className="text-xs text-gray-600">{Math.round(zoom * 100)}%</span>
        <button
          onClick={() => setZoom((value) => Math.min(3.0, +(value + 0.25).toFixed(2)))}
          disabled={zoom >= 3.0}
          className="px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-100 disabled:opacity-40"
        >
          +
        </button>
        <button
          type="button"
          onClick={handleOpenInLocalViewer}
          disabled={!pdfId || openingLocal}
          className="ml-auto px-2 py-1 rounded text-xs border border-gray-200 text-gray-600 hover:bg-gray-100 disabled:opacity-40"
        >
          {openingLocal ? 'Opening…' : 'Open in Local PDF Viewer'}
        </button>
      </div>
      <div className="shrink-0 px-3 py-2 border-b border-gray-200 bg-gray-50 text-xs text-gray-600">
        This pane is optimized for evidence highlights. Use the local PDF viewer when you want standard reading behavior such as hand-pan, text selection, or full-document search.
      </div>
      <div ref={scrollRef} className="flex-1 overflow-auto p-3">
        {openLocalError && (
          <div className="mb-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
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
          {exactHighlights.map((highlight, index) => (
            <div
              key={`exact-${index}`}
              className="absolute pointer-events-none"
              style={{
                left: highlight.x,
                top: highlight.y,
                width: highlight.w,
                height: highlight.h,
                backgroundColor: 'rgba(59, 130, 246, 0.25)',
                border: '1px solid rgba(59, 130, 246, 0.7)',
                boxShadow: '0 0 0 2px rgba(59, 130, 246, 0.18)',
              }}
            />
          ))}
          {approxHighlights.map((highlight, index) => (
            <div
              key={`approx-${index}`}
              className="absolute pointer-events-none"
              style={{
                left: highlight.x,
                top: highlight.y,
                width: highlight.w,
                height: highlight.h,
                border: '2px dashed rgba(234, 88, 12, 0.7)',
                backgroundColor: 'rgba(234, 88, 12, 0.08)',
              }}
            >
              <span
                className="absolute -top-4 left-0 text-xs text-orange-600 bg-white px-0.5 rounded"
                style={{ fontSize: 9, lineHeight: '1rem' }}
              >
                Approx
              </span>
            </div>
          ))}
        </div>

        {showTextFallback && evidence?.quote_text && (
          <div className="mt-3 rounded border border-amber-200 bg-amber-50 p-3">
            <p className="text-xs font-medium text-amber-700 mb-1">
              Text fallback – exact highlighting unavailable
            </p>
            <p className="text-xs text-amber-900 italic">"{evidence.quote_text}"</p>
          </div>
        )}
      </div>
    </div>
  )
}
