import { useEffect, useRef, useState } from 'react'
import { getDocument, GlobalWorkerOptions } from 'pdfjs-dist'
import workerSrc from 'pdfjs-dist/build/pdf.worker.mjs?url'
import type { ProposalDetail } from '../lib/types'
import { api } from '../lib/api'

GlobalWorkerOptions.workerSrc = workerSrc

interface Props {
  runId: string | null
  detail: ProposalDetail | null
}

export function PdfJsEvidenceViewer({ runId, detail }: Props) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [renderFailed, setRenderFailed] = useState(false)

  useEffect(() => {
    async function renderPdf() {
      if (!runId || !detail || !detail.primary_evidence || !canvasRef.current || detail.primary_evidence.source_type === 'figure') {
        return
      }
      try {
        const loadingTask = getDocument(api.pdfAsset(runId, detail.proposal.pdf_id))
        const pdf = await loadingTask.promise
        const page = await pdf.getPage(detail.primary_evidence.page)
        const viewport = page.getViewport({ scale: 1.1 })
        const canvas = canvasRef.current
        const context = canvas.getContext('2d')
        if (!context) return
        canvas.width = viewport.width
        canvas.height = viewport.height
        await page.render({ canvasContext: context, viewport }).promise
        setRenderFailed(false)
      } catch {
        setRenderFailed(true)
      }
    }
    void renderPdf()
  }, [runId, detail])

  if (!runId || !detail) {
    return (
      <section className="panel" aria-label="evidence-viewer">
        <h2 className="section-title">Evidence viewer</h2>
        <p className="empty-state">Select a proposal to inspect the PDF page, figure crop, quote, and page-level context.</p>
      </section>
    )
  }

  if (!detail.primary_evidence) {
    return (
      <section className="panel" aria-label="evidence-viewer">
        <div className="section-title-row">
          <div>
            <h2 className="section-title">Evidence viewer</h2>
            <p className="section-caption">This proposal currently has no primary evidence item.</p>
          </div>
          <span className="badge badge-warning">No evidence</span>
        </div>
      </section>
    )
  }

  const evidence = detail.primary_evidence
  const pageSrc = api.pageAsset(runId, detail.proposal.pdf_id, evidence.page)

  return (
    <section className="panel" aria-label="evidence-viewer">
      <div className="section-title-row">
        <div>
          <h2 className="section-title">Evidence viewer</h2>
          <p className="section-caption">{detail.proposal.pdf_name} · page {evidence.page}</p>
        </div>
        <div className="badge-row">
          <span className={evidence.source_type === 'figure' ? 'badge badge-accent' : 'badge badge-neutral'}>
            {evidence.source_type}
          </span>
          <span className={evidence.highlight.length > 0 ? 'badge badge-success' : 'badge badge-warning'}>
            {evidence.highlight.length > 0 ? 'Highlight anchored' : 'Quote + page fallback'}
          </span>
        </div>
      </div>

      {evidence.source_type === 'figure' && evidence.crop_path ? (
        <div className="stack">
          <div className="viewer-stage">
            <img
              className="viewer-image"
              src={`${import.meta.env.VITE_SERVER_ROOT ?? 'http://127.0.0.1:8000'}/api/runs/${runId}/assets/evidence/${evidence.evidence_id}?download=crop`}
              alt="Figure crop"
            />
          </div>
          <div className="detail-card">
            <span className="detail-label">Figure caption</span>
            <p className="detail-value">{evidence.caption_text || 'No caption text recorded.'}</p>
          </div>
        </div>
      ) : (
        <div className="stack">
          <div className="viewer-stage">
            {!renderFailed ? (
              <canvas ref={canvasRef} className="viewer-canvas" />
            ) : (
              <img className="viewer-image" src={pageSrc} alt={`Page ${evidence.page}`} />
            )}
            {evidence.highlight.map((box, index) => (
              <div
                key={index}
                data-testid="highlight-overlay"
                style={{
                  position: 'absolute',
                  left: `${(box.x / 612) * 100}%`,
                  top: `${(box.y / 792) * 100}%`,
                  width: `${(box.width / 612) * 100}%`,
                  height: `${(box.height / 792) * 100}%`,
                  border: '2px solid #d97706',
                  background: 'rgba(251, 191, 36, 0.18)',
                  borderRadius: '6px',
                }}
              />
            ))}
          </div>
          <p className="viewer-note">
            {evidence.highlight.length > 0
              ? 'The overlay marks the current evidence anchor on the PDF page.'
              : 'Highlight geometry was unavailable, so the reviewer falls back to quote + page context.'}
          </p>
        </div>
      )}

      <blockquote className="viewer-quote">{evidence.quote_text || 'No quote available.'}</blockquote>

      {detail.secondary_evidence.length > 0 && (
        <div className="detail-card" style={{ marginTop: '0.9rem' }}>
          <span className="detail-label">Additional evidence items</span>
          <ul className="column-summary-list">
            {detail.secondary_evidence.map((item) => (
              <li key={item.evidence_id}>
                Page {item.page} · {item.source_type} · {item.quote_text || item.caption_text || 'No snippet'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
