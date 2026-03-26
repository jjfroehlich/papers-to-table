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
    writer.add_metadata({"/Title": title, "/Author": author, "/CreationDate": f"D:{year}0101000000"})
    with path.open("wb") as handle:
        writer.write(handle)


def test_batch5_summary_and_download_endpoints(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    table.write_text(
        "\n".join(
            [
                "Title,Authors,Publication Year,Material",
                "Alpha Study,Alice Smith,2020,",
            ]
        ),
        encoding="utf-8",
    )
    schema = tmp_path / "schema.csv"
    schema.write_text(
        "\n".join(
            [
                "column_name,description",
                "Material,Primary material extracted from text",
            ]
        ),
        encoding="utf-8",
    )
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_pdf(pdf_dir / "alpha.pdf", "Alpha Study", "Alice Smith", 2020)

    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "paths": {
                    "table_path": str(table),
                    "schema_path": str(schema),
                    "pdf_dir": str(pdf_dir),
                    "output_dir": str(tmp_path / "artifacts"),
                }
            }
        ),
        encoding="utf-8",
    )

    created = client.post("/api/runs", json={"config_path": str(cfg)}).json()
    run = _wait_for_terminal(created["run_id"])
    assert run["status"] in {"completed", "completed_with_warnings"}
    assert run.get("current_stage")

    run_summary = client.get(f"/api/runs/{created['run_id']}/summaries/run")
    reviewer_summary = client.get(f"/api/runs/{created['run_id']}/summaries/reviewer")
    assert run_summary.status_code == 200
    assert reviewer_summary.status_code == 200

    manifest = client.get(f"/api/runs/{created['run_id']}/downloads")
    assert manifest.status_code == 200
    payload = manifest.json()
    assert payload["downloads"]["run_summary"]["ready"] is True
    assert payload["downloads"]["reviewer_summary"]["ready"] is True

    run_summary_file = client.get(f"/api/runs/{created['run_id']}/downloads/run-summary")
    reviewer_summary_file = client.get(f"/api/runs/{created['run_id']}/downloads/reviewer-summary")
    artifacts_zip = client.get(f"/api/runs/{created['run_id']}/downloads/artifacts")
    assert run_summary_file.status_code == 200
    assert reviewer_summary_file.status_code == 200
    assert artifacts_zip.status_code == 200
