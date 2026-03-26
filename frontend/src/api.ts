import type {
  AvailableDownloads,
  InputSummary,
  MatchingSummary,
  ProposalDetail,
  ProposalListItem,
  ProposalProgress,
  ReviewDecision,
  ReviewDecisionRecord,
  RunRecord,
  RunSummary,
  RunSummaryFull,
  UnresolvedMatch,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })

  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string }
    throw new Error(body.detail ?? `Request failed with ${response.status}`)
  }

  return (await response.json()) as T
}

// Run management
export async function createRun(configPath: string): Promise<{ run_id: string }> {
  return request('/api/runs', {
    method: 'POST',
    body: JSON.stringify({ config_path: configPath }),
  })
}

export async function listRuns(): Promise<RunRecord[]> {
  return request('/api/runs')
}

export async function getRunSummary(runId: string): Promise<RunSummary> {
  return request(`/api/runs/${runId}/summary`)
}

export async function getInputSummary(runId: string): Promise<InputSummary> {
  return request(`/api/runs/${runId}/input-summary`)
}

// Run summaries (full)
export async function getRunSummaryFull(runId: string): Promise<RunSummaryFull> {
  return request(`/api/runs/${runId}/summaries/run`)
}

export async function getReviewerSummary(runId: string): Promise<Record<string, unknown>> {
  return request(`/api/runs/${runId}/summaries/reviewer`)
}

export async function recomputeSummaries(runId: string): Promise<{ run_summary: unknown; reviewer_summary: unknown }> {
  return request(`/api/runs/${runId}/summaries/recompute`, { method: 'POST' })
}

// Matching
export async function getMatchingSummary(runId: string): Promise<MatchingSummary> {
  return request(`/api/runs/${runId}/matching/summary`)
}

export async function getMatchingUnresolved(runId: string): Promise<UnresolvedMatch[]> {
  return request(`/api/runs/${runId}/matching/unresolved`)
}

// Proposals
export async function listProposals(
  runId: string,
  filters?: {
    row_id?: string
    column_name?: string
    pdf_id?: string
    has_figure_evidence?: boolean
    has_ambiguous_match?: boolean
    decision_status?: ReviewDecision
  },
): Promise<ProposalListItem[]> {
  const params = new URLSearchParams()
  if (filters?.row_id) params.set('row_id', filters.row_id)
  if (filters?.column_name) params.set('column_name', filters.column_name)
  if (filters?.pdf_id) params.set('pdf_id', filters.pdf_id)
  if (filters?.has_figure_evidence != null) params.set('has_figure_evidence', String(filters.has_figure_evidence))
  if (filters?.has_ambiguous_match != null) params.set('has_ambiguous_match', String(filters.has_ambiguous_match))
  if (filters?.decision_status) params.set('decision_status', filters.decision_status)
  const qs = params.toString()
  return request(`/api/runs/${runId}/proposals${qs ? `?${qs}` : ''}`)
}

export async function getProposalDetail(runId: string, proposalId: string): Promise<ProposalDetail> {
  return request(`/api/runs/${runId}/proposals/${proposalId}`)
}

// Review decisions
export async function recordDecision(
  runId: string,
  proposalId: string,
  decision: ReviewDecision,
  editedValue?: string,
): Promise<ReviewDecisionRecord> {
  return request(`/api/runs/${runId}/proposals/${proposalId}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, edited_value: editedValue ?? null }),
  })
}

export async function bulkAccept(
  runId: string,
  filters?: { row_id?: string; column_name?: string; pdf_id?: string },
): Promise<ReviewDecisionRecord[]> {
  return request(`/api/runs/${runId}/proposals/bulk-accept`, {
    method: 'POST',
    body: JSON.stringify({
      row_id: filters?.row_id ?? null,
      column_name: filters?.column_name ?? null,
      pdf_id: filters?.pdf_id ?? null,
    }),
  })
}

// Progress
export async function getProgress(runId: string): Promise<ProposalProgress> {
  return request(`/api/runs/${runId}/progress`)
}

// Downloads
export async function getAvailableDownloads(runId: string): Promise<AvailableDownloads> {
  return request(`/api/runs/${runId}/downloads/available`)
}

export function getRunSummaryDownloadUrl(runId: string): string {
  return `${API_BASE}/api/runs/${runId}/downloads/run-summary`
}

export function getReviewerSummaryDownloadUrl(runId: string): string {
  return `${API_BASE}/api/runs/${runId}/downloads/reviewer-summary`
}

export function getWorkbookDownloadUrl(runId: string): string {
  return `${API_BASE}/api/runs/${runId}/downloads/workbook`
}

export function getAuditLogDownloadUrl(runId: string): string {
  return `${API_BASE}/api/runs/${runId}/downloads/audit-log`
}

// Asset URLs (for PDF viewer and images)
export function getPdfUrl(runId: string, pdfId: string): string {
  return `${API_BASE}/api/runs/${runId}/assets/pdf/${pdfId}`
}

export function getPageImageUrl(runId: string, pdfId: string, pageNo: number): string {
  return `${API_BASE}/api/runs/${runId}/assets/pages/${pdfId}/${pageNo}`
}

export function getFigureCropUrl(runId: string, evidenceId: string): string {
  return `${API_BASE}/api/runs/${runId}/assets/figures/${evidenceId}`
}
