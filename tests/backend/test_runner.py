"""Tests for the staged asyncio runner."""
from __future__ import annotations

import asyncio
import pathlib
from datetime import datetime, timezone

import pytest
import respx
import httpx

from backend.app.artifacts import (
    get_config_snapshot_path,
    get_input_summary_path,
    get_run_json_path,
    get_reviewer_summary_path,
    get_run_summary_path,
    init_run_bundle,
    read_json,
    write_json,
)
from backend.app.config import RunConfig
from backend.app.runner import get_initial_run_data, run_pipeline
from backend.app.schemas import RunStatus

FIXTURE_TABLE = "tests/fixtures/tables/literature_fixture.xlsx"
FIXTURE_SCHEMA = "tests/fixtures/tables/literature_fixture_schema.csv"
FIXTURE_PDF_DIR = "tests/fixtures/papers"


def make_config(tmp_path: pathlib.Path, **kwargs) -> RunConfig:
    data = {
        "table_path": FIXTURE_TABLE,
        "schema_path": FIXTURE_SCHEMA,
        "pdf_dir": FIXTURE_PDF_DIR,
        "output_dir": str(tmp_path / "runs"),
        "verify_mode": False,
        "provider": {
            "token": "lm_studio",
            "base_url": "http://localhost:1234",
        },
        **kwargs,
    }
    return RunConfig.model_validate(data)


class TestGetInitialRunData:
    def test_has_required_fields(self, tmp_path):
        config = make_config(tmp_path)
        data = get_initial_run_data("run_test_123", config, "config.json")
        assert data["run_id"] == "run_test_123"
        assert data["status"] == RunStatus.created.value
        assert data["config_path"] == "config.json"
        assert data["verify_mode"] is False
        assert data["provider_token"] == "lm_studio"

    def test_timestamps(self, tmp_path):
        config = make_config(tmp_path)
        data = get_initial_run_data("run_test_123", config, None)
        assert data["started_at"] is None
        assert data["completed_at"] is None
        assert data["created_at"] is not None


class TestRunPipeline:
    @pytest.mark.asyncio
    @respx.mock
    async def test_completes_with_valid_inputs(self, tmp_path):
        """Happy-path: pipeline completes when LM Studio is reachable."""
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_test_happy"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["status"] in (
            RunStatus.completed.value,
            RunStatus.completed_with_warnings.value,
        )
        assert run_data["completed_at"] is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_writes_config_snapshot(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_snap"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        snap_path = get_config_snapshot_path(output_dir, run_id)
        assert snap_path.exists()
        snap = read_json(snap_path)
        assert snap["provider"]["token"] == "lm_studio"

    @pytest.mark.asyncio
    @respx.mock
    async def test_writes_input_summary(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_inputs"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        input_path = get_input_summary_path(output_dir, run_id)
        assert input_path.exists()
        summary = read_json(input_path)
        assert summary["table_rows"] is not None
        assert summary["table_rows"] > 0
        assert summary["pdf_count"] is not None

    @pytest.mark.asyncio
    @respx.mock
    async def test_fails_with_unreachable_provider(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            side_effect=httpx.ConnectError("refused")
        )
        config = make_config(tmp_path)
        run_id = "run_fail"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["status"] == RunStatus.failed.value
        assert run_data["error_message"] is not None

    @pytest.mark.asyncio
    async def test_input_summary_written_before_readiness_check(self, tmp_path):
        """Input summary should exist even when readiness fails."""
        config = make_config(tmp_path, pdf_dir="/nonexistent/dir")
        run_id = "run_early_summary"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["status"] == RunStatus.failed.value

        # Input summary should still exist
        input_path = get_input_summary_path(output_dir, run_id)
        assert input_path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_records_total_rows_and_eligible_cells(self, tmp_path):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        config = make_config(tmp_path)
        run_id = "run_counts"
        output_dir = str(tmp_path / "runs")
        (tmp_path / "runs").mkdir(exist_ok=True)

        await run_pipeline(run_id, config, "config.json", output_dir)

        run_data = read_json(get_run_json_path(output_dir, run_id))
        assert run_data["total_rows"] > 0
        assert run_data["eligible_cells"] >= 0
