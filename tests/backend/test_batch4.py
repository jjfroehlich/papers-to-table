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


def test_batch4_review_api_decisions_and_summaries(tmp_path: Path) -> None:
    table = tmp_path / "table.csv"
    table.write_text(
        "\n".join(
            [
                "Title,Authors,Publication Year,Material,Figure Metric",
                "Alpha Study,Alice Smith,2020,,",
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
    _make_pdf(pdf_dir / "unmatched.pdf", "Different Study", "Unknown", 2014)

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
    assert run["status"] in {"completed", "completed_with_warnings"}

    proposal_list = client.get(f"/api/runs/{created['run_id']}/proposals").json()
    assert proposal_list["counters"]["total"] > 0
    assert "completed_with_warnings" in proposal_list["run_warning_categories"]

    weak_only = client.get(f"/api/runs/{created['run_id']}/proposals", params={"evidence_status": "weak"}).json()
    assert weak_only["items"]

    undecided = [item for item in proposal_list["items"] if item["review_decision"] == "undecided"]
    assert undecided
    chosen = undecided[0]

    detail = client.get(f"/api/runs/{created['run_id']}/proposals/{chosen['proposal_id']}").json()
    assert detail["proposal"]["proposal_id"] == chosen["proposal_id"]
    assert "warning_status_flags" in detail

    decision = client.post(
        f"/api/runs/{created['run_id']}/review/decisions",
        json={
            "proposal_id": chosen["proposal_id"],
            "decision": "accept_edited",
            "edited_value": "Edited by reviewer",
            "reviewer_note": "Looks good after normalization",
        },
    ).json()
    assert decision["decision"] == "accept_edited"

    visible_filtered = client.get(
        f"/api/runs/{created['run_id']}/proposals",
        params={"column_name": chosen["column_name"], "review_decision": "undecided"},
    ).json()
    bulk = client.post(
        f"/api/runs/{created['run_id']}/review/decisions/bulk-accept-visible",
        json={"column_name": chosen["column_name"], "review_decision": "undecided"},
    ).json()
    assert bulk["updated"] == visible_filtered["counters"]["undecided_visible"]

    run_dir = Path(run["artifact_dir"])
    history_rows = [
        json.loads(line)
        for line in (run_dir / "review" / "decision_history.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert history_rows

    summary = json.loads((run_dir / "summaries" / "run_summary.json").read_text(encoding="utf-8"))
    reviewer = json.loads((run_dir / "summaries" / "reviewer_summary.json").read_text(encoding="utf-8"))
    assert summary["matched_pdfs"] >= 1
    assert summary["ambiguous_pdfs"] >= 0
    assert reviewer["accepted_with_edit"] >= 1

    export_candidates = json.loads((run_dir / "exports" / "export_candidates.json").read_text(encoding="utf-8"))
    assert export_candidates["candidate_proposal_ids"]

    first_pdf = proposal_list["items"][0]["pdf_id"]
    page_res = client.get(f"/api/runs/{created['run_id']}/review/assets/page/{first_pdf}/1")
    assert page_res.status_code == 200

    parsed_docs = [
        json.loads(line)
        for line in (run_dir / "parsed" / "documents.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matched_doc = next(item for item in parsed_docs if item["pdf_id"] == first_pdf)
    pdf_res = client.get(f"/api/runs/{created['run_id']}/review/assets/pdf/{first_pdf}")
    assert pdf_res.status_code == 200
    assert matched_doc["source_pdf_path"].endswith(".pdf")

    # recomputation must remain derivable from artifacts
    recompute = client.get(f"/api/runs/{created['run_id']}/proposals").json()
    assert recompute["counters"]["reviewed"] >= 1
