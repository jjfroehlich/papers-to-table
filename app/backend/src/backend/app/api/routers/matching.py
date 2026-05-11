from fastapi import APIRouter, HTTPException

from ...artifacts import get_run_dir, read_json
from ...matching import load_ambiguous, load_conflicts, load_match_results, load_match_summary, load_unmatched
from ...parsing import get_parsed_dir

router = APIRouter()


@router.get('/api/runs/{run_id}/matching')
async def get_run_matching(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return {'run_id': run_id, 'summary': load_match_summary(run_dir), 'results': load_match_results(run_dir)}


@router.get('/api/runs/{run_id}/matching/summary')
async def get_run_matching_summary(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    summary = load_match_summary(run_dir)
    if summary is None:
        raise HTTPException(status_code=404, detail='Matching not yet complete for this run')
    return summary


@router.get('/api/runs/{run_id}/matching/unmatched')
async def get_run_unmatched(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return {'run_id': run_id, 'unmatched': load_unmatched(run_dir)}


@router.get('/api/runs/{run_id}/matching/ambiguous')
async def get_run_ambiguous(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return {'run_id': run_id, 'ambiguous': load_ambiguous(run_dir)}


@router.get('/api/runs/{run_id}/matching/conflicts')
async def get_run_conflicts(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return {'run_id': run_id, 'conflicts': load_conflicts(run_dir)}


@router.get('/api/runs/{run_id}/parsed/{pdf_id}')
async def get_parsed_document(run_id: str, pdf_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    parsed_path = get_parsed_dir(run_dir, pdf_id) / 'parsed_document.json'
    if not parsed_path.exists():
        raise HTTPException(status_code=404, detail=f'Parsed document not found for pdf_id={pdf_id} in run {run_id}')
    return read_json(parsed_path)


@router.get('/api/runs/{run_id}/parsed/{pdf_id}/diagnostics')
async def get_parse_diagnostics(run_id: str, pdf_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    diagnostics_path = get_parsed_dir(run_dir, pdf_id) / 'diagnostics.json'
    if not diagnostics_path.exists():
        raise HTTPException(status_code=404, detail=f'Parser diagnostics not found for pdf_id={pdf_id} in run {run_id}')
    return read_json(diagnostics_path)
