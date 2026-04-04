const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!resp.ok) {
    const text = await resp.text()
    throw new Error(`API error ${resp.status}: ${text}`)
  }
  return resp.json() as Promise<T>
}

function qs(params: Record<string, string | boolean | undefined>): string {
  const pairs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null)
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v!)}`)
  return pairs.length ? `?${pairs.join('&')}` : ''
}

export const api = {
  health: () => request<{ status: string }>('/api/health'),

  listRuns: (outputDir?: string) => {
    const params = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').ListRunsResponse>(`/api/runs${params}`)
  },

  getRun: (runId: string, outputDir?: string) => {
    const params = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').RunData>(`/api/runs/${runId}${params}`)
  },

  getRunConfig: (runId: string, outputDir?: string) => {
    const params = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<Record<string, unknown>>(`/api/runs/${runId}/config${params}`)
  },

  getRunInputs: (runId: string, outputDir?: string) => {
    const params = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').InputSummary>(`/api/runs/${runId}/inputs${params}`)
  },

  createRun: (req: import('../types').CreateRunRequest) =>
    request<import('../types').CreateRunResponse>('/api/runs', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  stageInputFiles: async (
    kind: 'table_path' | 'schema_path' | 'pdf_dir',
    files: File[],
    outputDir = './runs'
  ) => {
    const form = new FormData()
    form.append('kind', kind)
    form.append('output_dir', outputDir)
    for (const file of files) {
      form.append('files', file)
    }
    const resp = await fetch(`${API_BASE}/api/staged-inputs`, {
      method: 'POST',
      body: form,
    })
    if (!resp.ok) {
      const text = await resp.text()
      throw new Error(`API error ${resp.status}: ${text}`)
    }
    return resp.json() as Promise<import('../types').StagedInputResponse>
  },

  // Proposals
  listProposals: (
    runId: string,
    params?: {
      row_id?: string
      column_name?: string
      decision?: string
      match_status?: string
      evidence_status?: string
      reviewable_only?: boolean
      output_dir?: string
    }
  ) => {
    const q = qs({
      output_dir: params?.output_dir,
      row_id: params?.row_id,
      column_name: params?.column_name,
      decision: params?.decision,
      match_status: params?.match_status,
      evidence_status: params?.evidence_status,
      reviewable_only: params?.reviewable_only,
    })
    return request<{ run_id: string; count: number; proposals: import('../types').EnrichedProposal[] }>(
      `/api/runs/${runId}/proposals${q}`
    )
  },

  getProposalDetail: (runId: string, proposalId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').ProposalDetail>(
      `/api/runs/${runId}/proposals/${proposalId}${q}`
    )
  },

  recordDecision: (
    runId: string,
    proposalId: string,
    body: {
      decision: string
      resolution_reason?: string
      edited_value?: string
      reviewer_note?: string
    },
    outputDir?: string
  ) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').DecisionRecord>(
      `/api/runs/${runId}/proposals/${proposalId}/decision${q}`,
      { method: 'POST', body: JSON.stringify(body) }
    )
  },

  bulkAccept: (runId: string, proposalIds: string[], outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<{ run_id: string; accepted_count: number; decisions: import('../types').DecisionRecord[] }>(
      `/api/runs/${runId}/proposals/bulk-accept${q}`,
      { method: 'POST', body: JSON.stringify({ proposal_ids: proposalIds }) }
    )
  },

  getProgress: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').ReviewProgress>(`/api/runs/${runId}/progress${q}`)
  },

  getReviewProgress: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').ReviewProgress>(`/api/runs/${runId}/progress-review${q}`)
  },

  getReviewerSummary: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').ReviewerSummary>(`/api/runs/${runId}/reviewer-summary${q}`)
  },

  getMatchingSummary: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').MatchingSummary>(`/api/runs/${runId}/matching/summary${q}`)
  },

  getUnmatched: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<{ run_id: string; unmatched: unknown[] }>(`/api/runs/${runId}/matching/unmatched${q}`)
  },

  getAmbiguous: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<{ run_id: string; ambiguous: unknown[] }>(`/api/runs/${runId}/matching/ambiguous${q}`)
  },

  getConflicts: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<{ run_id: string; conflicts: unknown[] }>(`/api/runs/${runId}/matching/conflicts${q}`)
  },

  abortRun: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<{ run_id: string; status: string }>(`/api/runs/${runId}/abort${q}`, {
      method: 'POST',
    })
  },

  triggerExport: (runId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<import('../types').ExportResult>(`/api/runs/${runId}/export${q}`, {
      method: 'POST',
    })
  },

  // Assets — return URL strings (no fetch needed)
  getPdfUrl: (runId: string, pdfId: string, outputDir?: string): string => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return `${API_BASE}/api/runs/${runId}/assets/pdf/${pdfId}${q}`
  },

  getFigureUrl: (runId: string, pdfId: string, figureId: string, outputDir?: string): string => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return `${API_BASE}/api/runs/${runId}/assets/figures/${pdfId}/${figureId}${q}`
  },

  getPageImageUrl: (runId: string, pdfId: string, pageNumber: number, outputDir?: string): string => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return `${API_BASE}/api/runs/${runId}/assets/pages/${pdfId}/${pageNumber}${q}`
  },

  openPdfInLocalViewer: (runId: string, pdfId: string, outputDir?: string) => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return request<{ run_id: string; pdf_id: string; status: string; path: string }>(
      `/api/runs/${runId}/assets/pdf/${pdfId}/open${q}`,
      { method: 'POST' }
    )
  },

  getWorkbookDownloadUrl: (runId: string, outputDir?: string): string => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return `${API_BASE}/api/runs/${runId}/downloads/workbook${q}`
  },

  getAuditLogDownloadUrl: (runId: string, outputDir?: string): string => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return `${API_BASE}/api/runs/${runId}/downloads/audit-log${q}`
  },

  getRunSummaryDownloadUrl: (runId: string, outputDir?: string): string => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return `${API_BASE}/api/runs/${runId}/downloads/run-summary${q}`
  },

  getReviewerSummaryDownloadUrl: (runId: string, outputDir?: string): string => {
    const q = outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ''
    return `${API_BASE}/api/runs/${runId}/downloads/reviewer-summary${q}`
  },
}
