from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...artifacts import get_config_snapshot_path, get_input_summary_path, get_run_dir, get_run_json_path, get_run_summary_path, list_run_ids, read_json
from ...review import compute_reviewer_summary, get_progress, get_progress_for_review, recompute_summaries
from ...run_executor import get_run_executor
from ...schemas import RunStatus

router = APIRouter()


@router.get('/api/runs')
async def list_runs(output_dir: str = './runs'):
    try:
        run_ids = list_run_ids(output_dir)
    except Exception:
        return {'runs': []}
    runs = []
    for run_id in run_ids:
        try:
            runs.append(read_json(get_run_json_path(output_dir, run_id)))
        except Exception:
            pass
    runs.sort(key=lambda item: item.get('created_at', ''), reverse=True)
    return {'runs': runs}


@router.get('/api/runs/{run_id}')
async def get_run(run_id: str, output_dir: str = './runs'):
    path = get_run_json_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return read_json(path)


@router.get('/api/runs/{run_id}/config')
async def get_run_config(run_id: str, output_dir: str = './runs'):
    path = get_config_snapshot_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail='Config snapshot not found')
    return read_json(path)


@router.get('/api/runs/{run_id}/inputs')
async def get_run_inputs(run_id: str, output_dir: str = './runs'):
    path = get_input_summary_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail='Input summary not found')
    return read_json(path)


@router.get('/api/runs/{run_id}/summary')
async def get_run_summary(run_id: str, output_dir: str = './runs'):
    path = get_run_summary_path(output_dir, run_id)
    if not path.exists():
        return await get_run(run_id, output_dir)
    return read_json(path)


@router.get('/api/runs/{run_id}/progress')
async def get_run_progress(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return {'run_id': run_id, **get_progress(run_dir)}


@router.get('/api/runs/{run_id}/progress-review')
async def get_run_review_progress(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return {'run_id': run_id, **get_progress_for_review(run_dir)}


@router.post('/api/runs/{run_id}/abort')
async def abort_run_endpoint(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    run_data = read_json(run_dir / 'run.json')
    if run_data.get('status') not in {RunStatus.created.value, RunStatus.validating.value, RunStatus.running.value}:
        raise HTTPException(status_code=409, detail=f'Run is not active: {run_id}')
    cancelled = await get_run_executor().abort(run_id)
    if not cancelled:
        raise HTTPException(status_code=409, detail=f'Run is not active in the current backend process: {run_id}')
    return {'run_id': run_id, 'status': 'interrupting'}


@router.get('/api/runs/{run_id}/reviewer-summary')
async def get_reviewer_summary_endpoint(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    return compute_reviewer_summary(run_dir, run_id).model_dump()


@router.post('/api/runs/{run_id}/summaries/recompute')
async def recompute_run_summaries(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    try:
        return recompute_summaries(run_dir, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
