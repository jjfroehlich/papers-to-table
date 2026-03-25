from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .artifacts import RunArtifacts


class PathConfig(BaseModel):
    table_path: str
    schema_path: str | None = None
    pdf_dir: str
    output_dir: str


class RunConfig(BaseModel):
    paths: PathConfig
    parser: dict[str, Any] = Field(default_factory=dict)
    ocr_fallback: dict[str, Any] = Field(default_factory=dict)
    matching: dict[str, Any] = Field(default_factory=dict)
    style_profiles: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, Any] = Field(default_factory=dict)
    figure_fallback: dict[str, Any] = Field(default_factory=dict)
    review: dict[str, Any] = Field(default_factory=dict)
    export: dict[str, Any] = Field(default_factory=dict)
    verify_mode: bool = True
    placeholders_treated_as_empty: list[str] = Field(default_factory=lambda: ["", " "])


REQUIRED_SECTIONS = {
    "parser",
    "ocr_fallback",
    "matching",
    "style_profiles",
    "retrieval",
    "provider",
    "figure_fallback",
    "review",
    "export",
}


class ConfigError(ValueError):
    pass


def _ensure_path_exists(path: Path, label: str, must_be_dir: bool = False) -> None:
    if not path.exists():
        raise ConfigError(f"{label} does not exist: {path}")
    if must_be_dir and not path.is_dir():
        raise ConfigError(f"{label} must be a directory: {path}")
    if not must_be_dir and path.is_dir() and label.endswith("file"):
        raise ConfigError(f"{label} must be a file: {path}")


def load_and_validate_config(config_path: str) -> tuple[RunConfig, Path]:
    config_file = Path(config_path).expanduser().resolve()
    _ensure_path_exists(config_file, "config file")

    with config_file.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)

    missing_sections = sorted(section for section in REQUIRED_SECTIONS if section not in raw)
    if missing_sections:
        raise ConfigError(f"Config is missing required sections: {', '.join(missing_sections)}")

    config = RunConfig.model_validate(raw)

    table_path = Path(config.paths.table_path).expanduser().resolve()
    schema_path = Path(config.paths.schema_path).expanduser().resolve() if config.paths.schema_path else None
    pdf_dir = Path(config.paths.pdf_dir).expanduser().resolve()
    output_dir = Path(config.paths.output_dir).expanduser().resolve()

    _ensure_path_exists(table_path, "table file")
    if schema_path is not None:
        _ensure_path_exists(schema_path, "schema file")
    _ensure_path_exists(pdf_dir, "pdf directory", must_be_dir=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    config.paths.table_path = str(table_path)
    config.paths.schema_path = str(schema_path) if schema_path else None
    config.paths.pdf_dir = str(pdf_dir)
    config.paths.output_dir = str(output_dir)

    return config, config_file


def snapshot_config(artifacts: RunArtifacts, config: RunConfig) -> None:
    artifacts.write_json("config.snapshot.json", config.model_dump(mode="json"))
