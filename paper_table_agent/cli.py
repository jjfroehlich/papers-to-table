from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from paper_table_agent.config import RunConfig, RunPaths, capture_run_config, create_run_paths, load_prompt_versions
from paper_table_agent.graph.workflow import run_workflow
from paper_table_agent.store.db import Store


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="paper-table-agent")
    sub = parser.add_subparsers(dest="command", required=True)

    ui_parser = sub.add_parser("ui", help="Launch Streamlit UI")
    ui_parser.add_argument("--host", default="0.0.0.0")
    ui_parser.add_argument("--port", default=8501, type=int)

    run_parser = sub.add_parser("run", help="Run batch pipeline")
    run_parser.add_argument("--config", required=True, type=Path)
    resume_parser = sub.add_parser("resume", help="Resume a batch pipeline")
    resume_parser.add_argument("--run_dir", required=True, type=Path)

    stop_parser = sub.add_parser("stop", help="Stop a running batch pipeline")
    stop_parser.add_argument("--run_dir", required=True, type=Path)

    export_parser = sub.add_parser("export", help="Export run outputs")
    export_parser.add_argument("--run_dir", required=True, type=Path)

    bundle_parser = sub.add_parser("bundle", help="Create a run bundle zip")
    bundle_parser.add_argument("--run_dir", required=True, type=Path)

    init_db_parser = sub.add_parser("init-db", help="Initialize run DB")
    init_db_parser.add_argument("--run_dir", required=True, type=Path)

    config_parser = sub.add_parser("init-config", help="Write a sample run config")
    config_parser.add_argument("--output", required=True, type=Path)

    snapshot_parser = sub.add_parser("snapshot", help="Capture a project snapshot bundle")
    snapshot_parser.add_argument("--out", type=Path, default=None)
    snapshot_parser.add_argument("--include-run", dest="include_run", type=Path, default=None)

    doctor_parser = sub.add_parser("doctor", help="Validate docs/spec consistency")
    doctor_parser.add_argument("--verbose", action="store_true")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.command == "ui":
        cmd = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "paper_table_agent/ui/app.py",
            "--server.address",
            args.host,
            "--server.port",
            str(args.port),
        ]
        subprocess.run(cmd, check=True)
        return

    if args.command == "init-db":
        Store.init_db(args.run_dir / "proposals.sqlite")
        return

    if args.command == "run":
        config = RunConfig.model_validate_json(Path(args.config).read_text(encoding="utf-8"))
        run_paths = create_run_paths(config.table_path, run_name=config.run_name)
        prompt_versions = load_prompt_versions(Path("paper_table_agent/prompts"))
        capture_run_config(config, run_paths, prompt_versions)
        store = Store.init_db(run_paths.db_path)
        run_workflow(config=config, run_paths=run_paths, store=store)
        return

    if args.command == "resume":
        run_dir = args.run_dir
        config_path = run_dir / "run_config.json"
        config = RunConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
        store = Store.init_db(run_dir / "proposals.sqlite")
        run_workflow(config=config, run_paths=RunPaths(run_dir=run_dir), store=store, resume=True)
        return

    if args.command == "stop":
        (args.run_dir / "STOP").write_text("stop", encoding="utf-8")
        return

    if args.command == "export":
        from paper_table_agent.graph.exporter import export_run

        export_run(args.run_dir)
        return

    if args.command == "bundle":
        from paper_table_agent.graph.reporting import write_run_bundle

        write_run_bundle(args.run_dir)
        return

    if args.command == "init-config":
        config = RunConfig(table_path=Path("table.xlsx"), pdf_folder=Path("pdfs"))
        args.output.write_text(config.to_json(), encoding="utf-8")
        return

    if args.command == "snapshot":
        from paper_table_agent.snapshot import DEFAULT_SNAPSHOT_DIR, write_snapshot

        out_dir = args.out or DEFAULT_SNAPSHOT_DIR
        write_snapshot(out_dir, include_run=args.include_run)
        return

    if args.command == "doctor":
        from paper_table_agent.doctor import run_doctor

        exit_code = run_doctor(verbose=args.verbose)
        if exit_code:
            sys.exit(exit_code)
        return


if __name__ == "__main__":
    main()
