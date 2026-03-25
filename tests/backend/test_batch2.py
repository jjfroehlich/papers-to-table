from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfWriter

from app.main import app


client = TestClient(app)


def _wait_for_terminal(run_id: str) -> dict:
    for _ in range(400):
        payload = client.get(f"/api/runs/{run_id}").json()
        if payload["status"] in {"completed", "completed_with_warnings", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("run did not reach terminal state")


def _make_pdf(path: Path, title: str, author: str, year: int) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_metadata(
        {
            "/Title": title,
            "/Author": author,
            "/CreationDate": f"D:{year}0101000000",
        }
    )
    with path.open("wb") as handle:
        writer.write(handle)


def _config(tmp_path: Path, table: Path, schema: Path, pdf_dir: Path) -> Path:
    cfg_path = tmp_path / "config.json"
    cfg = {
        "paths": {
            "table_path": str(table),
            "schema_path": str(schema),
            "pdf_dir": str(pdf_dir),
            "output_dir": str(tmp_path / "out"),
        }
    }
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    return cfg_path


def test_batch2_parsing_and_matching_artifacts(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    table.write_text(
        "\n".join(
            [
                "Title,Authors,Publication Year,Material",
                "Alpha Study,Alice Smith,2020,",
                "Beta Study,Bob Ray,2021,",
                "Gamma Study,Carol Doe,2022,",
                "Twin Study,Dana Lee,2024,",
                "Twin Study,Dana Lee,2024,",
                "Delta Study,Evan Poe,2023,",
            ]
        ),
        encoding="utf-8",
    )
    schema = tmp_path / "schema.csv"
    schema.write_text("column_name,description\nMaterial,Material desc\n", encoding="utf-8")
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_pdf(pdf_dir / "alpha.pdf", "Alpha Study", "Alice Smith", 2020)
    _make_pdf(pdf_dir / "no_match.pdf", "Unrelated Work", "No One", 2017)
    _make_pdf(pdf_dir / "twin_a.pdf", "Twin Study", "Dana Lee", 2024)
    _make_pdf(pdf_dir / "beta_like.pdf", "Beta", "Bob Ray", 2021)
    _make_pdf(pdf_dir / "delta_a.pdf", "Delta Study", "Evan Poe", 2023)
    _make_pdf(pdf_dir / "delta_b.pdf", "Delta Study", "Evan Poe", 2023)

    cfg = _config(tmp_path, table, schema, pdf_dir)
    created = client.post("/api/runs", json={"config_path": str(cfg)}).json()
    run = _wait_for_terminal(created["run_id"])
    assert run["status"] == "completed"

    run_dir = Path(run["artifact_dir"])
    parsed = json.loads((run_dir / "parsed" / "documents.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert parsed["parser_name"] == "docling"
    diag = json.loads((run_dir / "parsed" / "diagnostics.json").read_text(encoding="utf-8"))
    assert len(diag["documents"]) == 6
    assert all("ocr_reason" in item for item in diag["documents"])

    issues = client.get(f"/api/runs/{created['run_id']}/matching/issues").json()
    assert len(issues["unmatched"]) >= 1
    assert len(issues["duplicate_row_conflicts"]) == 2
    assert len(issues["ambiguous"]) >= 1
