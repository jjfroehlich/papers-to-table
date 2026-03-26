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


def test_batch3_retrieval_profiles_and_proposals(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    table.write_text(
        "\n".join(
            [
                "Title,Authors,Publication Year,Material,Figure Metric",
                "Alpha Study,Alice Smith,2020,,existing",
                "Beta Study,Bob Ray,2021,,",
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
                "Figure Metric,Value typically read from a figure chart",
            ]
        ),
        encoding="utf-8",
    )
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    _make_pdf(pdf_dir / "alpha.pdf", "Alpha Study", "Alice Smith", 2020)
    _make_pdf(pdf_dir / "unmatched.pdf", "Completely Different", "Nobody", 2012)

    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "paths": {
                    "table_path": str(table),
                    "schema_path": str(schema),
                    "pdf_dir": str(pdf_dir),
                    "output_dir": str(tmp_path / "artifacts"),
                },
                "review": {"verify_mode": True, "placeholder_values": ["n/a", "na", "-"]},
            }
        ),
        encoding="utf-8",
    )

    created = client.post("/api/runs", json={"config_path": str(cfg)}).json()
    run = _wait_for_terminal(created["run_id"])
    assert run["status"] == "completed"

    run_dir = Path(run["artifact_dir"])

    profiles = json.loads((run_dir / "style_profiles" / "profiles.json").read_text(encoding="utf-8"))
    assert profiles["profiles"]["Material"]["semantic_examples_included"] is False

    retrieval_diag = json.loads((run_dir / "retrieval" / "diagnostics.json").read_text(encoding="utf-8"))
    assert retrieval_diag["top_k"] == 6
    assert retrieval_diag["reranker_enabled"] is False
    assert retrieval_diag["query_expansion_enabled"] is False

    proposals = [json.loads(line) for line in (run_dir / "proposals" / "proposals.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert proposals, "expected proposals to be generated"
    assert any(p["proposal_state"] == "blocked" for p in proposals)
    assert any(p["column_name"] == "Figure Metric" and p["support_label"] == "figure_based_evidence" for p in proposals)

    evidence = [json.loads(line) for line in (run_dir / "evidence" / "evidence.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert evidence, "expected evidence records"

    diagnostics = json.loads((run_dir / "proposals" / "diagnostics.json").read_text(encoding="utf-8"))
    assert diagnostics["provider_probe"]["structured_output"] is True
