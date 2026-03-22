from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path

from pydantic import ValidationError

from .models import AppConfig


def _resolve_runtime_path(value: str | None, base_dir: Path) -> str | None:
    if not value:
        return value
    path = Path(value)
    if path.is_absolute():
        return str(path)
    if path.exists():
        return str(path.resolve())
    return str((base_dir / path).resolve())


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(str(item) for item in error.get("loc", [])) or "config"
        parts.append(f"{location}: {error.get('msg', 'Invalid value')}")
    return "; ".join(parts)


def _validate_model(payload: dict) -> AppConfig:
    try:
        return AppConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Config validation failed: {_format_validation_error(exc)}") from exc


def load_config(config_path: str | None = None, config_data: dict | None = None) -> AppConfig:
    if config_data is not None:
        return _validate_model(config_data)
    if not config_path:
        raise ValueError("Either config_path or config must be provided")
    path = Path(config_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Config file does not exist: {path}") from exc
    except JSONDecodeError as exc:
        raise ValueError(f"Config file is not valid JSON: {path} ({exc.msg})") from exc
    paths = payload.setdefault("paths", {})
    base_dir = path.resolve().parent
    for key in ("table_path", "schema_path", "pdf_dir", "output_dir"):
        if key in paths:
            paths[key] = _resolve_runtime_path(paths[key], base_dir)
    return _validate_model(payload)


def resolve_config_defaults(config: AppConfig) -> AppConfig:
    return AppConfig.model_validate(config.model_dump())


def validate_config(config: AppConfig) -> None:
    table_path = Path(config.paths.table_path)
    if not table_path.exists():
        raise FileNotFoundError(f"Configured table path does not exist: {table_path}")
    pdf_dir = Path(config.paths.pdf_dir)
    if not pdf_dir.exists() or not pdf_dir.is_dir():
        raise FileNotFoundError(f"Configured PDF directory does not exist: {pdf_dir}")
    if config.paths.schema_path:
        schema_path = Path(config.paths.schema_path)
        if not schema_path.exists():
            raise FileNotFoundError(f"Configured schema path does not exist: {schema_path}")
    if not any(pdf_dir.glob("*.pdf")):
        raise ValueError(f"Configured PDF directory contains no .pdf files: {pdf_dir}")
    Path(config.paths.output_dir).mkdir(parents=True, exist_ok=True)
