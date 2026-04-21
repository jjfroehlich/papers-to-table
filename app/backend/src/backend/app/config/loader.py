from __future__ import annotations

import json
from pathlib import Path

from .models import RunConfig


def _resolve_path_value(value: object, base_dir: Path) -> object:
    if not isinstance(value, str) or not value.strip():
        return value
    candidate = Path(value)
    if candidate.is_absolute():
        return str(candidate.resolve())
    return str((base_dir / candidate).resolve())


def _resolve_config_paths(data: dict, base_dir: Path) -> dict:
    resolved = dict(data)
    for key in ('table_path', 'schema_path', 'pdf_dir', 'output_dir'):
        if key in resolved:
            resolved[key] = _resolve_path_value(resolved.get(key), base_dir)
    prompt_data = resolved.get('prompt')
    if isinstance(prompt_data, dict) and 'bundle_path' in prompt_data:
        prompt_resolved = dict(prompt_data)
        prompt_resolved['bundle_path'] = _resolve_path_value(prompt_data.get('bundle_path'), base_dir)
        resolved['prompt'] = prompt_resolved
    return resolved


def load_config(path: str) -> RunConfig:
    config_path = Path(path).resolve()
    with open(config_path, 'r', encoding='utf-8') as handle:
        data = json.load(handle)
    return RunConfig.model_validate(_resolve_config_paths(data, config_path.parent))


def apply_overrides(config: RunConfig, overrides: dict, base_dir: str | None = None) -> RunConfig:
    data = config.model_dump()
    resolved_base_dir = Path(base_dir).resolve() if base_dir else None
    for key in ('table_path', 'schema_path', 'pdf_dir'):
        if key in overrides and overrides[key] is not None:
            data[key] = _resolve_path_value(overrides[key], resolved_base_dir) if resolved_base_dir is not None else overrides[key]
    return RunConfig.model_validate(data)
