from __future__ import annotations

import argparse
from pathlib import Path

from paper_eval.aggregate import build_run_summary
from paper_eval.errors import CliUsageError, ContractError, EvaluationError
from paper_eval.gold_loader import load_gold
from paper_eval.output_paths import create_output_layout
from paper_eval.run_loader import discover_run_directories, load_run
from paper_eval.schema_loader import load_schema
from paper_eval.score import score_run
from paper_eval.writers import write_run_summary, write_scored_cells


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-eval", description="Evaluate main-app run artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    evaluate = subparsers.add_parser("evaluate", help="Score one or more runs against a gold table.")
    evaluate.add_argument("--run", dest="runs", action="append", default=[], help="Path to a run directory.")
    evaluate.add_argument("--runs-root", type=Path, help="Directory containing many run directories.")
    evaluate.add_argument("--gold", type=Path, required=True, help="Path to the gold CSV or XLSX file.")
    evaluate.add_argument(
        "--gold-sheet",
        help="Worksheet name for XLSX gold inputs. Defaults to the first worksheet in workbook order.",
    )
    evaluate.add_argument("--schema", type=Path, help="Optional schema metadata JSON file.")
    evaluate.add_argument("--out", type=Path, required=True, help="Output directory for evaluation artifacts.")
    evaluate.set_defaults(handler=_handle_evaluate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except (CliUsageError, ContractError) as exc:
        parser.error(str(exc))
    except EvaluationError as exc:
        parser.exit(status=1, message=f"{exc}\n")
    return 0


def _handle_evaluate(args: argparse.Namespace) -> int:
    output_layout = create_output_layout(args.out.resolve())
    schema = load_schema(args.schema.resolve() if args.schema else None)
    gold_dataset = load_gold(args.gold.resolve(), sheet_name=args.gold_sheet)
    run_dirs = discover_run_directories([Path(path).resolve() for path in args.runs], args.runs_root.resolve() if args.runs_root else None)

    for run_dir in run_dirs:
        loaded_run = load_run(run_dir)
        scored_cells = score_run(loaded_run, gold_dataset, schema)
        summary = build_run_summary(loaded_run, gold_dataset, scored_cells)
        run_output_dir = output_layout.run_dir(summary.run_id)
        run_output_dir.mkdir(parents=True, exist_ok=True)
        write_scored_cells(run_output_dir, scored_cells)
        write_run_summary(run_output_dir, summary)
        print(f"Scored run {summary.run_id} -> {run_output_dir}")
    return 0
