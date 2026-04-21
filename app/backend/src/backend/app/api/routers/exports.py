from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...artifacts import get_run_dir, get_run_summary_path
from ...export import run_export

router = APIRouter()


@router.get('/api/runs/{run_id}/downloads/workbook')
async def download_workbook(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    exports_dir = run_dir / 'exports'
    if not exports_dir.exists():
        raise HTTPException(status_code=404, detail='No exports found. Complete review and trigger export first.')
    workbook_files = sorted(exports_dir.glob('*.xlsx'))
    if not workbook_files:
        raise HTTPException(status_code=404, detail='No workbook export found. Trigger export after completing review.')
    latest = workbook_files[-1]
    return FileResponse(str(latest), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', filename=latest.name)


@router.get('/api/runs/{run_id}/downloads/audit-log')
async def download_audit_log(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    exports_dir = run_dir / 'exports'
    if not exports_dir.exists():
        raise HTTPException(status_code=404, detail='No exports found.')
    audit_files = sorted(exports_dir.glob('audit_log*.json')) + sorted(exports_dir.glob('audit_log*.csv'))
    if not audit_files:
        raise HTTPException(status_code=404, detail='No audit log found.')
    latest = audit_files[-1]
    return FileResponse(str(latest), media_type='application/json' if latest.suffix.lower() == '.json' else 'text/csv', filename=latest.name)


@router.get('/api/runs/{run_id}/downloads/run-summary')
async def download_run_summary_file(run_id: str, output_dir: str = './runs'):
    path = get_run_summary_path(output_dir, run_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail='run_summary.json not found.')
    return FileResponse(str(path), media_type='application/json', filename='run_summary.json')


@router.get('/api/runs/{run_id}/downloads/reviewer-summary')
async def download_reviewer_summary_file(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    reviewer_path = run_dir / 'summaries' / 'reviewer_summary.json'
    if not reviewer_path.exists():
        raise HTTPException(status_code=404, detail='reviewer_summary.json not found.')
    return FileResponse(str(reviewer_path), media_type='application/json', filename='reviewer_summary.json')


@router.post('/api/runs/{run_id}/export')
async def trigger_export(run_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    try:
        return run_export(run_dir, output_dir, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Export failed: {exc}')
