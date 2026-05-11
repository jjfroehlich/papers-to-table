"""Shared fixtures for backend tests."""
from __future__ import annotations

import json
import pathlib
from typing import Generator

import pytest

FIXTURE_TABLE = "../benchmark_datasets/massively_parallel_reporter_assays/table_template.csv"
FIXTURE_TABLE_CSV = "../benchmark_datasets/massively_parallel_reporter_assays/table_template.csv"
FIXTURE_SCHEMA = "../benchmark_datasets/massively_parallel_reporter_assays/schema.csv"
FIXTURE_PDF_DIR = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs"
FIXTURE_CONFIG = "config.example.json"


@pytest.fixture
def tmp_output_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    out = tmp_path / "runs"
    out.mkdir()
    return out


@pytest.fixture
def minimal_config_dict(tmp_output_dir: pathlib.Path) -> dict:
    return {
        "table_path": FIXTURE_TABLE,
        "schema_path": FIXTURE_SCHEMA,
        "pdf_dir": FIXTURE_PDF_DIR,
        "output_dir": str(tmp_output_dir),
        "verify_mode": False,
        "provider": {
            "token": "lm_studio",
            "base_url": "http://localhost:1234",
            "text_model": {
                "model_id": "qwen/qwen3-30b-a3b-2507"
            },
        },
    }


@pytest.fixture
def minimal_config_file(tmp_path: pathlib.Path, minimal_config_dict: dict) -> pathlib.Path:
    p = tmp_path / "config.json"
    p.write_text(json.dumps(minimal_config_dict), encoding="utf-8")
    return p


@pytest.fixture
def lm_studio_config(minimal_config_dict: dict):
    from backend.app.config import RunConfig
    return RunConfig.model_validate(minimal_config_dict)

