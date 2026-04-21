from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .models import RunConfig


def _is_configured_model_id(model_id: Optional[str]) -> bool:
    if model_id is None:
        return False
    normalized = model_id.strip()
    return bool(normalized) and normalized != 'default'


class ReadinessResult:
    def __init__(self) -> None:
        self.ok: bool = True
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.provider_mode: Optional[str] = None
        self.provider_readiness_error: Optional[str] = None
        self.provider_readiness_reason: Optional[str] = None
        self.structured_output_mode: Optional[str] = None
        self.structured_output_fallback_used: bool = False
        self.provider_model_management: Optional[dict[str, Any]] = None

    def fail(self, msg: str) -> None:
        self.ok = False
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


async def check_readiness(config: RunConfig) -> ReadinessResult:
    r = ReadinessResult()

    if config.verify_mode and config.eval_mode:
        r.fail(
            'verify_mode=true and eval_mode=true cannot be used together. '
            'Disable one mode before starting the run.'
        )

    if not os.path.exists(config.table_path):
        r.fail(f'table_path does not exist: {config.table_path}')
    elif not os.access(config.table_path, os.R_OK):
        r.fail(f'table_path is not readable: {config.table_path}')

    if config.schema_path and not os.path.exists(config.schema_path):
        r.fail(f'schema_path does not exist: {config.schema_path}')
    elif config.schema_path and not os.access(config.schema_path, os.R_OK):
        r.fail(f'schema_path is not readable: {config.schema_path}')

    if not os.path.exists(config.pdf_dir):
        r.fail(f'pdf_dir does not exist: {config.pdf_dir}')
    elif not os.path.isdir(config.pdf_dir):
        r.fail(f'pdf_dir is not a directory: {config.pdf_dir}')

    output_dir = config.output_dir
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as exc:
            r.fail(f'Cannot create output_dir: {exc}')
    elif not os.path.isdir(output_dir):
        r.fail(f'output_dir is not a directory: {output_dir}')
    elif not os.access(output_dir, os.W_OK):
        r.fail(f'output_dir is not writable: {output_dir}')

    if config.provider.token == 'lm_studio':
        text_model_id = config.provider.text_model.model_id
        if not _is_configured_model_id(text_model_id):
            r.provider_mode = 'unavailable'
            r.provider_readiness_reason = 'model_unavailable'
            r.provider_readiness_error = (
                'provider.text_model.model_id must be set to a real LM Studio model id; '
                '"default" is not allowed.'
            )
            r.fail(r.provider_readiness_error)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f'{config.provider.base_url}/v1/models')
                if resp.status_code != 200:
                    r.fail(
                        f'LM Studio at {config.provider.base_url} returned HTTP {resp.status_code}. '
                        'Is LM Studio running?'
                    )
                else:
                    vision_model = config.provider.vision_model
                    vision_model_id = vision_model.model_id if vision_model else None
                    if config.figure_review.enabled and not _is_configured_model_id(vision_model_id):
                        message = 'figure_review is enabled, but provider.vision_model.model_id is missing or invalid.'
                        r.provider_mode = 'unavailable'
                        r.provider_readiness_reason = 'model_unavailable'
                        r.provider_readiness_error = message
                        r.fail(message)
                    if r.ok:
                        r.provider_mode = 'live_local'
        except Exception as exc:
            message = f'Cannot reach LM Studio at {config.provider.base_url}: {exc}. Is LM Studio running?'
            r.provider_mode = 'unavailable'
            r.provider_readiness_reason = 'provider_unreachable'
            r.provider_readiness_error = message
            r.structured_output_mode = 'none'
            r.structured_output_fallback_used = False
            r.fail(message)

    from ..parsing import check_ocr_readiness, check_parser_readiness

    for err in check_parser_readiness(config.parser.backend, config.parser.allow_basic_fallback):
        r.fail(err)
    for err in check_ocr_readiness(config.parser.ocr_enabled):
        r.fail(err)

    return r
