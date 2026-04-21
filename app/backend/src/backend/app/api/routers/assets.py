from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ...artifacts import get_run_dir
from ...review import get_evidence_asset_metadata, get_figure_crop_path, get_page_image_path, get_pdf_asset_path
from ..common import open_in_local_viewer
from ..models import OpenPdfResponse

router = APIRouter()


@router.get('/api/runs/{run_id}/assets/pdf/{pdf_id}')
async def serve_pdf(run_id: str, pdf_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    pdf_path = get_pdf_asset_path(run_dir, pdf_id)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f'PDF not found for pdf_id={pdf_id}')
    return FileResponse(str(pdf_path), media_type='application/pdf')


@router.post('/api/runs/{run_id}/assets/pdf/{pdf_id}/open', response_model=OpenPdfResponse)
async def open_pdf_in_local_viewer(run_id: str, pdf_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    pdf_path = get_pdf_asset_path(run_dir, pdf_id)
    if pdf_path is None or not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f'PDF not found for pdf_id={pdf_id}')
    try:
        open_in_local_viewer(pdf_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Failed to open local PDF viewer: {exc}')
    return OpenPdfResponse(run_id=run_id, pdf_id=pdf_id, status='opened', path=str(pdf_path))


@router.get('/api/runs/{run_id}/assets/pages/{pdf_id}/{page}')
async def serve_page_image(run_id: str, pdf_id: str, page: int, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    image_path = get_page_image_path(run_dir, pdf_id, page)
    if image_path is None:
        raise HTTPException(status_code=404, detail=f'Page image not found for pdf_id={pdf_id} page={page}')
    return FileResponse(str(image_path), media_type='image/png')


@router.get('/api/runs/{run_id}/assets/figures/{pdf_id}/{figure_id}')
async def serve_figure_crop(run_id: str, pdf_id: str, figure_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    crop_path = get_figure_crop_path(run_dir, pdf_id, figure_id)
    if crop_path is None:
        raise HTTPException(status_code=404, detail=f'Figure crop not found for pdf_id={pdf_id} figure_id={figure_id}')
    return FileResponse(str(crop_path), media_type='image/png')


@router.get('/api/runs/{run_id}/assets/evidence/{evidence_id}')
async def get_evidence_metadata(run_id: str, evidence_id: str, output_dir: str = './runs'):
    run_dir = get_run_dir(output_dir, run_id)
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f'Run not found: {run_id}')
    metadata = get_evidence_asset_metadata(run_dir, evidence_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f'Evidence not found: {evidence_id}')
    return metadata
