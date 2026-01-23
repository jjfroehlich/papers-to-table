import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from paper_table_agent.config import RunConfig, create_run_paths
from paper_table_agent.graph.runner import run_pipeline
from paper_table_agent.store.db import Store


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def test_review_ui_loads_stub_proposals(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assets = Path(__file__).resolve().parent / "assets"
    table_path = assets / "mock_table.csv"
    schema_path = assets / "mock_schema.csv"
    pdf_folder = assets / "mock_pdfs"
    mock_payloads = _fixture_dir() / "mock_payloads" / "mock_payloads.json"

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

    (tmp_path / "run_config.json").write_text(
        json.dumps({"table_path": str(table_path), "pdf_folder": str(pdf_folder)}, indent=2),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PAPER_TABLE_AGENT_TEST_MODE", "review")

    app_path = Path(__file__).resolve().parents[1] / "paper_table_agent" / "ui" / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=30)
    assert any("Column stepper" in selectbox.label for selectbox in app.selectbox)
    assert any("Method" in markdown.value for markdown in app.markdown)
    assert any("Evidence" in markdown.value for markdown in app.markdown)
