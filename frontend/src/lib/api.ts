import type { ProposalDetail, ProposalRecord, ReviewerSummary, RunRecord, RunSummary } from './types'

const API_ROOT = import.meta.env.VITE_API_ROOT ?? 'http://127.0.0.1:8000/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}

export const api = {
  listRuns: () => request<RunRecord[]>('/runs'),
  getSummary: (runId: string) => request<RunSummary>(`/runs/${runId}/summary`),
  getReviewerSummary: (runId: string) => request<ReviewerSummary>(`/runs/${runId}/reviewer-summary`),
  getProposals: (runId: string, params = '') => request<{ proposals: ProposalRecord[]; total: number }>(`/runs/${runId}/proposals${params}`),
  getProposal: (runId: string, proposalId: string) => request<ProposalDetail>(`/runs/${runId}/proposals/${proposalId}`),
  getMatches: (runId: string, outcome?: string) => request<{ matches: any[] }>(`/runs/${runId}/matches${outcome ? `?outcome=${outcome}` : ''}`),
  review: (runId: string, proposalId: string, decision: string, editedValue?: string | null) => request(`/runs/${runId}/reviews`, { method: 'POST', body: JSON.stringify({ proposal_id: proposalId, decision, edited_value: editedValue }) }),
  bulkAccept: (runId: string, proposalIds: string[]) => request(`/runs/${runId}/bulk-accept`, { method: 'POST', body: JSON.stringify({ proposal_ids: proposalIds }) }),
  pageAsset: (runId: string, pdfId: string, pageNumber: number) => `${API_ROOT}/runs/${runId}/assets/page/${pdfId}/${pageNumber}`,
  pdfAsset: (runId: string, pdfId: string) => `${API_ROOT}/runs/${runId}/assets/pdf/${pdfId}`,
}
