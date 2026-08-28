import { readFileSync } from 'node:fs'
import path from 'node:path'
import { describe, expect, it } from 'vitest'

const sourcePath = path.join(process.cwd(), 'src', 'components', 'EvidenceViewer.tsx')

describe('standalone EvidenceViewer source contract', () => {
  it('keeps highlight quality labels and text-source priority', () => {
    const source = readFileSync(sourcePath, 'utf-8')

    expect(source).toContain('Quote-anchored highlight')
    expect(source).toContain('Exact quote highlight')
    expect(source).toContain('Approximate region highlight')
    expect(source).toContain('Quote + page fallback')
    expect(source).toContain('evidence?.quote_text')
    expect(source).toContain('evidence?.table_text')
    expect(source).toContain('evidence?.evidence_text')
    expect(source).toContain('evidence?.caption_text')
    expect(source).toContain('container.scrollTo')
    expect(source).toContain('loadedPdf?.pdfId === pdfId')
    expect(source).toContain('Promise.resolve().then(() =>')
    expect(source).toContain('Previous evidence (Ctrl/⌘ + ←)')
    expect(source).toContain('Next evidence (Ctrl/⌘ + →)')
  })
})
