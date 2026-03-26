from __future__ import annotations

import json
from pathlib import Path
import time

from fastapi.testclient import TestClient

from app.main import app
from app.services.config_service import classify_cells


client = TestClient(app)


def _write_csv(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _config(tmp_path: Path, table: Path, schema: Path | None, pdf_dir: Path, verify_mode: bool = False) -> Path:
    paths = {
        "table_path": str(table),
        "pdf_dir": str(pdf_dir),
        "output_dir": str(tmp_path / "artifacts"),
    }
    if schema is not None:
        paths["schema_path"] = str(schema)
    cfg = {
        "paths": paths,
        "review": {"verify_mode": verify_mode, "placeholder_values": ["n/a", "na", "-"]},
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    return cfg_path


def _wait_for_terminal(run_id: str) -> dict:
    for _ in range(400):
        res = client.get(f"/api/runs/{run_id}")
        payload = res.json()
        if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("run did not reach terminal state")


def test_run_creation_and_valid_input(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    _write_csv(
        table,
        "Title,Authors,Publication Year,Material\nA,One,2020,n/a\n",
    )
    schema = tmp_path / "schema.csv"
    _write_csv(schema, "column_name,description\nMaterial,Material desc\n")
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    (pdf_dir / "x.pdf").write_bytes(b"%PDF-1.4\n")

    cfg = _config(tmp_path, table, schema, pdf_dir)
    created = client.post("/api/runs", json={"config_path": str(cfg)}).json()
    run = _wait_for_terminal(created["run_id"])
    assert run["status"] in {"completed", "completed_with_warnings"}

    inputs = client.get(f"/api/runs/{created['run_id']}/inputs").json()
    assert inputs["eligible_missing_cells"] == 1




def test_embedded_schema_sheet_used_when_schema_path_missing() -> None:
    cfg = Path('config.example.json')
    created = client.post("/api/runs", json={"config_path": str(cfg)}).json()
    run = _wait_for_terminal(created["run_id"])
    assert run["status"] in {"completed", "completed_with_warnings"}

def test_missing_metadata_rejected(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    _write_csv(table, "Title,Publication Year,Material\nA,2020,x\n")
    schema = tmp_path / "schema.csv"
    _write_csv(schema, "column_name,description\nMaterial,Material desc\n")
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()

    cfg = _config(tmp_path, table, schema, pdf_dir)
    created = client.post("/api/runs", json={"config_path": str(cfg)}).json()
    run = _wait_for_terminal(created["run_id"])
    assert run["status"] == "failed"
    assert "metadata columns" in run["error"]


def test_missing_path_rejected(tmp_path: Path) -> None:
    cfg = _config(tmp_path, tmp_path / "missing.csv", tmp_path / "schema.csv", tmp_path / "pdfs")
    created = client.post("/api/runs", json={"config_path": str(cfg)}).json()
    run = _wait_for_terminal(created["run_id"])
    assert run["status"] == "failed"
    assert "does not exist" in run["error"]


def test_placeholder_and_verify_mode_behavior() -> None:
    import pandas as pd

    df = pd.DataFrame([
        {"Material": "n/a"},
        {"Material": "Copper"},
    ])
    no_verify = classify_cells(df, ["Material"], verify_mode=False, placeholders=["n/a"])
    verify = classify_cells(df, ["Material"], verify_mode=True, placeholders=["n/a"])

    assert no_verify == {"missing": 1, "filled": 0, "skipped": 0}
    assert verify == {"missing": 1, "filled": 1, "skipped": 0}
