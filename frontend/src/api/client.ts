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
}
