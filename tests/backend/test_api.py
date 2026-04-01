"""Tests for FastAPI endpoints."""
from __future__ import annotations

import asyncio
import json
import pathlib

import pytest
import respx
import httpx
from httpx import ASGITransport, AsyncClient

from backend.app.artifacts import (
    get_run_json_path, init_run_bundle, write_json, read_json,
    get_input_summary_path,
)
from backend.app.main import app
from backend.app.schemas import RunStatus

FIXTURE_CONFIG = "config.example.json"


async def get_client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_ok(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestListRuns:
    @pytest.mark.asyncio
    async def test_empty_output_dir(self, tmp_path):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs?output_dir={tmp_path}")
        assert resp.status_code == 200
        assert resp.json() == {"runs": []}

    @pytest.mark.asyncio
    async def test_lists_existing_runs(self, tmp_path):
        for rid in ["run_aaa", "run_bbb"]:
            init_run_bundle(str(tmp_path), rid)
            write_json(get_run_json_path(str(tmp_path), rid), {
                "run_id": rid,
                "status": RunStatus.completed.value,
                "created_at": "2024-01-01T00:00:00+00:00",
            })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs?output_dir={tmp_path}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["runs"]) == 2


class TestGetRun:
    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs/run_missing?output_dir={tmp_path}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_found(self, tmp_path):
        rid = "run_found"
        init_run_bundle(str(tmp_path), rid)
        write_json(get_run_json_path(str(tmp_path), rid), {
            "run_id": rid,
            "status": RunStatus.completed.value,
        })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs/{rid}?output_dir={tmp_path}")
        assert resp.status_code == 200
        assert resp.json()["run_id"] == rid


class TestGetRunConfig:
    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path):
        rid = "run_nocfg"
        init_run_bundle(str(tmp_path), rid)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs/{rid}/config?output_dir={tmp_path}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_found(self, tmp_path):
        from backend.app.artifacts import get_config_snapshot_path
        rid = "run_cfg"
        init_run_bundle(str(tmp_path), rid)
        write_json(get_config_snapshot_path(str(tmp_path), rid), {
            "provider": {"token": "lm_studio"},
        })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs/{rid}/config?output_dir={tmp_path}")
        assert resp.status_code == 200
        assert resp.json()["provider"]["token"] == "lm_studio"


class TestGetRunInputs:
    @pytest.mark.asyncio
    async def test_not_found(self, tmp_path):
        rid = "run_noinput"
        init_run_bundle(str(tmp_path), rid)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs/{rid}/inputs?output_dir={tmp_path}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_found(self, tmp_path):
        rid = "run_inputs"
        init_run_bundle(str(tmp_path), rid)
        write_json(get_input_summary_path(str(tmp_path), rid), {
            "run_id": rid,
            "table_rows": 10,
        })
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/runs/{rid}/inputs?output_dir={tmp_path}")
        assert resp.status_code == 200
        assert resp.json()["table_rows"] == 10


class TestOpenPdfInLocalViewer:
    @pytest.mark.asyncio
    async def test_open_pdf_not_found(self, tmp_path):
        rid = "run_missing_pdf"
        init_run_bundle(str(tmp_path), rid)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/runs/{rid}/assets/pdf/paper-1/open?output_dir={tmp_path}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_open_pdf_uses_os_viewer(self, tmp_path, monkeypatch):
        rid = "run_open_pdf"
        run_dir = init_run_bundle(str(tmp_path), rid)
        pdf_dir = run_dir / "source"
        pdf_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = pdf_dir / "paper-1.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%stub\n")
        parsed_dir = run_dir / "parsed" / "paper-1"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        write_json(parsed_dir / "parsed_document.json", {"source_path": str(pdf_path)})

        opened: list[str] = []

        def fake_open(path: pathlib.Path) -> None:
            opened.append(str(path))

        monkeypatch.setattr("backend.app.main.open_in_local_viewer", fake_open)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/runs/{rid}/assets/pdf/paper-1/open?output_dir={tmp_path}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "opened"
        assert opened == [str(pdf_path)]


class TestCreateRun:
    @pytest.mark.asyncio
    async def test_invalid_config_path(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/runs", json={
                "config_path": "/nonexistent/config.json"
            })
        assert resp.status_code == 400
        assert "not found" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_provider_token_in_config(self, tmp_path, minimal_config_file):
        # Write a config with bad provider
        bad_config = tmp_path / "bad.json"
        bad_config.write_text(json.dumps({
            "table_path": "t.xlsx",
            "pdf_dir": "pdfs/",
            "provider": {"token": "openai"},
        }), encoding="utf-8")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/runs", json={"config_path": str(bad_config)})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    @respx.mock
    async def test_creates_run_and_returns_id(self, tmp_path, minimal_config_file):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/runs", json={"config_path": str(minimal_config_file)})
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert data["run_id"].startswith("run_")
        assert data["status"] == RunStatus.created.value
        # Let background task run
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    @respx.mock
    async def test_picker_overrides_applied(self, tmp_path, minimal_config_file):
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/runs", json={
                "config_path": str(minimal_config_file),
                "pdf_dir": "tests/fixtures/papers",
            })
        assert resp.status_code == 200
        await asyncio.sleep(0.2)
