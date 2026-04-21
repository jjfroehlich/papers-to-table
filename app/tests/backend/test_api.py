"""Tests for FastAPI endpoints."""
from __future__ import annotations

import asyncio
import json
import pathlib
import shutil

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

        monkeypatch.setattr("backend.app.api.routers.assets.open_in_local_viewer", fake_open)

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

    @pytest.mark.asyncio
    @respx.mock
    async def test_preflight_reports_scope_and_readiness(self, minimal_config_file, monkeypatch):
        monkeypatch.setattr("backend.app.parsing.check_parser_readiness", lambda *_args: [])
        monkeypatch.setattr("backend.app.parsing.check_ocr_readiness", lambda *_args: [])
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "qwen/qwen3-30b-a3b-2507"}]})
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/runs/preflight", json={"config_path": str(minimal_config_file)})

        assert resp.status_code == 200
        payload = resp.json()
        assert "ok" in payload["readiness"]
        assert "errors" in payload["readiness"]
        assert "table_rows" in payload["scope"]
        assert "pdf_count" in payload["scope"]
        assert payload["provider"]["token"] == "lm_studio"

    @pytest.mark.asyncio
    async def test_stage_single_input_file_materializes_handle(self, tmp_path):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/staged-inputs",
                data={"kind": "table_path", "output_dir": str(tmp_path)},
                files={"files": ("table.csv", b"Title\nPaper A\n", "text/csv")},
            )

        assert resp.status_code == 200
        payload = resp.json()
        assert payload["kind"] == "table_path"
        assert payload["handle"].startswith("staged_table_path_")
        assert pathlib.Path(payload["runtime_locator"]).exists()

    @pytest.mark.asyncio
    async def test_stage_pdf_dir_materializes_backend_readable_directory(self, tmp_path):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/staged-inputs",
                data={"kind": "pdf_dir", "output_dir": str(tmp_path)},
                files=[
                    ("files", ("a.pdf", b"%PDF-1.4\n%a\n", "application/pdf")),
                    ("files", ("b.pdf", b"%PDF-1.4\n%b\n", "application/pdf")),
                ],
            )

        assert resp.status_code == 200
        payload = resp.json()
        runtime_locator = pathlib.Path(payload["runtime_locator"])
        assert runtime_locator.is_dir()
        assert (runtime_locator / "a.pdf").exists()
        assert (runtime_locator / "b.pdf").exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_create_run_uses_staged_handles_and_reports_resolved_context(self, tmp_path):
        table_fixture = pathlib.Path("tests/fixtures/tables/literature_fixture.xlsx").resolve()
        schema_fixture = pathlib.Path("tests/fixtures/tables/literature_fixture_schema.csv").resolve()
        pdf_fixture = pathlib.Path("tests/fixtures/papers/paper_1.pdf").resolve()

        config_path = tmp_path / "staged-config.json"
        output_dir = tmp_path / "runs"
        config_path.write_text(
            json.dumps(
                {
                    "table_path": "./missing-table.xlsx",
                    "schema_path": "./missing-schema.csv",
                    "pdf_dir": "./missing-pdfs",
                    "output_dir": str(output_dir),
                    "provider": {
                        "token": "lm_studio",
                        "base_url": "http://localhost:1234",
                        "text_model": {"model_id": "qwen/qwen3-30b-a3b-2507"},
                    },
                }
            ),
            encoding="utf-8",
        )

        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(
                200,
                json={"data": [{"id": "qwen/qwen3-30b-a3b-2507"}]},
            )
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            table_stage = await client.post(
                "/api/staged-inputs",
                data={"kind": "table_path", "output_dir": str(output_dir)},
                files={
                    "files": (
                        table_fixture.name,
                        table_fixture.read_bytes(),
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                },
            )
            schema_stage = await client.post(
                "/api/staged-inputs",
                data={"kind": "schema_path", "output_dir": str(output_dir)},
                files={"files": (schema_fixture.name, schema_fixture.read_bytes(), "text/csv")},
            )
            pdf_stage = await client.post(
                "/api/staged-inputs",
                data={"kind": "pdf_dir", "output_dir": str(output_dir)},
                files={"files": (pdf_fixture.name, pdf_fixture.read_bytes(), "application/pdf")},
            )

            assert table_stage.status_code == 200
            assert schema_stage.status_code == 200
            assert pdf_stage.status_code == 200

            resp = await client.post(
                "/api/runs",
                json={
                    "config_path": str(config_path),
                    "table_staged_handle": table_stage.json()["handle"],
                    "schema_staged_handle": schema_stage.json()["handle"],
                    "pdf_dir_staged_handle": pdf_stage.json()["handle"],
                },
            )

        assert resp.status_code == 200
        payload = resp.json()
        run_id = payload["run_id"]
        assert payload["resolved_inputs"]["table_path"]["source_kind"] == "staged_handle"
        assert payload["resolved_inputs"]["schema_path"]["source_kind"] == "staged_handle"
        assert payload["resolved_inputs"]["pdf_dir"]["source_kind"] == "staged_handle"

        await asyncio.sleep(0.2)
        run_json = read_json(get_run_json_path(str(output_dir), run_id))
        input_summary = read_json(get_input_summary_path(str(output_dir), run_id))

        assert run_json["resolved_inputs"]["table_path"]["source_kind"] == "staged_handle"
        assert run_json["resolved_inputs"]["schema_path"]["source_kind"] == "staged_handle"
        assert run_json["resolved_inputs"]["pdf_dir"]["source_kind"] == "staged_handle"
        assert input_summary["resolved_inputs"]["table_path"]["source_kind"] == "staged_handle"
        assert pathlib.Path(run_json["table_path"]).exists()
        assert pathlib.Path(run_json["schema_path"]).exists()
        assert pathlib.Path(run_json["pdf_dir"]).is_dir()

        staged_root = output_dir / ".staged_inputs"
        if staged_root.exists():
            shutil.rmtree(staged_root, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_relative_config_paths_report_resolved_runtime_paths_on_failure(self, tmp_path):
        config_dir = tmp_path / "configs"
        config_dir.mkdir()
        table_path = tmp_path / "table.xlsx"
        schema_path = tmp_path / "schema.csv"
        table_path.write_text("Title\nPaper A\n", encoding="utf-8")
        schema_path.write_text("column_name,description\nOutcome,Outcome description\n", encoding="utf-8")

        config_path = config_dir / "config.json"
        config_path.write_text(json.dumps({
            "table_path": "../table.xlsx",
            "schema_path": "../schema.csv",
            "pdf_dir": "../missing-pdfs",
            "output_dir": "../runs",
            "provider": {
                "token": "lm_studio",
                "text_model": {"model_id": "qwen/qwen3-30b-a3b-2507"},
            },
        }), encoding="utf-8")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/runs", json={"config_path": str(config_path)})
            assert resp.status_code == 200
            run_id = resp.json()["run_id"]

        run_json_path = get_run_json_path(str(tmp_path / "runs"), run_id)
        for _ in range(20):
            if run_json_path.exists():
                break
            await asyncio.sleep(0.05)

        run_json = read_json(run_json_path)
        for _ in range(80):
            if run_json.get("status") not in {RunStatus.created.value, RunStatus.validating.value, RunStatus.running.value}:
                break
            await asyncio.sleep(0.1)
            run_json = read_json(run_json_path)

        assert run_json["status"] == RunStatus.failed.value
        assert run_json["table_path"] == str(table_path.resolve())
        assert run_json["schema_path"] == str(schema_path.resolve())
        assert run_json["pdf_dir"] == str((tmp_path / "missing-pdfs").resolve())
