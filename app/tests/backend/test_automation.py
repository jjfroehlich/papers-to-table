from __future__ import annotations

import json
import pathlib

import pytest

from backend.app.artifacts import (
    get_config_snapshot_path,
    get_reviewer_summary_path,
    get_run_dir,
    get_run_json_path,
    get_run_summary_path,
    init_run_bundle,
    write_json,
)
from backend.app.automation import AUTOMATION_PAYLOAD_SCHEMA_VERSION, run_start, run_status, run_wait
from backend.app.schemas import RunStatus


@pytest.fixture
def config_path(tmp_path: pathlib.Path) -> str:
    table = tmp_path / "table.xlsx"
    schema = tmp_path / "schema.csv"
    pdf_dir = tmp_path / "pdfs"
    output_dir = tmp_path / "runs"

    table.write_text("stub", encoding="utf-8")
    schema.write_text("column_name,description\nassay,desc\n", encoding="utf-8")
    pdf_dir.mkdir(parents=True)

    config = {
        "table_path": str(table),
        "schema_path": str(schema),
        "pdf_dir": str(pdf_dir),
        "output_dir": str(output_dir),
        "provider": {
            "token": "lm_studio",
            "text_model": {"model_id": "qwen/qwen3-30b-a3b-2507"},
        },
    }
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(config), encoding="utf-8")
    return str(config_file)


def _write_terminal_run(
    *,
    run_id: str,
    output_dir: str,
    status: str,
    mode: str = "normal",
    error_message: str | None = None,
    provider_readiness_reason: str | None = None,
) -> None:
    run_dir = init_run_bundle(output_dir, run_id)
    write_json(
        get_run_json_path(output_dir, run_id),
        {
            "run_id": run_id,
            "status": status,
            "run_mode": mode,
            "prompt_hash": "prompt-hash",
            "prompt_bundle_id": "default",
            "retrieval_mode": "lexical",
            "provider_mode": "live_local",
            "warnings": [],
            "current_stage": None,
            "error_message": error_message,
            "provider_readiness_error": None,
            "provider_readiness_reason": provider_readiness_reason,
        },
    )
    write_json(get_config_snapshot_path(output_dir, run_id), {"provider": {"token": "lm_studio"}})
    write_json(get_run_summary_path(output_dir, run_id), {"run_id": run_id, "status": status})
    write_json(get_reviewer_summary_path(output_dir, run_id), {"run_id": run_id, "pending": 0})

    exports_dir = run_dir / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "workbook_20260406.xlsx").write_bytes(b"xlsx")


def test_run_start_no_wait_returns_machine_readable_startup(config_path: str, monkeypatch):
    monkeypatch.setattr("backend.app.automation.generate_run_id", lambda: "run_auto_start")
    monkeypatch.setattr("backend.app.automation._spawn_detached_worker", lambda **_kwargs: 12345)

    exit_code, payload = run_start(config_path=config_path, wait=False)

    assert exit_code == 0
    assert payload["run_id"] == "run_auto_start"
    assert payload["status"] == RunStatus.created.value
    assert payload["schema_version"] == AUTOMATION_PAYLOAD_SCHEMA_VERSION
    assert payload["is_terminal"] is False
    assert payload["mode"] == "normal"
    assert payload["worker_pid"] == 12345
    assert pathlib.Path(payload["artifacts"]["run_dir"]).name == "run_auto_start"
    assert "config_snapshot_path" in payload["artifacts"]


def test_run_start_wait_success_returns_terminal_output(config_path: str, monkeypatch):
    monkeypatch.setattr("backend.app.automation.generate_run_id", lambda: "run_auto_wait_success")

    async def _fake_run_pipeline(run_id, config, config_path, output_dir, resolved_inputs=None):
        _write_terminal_run(
            run_id=run_id,
            output_dir=output_dir,
            status=RunStatus.completed.value,
            mode="normal",
        )

    monkeypatch.setattr("backend.app.automation.run_pipeline", _fake_run_pipeline)

    exit_code, payload = run_start(config_path=config_path, wait=True)

    assert exit_code == 0
    assert payload["run_id"] == "run_auto_wait_success"
    assert payload["status"] == RunStatus.completed.value
    assert payload["schema_version"] == AUTOMATION_PAYLOAD_SCHEMA_VERSION
    assert payload["is_terminal"] is True
    assert payload["artifacts"]["run_summary_path"] is not None
    assert payload["artifacts"]["reviewer_summary_path"] is not None
    assert payload["artifacts"]["latest_export_path"] is not None


def test_run_start_wait_failure_returns_terminal_failure_info(config_path: str, monkeypatch):
    monkeypatch.setattr("backend.app.automation.generate_run_id", lambda: "run_auto_wait_fail")

    async def _fake_run_pipeline(run_id, config, config_path, output_dir, resolved_inputs=None):
        _write_terminal_run(
            run_id=run_id,
            output_dir=output_dir,
            status=RunStatus.failed.value,
            mode="normal",
            error_message="provider unreachable",
            provider_readiness_reason="provider_unreachable",
        )

    monkeypatch.setattr("backend.app.automation.run_pipeline", _fake_run_pipeline)

    exit_code, payload = run_start(config_path=config_path, wait=True)

    assert exit_code == 2
    assert payload["status"] == RunStatus.failed.value
    assert payload["schema_version"] == AUTOMATION_PAYLOAD_SCHEMA_VERSION
    assert payload["is_terminal"] is True
    assert payload["error_message"] == "provider unreachable"
    assert payload["provider_readiness_reason"] == "provider_unreachable"


def test_run_start_applies_path_override_in_resolved_inputs(config_path: str, tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setattr("backend.app.automation.generate_run_id", lambda: "run_auto_override")

    override_table = tmp_path / "override.xlsx"
    override_table.write_text("override", encoding="utf-8")

    monkeypatch.setattr("backend.app.automation._spawn_detached_worker", lambda **_kwargs: 222)
    exit_code, payload = run_start(
        config_path=config_path,
        table_path=str(override_table),
        wait=False,
    )

    assert exit_code == 0
    assert payload["resolved_inputs"]["table_path"]["source_kind"] == "path_override"
    assert payload["resolved_inputs"]["table_path"]["logical_source"] == str(override_table)
    assert pathlib.Path(payload["resolved_inputs"]["table_path"]["runtime_locator"]).is_absolute()


def test_run_status_reports_not_found(tmp_path: pathlib.Path):
    exit_code, payload = run_status(run_id="missing", output_dir=str(tmp_path / "runs"))

    assert exit_code == 4
    assert payload["status"] == "not_found"
    assert payload["schema_version"] == AUTOMATION_PAYLOAD_SCHEMA_VERSION
    assert payload["is_terminal"] is False


def test_run_status_reports_terminal_state(config_path: str, monkeypatch):
    monkeypatch.setattr("backend.app.automation.generate_run_id", lambda: "run_auto_status")

    async def _fake_run_pipeline(run_id, config, config_path, output_dir, resolved_inputs=None):
        _write_terminal_run(
            run_id=run_id,
            output_dir=output_dir,
            status=RunStatus.completed_with_warnings.value,
            mode="verify",
        )

    monkeypatch.setattr("backend.app.automation.run_pipeline", _fake_run_pipeline)

    exit_code, payload = run_start(config_path=config_path, wait=True)
    assert exit_code == 0

    status_exit, status_payload = run_status(run_id="run_auto_status", output_dir=payload["output_dir"])
    assert status_exit == 0
    assert status_payload["status"] == RunStatus.completed_with_warnings.value
    assert status_payload["schema_version"] == AUTOMATION_PAYLOAD_SCHEMA_VERSION
    assert status_payload["is_terminal"] is True
    assert status_payload["mode"] == "verify"


def test_run_wait_by_run_id_returns_terminal_payload(monkeypatch, tmp_path: pathlib.Path):
    output_dir = str(tmp_path / "runs")

    async def _fake_wait_for_terminal_status(*, run_id, output_dir, poll_interval, timeout_seconds):
        return {
            "run_id": run_id,
            "status": RunStatus.completed.value,
            "run_mode": "normal",
            "warnings": [],
            "current_stage": None,
            "error_message": None,
            "provider_readiness_error": None,
            "provider_readiness_reason": None,
        }

    monkeypatch.setattr("backend.app.automation._wait_for_terminal_status", _fake_wait_for_terminal_status)
    monkeypatch.setattr(
        "backend.app.automation.run_status",
        lambda *, run_id, output_dir: (
            0,
            {
                "schema_version": AUTOMATION_PAYLOAD_SCHEMA_VERSION,
                "run_id": run_id,
                "status": RunStatus.completed.value,
                "is_terminal": True,
                "mode": "normal",
                "output_dir": output_dir,
                "artifacts": {},
                "timestamp": "2026-04-06T00:00:00+00:00",
            },
        ),
    )

    exit_code, payload = run_wait(run_id="run_wait_123", output_dir=output_dir)

    assert exit_code == 0
    assert payload["schema_version"] == AUTOMATION_PAYLOAD_SCHEMA_VERSION
    assert payload["run_id"] == "run_wait_123"
    assert payload["status"] == RunStatus.completed.value
    assert payload["is_terminal"] is True
