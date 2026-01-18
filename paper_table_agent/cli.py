from __future__ import annotations

import argparse
from pathlib import Path

from paper_table_agent.config import RunConfig, capture_run_config, create_run_paths, load_prompt_versions
from paper_table_agent.graph.runner import run_pipeline
from paper_table_agent.store.db import Store


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="paper-table-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    ui_parser = sub.add_parser("ui", help="Launch Streamlit UI")
    ui_parser.add_argument("--host", default="0.0.0.0")
    ui_parser.add_argument("--port", default=8501, type=int)

    run_parser = sub.add_parser("run", help="Run batch pipeline")
    run_parser.add_argument("--config", required=True, type=Path)

    export_parser = sub.add_parser("export", help="Export run outputs")
    export_parser.add_argument("--run_dir", required=True, type=Path)

    init_db_parser = sub.add_parser("init-db", help="Initialize run DB")
    init_db_parser.add_argument("--run_dir", required=True, type=Path)

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "ui":
        import streamlit.web.bootstrap

        streamlit.web.bootstrap.run(
            "paper_table_agent/ui/app.py",
            f"streamlit run paper_table_agent/ui/app.py",
            [],
            {"server.address": args.host, "server.port": args.port},
        )
        return

    if args.command == "init-db":
        Store.init_db(args.run_dir / "proposals.sqlite")
        return

    if args.command == "run":
        config = RunConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8"))
        run_paths = create_run_paths(config.table_path)
        prompt_versions = load_prompt_versions(Path("paper_table_agent/prompts"))
        capture_run_config(config, run_paths, prompt_versions)
        store = Store.init_db(run_paths.db_path)
        run_pipeline(config=config, run_paths=run_paths, store=store)
        return

    if args.command == "export":
        from paper_table_agent.graph.exporter import export_run

        export_run(args.run_dir)
        return


if __name__ == "__main__":
    main()
