from __future__ import annotations

import pathlib
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ...config import apply_overrides, check_readiness, load_config
from ...ids import generate_run_id
from ...ingest import load_schema, load_table
from ...run_executor import get_run_executor
from ...schemas import RunStatus
from ..common import load_staged_input_metadata, materialize_staged_input_files, resolve_path_like
from ..models import CreateRunRequest, CreateRunResponse, RunPreflightRequest, StagedInputResponse

router = APIRouter()


@router.post('/api/staged-inputs', response_model=StagedInputResponse)
async def stage_input_files(
    kind: str = Form(...),
    output_dir: str = Form('./runs'),
    files: list[UploadFile] = File(...),
):
    metadata = await materialize_staged_input_files(kind=kind, output_dir=output_dir, files=files)
    return StagedInputResponse(
        handle=metadata['handle'],
        kind=metadata['kind'],
        logical_source=metadata['logical_source'],
        runtime_locator=metadata['runtime_locator'],
    )


def _resolve_preflight_config(request: RunPreflightRequest):
    try:
        config = load_config(request.config_path)
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail=f'Config file not found: {request.config_path}')
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f'Config error: {exc}')

    config_base_dir = pathlib.Path(request.config_path).resolve().parent
    resolved_inputs: dict[str, Any] = {
        'table_path': {
            'source_kind': 'config',
            'logical_source': config.table_path,
            'runtime_locator': config.table_path,
        },
        'schema_path': {
            'source_kind': 'config',
            'logical_source': config.schema_path,
            'runtime_locator': config.schema_path,
        },
        'pdf_dir': {
            'source_kind': 'config',
            'logical_source': config.pdf_dir,
            'runtime_locator': config.pdf_dir,
        },
    }

    for key, path_value, staged_handle in (
        ('table_path', request.table_path, request.table_staged_handle),
        ('schema_path', request.schema_path, request.schema_staged_handle),
        ('pdf_dir', request.pdf_dir, request.pdf_dir_staged_handle),
    ):
        if path_value and staged_handle:
            raise HTTPException(
                status_code=422,
                detail=f"Provide either {key} or {key.replace('_path', '')}_staged_handle, not both.",
            )

    overrides = {}
    for key, path_value, staged_handle in (
        ('table_path', request.table_path, request.table_staged_handle),
        ('schema_path', request.schema_path, request.schema_staged_handle),
        ('pdf_dir', request.pdf_dir, request.pdf_dir_staged_handle),
    ):
        if staged_handle:
            meta = load_staged_input_metadata(config.output_dir, staged_handle, key)
            overrides[key] = meta['runtime_locator']
            resolved_inputs[key] = {
                'source_kind': 'staged_handle',
                'staged_handle': staged_handle,
                'logical_source': meta.get('logical_source'),
                'runtime_locator': meta['runtime_locator'],
            }
        elif path_value:
            runtime_locator = resolve_path_like(path_value, config_base_dir)
            overrides[key] = path_value
            resolved_inputs[key] = {
                'source_kind': 'path_override',
                'logical_source': path_value,
                'runtime_locator': runtime_locator,
            }

    if overrides:
        try:
            config = apply_overrides(config, overrides, base_dir=str(config_base_dir))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f'Override error: {exc}')

    return config, resolved_inputs


@router.post('/api/runs/preflight')
async def preflight_run(request: RunPreflightRequest):
    config, resolved_inputs = _resolve_preflight_config(request)
    readiness = await check_readiness(config)

    table_rows = None
    schema_columns = None
    pdf_count = None
    scope_warnings: list[str] = []
    try:
        table_rows = len(load_table(config.table_path))
    except Exception as exc:
        scope_warnings.append(f'Table preview unavailable: {exc}')
    try:
        schema_columns = len(load_schema(config.schema_path, config.table_path))
    except Exception as exc:
        scope_warnings.append(f'Schema preview unavailable: {exc}')
    try:
        pdf_count = len([path for path in pathlib.Path(config.pdf_dir).iterdir() if path.suffix.lower() == '.pdf'])
    except Exception as exc:
        scope_warnings.append(f'PDF scope preview unavailable: {exc}')

    return {
        'config_path': request.config_path,
        'run_mode': 'eval' if config.eval_mode else 'verify' if config.verify_mode else 'normal',
        'output_dir': config.output_dir,
        'resolved_inputs': resolved_inputs,
        'provider': {
            'token': config.provider.token,
            'locality': config.provider.locality,
            'base_url': config.provider.base_url,
            'text_model_id': config.provider.text_model.model_id,
            'vision_model_id': config.provider.vision_model.model_id if config.provider.vision_model else None,
        },
        'scope': {
            'table_rows': table_rows,
            'schema_columns': schema_columns,
            'pdf_count': pdf_count,
        },
        'readiness': {
            'ok': readiness.ok,
            'errors': readiness.errors,
            'warnings': readiness.warnings + scope_warnings,
            'provider_mode': readiness.provider_mode,
            'provider_readiness_reason': readiness.provider_readiness_reason,
            'provider_readiness_error': readiness.provider_readiness_error,
        },
        'what_happens_next': [
            'Validate inputs and provider readiness again at run start.',
            'Parse PDFs and resolve row matching before extraction.',
            'Generate one best proposal per eligible target cell with evidence.',
            'Open the completed run in the review workspace for explicit decisions and export.',
        ],
    }


@router.post('/api/runs', response_model=CreateRunResponse)
async def create_run(request: CreateRunRequest):
    config, resolved_inputs = _resolve_preflight_config(RunPreflightRequest.model_validate(request.model_dump()))

    run_id = generate_run_id()
    get_run_executor().launch(run_id, config, request.config_path, config.output_dir, resolved_inputs=resolved_inputs)
    return CreateRunResponse(run_id=run_id, status=RunStatus.created.value, resolved_inputs=resolved_inputs)
