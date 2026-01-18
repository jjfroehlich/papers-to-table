from pathlib import Path

from paper_table_agent.config import RunConfig


def test_run_config_validation(tmp_path: Path):
    table_path = tmp_path / "table.xlsx"
    table_path.write_text("stub", encoding="utf-8")
    pdf_folder = tmp_path / "pdfs"
    pdf_folder.mkdir()
    config = RunConfig(table_path=table_path, pdf_folder=pdf_folder)
    assert config.table_path == table_path
