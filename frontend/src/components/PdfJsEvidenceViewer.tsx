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
        const viewport = page.getViewport({ scale: 1 })
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

  if (!runId || !detail || !detail.primary_evidence) {
    return <section aria-label="evidence-viewer">Select a proposal to view evidence.</section>
  }
  const evidence = detail.primary_evidence
  const pageSrc = api.pageAsset(runId, detail.proposal.pdf_id, evidence.page)
  return (
    <section aria-label="evidence-viewer">
      <h2>Evidence Viewer</h2>
      <p>Page {evidence.page}</p>
      {evidence.source_type === 'figure' && evidence.crop_path ? (
        <div>
          <img src={`${import.meta.env.VITE_SERVER_ROOT ?? 'http://127.0.0.1:8000'}/api/runs/${runId}/assets/evidence/${evidence.evidence_id}?download=crop`} alt="Figure crop" style={{ maxWidth: '100%' }} />
          <p>{evidence.caption_text}</p>
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          {!renderFailed ? <canvas ref={canvasRef} style={{ width: '100%', border: '1px solid #ddd' }} /> : <img src={pageSrc} alt={`Page ${evidence.page}`} style={{ width: '100%', border: '1px solid #ddd' }} />}
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
                background: 'rgba(251, 191, 36, 0.2)',
              }}
            />
          ))}
          {!evidence.highlight.length && <p>Quote + page fallback: highlight unavailable.</p>}
        </div>
      )}
      <blockquote>{evidence.quote_text || 'No quote available.'}</blockquote>
    </section>
  )
}
