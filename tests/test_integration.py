import json
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
pd = pytest.importorskip("pandas")

from paper_table_agent.config import RunConfig, create_run_paths
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.runner import run_pipeline
from paper_table_agent.store.db import Store
from paper_table_agent.ui.registry import discover_runs


def _write_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(path)


def test_end_to_end_with_mock_llm(tmp_path: Path):
    table_path = tmp_path / "table.xlsx"
    df = pd.DataFrame({"Title": ["Test Paper"], "Authors": ["Ada"], "Year": ["2024"], "Method": [""]})
    schema = pd.DataFrame({"column_name": ["Method"], "description": ["Method used"], "group": ["methods"]})
    with pd.ExcelWriter(table_path) as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
        schema.to_excel(writer, sheet_name="schema", index=False)

    pdf_folder = tmp_path / "pdfs"
    pdf_folder.mkdir()
    pdf_path = pdf_folder / "paper.pdf"
    _write_pdf(pdf_path, "Test Paper\nAda\n2024\nWe used method X.")

    mock_payloads = {
        "extracting paper metadata": {
            "title": "Test Paper",
            "authors": ["Ada"],
            "year": "2024",
            "evidence": [{"quote": "Test Paper", "page": 1, "chunk_id": "page-1", "locator_hint": "Test Paper"}],
            "confidence": 0.9,
        },
        "matching a PDF": {
            "row_id": "0",
            "status": "matched",
            "top_candidates": [],
            "confidence": 0.9,
            "evidence": [{"quote": "Test Paper", "page": 1, "chunk_id": "page-1", "locator_hint": "Test Paper"}],
            "rationale": "Exact match",
        },
        "extracting values for a group": {
            "proposals": [
                {
                    "column": "Method",
                    "proposed_value": "method X",
                    "status": "found",
                    "confidence": 0.8,
                    "evidence": [{"quote": "method X", "page": 1, "chunk_id": "page-1", "locator_hint": "method X"}],
                    "needs_more_evidence": False,
                    "rationale": "Quoted",
                }
            ]
        },
    }
    mock_path = tmp_path / "mock_payloads.json"
    mock_path.write_text(json.dumps(mock_payloads), encoding="utf-8")

    config = RunConfig(
        table_path=table_path,
        pdf_folder=pdf_folder,
        schema_sheet_name="schema",
        title_col="Title",
        authors_col="Authors",
        year_col="Year",
    )
    config.provider.mode = "mock"
    config.provider.mock_payloads_path = mock_path

    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    run_pipeline(config, run_paths, store)

    proposals = store.conn.execute("SELECT * FROM proposals").fetchall()
    assert proposals


def test_registry_lists_runs(tmp_path: Path):
    run_dir = tmp_path / "runs" / "20250101_000000__demo"
    run_dir.mkdir(parents=True)
    (run_dir / "run_config.json").write_text(
        json.dumps({"table_path": "table.xlsx", "pdf_folder": "pdfs"}),
        encoding="utf-8",
    )
    (run_dir / "proposals.sqlite").write_text("stub", encoding="utf-8")
    runs = discover_runs(tmp_path / "runs")
    assert runs


def test_integration_run_report_and_validation(tmp_path: Path):
    table_path = tmp_path / "table.xlsx"
    df = pd.DataFrame(
        {
            "Title": ["Test Paper"],
            "Authors": ["Ada"],
            "Year": ["2024"],
            "Method": [""],
            "Outcome": [""],
        }
    )
    schema = pd.DataFrame(
        {
            "column_name": ["Method", "Outcome"],
            "description": ["Method used", "Observed outcome"],
            "group": ["methods", "methods"],
        }
    )
    with pd.ExcelWriter(table_path) as writer:
        df.to_excel(writer, sheet_name="Sheet1", index=False)
        schema.to_excel(writer, sheet_name="schema", index=False)

    pdf_folder = tmp_path / "pdfs"
    pdf_folder.mkdir()
    pdf_path = pdf_folder / "paper.pdf"
    _write_pdf(pdf_path, "Test Paper\nAda\n2024\nMethod: method X\nOutcome: success")

    mock_payloads = {
        "extracting paper metadata": {
            "title": "Test Paper",
            "authors": ["Ada"],
            "year": "2024",
            "evidence": [{"quote": "Test Paper", "page": 1, "chunk_id": "page-1", "locator_hint": "Test Paper"}],
            "confidence": 0.9,
        },
        "matching a PDF": {
            "row_id": "0",
            "status": "matched",
            "top_candidates": [],
            "confidence": 0.9,
            "evidence": [{"quote": "Test Paper", "page": 1, "chunk_id": "page-1", "locator_hint": "Test Paper"}],
            "rationale": "Exact match",
        },
        "extracting values for a group": {
            "proposals": [
                {
                    "column": "Method",
                    "proposed_value": "method X",
                    "status": "found",
                    "confidence": 0.8,
                    "evidence": [{"quote": "method X", "page": 1, "chunk_id": "page-1", "locator_hint": "method X"}],
                    "needs_more_evidence": False,
                    "rationale": "Quoted",
                },
                {
                    "column": "Outcome",
                    "proposed_value": "success",
                    "status": "found",
                    "confidence": 0.8,
                    "evidence": [{"quote": "success", "page": 1, "chunk_id": "page-1", "locator_hint": "success"}],
                    "needs_more_evidence": False,
                    "rationale": "Quoted",
                },
            ]
        },
    }
    mock_path = tmp_path / "mock_payloads.json"
    mock_path.write_text(json.dumps(mock_payloads), encoding="utf-8")

    config = RunConfig(
        table_path=table_path,
        pdf_folder=pdf_folder,
        schema_sheet_name="schema",
        title_col="Title",
        authors_col="Authors",
        year_col="Year",
    )
    config.provider.mode = "mock"
    config.provider.mock_payloads_path = mock_path

    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    run_pipeline(config, run_paths, store)

    proposals = store.conn.execute("SELECT column, flags_json, proposal_id FROM proposals").fetchall()
    columns = {row["column"] for row in proposals}
    assert columns == {"Method", "Outcome"}
    flags = [json.loads(row["flags_json"] or "{}") for row in proposals]
    assert any(flag.get("validation_mode") in {"exact", "normalized"} for flag in flags)

    assert (run_paths.run_dir / "run_report.json").exists()
    assert (run_paths.exports_dir / "mapping_report.html").exists()

    first_proposal = proposals[0]
    store.insert_review(
        {
            "review_id": first_proposal["proposal_id"],
            "proposal_id": first_proposal["proposal_id"],
            "decision": "accepted",
            "final_value": "method X",
            "note": "ok",
        }
    )
    export_run(run_paths.run_dir)
    exported = pd.read_excel(run_paths.exports_dir / "updated_table.xlsx")
    assert exported.loc[0, "Method"] == "method X"
    assert (run_paths.exports_dir / "audit_log.csv").exists()
    assert not (run_paths.exports_dir / "proposals.jsonl").exists()
