import type {
  DecisionRecord,
  EnrichedProposal,
  EvidenceItem,
  ExportResult,
  ProposalDetail,
  ReviewProgress,
  ReviewTableCell,
  ReviewTableColumn,
  ReviewTableData,
  ReviewTableProposal,
} from '../types'

type PackageColumn = {
  column_name: string
  description?: string | null
  field_type?: string | null
  is_target?: boolean
}

type PackageRow = {
  row_id: string
  row_index?: number | null
  pdf_id?: string | null
  paper_label?: string | null
  values?: Record<string, unknown>
}

type PackagePdf = {
  pdf_id: string
  label?: string | null
  title?: string | null
  authors?: string | string[] | null
  year?: string | number | null
  path?: string | null
  asset_path?: string | null
}

export interface ReviewPackage {
  schema_version: string
  run_id: string
  generated_at?: string | null
  source?: Record<string, unknown>
  pdfs?: PackagePdf[]
  columns?: PackageColumn[]
  rows?: PackageRow[]
  proposals?: Array<EnrichedProposal & { evidence?: EvidenceItem[] }>
  review_progress?: ReviewProgress
}

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1', '::1'])
const served = location.protocol.startsWith('http') && LOCAL_HOSTS.has(location.hostname)

function packageData(): ReviewPackage {
  const pkg = window.__REVIEW_PACKAGE__
  if (!pkg) throw new Error('Missing embedded review package.')
  return pkg
}

function localKey() {
  return `papersToTable.agentKit.react.decisions.${packageData().run_id}`
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers)
  if (options?.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  const response = await fetch(path, { ...options, headers })
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`API error ${response.status}: ${text}`)
  }
  return response.json() as Promise<T>
}

function readLocalDecisions(): DecisionRecord[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(localKey()) || '[]')
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function writeLocalDecisions(rows: DecisionRecord[]) {
  localStorage.setItem(localKey(), JSON.stringify(rows))
}

function latestDecisions(rows: DecisionRecord[]): Map<string, DecisionRecord> {
  const latest = new Map<string, DecisionRecord>()
  for (const row of rows) {
    if (row?.proposal_id) latest.set(row.proposal_id, row)
  }
  return latest
}

function textValue(value: unknown): string | null {
  if (value === null || value === undefined || value === '') return null
  return String(value)
}

function rowTitle(row: PackageRow | undefined, pdf: PackagePdf | undefined): string | null {
  const values = row?.values ?? {}
  return (
    textValue(values.Title) ??
    textValue(values.title) ??
    textValue(values.paper_title) ??
    textValue(values.Paper) ??
    textValue(values.paper) ??
    textValue(pdf?.title) ??
    textValue(row?.paper_label) ??
    null
  )
}

function rowAuthors(row: PackageRow | undefined, pdf: PackagePdf | undefined): string | null {
  const values = row?.values ?? {}
  const authors = values.Authors ?? values.authors ?? pdf?.authors
  if (Array.isArray(authors)) return authors.join('; ')
  return textValue(authors)
}

function rowYear(row: PackageRow | undefined, pdf: PackagePdf | undefined): string | number | null {
  const values = row?.values ?? {}
  return textValue(values['Publication Year']) ?? textValue(values.year) ?? textValue(pdf?.year)
}

function normalizeColumn(column: PackageColumn): ReviewTableColumn {
  return {
    name: column.column_name,
    description: column.description ?? null,
    field_type: column.field_type ?? null,
    is_target: column.is_target !== false,
  }
}

function packageMaps(pkg = packageData()) {
  const rows = new Map((pkg.rows ?? []).map((row) => [row.row_id, row]))
  const pdfs = new Map((pkg.pdfs ?? []).map((pdf) => [pdf.pdf_id, pdf]))
  const columns = new Map((pkg.columns ?? []).map((column) => [column.column_name, column]))
  return { rows, pdfs, columns }
}

function localProposals(): EnrichedProposal[] {
  const pkg = packageData()
  const { rows, pdfs } = packageMaps(pkg)
  const latest = latestDecisions(readLocalDecisions())
  return (pkg.proposals ?? []).map((proposal) => {
    const row = rows.get(proposal.row_id)
    const pdf = pdfs.get(proposal.pdf_id)
    return {
      ...proposal,
      latest_decision: latest.get(proposal.proposal_id) ?? proposal.latest_decision ?? null,
      paper_title: proposal.paper_title ?? rowTitle(row, pdf),
      paper_authors: proposal.paper_authors ?? rowAuthors(row, pdf),
      paper_year: proposal.paper_year ?? rowYear(row, pdf),
      is_figure_derived: proposal.is_figure_derived ?? false,
      is_fallback_evidence: proposal.is_fallback_evidence ?? false,
    }
  })
}

function proposalEvidence(proposalId: string): EvidenceItem[] {
  const proposal = (packageData().proposals ?? []).find((item) => item.proposal_id === proposalId)
  return (proposal?.evidence ?? []).map((item) => ({
    ...item,
    quote_text: item.quote_text ?? item.table_text ?? item.evidence_text ?? item.caption_text ?? null,
  }))
}

function makeDecision(
  proposal: EnrichedProposal,
  body: {
    decision: string
    resolution_reason?: string
    edited_value?: string
    reviewer_note?: string
    decision_source?: string
  },
  source = 'human_individual',
): DecisionRecord {
  const decidedAt = new Date().toISOString()
  const randomId = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}_${Math.random().toString(16).slice(2)}`
  return {
    review_decision_id: `rev_${randomId}`,
    run_id: packageData().run_id,
    proposal_id: proposal.proposal_id,
    cell_id: proposal.cell_id,
    decision: body.decision as DecisionRecord['decision'],
    decision_source: body.decision_source ?? source,
    resolution_reason: body.resolution_reason ?? null,
    edited_value: body.edited_value ?? null,
    reviewer_note: body.reviewer_note ?? null,
    decided_at: decidedAt,
  }
}

function buildProgress(proposals: EnrichedProposal[]): ReviewProgress {
  const reviewable = proposals.filter((proposal) => proposal.review_bucket !== 'diagnostic')
  const counts = {
    accepted: 0,
    accepted_with_edit: 0,
    confirmed_no_data: 0,
    rejected: 0,
  }
  for (const proposal of reviewable) {
    const decision = proposal.latest_decision?.decision
    if (decision && decision in counts) counts[decision as keyof typeof counts] += 1
  }
  const reviewed = Object.values(counts).reduce((total, count) => total + count, 0)
  return {
    run_id: packageData().run_id,
    total_proposals: reviewable.length,
    reviewed,
    pending: Math.max(reviewable.length - reviewed, 0),
    ...counts,
  }
}

function proposalValue(proposal: ReviewTableProposal, originalValue: unknown): { value: unknown; status: string } {
  const decision = proposal.latest_decision?.decision
  if (decision === 'accepted') return { value: proposal.proposed_value, status: 'accepted' }
  if (decision === 'accepted_with_edit') return { value: proposal.latest_decision?.edited_value ?? proposal.proposed_value, status: 'accepted_with_edit' }
  if (decision === 'confirmed_no_data') return { value: originalValue ?? '', status: 'confirmed_no_data' }
  if (decision === 'rejected') return { value: originalValue ?? '', status: 'rejected' }
  return { value: proposal.proposed_value ?? originalValue ?? '', status: 'pending' }
}

function localReviewTable(): ReviewTableData {
  const pkg = packageData()
  const proposals = localProposals()
  const proposalByCell = new Map<string, ReviewTableProposal>()
  for (const proposal of proposals) {
    proposalByCell.set(`${proposal.row_id}\u0000${proposal.column_name}`, proposal as ReviewTableProposal)
  }
  const columns = (pkg.columns ?? []).map(normalizeColumn)
  const rows = (pkg.rows ?? []).map((row) => {
    const values = row.values ?? {}
    const cells: Record<string, ReviewTableCell> = {}
    for (const column of columns) {
      const proposal = proposalByCell.get(`${row.row_id}\u0000${column.name}`) ?? null
      const originalValue = values[column.name] ?? null
      const decided = proposal ? proposalValue(proposal, originalValue) : { value: originalValue, status: 'unchanged' }
      cells[column.name] = {
        column_name: column.name,
        original_value: originalValue,
        display_value: decided.value,
        display_status: decided.status,
        has_proposal: !!proposal,
        proposal,
      }
    }
    return {
      row_id: row.row_id,
      row_index: row.row_index ?? null,
      paper_label: row.paper_label ?? row.row_id,
      title: rowTitle(row, (pkg.pdfs ?? []).find((pdf) => pdf.pdf_id === row.pdf_id)),
      values,
      cells,
    }
  })
  return {
    run_id: pkg.run_id,
    columns,
    rows,
    proposal_count: proposals.length,
  }
}

function pdfAssetPath(pdfId: string): string {
  const pdf = (packageData().pdfs ?? []).find((item) => item.pdf_id === pdfId)
  return pdf?.asset_path ?? (pdf?.path ? `../${pdf.path}` : '#')
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export const api = {
  isServed: () => served,

  downloadDecisions: async () => {
    const decisions = served
      ? (await request<{ decisions: DecisionRecord[] }>('/api/decisions')).decisions
      : readLocalDecisions()
    downloadJson('downloaded_decisions.json', {
      schema_version: 'papers_to_table.agent_decisions.v1',
      run_id: packageData().run_id,
      exported_at: new Date().toISOString(),
      decisions,
    })
  },

  listProposals: async (
    _runId: string,
    params?: { reviewable_only?: boolean },
  ): Promise<{ run_id: string; count: number; proposals: EnrichedProposal[] }> => {
    if (served) return request(`/api/proposals${params?.reviewable_only ? '?reviewable_only=true' : ''}`)
    const proposals = localProposals().filter((proposal) => !params?.reviewable_only || proposal.review_bucket !== 'diagnostic')
    return { run_id: packageData().run_id, count: proposals.length, proposals }
  },

  getProposalDetail: async (_runId: string, proposalId: string): Promise<ProposalDetail> => {
    if (served) return request(`/api/proposals/${encodeURIComponent(proposalId)}`)
    const proposals = localProposals()
    const proposal = proposals.find((item) => item.proposal_id === proposalId)
    if (!proposal) throw new Error(`Unknown proposal: ${proposalId}`)
    const { rows, columns } = packageMaps()
    return {
      proposal,
      evidence: proposalEvidence(proposalId),
      latest_decision: proposal.latest_decision,
      decision_history: readLocalDecisions().filter((decision) => decision.proposal_id === proposalId),
      row_context: rows.get(proposal.row_id)?.values ?? {},
      column_definition: columns.get(proposal.column_name) ?? null,
    }
  },

  getReviewTable: async (): Promise<ReviewTableData> => {
    if (served) return request('/api/review-table')
    return localReviewTable()
  },

  getReviewProgress: async (): Promise<ReviewProgress> => {
    if (served) return request('/api/progress-review')
    return buildProgress(localProposals())
  },

  getMatchingSummary: async () => {
    const pkg = packageData()
    return {
      run_id: pkg.run_id,
      total_pdfs: pkg.pdfs?.length ?? 0,
      matched: pkg.pdfs?.length ?? 0,
      unmatched: 0,
      ambiguous: 0,
      duplicate_row_conflict: 0,
    }
  },

  recordDecision: async (
    _runId: string,
    proposalId: string,
    body: { decision: string; resolution_reason?: string; edited_value?: string; reviewer_note?: string },
  ): Promise<DecisionRecord> => {
    if (served) {
      return request(`/api/proposals/${encodeURIComponent(proposalId)}/decision`, {
        method: 'POST',
        body: JSON.stringify(body),
      })
    }
    const proposal = localProposals().find((item) => item.proposal_id === proposalId)
    if (!proposal) throw new Error(`Unknown proposal: ${proposalId}`)
    const decision = makeDecision(proposal, body)
    writeLocalDecisions([...readLocalDecisions(), decision])
    return decision
  },

  bulkAccept: async (_runId: string, proposalIds: string[]): Promise<{ run_id: string; accepted_count: number; decisions: DecisionRecord[] }> => {
    if (served) {
      return request('/api/proposals/bulk-accept', {
        method: 'POST',
        body: JSON.stringify({ proposal_ids: proposalIds }),
      })
    }
    const latest = latestDecisions(readLocalDecisions())
    const proposals = localProposals()
    const decisions = proposalIds
      .map((proposalId) => proposals.find((proposal) => proposal.proposal_id === proposalId))
      .filter((proposal): proposal is EnrichedProposal => !!proposal && !latest.has(proposal.proposal_id))
      .map((proposal) => makeDecision(proposal, { decision: 'accepted', decision_source: 'human_bulk_accept', reviewer_note: 'Bulk accepted in the standalone review UI.' }, 'human_bulk_accept'))
    writeLocalDecisions([...readLocalDecisions(), ...decisions])
    return { run_id: packageData().run_id, accepted_count: decisions.length, decisions }
  },

  triggerExport: async (): Promise<ExportResult> => {
    if (!served) {
      throw new Error('Export reviewed bundle requires localhost serving. Download decisions and apply them with serve_review.py or apply_review_decisions.py.')
    }
    const result = await request<Record<string, unknown>>('/api/export', { method: 'POST', body: '{}' })
    return {
      run_id: String(result.run_id ?? packageData().run_id),
      exported_at: new Date().toISOString(),
      accepted_changes_count: Number(result.accepted_changes_count ?? 0),
      workbook_path: String(result.final_table_path ?? ''),
      final_table_path: String(result.final_table_path ?? ''),
      reviewed_bundle_path: String(result.reviewed_bundle_path ?? ''),
      audit_log_path: String(result.audit_log_path ?? ''),
      diagnostics_path: String(result.diagnostics_path ?? ''),
      unsupported_feature_warnings: [],
      unsupported_feature_warnings_count: 0,
      fidelity_boundary: 'standalone_reviewed_bundle',
    }
  },

  getPdfUrl: (_runId: string, pdfId: string): string => (
    served ? `/api/assets/pdf/${encodeURIComponent(pdfId)}` : pdfAssetPath(pdfId)
  ),

  getFigureUrl: (_runId: string, _pdfId: string, figureId: string): string => figureId,
  getPageImageUrl: (_runId: string, pdfId: string): string => api.getPdfUrl(packageData().run_id, pdfId),

  openPdfInLocalViewer: async (_runId: string, pdfId: string) => {
    const url = api.getPdfUrl(packageData().run_id, pdfId)
    window.open(url, '_blank', 'noopener,noreferrer')
    return { run_id: packageData().run_id, pdf_id: pdfId, status: 'opened', path: url }
  },

  getWorkbookDownloadUrl: () => '#',
  getAuditLogDownloadUrl: () => '#',
  getRunSummaryDownloadUrl: () => '#',
  getReviewerSummaryDownloadUrl: () => '#',
}
