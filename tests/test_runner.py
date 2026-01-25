from pathlib import Path

from paper_table_agent.config import RunConfig, create_run_paths
from paper_table_agent.config import MatchingConfig
from paper_table_agent.graph.matching import RowCandidate
from paper_table_agent.graph.runner import _align_schema_columns, _should_attempt_llm_match, prepare_context, process_pdf
from paper_table_agent.io.schema import ColumnSpec
from paper_table_agent.llm.models import AdjudicationResult
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
    assert grouped_columns == {"Method", "Outcome", "Dose", "Population", "Setting"}


def test_align_schema_columns_normalizes_nbsp() -> None:
    specs = [
        ColumnSpec(column_name="Dose\u00a0mg", description="dose", column_key="Dose\u00a0mg"),
    ]
    _align_schema_columns(specs, ["Dose mg"])
    assert specs[0].column_name == "Dose mg"


def test_matching_fallback_triggers_llm_adjudication() -> None:
    config = MatchingConfig()
    candidates = [
        RowCandidate(
            row_id="1",
            title="Test",
            authors="A",
            year="2020",
            doi="",
            score=0.55,
            title_score=0.55,
            author_score=0.1,
            year_bonus=0.0,
            doi_bonus=0.0,
        ),
        RowCandidate(
            row_id="2",
            title="Test 2",
            authors="B",
            year="2020",
            doi="",
            score=0.42,
            title_score=0.42,
            author_score=0.0,
            year_bonus=0.0,
            doi_bonus=0.0,
        ),
    ]
    assert _should_attempt_llm_match(candidates, config)


def test_matching_fallback_invokes_llm(monkeypatch, tmp_path: Path) -> None:
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
    config.retrieval.embedding_backend = "hash"
    config.retrieval.reranker_backend = "hash"
    run_paths = create_run_paths(config.table_path, root=tmp_path / "runs")
    store = Store.init_db(run_paths.db_path)
    context, pdfs = prepare_context(config, run_paths, store)

    invoked = {"called": False}

    def fake_deterministic_match(*args, **kwargs):
        return None

    def fake_adjudicate_match(*args, **kwargs):
        invoked["called"] = True
        return AdjudicationResult(
            row_id="0",
            status="matched",
            top_candidates=[],
            confidence=0.8,
            rationale="",
            evidence=[],
        )

    monkeypatch.setattr("paper_table_agent.graph.runner.deterministic_match", fake_deterministic_match)
    monkeypatch.setattr("paper_table_agent.graph.runner.adjudicate_match", fake_adjudicate_match)
    monkeypatch.setattr("paper_table_agent.graph.runner._should_attempt_llm_match", lambda *_: True)

    assert pdfs
    process_pdf(context, pdfs[0], {})
    assert invoked["called"]
