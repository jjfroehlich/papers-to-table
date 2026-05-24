from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException

from ...artifacts import get_run_dir, read_json
from ...extraction import load_proposals
from ...review import (
    ProposalFilter,
    build_review_table,
    bulk_accept_proposals,
    get_export_candidates,
    get_proposal_detail,
    get_latest_decision,
    list_proposals,
    record_review_decision,
)
from ...review_lookup import ensure_review_lookup, load_review_lookup
from ...schemas import ReviewDecision, ReviewResolutionReason
from ..models import BulkAcceptRequest, RecordDecisionRequest

router = APIRouter()


def _lookup_context(output_dir: str, run_id: str, run_dir) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    run_data = None
    try:
        run_data = read_json(run_dir / 'run.json')
    except Exception:
        pass
    lookup = None
    if run_data and run_data.get('table_path'):
        try:
            lookup = ensure_review_lookup(output_dir, run_id, run_data['table_path'], run_data.get('schema_path'))
        except Exception:
            lookup = load_review_lookup(output_dir, run_id)
    rows = (lookup or {}).get('rows_by_id') if isinstance(lookup, dict) else None
    columns = (lookup or {}).get('columns_by_name') if isinstance(lookup, dict) else None
    papers = (lookup or {}).get('papers_by_pdf_id') if isinstance(lookup, dict) else None
    return rows, columns, papers


@router.get('/api/runs/{run_id}/proposals')
async def get_proposals(
    run_id: str,
    output_dir: str = './runs',
    row_id: Optional[str] = None,
    column_name: Optional[str] = None,
    pdf_id: Optional[str] = None,
    evidence_status: Optional[str] = None,
    figure_derived: Optional[bool] = None,
    decision: Optional[str] = None,
    match_status: Optional[str] = None,
    reviewable_only: bool = False,
):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    proposals = list_proposals(
        run_dir,
        ProposalFilter(
            row_id=row_id,
            column_name=column_name,
            pdf_id=pdf_id,
            evidence_status=evidence_status,
            figure_derived=figure_derived,
            decision=decision,
            match_status=match_status,
            reviewable_only=reviewable_only,
        ),
    )
    rows, _columns, papers = _lookup_context(output_dir, run_id, run_dir)
    for proposal in proposals:
        row_context = rows.get(proposal.get('row_id', '')) if isinstance(rows, dict) else None
        paper_context = papers.get(proposal.get('pdf_id', '')) if isinstance(papers, dict) else None
        if isinstance(row_context, dict):
            proposal['paper_title'] = row_context.get('title')
            proposal['paper_authors'] = row_context.get('authors')
            proposal['paper_year'] = row_context.get('year')
            proposal['paper_label'] = row_context.get('paper_label')
        elif isinstance(paper_context, dict):
            proposal['paper_title'] = paper_context.get('paper_title')
            proposal['paper_authors'] = paper_context.get('paper_authors')
            proposal['paper_year'] = paper_context.get('paper_year')
            proposal['paper_label'] = paper_context.get('paper_label')
    return {'run_id': run_id, 'count': len(proposals), 'proposals': proposals}


@router.get('/api/runs/{run_id}/review-table')
async def get_review_table(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    run_data = None
    try:
        run_data = read_json(run_dir / 'run.json')
    except Exception:
        pass
    lookup = None
    if run_data and run_data.get('table_path'):
        try:
            lookup = ensure_review_lookup(output_dir, run_id, run_data['table_path'], run_data.get('schema_path'))
        except Exception:
            lookup = load_review_lookup(output_dir, run_id)
    else:
        lookup = load_review_lookup(output_dir, run_id)
    return build_review_table(run_dir, lookup)


@router.get('/api/runs/{run_id}/proposals/{proposal_id}')
async def get_proposal(run_id: str, proposal_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    rows, columns, _papers = _lookup_context(output_dir, run_id, run_dir)
    row_values = (
        {row_id: row_info.get('values') for row_id, row_info in rows.items()}
        if isinstance(rows, dict)
        else None
    )
    detail = get_proposal_detail(run_dir, proposal_id, row_data=row_values, column_defs=columns)
    if detail is None:
        raise HTTPException(status_code=404, detail=f'Proposal not found: {proposal_id}')
    return detail


@router.post('/api/runs/{run_id}/proposals/{proposal_id}/decision')
async def record_decision(run_id: str, proposal_id: str, request: RecordDecisionRequest, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    try:
        decision = ReviewDecision(request.decision)
    except ValueError:
        raise HTTPException(status_code=422, detail=f'Invalid decision value: {request.decision!r}. Must be one of: {[d.value for d in ReviewDecision]}')
    resolution_reason = None
    if request.resolution_reason:
        try:
            resolution_reason = ReviewResolutionReason(request.resolution_reason)
        except ValueError:
            raise HTTPException(status_code=422, detail=f'Invalid resolution_reason: {request.resolution_reason!r}')
    proposal = next((proposal for proposal in load_proposals(run_dir) if proposal.proposal_id == proposal_id), None)
    if proposal is None:
        raise HTTPException(status_code=404, detail=f'Proposal not found: {proposal_id}')
    return record_review_decision(
        run_dir=run_dir,
        proposal_id=proposal_id,
        cell_id=proposal.cell_id,
        run_id=run_id,
        decision=decision,
        resolution_reason=resolution_reason,
        edited_value=request.edited_value,
        reviewer_note=request.reviewer_note,
    ).model_dump()


@router.post('/api/runs/{run_id}/proposals/bulk-accept')
async def bulk_accept(run_id: str, request: BulkAcceptRequest, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    recorded = bulk_accept_proposals(run_dir, run_id, request.proposal_ids)
    return {'run_id': run_id, 'accepted_count': len(recorded), 'decisions': [decision.model_dump() for decision in recorded]}


@router.get('/api/runs/{run_id}/export-candidates')
async def get_run_export_candidates(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    candidates = get_export_candidates(run_dir)
    return {'run_id': run_id, 'count': len(candidates), 'candidates': candidates}
