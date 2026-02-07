from __future__ import annotations

import argparse
import json
import os
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
    ui_parser.add_argument("--smoke", action="store_true", help="Run UI import smoke test without launching server")

    run_parser = sub.add_parser("run", help="Run batch pipeline")
    run_parser.add_argument("--config", required=True, type=Path)
    resume_parser = sub.add_parser("resume", help="Resume a batch pipeline")
    resume_parser.add_argument("--run_dir", required=True, type=Path)

    stop_parser = sub.add_parser("stop", help="Stop a running batch pipeline")
    stop_parser.add_argument("--run_dir", required=True, type=Path)

    export_parser = sub.add_parser("export", help="Export run outputs")
    export_parser.add_argument("--run_dir", required=True, type=Path)

    bundle_parser = sub.add_parser("bundle", help="Create a run bundle zip")
    bundle_parser.add_argument("--run_dir", type=Path, help="Run directory (defaults to latest in runs)")

    eval_parser = sub.add_parser("eval", help="Evaluate proposals against filled cells")
    eval_parser.add_argument("--run_dir", type=Path, help="Run directory (uses run_config.json + proposals.sqlite)")
    eval_parser.add_argument("--db_path", type=Path, help="Path to proposals.sqlite")
    eval_parser.add_argument("--table_path", type=Path, help="Table path (CSV/XLSX)")
    eval_parser.add_argument("--schema_sheet_name", type=str, default=None)
    eval_parser.add_argument("--pdf_folder", type=Path, default=None)
    eval_parser.add_argument("--output_dir", type=Path, default=None)

    init_db_parser = sub.add_parser("init-db", help="Initialize run DB")
    init_db_parser.add_argument("--run_dir", required=True, type=Path)

    config_parser = sub.add_parser("init-config", help="Write a sample run config")
    config_parser.add_argument("--output", required=True, type=Path)

    snapshot_parser = sub.add_parser("snapshot", help="Capture a project snapshot bundle")
    snapshot_parser.add_argument("--out", type=Path, default=None)

    return parser.parse_args()


def _resolve_latest_run_dir() -> Path:
    runs_root = Path(os.getenv("PAPER_TABLE_AGENT_RUNS_ROOT", "runs"))
    if not runs_root.exists():
        raise SystemExit(f"Runs root not found: {runs_root}")
    candidates = []
    for path in runs_root.iterdir():
        if not path.is_dir():
            continue
        if path.name.startswith("_"):
            continue
        if not (path / "run_config.json").exists():
            continue
        candidates.append(path)
    if not candidates:
        raise SystemExit(f"No runs found under {runs_root}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> None:
    args = _parse_args()
    if args.command == "ui":
        if args.smoke:
            os.environ.setdefault("PAPER_TABLE_AGENT_UI_SMOKE", "1")
            import paper_table_agent.ui.app  # noqa: F401

            return
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

        run_dir = args.run_dir or _resolve_latest_run_dir()
        write_run_bundle(run_dir)
        return

    if args.command == "eval":
        from paper_table_agent.graph.evaluation import evaluate_run

        run_dir = args.run_dir
        if run_dir:
            run_config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
            db_path = run_dir / "proposals.sqlite"
            table_path = Path(run_config["table_path"])
            schema_sheet_name = run_config.get("schema_sheet_name")
            pdf_folder = Path(run_config["pdf_folder"]) if run_config.get("pdf_folder") else None
            evaluate_run(
                run_dir=run_dir,
                db_path=db_path,
                table_path=table_path,
                schema_sheet_name=schema_sheet_name,
                pdf_folder=pdf_folder,
                output_dir=args.output_dir,
            )
            return
        if not args.db_path or not args.table_path:
            raise SystemExit("eval requires --run_dir or both --db_path and --table_path")
        evaluate_run(
            run_dir=None,
            db_path=args.db_path,
            table_path=args.table_path,
            schema_sheet_name=args.schema_sheet_name,
            pdf_folder=args.pdf_folder,
            output_dir=args.output_dir,
        )
        return

    if args.command == "init-config":
        config = RunConfig(table_path=Path("table.xlsx"), pdf_folder=Path("pdfs"))
        args.output.write_text(config.to_json(), encoding="utf-8")
        return

    if args.command == "snapshot":
        from paper_table_agent.snapshot import DEFAULT_SNAPSHOT_DIR, write_snapshot

        out_dir = args.out or DEFAULT_SNAPSHOT_DIR
        write_snapshot(out_dir)
        return

if __name__ == "__main__":
    main()
