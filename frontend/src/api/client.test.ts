import { describe, it, expect } from 'vitest'

describe('api client', () => {
  it('exports expected methods', async () => {
    const { api } = await import('./client')
    expect(typeof api.health).toBe('function')
    expect(typeof api.listRuns).toBe('function')
    expect(typeof api.getRun).toBe('function')
    expect(typeof api.createRun).toBe('function')
    expect(typeof api.stageInputFiles).toBe('function')
    expect(typeof api.getRunConfig).toBe('function')
    expect(typeof api.getRunInputs).toBe('function')
    expect(typeof api.triggerExport).toBe('function')
    expect(typeof api.openPdfInLocalViewer).toBe('function')
    expect(typeof api.getWorkbookDownloadUrl).toBe('function')
  })
})
