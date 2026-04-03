import { useEffect, useRef, useState } from 'react'
import * as pdfjsLib from 'pdfjs-dist'
import type { EvidenceItem } from '../types'
import { api } from '../api/client'

// Set worker source before any PDF operations
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
  outputDir: string
}

export function EvidenceViewer({ runId, pdfId, evidence, outputDir }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
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

  // Load PDF when pdfId changes
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
      } catch (err) {
        if (!cancelled) {
          setLoadError(err instanceof Error ? err.message : String(err))
          setPdfDoc(null)
        }
      }
    }
    loadPdf()
    return () => {
      cancelled = true
      if (loadingTask && typeof loadingTask.destroy === 'function') {
        void loadingTask.destroy()
      }
    }
  }, [pdfId, runId, outputDir])

  // Navigate to evidence page when evidence changes
  useEffect(() => {
    if (evidence?.page_number != null) {
      const page = evidence.page_number
      Promise.resolve().then(() => {
        setCurrentPage(page)
        setPageInput(String(page))
      })
    }
  }, [evidence])

  // Render page when doc/page/zoom changes
  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    // Cancel any in-flight render
    if (renderTaskRef.current) {
      renderTaskRef.current.cancel()
    }

    Promise.resolve().then(() => setRenderError(null))

    pdfDoc.getPage(currentPage).then((page) => {
      // Store unscaled page dimensions (PDF points) for coordinate conversion
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
    }).catch((err) => {
      if (err?.name !== 'RenderingCancelledException') {
        setRenderError(err instanceof Error ? err.message : String(err))
      }
    })
  }, [pdfDoc, currentPage, zoom])

  function goToPage(n: number) {
    const clamped = Math.max(1, Math.min(n, totalPages))
    setCurrentPage(clamped)
    setPageInput(String(clamped))
  }

  function handlePageInputBlur() {
    const n = parseInt(pageInput, 10)
    if (!isNaN(n)) goToPage(n)
    else setPageInput(String(currentPage))
  }

  async function handleOpenInLocalViewer() {
    if (!pdfId || openingLocal) {
      return
    }
    setOpeningLocal(true)
    setOpenLocalError(null)
    try {
      await api.openPdfInLocalViewer(runId, pdfId, outputDir)
    } catch (err) {
      setOpenLocalError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningLocal(false)
    }
  }

  // Compute highlight boxes relative to current rendered canvas.
  // Evidence coordinates are in PDF points (same space as pdfPageSize).
  // PDF origin is bottom-left; canvas origin is top-left.
  function getHighlights(regions: HighlightRegion[] | null) {
    if (!regions || canvasSize.width === 0 || pdfPageSize.width === 0) return []
    const scaleX = canvasSize.width / pdfPageSize.width
    const scaleY = canvasSize.height / pdfPageSize.height
    return regions
      .filter((r) => r.page === currentPage)
      .map((r) => {
        const x = r.x0 * scaleX
        const y = (pdfPageSize.height - r.y1) * scaleY  // flip Y axis
        const w = (r.x1 - r.x0) * scaleX
        const h = (r.y1 - r.y0) * scaleY
        return { x, y, w, h }
      })
  }

  const isFigureEvidence =
    evidence?.source_type === 'caption_grounded_figure_evidence' ||
    evidence?.source_type === 'visual_interpretation_figure_evidence'

  if (isFigureEvidence && evidence?.figure_ref) {
    const figUrl = api.getFigureUrl(runId, evidence.pdf_id, evidence.figure_ref, outputDir)
    return (
      <div className="flex flex-col h-full bg-gray-50">
        <div className="px-3 py-2 border-b border-gray-200 bg-white flex items-center gap-2">
          <span className="text-xs font-medium text-gray-600">Figure</span>
          <span className="text-xs text-purple-600 bg-purple-100 px-1.5 rounded">
            {evidence.figure_ref}
          </span>
        </div>
        <div className="flex-1 overflow-auto flex items-start justify-center p-4">
          <img
            src={figUrl}
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

  // Determine highlight regions
  const exactRegions = evidence?.exact_highlight_regions ?? null
  const approxRegions = evidence?.approximate_highlight_regions ?? null
  const exactHighlights = getHighlights(exactRegions)
  const approxHighlights = getHighlights(approxRegions)
  const showTextFallback =
    evidence?.source_type === 'quote_plus_page' ||
    (!exactRegions && !approxRegions && evidence?.quote_text)

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Toolbar */}
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
            onChange={(e) => setPageInput(e.target.value)}
            onBlur={handlePageInputBlur}
            onKeyDown={(e) => e.key === 'Enter' && handlePageInputBlur()}
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
          onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))}
          disabled={zoom <= 0.5}
          className="px-2 py-1 rounded text-xs border border-gray-200 hover:bg-gray-100 disabled:opacity-40"
        >
          −
        </button>
        <span className="text-xs text-gray-600">{Math.round(zoom * 100)}%</span>
        <button
          onClick={() => setZoom((z) => Math.min(3.0, +(z + 0.25).toFixed(2)))}
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
      <div className="flex-1 overflow-auto p-3">
        {openLocalError && (
          <div className="mb-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            Could not open the local PDF viewer: {openLocalError}
          </div>
        )}
        {renderError && (
          <div className="text-xs text-red-600 mb-2">Render error: {renderError}</div>
        )}
        <div
          ref={overlayRef}
          className="relative inline-block"
          style={{ width: canvasSize.width || undefined }}
        >
          <canvas ref={canvasRef} className="shadow-md" />
          {exactHighlights.map((h, i) => (
            <div
              key={`exact-${i}`}
              className="absolute pointer-events-none"
              style={{
                left: h.x,
                top: h.y,
                width: h.w,
                height: h.h,
                backgroundColor: 'rgba(59, 130, 246, 0.25)',
                border: '1px solid rgba(59, 130, 246, 0.6)',
              }}
            />
          ))}
          {approxHighlights.map((h, i) => (
            <div
              key={`approx-${i}`}
              className="absolute pointer-events-none"
              style={{
                left: h.x,
                top: h.y,
                width: h.w,
                height: h.h,
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
