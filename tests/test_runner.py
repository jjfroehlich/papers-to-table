from pathlib import Path

from paper_table_agent.config import RunConfig, create_run_paths
from paper_table_agent.graph.runner import prepare_context
from paper_table_agent.store.db import Store


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def test_empty_extraction_groups_default_to_schema(tmp_path: Path) -> None:
    fixtures = _fixture_dir()
    config = RunConfig(
        table_path=fixtures / "minimal_table.csv",
        pdf_folder=fixtures / "pdfs",
        schema_sheet_name="schema",
        schema_mode="separate",
        schema_path=fixtures / "minimal_schema.csv",
        title_col="Title",
        authors_col="Authors",
        year_col="Year",
    )
    config.provider.mode = "stub"
    config.extraction.groups = []

    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    context, _ = prepare_context(config, run_paths, store)

    grouped_columns = {
        spec.column_name for specs in context.grouped.values() for spec in specs
    }
    assert grouped_columns == {"Method", "Outcome", "Dose"}
