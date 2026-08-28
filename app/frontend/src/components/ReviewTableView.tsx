import { useEffect, useMemo, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { api } from '../api/client'
import type { ReviewTableCell, ReviewTableColumn, ReviewTableData, ReviewTableProposal, ReviewTableRow } from '../types'
import {
  ProposalStatusIndicator,
  EvidenceStatusIndicator,
  ReviewStatusIndicator,
  isGreenEvidenceStatus,
  isGreenProposalStatus,
} from './ReviewTags'
import { proposalConclusionLabel } from './proposalDisplay'

export type ReviewFilter =
  | 'pending'
  | 'needs_attention'
  | 'all'
  | 'accepted'
  | 'accepted_with_edit'
  | 'confirmed_no_data'
  | 'rejected'

interface Props {
  runId: string
  outputDir: string
  selectedProposalId: string | null
  selectedProposalIds: string[]
  filter: ReviewFilter
  onFilterChange: (filter: ReviewFilter) => void
  onSelect: (proposalId: string) => void
  onSelectionChange: (proposalIds: string[], primaryProposalId: string | null) => void
  onVisibleProposalOrderChange?: (proposalIds: string[]) => void
  onSelectCell?: (cell: SelectedReviewCell) => void
  refreshVersion?: number
}

export interface SelectedReviewCell {
  rowId: string
  rowIndex: number | null
  paperLabel: string
  title: string | null
  columnName: string
  columnDescription: string | null
  originalValue: unknown
  displayValue: unknown
  displayStatus: string
}

const FILTER_LABELS: Record<ReviewFilter, string> = {
  pending: 'Pending',
  needs_attention: 'Attention',
  all: 'All',
  accepted: 'Reviewed - Accepted',
  accepted_with_edit: 'Reviewed - Edited',
  confirmed_no_data: 'Reviewed - No data',
  rejected: 'Reviewed - Rejected',
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

function isReviewableProposal(proposal: ReviewTableProposal | null): proposal is ReviewTableProposal {
  if (!proposal) return false
  return proposal.review_bucket !== 'diagnostic'
}

function displayCellValue(cell: ReviewTableCell | undefined): string {
  if (cell?.proposal) return proposalConclusionLabel(cell.proposal)
  return formatCellValue(cell?.display_value)
}

function statusClass(cell: ReviewTableCell): string {
  const proposal = cell.proposal
  if (proposal?.is_fallback_evidence) return 'bg-orange-50 text-orange-950 ring-orange-200'
  if (proposal && hasAttentionSignal(proposal)) return 'bg-amber-50 text-amber-950 ring-amber-200'
  switch (cell.display_status) {
    case 'pending':
      return 'bg-sky-50 text-sky-950 ring-sky-200'
    case 'accepted':
      return 'bg-emerald-50 text-emerald-950 ring-emerald-200'
    case 'accepted_with_edit':
      return 'bg-teal-50 text-teal-950 ring-teal-200'
    case 'confirmed_no_data':
      return 'bg-violet-50 text-violet-950 ring-violet-200'
    case 'rejected':
      return 'bg-slate-100 text-slate-500 ring-slate-200'
    default:
      return 'bg-white text-slate-700 ring-slate-100'
  }
}

function proposalMatchesFilter(proposal: ReviewTableProposal | null, filter: ReviewFilter): boolean {
  if (!isReviewableProposal(proposal)) return false
  const decision = proposal.latest_decision?.decision
  if (filter === 'pending') return !decision
  if (filter === 'needs_attention') {
    return hasAttentionSignal(proposal)
  }
  if (filter === 'all') return true
  return decision === filter
}

function hasAttentionSignal(proposal: ReviewTableProposal): boolean {
  return !(
    isGreenProposalStatus(proposal.proposal_status) &&
    isGreenEvidenceStatus(proposal.evidence_status, proposal.is_fallback_evidence)
  )
}

function buildSelectedCell(row: ReviewTableRow, column: ReviewTableColumn, cell: ReviewTableCell): SelectedReviewCell {
  return {
    rowId: row.row_id,
    rowIndex: row.row_index,
    paperLabel: row.paper_label,
    title: row.title,
    columnName: column.name,
    columnDescription: column.description,
    originalValue: cell.original_value,
    displayValue: cell.display_value,
    displayStatus: cell.display_status,
  }
}

function emptyCellForColumn(row: ReviewTableRow, column: ReviewTableColumn): ReviewTableCell {
  const value = row.values[column.name] ?? null
  return {
    column_name: column.name,
    original_value: value,
    display_value: value,
    display_status: 'unchanged',
    has_proposal: false,
    proposal: null,
  }
}

function cssEscape(value: string): string {
  return globalThis.CSS?.escape ? globalThis.CSS.escape(value) : value.replace(/["\\]/g, '\\$&')
}

export function ReviewTableView({
  runId,
  outputDir,
  selectedProposalId,
  selectedProposalIds,
  filter,
  onFilterChange,
  onSelect,
  onSelectionChange,
  onVisibleProposalOrderChange,
  onSelectCell,
  refreshVersion = 0,
}: Props) {
  const [tableData, setTableData] = useState<ReviewTableData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const selectionAnchorRef = useRef<{ rowIndex: number; columnIndex: number } | null>(null)
  const dragSelectionRef = useRef<{
    rowIndex: number
    columnIndex: number
    endRowIndex: number
    endColumnIndex: number
    moved: boolean
  } | null>(null)
  const suppressClickRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    async function loadTable() {
      setLoading(true)
      setError(null)
      try {
        const next = await api.getReviewTable(runId, outputDir)
        if (!cancelled) setTableData(next)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void loadTable()
    return () => {
      cancelled = true
    }
  }, [outputDir, refreshVersion, runId])

  const filteredRows = useMemo(() => {
    if (!tableData) return []
    return tableData.rows.filter((row) => {
      return Object.values(row.cells).some(
        (cell) => proposalMatchesFilter(cell.proposal, filter)
      )
    })
  }, [filter, tableData])

  const visibleProposalIds = useMemo(() => {
    if (!tableData) return []
    const ids: string[] = []
    const seen = new Set<string>()
    for (const row of filteredRows) {
      for (const column of tableData.columns) {
        const proposal = row.cells[column.name]?.proposal ?? null
        if (!proposal) continue
        if (!proposalMatchesFilter(proposal, filter)) continue
        if (seen.has(proposal.proposal_id)) continue
        ids.push(proposal.proposal_id)
        seen.add(proposal.proposal_id)
      }
    }
    return ids
  }, [filter, filteredRows, tableData])

  useEffect(() => {
    onVisibleProposalOrderChange?.(visibleProposalIds)
  }, [onVisibleProposalOrderChange, visibleProposalIds])

  useEffect(() => {
    selectionAnchorRef.current = null
  }, [filter, refreshVersion])

  useEffect(() => {
    function finishDragSelection() {
      if (dragSelectionRef.current?.moved) suppressClickRef.current = true
      dragSelectionRef.current = null
    }
    window.addEventListener('mouseup', finishDragSelection)
    return () => window.removeEventListener('mouseup', finishDragSelection)
  }, [])

  function proposalIdsInRectangle(
    start: { rowIndex: number; columnIndex: number },
    end: { rowIndex: number; columnIndex: number },
  ): string[] {
    if (!tableData) return []
    const selected: string[] = []
    const rowStart = Math.min(start.rowIndex, end.rowIndex)
    const rowEnd = Math.max(start.rowIndex, end.rowIndex)
    const columnStart = Math.min(start.columnIndex, end.columnIndex)
    const columnEnd = Math.max(start.columnIndex, end.columnIndex)
    for (let selectedRow = rowStart; selectedRow <= rowEnd; selectedRow += 1) {
      for (let selectedColumn = columnStart; selectedColumn <= columnEnd; selectedColumn += 1) {
        const candidate = filteredRows[selectedRow]?.cells[tableData.columns[selectedColumn]?.name]?.proposal ?? null
        if (isReviewableProposal(candidate)) selected.push(candidate.proposal_id)
      }
    }
    return Array.from(new Set(selected))
  }

  function handleCellMouseDown(event: ReactMouseEvent, rowIndex: number, columnIndex: number) {
    if (event.button !== 0 || event.shiftKey || event.ctrlKey || event.metaKey) return
    dragSelectionRef.current = {
      rowIndex,
      columnIndex,
      endRowIndex: rowIndex,
      endColumnIndex: columnIndex,
      moved: false,
    }
  }

  function handleCellMouseEnter(rowIndex: number, columnIndex: number) {
    const anchor = dragSelectionRef.current
    if (!anchor) return
    if (anchor.endRowIndex === rowIndex && anchor.endColumnIndex === columnIndex) return
    anchor.endRowIndex = rowIndex
    anchor.endColumnIndex = columnIndex
    if (anchor.rowIndex === rowIndex && anchor.columnIndex === columnIndex) return
    anchor.moved = true
    const next = proposalIdsInRectangle(anchor, { rowIndex, columnIndex })
    const primary = selectedProposalId && next.includes(selectedProposalId)
      ? selectedProposalId
      : (next.at(-1) ?? null)
    onSelectionChange(next, primary)
  }

  function handleProposalCellClick(
    event: ReactMouseEvent,
    rowIndex: number,
    columnIndex: number,
    proposal: ReviewTableProposal,
  ) {
    const anchor = selectionAnchorRef.current
    if (event.shiftKey && anchor && tableData) {
      onSelectionChange(proposalIdsInRectangle(anchor, { rowIndex, columnIndex }), proposal.proposal_id)
      return
    }
    selectionAnchorRef.current = { rowIndex, columnIndex }
    if (event.ctrlKey || event.metaKey) {
      const next = selectedProposalIds.includes(proposal.proposal_id)
        ? selectedProposalIds.filter((proposalId) => proposalId !== proposal.proposal_id)
        : [...selectedProposalIds, proposal.proposal_id]
      onSelectionChange(next, next.includes(proposal.proposal_id) ? proposal.proposal_id : (next.at(-1) ?? null))
      return
    }
    onSelect(proposal.proposal_id)
  }

  useEffect(() => {
    if (!selectedProposalId) return
    window.requestAnimationFrame(() => {
      const target = scrollRef.current?.querySelector<HTMLElement>(`[data-proposal-id="${cssEscape(selectedProposalId)}"]`)
      target?.scrollIntoView?.({ block: 'center', inline: 'center' })
    })
  }, [filteredRows, selectedProposalId])

  if (loading && !tableData) {
    return <div className="flex h-32 items-center justify-center text-sm text-slate-400">Loading table...</div>
  }

  if (error) {
    return <div className="p-3 text-sm text-rose-600"><strong>Review table failed:</strong> {error}</div>
  }

  if (!tableData) return null

  return (
    <div className="flex h-full min-h-0 flex-col" data-testid="review-table-view">
      <div className="shrink-0 space-y-2 border-b border-slate-200 bg-white px-3 py-3">
        <select
          value={filter}
          onChange={(event) => onFilterChange(event.target.value as ReviewFilter)}
          className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs text-slate-700"
          aria-label="Table filter"
        >
          <option value="pending">{FILTER_LABELS.pending}</option>
          <option value="needs_attention">{FILTER_LABELS.needs_attention}</option>
          <option value="all">{FILTER_LABELS.all}</option>
          <option value="accepted">{FILTER_LABELS.accepted}</option>
          <option value="accepted_with_edit">{FILTER_LABELS.accepted_with_edit}</option>
          <option value="confirmed_no_data">{FILTER_LABELS.confirmed_no_data}</option>
          <option value="rejected">{FILTER_LABELS.rejected}</option>
        </select>
      </div>

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-auto" data-testid="review-table-scroll">
        <table className="min-w-full border-separate border-spacing-0 text-xs">
          <thead className="sticky top-0 z-20 bg-slate-50 text-left text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-500 shadow-sm">
            <tr>
              {tableData.columns.map((column, index) => (
                <th
                  key={column.name}
                  className={`border-b border-r border-slate-200 px-2 py-2 ${index === 0 ? 'sticky left-0 z-30 w-32 min-w-32 max-w-32 bg-slate-50' : 'min-w-36'}`}
                  title={column.description ?? column.name}
                >
                  <span className="block truncate">{column.name}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.map((row, rowIndex) => (
              <tr key={row.row_id}>
                {tableData.columns.map((column, index) => {
                  const cell = row.cells[column.name] ?? emptyCellForColumn(row, column)
                  const proposal = cell?.proposal ?? null
                  const isSelected = proposal?.proposal_id === selectedProposalId
                  const isMultiSelected = !!proposal && selectedProposalIds.includes(proposal.proposal_id)
                  return (
                    <td
                      key={`${row.row_id}-${column.name}`}
                      className={`border-b border-r border-slate-100 align-top ${index === 0 ? 'sticky left-0 z-10 bg-white shadow-[6px_0_14px_rgba(15,23,42,0.04)]' : ''}`}
                    >
                      <button
                        onMouseDown={(event) => handleCellMouseDown(event, rowIndex, index)}
                        onMouseEnter={() => handleCellMouseEnter(rowIndex, index)}
                        onMouseMove={() => handleCellMouseEnter(rowIndex, index)}
                        onClick={(event) => {
                          if (suppressClickRef.current) {
                            suppressClickRef.current = false
                            return
                          }
                          if (isReviewableProposal(proposal)) {
                            onVisibleProposalOrderChange?.(visibleProposalIds)
                            handleProposalCellClick(event, rowIndex, index, proposal)
                            return
                          }
                          selectionAnchorRef.current = null
                          onSelectCell?.(buildSelectedCell(row, column, cell))
                        }}
                        title={displayCellValue(cell)}
                        className={`flex h-full min-h-20 w-full flex-col justify-between px-2 py-2 text-left ring-1 ring-inset transition ${statusClass(cell)} ${
                          'hover:ring-slate-400'
                        } ${isMultiSelected ? 'outline outline-2 outline-sky-500' : ''} ${isSelected ? 'outline-sky-700' : ''}`}
                        data-testid={proposal ? `review-table-cell-${proposal.proposal_id}` : undefined}
                        data-proposal-id={proposal?.proposal_id}
                        aria-pressed={isMultiSelected}
                      >
                        <span className="line-clamp-2 min-h-8 text-[12px] font-medium leading-4">{displayCellValue(cell)}</span>
                        {proposal && (
                          <span className="mt-1 flex h-4 items-center gap-0.5">
                            <ReviewStatusIndicator decision={proposal.latest_decision?.decision ?? null} size="xs" />
                            <ProposalStatusIndicator status={proposal.proposal_status} size="xs" />
                            <EvidenceStatusIndicator evidenceStatus={proposal.evidence_status} isFallback={proposal.is_fallback_evidence} size="xs" />
                          </span>
                        )}
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {filteredRows.length === 0 && <div className="px-4 py-8 text-center text-sm text-slate-400">No rows match this filter.</div>}
      </div>
    </div>
  )
}
