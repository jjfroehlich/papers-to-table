import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

fitz = pytest.importorskip("fitz")
pd = pytest.importorskip("pandas")

from paper_table_agent.config import RunConfig, create_run_paths
from paper_table_agent.graph.exporter import export_run
from paper_table_agent.graph.runner import run_pipeline
from paper_table_agent.store.db import Store
from paper_table_agent.ui.registry import discover_runs
from paper_table_agent.ui.review_queue import build_review_rows, review_items_for_row


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def _write_stub_config(tmp_path: Path) -> Path:
    fixtures = _fixture_dir()
    config_path = tmp_path / "stub_run_config.json"
    payload = json.loads((fixtures / "stub_run_config.json").read_text(encoding="utf-8"))
    payload["table_path"] = str((fixtures / "minimal_table.csv").resolve())
    payload["schema_path"] = str((fixtures / "minimal_schema.csv").resolve())
    payload["pdf_folder"] = str((fixtures / "pdfs").resolve())
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return config_path


def test_end_to_end_with_stub_llm_cli(tmp_path: Path):
    fixtures = _fixture_dir()
    table_path = fixtures / "minimal_table.csv"
    pdf_folder = fixtures / "pdfs"
    config_path = _write_stub_config(tmp_path)

    env = dict(**os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    subprocess.run(
        [sys.executable, "-m", "paper_table_agent.cli", "run", "--config", str(config_path)],
        check=True,
        cwd=tmp_path,
        env=env,
    )
    runs_dir = tmp_path / "runs"
    run_dirs = sorted(runs_dir.iterdir())
    assert run_dirs
    run_dir = run_dirs[0]
    store = Store.init_db(run_dir / "proposals.sqlite")
    assert (run_dir / "exports" / "proposal_eval.json").exists()

    proposals = store.conn.execute("SELECT * FROM proposals").fetchall()
    assert proposals
    matches = store.fetch_matches()
    matched_rows = {row["row_id"] for row in matches if row["status"] == "matched"}
    assert matched_rows
    matched_proposals = [
        row for row in proposals if row["row_id"] in matched_rows
    ]
    assert matched_proposals
    evidence_found = False
    for row in matched_proposals:
        if not row["proposed_value"]:
            continue
        evidence = json.loads(row["evidence_json"] or "[]")
        if not evidence:
            continue
        if evidence[0].get("highlight_status") != "missing_quote_or_page":
            evidence_found = True
            break
    assert evidence_found

    rows = [dict(row) for row in store.fetch_rows()]
    matches = [dict(row) for row in store.fetch_matches()]
    proposals_meta = [dict(row) for row in store.conn.execute("SELECT * FROM proposals")]
    table = pd.read_csv(table_path)
    table_wrapper = type("Table", (), {"dataframe": table})
    review_rows = build_review_rows(rows, matches, proposals_meta, table_wrapper)
    assert review_rows
    row_items = review_items_for_row(review_rows[0], proposals_meta, table_wrapper)
    assert row_items


def test_registry_lists_runs(tmp_path: Path):
    run_dir = tmp_path / "runs" / "20250101_000000__demo"
    run_dir.mkdir(parents=True)
    (run_dir / "run_config.json").write_text(
        "{\"table_path\": \"table.xlsx\", \"pdf_folder\": \"pdfs\"}",
        encoding="utf-8",
    )
    (run_dir / "proposals.sqlite").write_text("stub", encoding="utf-8")
    runs = discover_runs(tmp_path / "runs")
    assert runs


def test_integration_run_report_and_validation(tmp_path: Path):
    fixtures = _fixture_dir()
    table_path = fixtures / "minimal_table.csv"
    schema_path = fixtures / "minimal_schema.csv"
    pdf_folder = fixtures / "pdfs"

    config = RunConfig(
        table_path=table_path,
        pdf_folder=pdf_folder,
        schema_sheet_name="schema",
        schema_mode="separate",
        schema_path=schema_path,
        title_col="Title",
        authors_col="Authors",
        year_col="Year",
    )
    config.provider.mode = "stub"
    config.retrieval.embedding_backend = "hash"
    config.retrieval.reranker_backend = "hash"

    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    run_pipeline(config, run_paths, store)

    proposals = store.conn.execute("SELECT column, flags_json, proposal_id FROM proposals").fetchall()
    columns = {row["column"] for row in proposals}
    assert columns == {"Method", "Outcome", "Dose", "Population", "Setting"}

    assert (run_paths.run_dir / "run_report.json").exists()
    assert (run_paths.exports_dir / "proposal_eval.json").exists()
    assert not (run_paths.exports_dir / "pdf_row_matches.csv").exists()
    report = (run_paths.run_dir / "run_report.json").read_text(encoding="utf-8")
    assert "\"status\": \"completed\"" in report

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
    assert exported.loc[0, "Method"]
    assert (run_paths.exports_dir / "audit_log.csv").exists()
    assert not (run_paths.exports_dir / "proposals.jsonl").exists()


def test_default_audit_eval_artifacts(tmp_path: Path):
    fixtures = _fixture_dir()
    table_path = fixtures / "audit_table.csv"
    schema_path = fixtures / "minimal_schema.csv"
    pdf_folder = fixtures / "pdfs"

    config = RunConfig(
        table_path=table_path,
        pdf_folder=pdf_folder,
        schema_sheet_name="schema",
        schema_mode="separate",
        schema_path=schema_path,
        title_col="Title",
        authors_col="Authors",
        year_col="Year",
    )
    config.provider.mode = "stub"
    config.retrieval.embedding_backend = "hash"
    config.retrieval.reranker_backend = "hash"

    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    run_pipeline(config, run_paths, store)

    proposals = store.conn.execute("SELECT flags_json FROM proposals").fetchall()
    audit_flags = [
        json.loads(row["flags_json"] or "{}")
        for row in proposals
        if json.loads(row["flags_json"] or "{}").get("proposal_kind") == "audit"
    ]
    assert audit_flags
    assert (run_paths.exports_dir / "proposal_eval.json").exists()
    report = json.loads((run_paths.run_dir / "run_report.json").read_text(encoding="utf-8"))
    assert report["summary"]["evaluation"]["audited_cells"] >= 1


def test_end_to_end_with_mock_mode(tmp_path: Path):
    assets = Path(__file__).resolve().parent / "assets"
    table_path = assets / "mock_table.csv"
    schema_path = assets / "mock_schema.csv"
    pdf_folder = assets / "mock_pdfs"
    mock_payloads = Path(__file__).resolve().parent / "fixtures" / "mock_payloads" / "mock_payloads.json"

    config = RunConfig(
        table_path=table_path,
        pdf_folder=pdf_folder,
        schema_sheet_name="schema",
        schema_mode="separate",
        schema_path=schema_path,
        title_col="Title",
        authors_col="Authors",
        year_col="Year",
    )
    config.provider.mock_mode = True
    config.provider.mock_payloads_path = mock_payloads
    config.retrieval.use_dense = False
    config.retrieval.use_reranker = False
    config.retrieval.use_query_expansion = False
    config.retrieval.use_hyde = False

    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    run_pipeline(config, run_paths, store)

    proposals = store.conn.execute(
        "SELECT proposed_value, evidence_json FROM proposals WHERE row_id = '0'"
    ).fetchall()
    assert proposals
    assert sum(1 for row in proposals if row["proposed_value"]) >= 2
    for row in proposals:
        evidence = json.loads(row["evidence_json"] or "[]")
        if row["proposed_value"]:
            assert evidence
            assert evidence[0].get("page") == 1
            assert evidence[0].get("chunk_id")


def test_mock_mode_backfills_missing_evidence(tmp_path: Path):
    fixtures = _fixture_dir()
    table_path = fixtures / "minimal_table.csv"
    schema_path = fixtures / "minimal_schema.csv"
    pdf_folder = fixtures / "pdfs"
    mock_payloads = (
        Path(__file__).resolve().parent / "fixtures" / "mock_payloads" / "mock_payloads_empty_evidence.json"
    )

    config = RunConfig(
        table_path=table_path,
        pdf_folder=pdf_folder,
        schema_sheet_name="schema",
        schema_mode="separate",
        schema_path=schema_path,
        title_col="Title",
        authors_col="Authors",
        year_col="Year",
    )
    config.provider.mock_mode = True
    config.provider.mock_payloads_path = mock_payloads
    config.retrieval.use_dense = False
    config.retrieval.use_reranker = False
    config.retrieval.use_query_expansion = False
    config.retrieval.use_hyde = False

    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    run_pipeline(config, run_paths, store)

    proposals = store.conn.execute(
        "SELECT proposed_value, evidence_json, flags_json FROM proposals WHERE row_id = '0'"
    ).fetchall()
    assert proposals
    for row in proposals:
        if not row["proposed_value"]:
            continue
        evidence = json.loads(row["evidence_json"] or "[]")
        flags = json.loads(row["flags_json"] or "{}")
        assert evidence
        assert flags.get("needs_more_evidence") is True
        assert flags.get("evidence_finder_attempted") is True
