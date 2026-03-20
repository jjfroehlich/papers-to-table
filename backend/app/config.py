from __future__ import annotations

import json
from pathlib import Path

from .models import AppConfig


def load_config(config_path: str | None = None, config_data: dict | None = None) -> AppConfig:
    if config_data is not None:
        return AppConfig.model_validate(config_data)
    if not config_path:
        raise ValueError("Either config_path or config must be provided")
    payload = json.loads(Path(config_path).read_text(encoding="utf-8"))
    return AppConfig.model_validate(payload)


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
