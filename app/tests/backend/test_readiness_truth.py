from __future__ import annotations

import pathlib
from unittest.mock import patch

import httpx
import pytest

from backend.app.config import RunConfig, check_readiness


def _config_dict(tmp_path: pathlib.Path) -> dict:
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    table_path = tmp_path / "table.csv"
    schema_path = tmp_path / "schema.csv"
    table_path.write_text("Title,Authors,Publication Year\nPaper A,Smith,2024\n", encoding="utf-8")
    schema_path.write_text("column_name,description\nMethod,Method used\n", encoding="utf-8")
    return {
        "table_path": str(table_path),
        "schema_path": str(schema_path),
        "pdf_dir": str(pdf_dir),
        "output_dir": str(tmp_path / "runs"),
        "provider": {
            "token": "lm_studio",
            "base_url": "http://localhost:1234",
            "text_model": {"model_id": "loaded-text-model"},
        },
    }


@pytest.mark.asyncio
async def test_readiness_reports_provider_unreachable(tmp_path: pathlib.Path):
    config = RunConfig.model_validate(_config_dict(tmp_path))

    with patch("backend.app.config.httpx.AsyncClient.get", side_effect=httpx.ConnectError("boom")):
        readiness = await check_readiness(config)

    assert readiness.ok is False
    assert readiness.provider_mode == "unavailable"
    assert readiness.provider_readiness_error is not None
    assert "Cannot reach LM Studio" in readiness.provider_readiness_error


@pytest.mark.asyncio
async def test_readiness_requires_configured_model_to_be_available(tmp_path: pathlib.Path):
    config = RunConfig.model_validate(_config_dict(tmp_path))

    response = httpx.Response(200, json={"data": [{"id": "other-model"}]})
    with patch("backend.app.config.httpx.AsyncClient.get", return_value=response):
        readiness = await check_readiness(config)

    assert readiness.ok is False
    assert readiness.provider_readiness_reason == "model_unavailable"


@pytest.mark.asyncio
async def test_readiness_reports_missing_ocr_dependency(tmp_path: pathlib.Path):
    config_data = _config_dict(tmp_path)
    config_data["parser"] = {"backend": "pypdfium2", "ocr_enabled": True}
    config = RunConfig.model_validate(config_data)

    response = httpx.Response(200, json={"data": [{"id": "loaded-text-model"}]})
    with patch("backend.app.config.httpx.AsyncClient.get", return_value=response):
        with patch("backend.app.parsing._ocrmypdf_available", return_value=(False, "not installed")):
            readiness = await check_readiness(config)

    assert readiness.ok is False
    assert any("ocrmypdf" in error for error in readiness.errors)


@pytest.mark.asyncio
async def test_readiness_rejects_output_path_that_is_a_file(tmp_path: pathlib.Path):
    config_data = _config_dict(tmp_path)
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("placeholder", encoding="utf-8")
    config_data["output_dir"] = str(output_file)
    config = RunConfig.model_validate(config_data)

    response = httpx.Response(200, json={"data": [{"id": "loaded-text-model"}]})
    with patch("backend.app.config.httpx.AsyncClient.get", return_value=response):
        readiness = await check_readiness(config)

    assert readiness.ok is False
    assert any("output_dir is not a directory" in error for error in readiness.errors)
