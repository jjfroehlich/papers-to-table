"""Tests for Phase A backend foundation (Batch 1)."""
from __future__ import annotations

import json
import pathlib

import pytest

from backend.app.artifacts import (
    append_jsonl,
    get_run_json_path,
    init_run_bundle,
    list_run_ids,
    lookup_by_id,
    read_json,
    read_jsonl,
    write_json,
)
from backend.app.config import RunConfig, apply_overrides, load_config
from backend.app.ids import (
    generate_cell_id,
    generate_pdf_id,
    generate_row_id,
    generate_run_id,
)
from backend.app.ingest import (
    classify_cell_eligibility,
    get_eligible_cells,
    is_trivial_placeholder,
    load_schema,
    load_table,
    validate_metadata_columns,
    validate_schema_columns,
)
from backend.app.lifecycle import LifecycleError, apply_transition, validate_transition
from backend.app.schemas import RunStatus

FIXTURE_TABLE = "tests/fixtures/tables/literature_fixture.xlsx"
FIXTURE_SCHEMA = "tests/fixtures/tables/literature_fixture_schema.csv"
FIXTURE_PDF_DIR = "tests/fixtures/papers"
FIXTURE_CONFIG = "config.example.json"


# ---------------------------------------------------------------------------
# IDs
# ---------------------------------------------------------------------------


def test_generate_run_id_format():
    rid = generate_run_id()
    assert rid.startswith("run_")
    parts = rid.split("_")
    assert len(parts) == 4  # run, date, time, suffix


def test_generate_cell_id_deterministic():
    a = generate_cell_id("row_abc", "Journal")
    b = generate_cell_id("row_abc", "Journal")
    assert a == b
    assert a.startswith("cell_")


def test_generate_cell_id_different_columns():
    a = generate_cell_id("row_abc", "Journal")
    b = generate_cell_id("row_abc", "Impact Factor")
    assert a != b


def test_generate_row_id_deterministic():
    a = generate_row_id(0, "Some Title")
    b = generate_row_id(0, "Some Title")
    assert a == b
    assert a.startswith("row_")


def test_generate_pdf_id_stable():
    a = generate_pdf_id("paper_1.pdf")
    b = generate_pdf_id("paper_1.pdf")
    assert a == b
    assert a.startswith("pdf_")


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_write_read_json(tmp_path):
    p = tmp_path / "test.json"
    data = {"key": "value", "num": 42}
    write_json(p, data)
    result = read_json(p)
    assert result == data


def test_write_json_atomic_creates_parent(tmp_path):
    p = tmp_path / "subdir" / "nested.json"
    write_json(p, {"x": 1})
    assert p.exists()


def test_append_and_read_jsonl(tmp_path):
    p = tmp_path / "records.jsonl"
    append_jsonl(p, {"id": "a", "val": 1})
    append_jsonl(p, {"id": "b", "val": 2})
    records = read_jsonl(p)
    assert len(records) == 2
    assert records[0]["id"] == "a"
    assert records[1]["id"] == "b"


def test_lookup_by_id(tmp_path):
    p = tmp_path / "records.jsonl"
    append_jsonl(p, {"proposal_id": "p1", "value": "foo"})
    append_jsonl(p, {"proposal_id": "p2", "value": "bar"})
    result = lookup_by_id(p, "proposal_id", "p2")
    assert result is not None
    assert result["value"] == "bar"
    assert lookup_by_id(p, "proposal_id", "missing") is None


def test_init_run_bundle(tmp_path):
    run_dir = init_run_bundle(str(tmp_path), "run_test_123")
    assert run_dir.exists()
    for sub in ["inputs", "proposals", "evidence", "review", "summaries", "logs"]:
        assert (run_dir / sub).exists()


def test_list_run_ids(tmp_path):
    for rid in ["run_aaa", "run_bbb"]:
        init_run_bundle(str(tmp_path), rid)
        write_json(get_run_json_path(str(tmp_path), rid), {"run_id": rid})
    ids = list_run_ids(str(tmp_path))
    assert set(ids) == {"run_aaa", "run_bbb"}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_load_config_example():
    config = load_config(FIXTURE_CONFIG)
    assert config.provider.token == "lm_studio"
    assert config.table_path == str(pathlib.Path("tests/fixtures/tables/literature_fixture.xlsx").resolve())


def test_invalid_provider_token():
    with pytest.raises(ValueError, match="Unknown provider token"):
        RunConfig.model_validate(
            {
                "table_path": "t.xlsx",
                "pdf_dir": "pdfs/",
                "provider": {"token": "openai"},
            }
        )


def test_apply_overrides():
    config = load_config(FIXTURE_CONFIG)
    overridden = apply_overrides(config, {"table_path": "other.xlsx"})
    assert overridden.table_path == "other.xlsx"
    assert overridden.pdf_dir == config.pdf_dir  # unchanged


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------


def test_load_table_xlsx():
    df = load_table(FIXTURE_TABLE)
    assert "Title" in df.columns
    assert "Authors" in df.columns
    assert "Publication Year" in df.columns
    assert len(df) > 0


def test_load_table_csv():
    df = load_table("tests/fixtures/tables/literature_fixture_table.csv")
    assert "Title" in df.columns
    assert len(df) > 0


def test_load_schema_csv():
    schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
    assert len(schema) > 0
    assert all("column_name" in s for s in schema)
    assert all("description" in s for s in schema)


def test_validate_metadata_columns_ok():
    df = load_table(FIXTURE_TABLE)
    errors = validate_metadata_columns(df)
    assert errors == []


def test_validate_schema_columns_ok():
    schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
    errors = validate_schema_columns(schema)
    assert errors == []


def test_classify_cell_eligibility_empty():
    assert classify_cell_eligibility("") == "eligible"
    assert classify_cell_eligibility("  ") == "eligible"


def test_classify_cell_eligibility_placeholder():
    for val in ["n/a", "N/A", "TBD", "-", "unknown"]:
        assert classify_cell_eligibility(val) == "placeholder"


def test_classify_cell_eligibility_filled():
    assert classify_cell_eligibility("Some value") == "already_filled"


def test_classify_cell_eligibility_verify_mode():
    assert classify_cell_eligibility("Some value", verify_mode=True) == "eligible"


def test_get_eligible_cells_returns_list():
    df = load_table(FIXTURE_TABLE)
    schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
    cells = get_eligible_cells(df, schema, verify_mode=False)
    assert isinstance(cells, list)
    for cell in cells:
        assert "row_id" in cell
        assert "column_name" in cell
        assert "eligibility" in cell


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def test_valid_transition_created_to_validating():
    validate_transition(RunStatus.created, RunStatus.validating)


def test_invalid_transition_created_to_running():
    with pytest.raises(LifecycleError):
        validate_transition(RunStatus.created, RunStatus.running)


def test_apply_transition_sets_started_at():
    run_data = {
        "status": RunStatus.created.value,
        "started_at": None,
        "completed_at": None,
    }
    updated = apply_transition(run_data, RunStatus.validating)
    assert updated["status"] == RunStatus.validating.value
    assert updated["started_at"] is not None


def test_apply_transition_sets_completed_at():
    run_data = {
        "status": RunStatus.running.value,
        "started_at": "2024-01-01T00:00:00+00:00",
        "completed_at": None,
    }
    updated = apply_transition(run_data, RunStatus.completed)
    assert updated["completed_at"] is not None


def test_terminal_states_cannot_transition():
    for terminal in [RunStatus.completed, RunStatus.failed, RunStatus.interrupted]:
        run_data = {"status": terminal.value}
        with pytest.raises(LifecycleError):
            apply_transition(run_data, RunStatus.running)


# ---------------------------------------------------------------------------
# FastAPI endpoints (basic smoke tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint():
    from httpx import ASGITransport, AsyncClient

    from backend.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_runs_empty(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from backend.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/runs?output_dir={tmp_path}")
    assert resp.status_code == 200
    assert resp.json() == {"runs": []}


@pytest.mark.asyncio
async def test_get_run_not_found(tmp_path):
    from httpx import ASGITransport, AsyncClient

    from backend.app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/runs/run_missing?output_dir={tmp_path}")
    assert resp.status_code == 404
