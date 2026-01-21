from pathlib import Path

from paper_table_agent.ui.defaults import load_default_run_config, resolve_default_paths


def test_ui_defaults_from_config(tmp_path: Path) -> None:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        "{\"table_path\": \"data/table.xlsx\", \"pdf_folder\": \"data/pdfs\"}",
        encoding="utf-8",
    )
    defaults = load_default_run_config(config_path)
    table_path, pdf_folder = resolve_default_paths(defaults)
    assert table_path == "data/table.xlsx"
    assert pdf_folder == "data/pdfs"
