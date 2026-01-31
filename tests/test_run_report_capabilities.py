import json
from pathlib import Path

from paper_table_agent.config import RunPaths
from paper_table_agent.graph.reporting import write_run_report
from paper_table_agent.store.db import Store


def test_run_report_includes_llm_capabilities(tmp_path: Path) -> None:
    fixtures = Path(__file__).resolve().parent / "fixtures"
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True)
    config_payload = {
        "table_path": str((fixtures / "minimal_table.csv").resolve()),
        "schema_mode": "separate",
        "schema_path": str((fixtures / "minimal_schema.csv").resolve()),
        "pdf_folder": str((fixtures / "pdfs").resolve()),
    }
    (run_dir / "run_config.json").write_text(json.dumps(config_payload), encoding="utf-8")

    store = Store.init_db(run_dir / "proposals.sqlite")
    store.record_event(
        "info",
        "llm_capabilities",
        {"model": "stub-model", "label": "extract", "guided_json": True, "prompt_json": True, "cached": True},
    )

    write_run_report(store, RunPaths(run_dir=run_dir))
    report = json.loads((run_dir / "run_report.json").read_text(encoding="utf-8"))

    capabilities = report["summary"].get("llm_capabilities")
    assert capabilities
    assert capabilities[0]["model"] == "stub-model"
