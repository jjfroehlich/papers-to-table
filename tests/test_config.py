from pathlib import Path

from paper_table_agent.config import RunConfig


def test_run_config_validation(tmp_path: Path):
    table_path = tmp_path / "table.xlsx"
    table_path.write_text("stub", encoding="utf-8")
    pdf_folder = tmp_path / "pdfs"
    pdf_folder.mkdir()
    config = RunConfig(table_path=table_path, pdf_folder=pdf_folder)
    assert config.table_path == table_path


def test_run_config_quality_defaults(tmp_path: Path):
    table_path = tmp_path / "table.xlsx"
    table_path.write_text("stub", encoding="utf-8")
    pdf_folder = tmp_path / "pdfs"
    pdf_folder.mkdir()

    config = RunConfig(table_path=table_path, pdf_folder=pdf_folder)

    assert config.provider.guided_json_mode == "auto"
    assert config.extraction.examples_per_col == 1
    assert config.extraction.column_batch_size == 1
    assert config.extraction.max_chunks == 32
    assert config.extraction.retry_extra_chunks == 8
    assert config.extraction.whole_text_max_tokens == 8000
    assert config.extraction.paper_memory_max_tokens == 2400
    assert config.retrieval.top_k == 24
    assert config.retrieval.rerank_k == 24
    assert config.retrieval.max_context_tokens == 3200
    assert config.retrieval.context_window == 2
    assert config.retrieval.section_chunk_limit == 8
