/**
 * T086–T089 — Evidence viewer pane.
 *
 * Uses pdfjs-dist for text evidence display with highlight overlay (T086–T087).
 * Falls back to quote+page display when coordinates are missing or invalid (T088).
 * Shows figure evidence crop-first with caption and full-page access (T089).
 *
 * The parent should pass a `key` prop tied to the proposal_id to reset the
 * internal tab selection whenever the proposal changes.
 */
import { useEffect, useRef, useState } from 'react'
import * as pdfjs from 'pdfjs-dist'
import type { PDFPageProxy, RenderTask } from 'pdfjs-dist'
import type { EvidenceRecord } from '../types'
import { getFigureCropUrl, getPageImageUrl, getPdfUrl } from '../api'

// Configure pdfjs worker
pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface Props {
  runId: string
  evidence: EvidenceRecord[]
}

export function EvidenceViewer({ runId, evidence }: Props) {
  const [selectedIdx, setSelectedIdx] = useState(0)

  if (evidence.length === 0) {
    return (
      <div className="evidence-viewer evidence-empty">
        <p className="muted">No evidence records for this proposal.</p>
      </div>
    )
  }

  const current = evidence[Math.min(selectedIdx, evidence.length - 1)]

  return (
    <div className="evidence-viewer">
      {evidence.length > 1 && (
        <div className="evidence-tabs" role="tablist">
          {evidence.map((ev, i) => (
            <button
              key={ev.evidence_id}
              role="tab"
              aria-selected={i === selectedIdx}
              className={i === selectedIdx ? 'active' : ''}
              onClick={() => setSelectedIdx(i)}
              title={ev.source_type}
            >
              {evidenceTabLabel(ev, i)}
            </button>
          ))}
        </div>
      )}

      <div className="evidence-content">
        {current.source_type === 'text_quote' || current.source_type === 'full_page' ? (
          <TextEvidencePanel key={current.evidence_id} runId={runId} evidence={current} />
        ) : (
          <FigureEvidencePanel runId={runId} evidence={current} />
        )}
      </div>
    </div>
  )
}

function evidenceTabLabel(ev: EvidenceRecord, idx: number): string {
  if (ev.source_type === 'text_quote') return `Text p.${ev.page ?? '?'}`
  if (ev.source_type === 'figure_crop') return `Figure ${ev.figure_ref ?? idx + 1}`
  if (ev.source_type === 'caption') return `Caption ${idx + 1}`
  if (ev.source_type === 'full_page') return `Page ${ev.page ?? idx + 1}`
  return `Evidence ${idx + 1}`
}

// ---------------------------------------------------------------------------
// Text evidence — PDF.js canvas with highlight overlay (T086-T087)
// Falls back to quote+page when coordinates are unavailable (T088)
// ---------------------------------------------------------------------------

interface TextPanelProps {
  runId: string
  evidence: EvidenceRecord
}

function TextEvidencePanel({ runId, evidence }: TextPanelProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [renderError, setRenderError] = useState<string | null>(null)
  const [useFallback, setUseFallback] = useState(false)
  const [pdfDimensions, setPdfDimensions] = useState<{ width: number; height: number } | null>(null)
  const renderTaskRef = useRef<RenderTask | null>(null)

  const hasHighlight =
    evidence.highlight != null &&
    isValidHighlight(evidence.highlight)

  const pdfUrl = getPdfUrl(runId, evidence.pdf_id)
  const pageNo = evidence.page ?? 1

  useEffect(() => {
    if (!evidence.pdf_id) return
    if (canvasRef.current == null) return

    let cancelled = false

    async function render() {
      try {
        const doc = await pdfjs.getDocument(pdfUrl).promise
        const page: PDFPageProxy = await doc.getPage(pageNo)
        const viewport = page.getViewport({ scale: 1.5 })

        if (cancelled) return

        const canvas = canvasRef.current
        if (!canvas) return
        const ctx = canvas.getContext('2d')
        if (!ctx) return

        canvas.width = viewport.width
        canvas.height = viewport.height
        setPdfDimensions({ width: viewport.width, height: viewport.height })

        if (renderTaskRef.current) {
          renderTaskRef.current.cancel()
        }
        renderTaskRef.current = page.render({ canvasContext: ctx, viewport, canvas })
        await renderTaskRef.current.promise

        if (!cancelled) {
          setUseFallback(false)
          setRenderError(null)
        }
      } catch (err: unknown) {
        if (cancelled) return
        setUseFallback(true)
        setRenderError(err instanceof Error ? err.message : 'PDF render failed')
      }
    }

    void render()

    return () => {
      cancelled = true
      if (renderTaskRef.current) {
        renderTaskRef.current.cancel()
        renderTaskRef.current = null
      }
    }
  }, [pdfUrl, pageNo])

  // Compute highlight overlay position
  const highlightStyle = hasHighlight && pdfDimensions && evidence.highlight
    ? computeHighlightStyle(evidence.highlight, pdfDimensions)
    : null

  if (useFallback) {
    return <PageImageFallback runId={runId} evidence={evidence} error={renderError} />
  }

  return (
    <div className="text-evidence">
      <div className="pdf-canvas-wrapper" style={{ position: 'relative', display: 'inline-block' }}>
        <canvas ref={canvasRef} className="pdf-canvas" />
        <div className="highlight-overlay" style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          {highlightStyle && (
            <div className="highlight-box" style={highlightStyle} />
          )}
        </div>
      </div>

      {!hasHighlight && evidence.quote_text && (
        <QuotePageFallback evidence={evidence} />
      )}
    </div>
  )
}

/**
 * T087: Convert canonical PDF page coordinates (PDF coordinate system, origin bottom-left)
 * into CSS pixel positions relative to the canvas dimensions.
 */
function computeHighlightStyle(
  h: { x0: number; y0: number; x1: number; y1: number },
  dims: { width: number; height: number },
): React.CSSProperties {
  const isNormalized = h.x0 <= 1 && h.y0 <= 1 && h.x1 <= 1 && h.y1 <= 1
  let left: number, top: number, width: number, height: number

  if (isNormalized) {
    left = h.x0 * dims.width
    top = (1 - h.y1) * dims.height
    width = (h.x1 - h.x0) * dims.width
    height = (h.y1 - h.y0) * dims.height
  } else {
    // PDF units — scale to canvas dimensions (assume ~595pt wide A4)
    const scale = dims.width / 595
    left = h.x0 * scale
    const pdfPageHeight = dims.height / scale
    top = (pdfPageHeight - h.y1) * scale
    width = (h.x1 - h.x0) * scale
    height = (h.y1 - h.y0) * scale
  }

  return {
    position: 'absolute',
    left: `${left}px`,
    top: `${top}px`,
    width: `${Math.max(width, 4)}px`,
    height: `${Math.max(height, 4)}px`,
    background: 'rgba(255, 220, 0, 0.35)',
    border: '2px solid rgba(200, 160, 0, 0.7)',
    borderRadius: '2px',
  }
}

function isValidHighlight(h: { x0: number; y0: number; x1: number; y1: number }): boolean {
  return (
    typeof h.x0 === 'number' &&
    typeof h.y0 === 'number' &&
    typeof h.x1 === 'number' &&
    typeof h.y1 === 'number' &&
    h.x1 > h.x0 &&
    h.y1 > h.y0
  )
}

/** T088: Quote + page fallback when highlight coordinates are missing or invalid */
function QuotePageFallback({ evidence }: { evidence: EvidenceRecord }) {
  return (
    <div className="quote-fallback">
      <span className="fallback-badge">No highlight coordinates — showing quote reference</span>
      {evidence.page != null && <p className="page-ref">Page {evidence.page}</p>}
      {evidence.quote_text && (
        <blockquote className="quote-text">&ldquo;{evidence.quote_text}&rdquo;</blockquote>
      )}
    </div>
  )
}

/** Fallback: render page image when PDF.js fails to load the PDF */
function PageImageFallback({
  runId,
  evidence,
  error,
}: { runId: string; evidence: EvidenceRecord; error: string | null }) {
  const pageNo = evidence.page ?? 1
  const imgUrl = getPageImageUrl(runId, evidence.pdf_id, pageNo)
  return (
    <div className="text-evidence">
      {error && <p className="muted fallback-note">PDF viewer unavailable ({error}). Showing page image.</p>}
      <img src={imgUrl} alt={`Page ${pageNo}`} className="page-image" />
      {evidence.quote_text && <QuotePageFallback evidence={evidence} />}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Figure evidence — crop-first, caption, full-page access (T089)
// ---------------------------------------------------------------------------

interface FigurePanelProps {
  runId: string
  evidence: EvidenceRecord
}

function FigureEvidencePanel({ runId, evidence }: FigurePanelProps) {
  const [showFullPage, setShowFullPage] = useState(false)

  const cropUrl = getFigureCropUrl(runId, evidence.evidence_id)
  const fullPageUrl =
    evidence.page != null ? getPageImageUrl(runId, evidence.pdf_id, evidence.page) : null

  return (
    <div className="figure-evidence">
      {evidence.figure_ref && <p className="figure-ref-label">Figure: {evidence.figure_ref}</p>}

      {evidence.source_type === 'figure_crop' && !showFullPage ? (
        <>
          <img
            src={cropUrl}
            alt={evidence.figure_ref ?? 'Figure crop'}
            className="figure-crop"
            onError={(e) => {
              ;(e.target as HTMLImageElement).style.display = 'none'
            }}
          />
          {fullPageUrl && (
            <button className="btn-sm link-btn" onClick={() => setShowFullPage(true)}>
              View full page
            </button>
          )}
        </>
      ) : null}

      {(showFullPage || evidence.source_type === 'full_page') && fullPageUrl ? (
        <>
          <img src={fullPageUrl} alt={`Full page ${evidence.page}`} className="full-page-image" />
          {evidence.source_type === 'figure_crop' && (
            <button className="btn-sm link-btn" onClick={() => setShowFullPage(false)}>
              Back to figure crop
            </button>
          )}
        </>
      ) : null}

      {evidence.caption_text && (
        <p className="figure-caption">
          <strong>Caption:</strong> {evidence.caption_text}
        </p>
      )}

      {evidence.source_type === 'caption' && !evidence.caption_text && (
        <p className="muted">Caption text not available.</p>
      )}
    </div>
  )
}
