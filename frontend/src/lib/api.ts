import type { ConfigSnapshot, InputSummary, MatchRecord, ProposalDetail, ProposalRecord, ReviewerSummary, RunDiagnostics, RunRecord, RunSummary } from './types'

const API_ROOT = import.meta.env.VITE_API_ROOT ?? 'http://127.0.0.1:8000/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_ROOT}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch (error) {
    const detail = error instanceof Error ? error.message : 'The backend is unavailable.'
    throw new Error(`Backend request failed. Ensure the FastAPI server is running at ${API_ROOT}. ${detail}`)
  }
  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json') ? await response.json().catch(() => null) : null
  if (!response.ok) {
    const detail = payload && typeof payload === 'object'
      ? (payload as { detail?: string; message?: string }).detail ?? (payload as { message?: string }).message
      : null
    throw new Error(detail ?? `Request failed: ${response.status}`)
  }
  return payload as T
}

export const api = {
  createRun: (configPath: string) => request<RunRecord>('/runs', { method: 'POST', body: JSON.stringify({ config_path: configPath }) }),
  listRuns: () => request<RunRecord[]>('/runs'),
  getSummary: (runId: string) => request<RunSummary>(`/runs/${runId}/summary`),
  getReviewerSummary: (runId: string) => request<ReviewerSummary>(`/runs/${runId}/reviewer-summary`),
  getConfigSnapshot: (runId: string) => request<ConfigSnapshot>(`/runs/${runId}/config`),
  getInputSummary: (runId: string) => request<InputSummary>(`/runs/${runId}/input-summary`),
  getDiagnostics: (runId: string) => request<RunDiagnostics>(`/runs/${runId}/diagnostics`),
  getProposals: (runId: string, params = '') => request<{ proposals: ProposalRecord[]; total: number }>(`/runs/${runId}/proposals${params}`),
  getProposal: (runId: string, proposalId: string) => request<ProposalDetail>(`/runs/${runId}/proposals/${proposalId}`),
  getMatches: (runId: string, outcome?: string) => request<{ matches: MatchRecord[] }>(`/runs/${runId}/matches${outcome ? `?outcome=${outcome}` : ''}`),
  review: (runId: string, proposalId: string, decision: string, editedValue?: string | null) => request(`/runs/${runId}/reviews`, { method: 'POST', body: JSON.stringify({ proposal_id: proposalId, decision, edited_value: editedValue }) }),
  bulkAccept: (runId: string, proposalIds: string[]) => request(`/runs/${runId}/bulk-accept`, { method: 'POST', body: JSON.stringify({ proposal_ids: proposalIds }) }),
  pageAsset: (runId: string, pdfId: string, pageNumber: number) => `${API_ROOT}/runs/${runId}/assets/page/${pdfId}/${pageNumber}`,
  pdfAsset: (runId: string, pdfId: string) => `${API_ROOT}/runs/${runId}/assets/pdf/${pdfId}`,
  downloadAsset: (runId: string, kind: 'workbook' | 'audit-log' | 'run-summary' | 'reviewer-summary' | 'config-snapshot') => `${API_ROOT}/runs/${runId}/downloads/${kind}`,
}
