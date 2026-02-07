from __future__ import annotations

import argparse
from pathlib import Path
import json

from paper_table_agent.graph.evaluation import evaluate_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate audit proposals against filled cells.")
    parser.add_argument("--run_dir", type=Path, help="Run directory containing run_config.json")
    parser.add_argument("--db_path", type=Path, help="Path to proposals.sqlite")
    parser.add_argument("--table_path", type=Path, help="Path to table CSV/XLSX")
    parser.add_argument("--schema_sheet_name", type=str, default=None)
    parser.add_argument("--pdf_folder", type=Path, default=None)
    parser.add_argument("--output_dir", type=Path, default=None)
    args = parser.parse_args()
    if args.run_dir:
        run_dir = args.run_dir
        config = json.loads((run_dir / "run_config.json").read_text(encoding="utf-8"))
        evaluate_run(
            run_dir=run_dir,
            db_path=run_dir / "proposals.sqlite",
            table_path=Path(config["table_path"]),
            schema_sheet_name=config.get("schema_sheet_name"),
            pdf_folder=Path(config["pdf_folder"]) if config.get("pdf_folder") else args.pdf_folder,
            output_dir=args.output_dir,
        )
        return
    if not args.db_path or not args.table_path:
        raise SystemExit("Provide --run_dir or both --db_path and --table_path")
    evaluate_run(
        run_dir=None,
        db_path=args.db_path,
        table_path=args.table_path,
        schema_sheet_name=args.schema_sheet_name,
        pdf_folder=args.pdf_folder,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
