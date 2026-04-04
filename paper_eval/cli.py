from __future__ import annotations

import argparse
import os
from pathlib import Path

from paper_eval.aggregate import build_run_summary
from paper_eval.contracts import (
    DEFAULT_JUDGE_MODEL_ID,
    DEFAULT_JUDGE_PROVIDER,
    DEFAULT_LM_STUDIO_API_BASE,
    JudgeConfig,
)
from paper_eval.errors import CliUsageError, ContractError, EvaluationError
from paper_eval.gold_loader import load_gold
from paper_eval.judge import LMStudioTextJudge
from paper_eval.output_paths import create_output_layout
from paper_eval.run_loader import discover_run_directories, load_run
from paper_eval.schema_loader import load_schema
from paper_eval.score import score_run
from paper_eval.writers import (
    load_summary_rows_from_directory,
    write_comparison_artifacts,
    write_comparison_artifacts_from_rows,
    write_judge_records,
    write_run_summary,
    write_scored_cells,
)


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
    evaluate.add_argument(
        "--judge-model",
        help=f"Judge model id for text fields. Defaults to {DEFAULT_JUDGE_MODEL_ID}.",
    )
    evaluate.add_argument(
        "--judge-api-base",
        help=f"Optional LM Studio OpenAI-compatible API base URL. Defaults to {DEFAULT_LM_STUDIO_API_BASE}.",
    )
    evaluate.add_argument("--out", type=Path, required=True, help="Output directory for evaluation artifacts.")
    evaluate.set_defaults(handler=_handle_evaluate)

    compare = subparsers.add_parser("compare", help="Rebuild comparison artifacts from per-run summary JSON files.")
    compare.add_argument(
        "--summaries",
        type=Path,
        required=True,
        help="Path to the per-run summary root or a specific run_summary.json file.",
    )
    compare.add_argument("--out", type=Path, required=True, help="Output directory for comparison artifacts.")
    compare.set_defaults(handler=_handle_compare)
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
    judge_config = build_judge_config(args)
    text_judge = build_text_judge(judge_config)

    summaries = []
    for run_dir in run_dirs:
        loaded_run = load_run(run_dir)
        score_result = score_run(
            loaded_run,
            gold_dataset,
            schema,
            text_judge=text_judge,
            judge_config=judge_config,
        )
        summary = build_run_summary(loaded_run, gold_dataset, score_result.scored_cells)
        summaries.append(summary)
        run_output_dir = output_layout.run_dir(summary.run_id)
        run_output_dir.mkdir(parents=True, exist_ok=True)
        write_scored_cells(run_output_dir, score_result.scored_cells)
        write_judge_records(run_output_dir, score_result.judge_records)
        write_run_summary(run_output_dir, summary)
        print(f"Scored run {summary.run_id} -> {run_output_dir}")
    write_comparison_artifacts(output_layout.compare_root, summaries)
    print(f"Wrote comparison artifacts -> {output_layout.compare_root}")
    return 0


def _handle_compare(args: argparse.Namespace) -> int:
    output_dir = args.out.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = load_summary_rows_from_directory(args.summaries.resolve())
    write_comparison_artifacts_from_rows(output_dir, rows)
    print(f"Wrote comparison artifacts -> {output_dir}")
    return 0


def build_judge_config(args: argparse.Namespace) -> JudgeConfig | None:
    model_id = args.judge_model or os.environ.get("PAPER_EVAL_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL_ID
    return JudgeConfig(
        model_id=model_id,
        provider=DEFAULT_JUDGE_PROVIDER,
        api_base=args.judge_api_base or os.environ.get("PAPER_EVAL_JUDGE_API_BASE") or DEFAULT_LM_STUDIO_API_BASE,
        api_key=os.environ.get("PAPER_EVAL_JUDGE_API_KEY"),
    )


def build_text_judge(judge_config: JudgeConfig | None) -> LMStudioTextJudge | None:
    if judge_config is None:
        return None
    return LMStudioTextJudge(judge_config)
