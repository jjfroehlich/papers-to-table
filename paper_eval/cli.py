from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from paper_eval.aggregate import build_run_summary
from paper_eval.contracts import (
    DEFAULT_JUDGE_MODEL_ID,
    DEFAULT_JUDGE_PROVIDER,
    DEFAULT_LM_STUDIO_API_BASE,
    JudgeConfig,
    RunSummary,
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

EVAL_STDOUT_SCHEMA_VERSION = "paper_eval_cli.v1"


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
    evaluate.add_argument(
        "--judge-model-b",
        help="Optional second judge model id for dual-judge scoring.",
    )
    evaluate.add_argument(
        "--judge-api-base-b",
        help="Optional LM Studio OpenAI-compatible API base URL for the second judge.",
    )
    evaluate.add_argument(
        "--json-output",
        action="store_true",
        help="Emit a machine-readable completion JSON payload to stdout.",
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
    compare.add_argument(
        "--json-output",
        action="store_true",
        help="Emit a machine-readable completion JSON payload to stdout.",
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
    run_dirs = discover_run_directories([Path(path).resolve() for path in args.runs], args.runs_root.resolve() if args.runs_root else None)
    judge_configs = build_judge_configs(args)
    text_judges = build_text_judges(judge_configs)
    gold_path = args.gold.resolve()
    gold_cache: dict[tuple[int, ...] | None, object] = {}

    summaries = []
    run_summary_paths: list[str] = []
    scored_cells_paths: list[str] = []
    judge_records_paths: list[str] = []
    for run_dir in run_dirs:
        score_result = None
        try:
            loaded_run = load_run(run_dir)
            cache_key = None
            if loaded_run.matched_row_indices is not None:
                cache_key = tuple(sorted(loaded_run.matched_row_indices))
            gold_dataset = gold_cache.get(cache_key)
            if gold_dataset is None:
                gold_dataset = load_gold(
                    gold_path,
                    sheet_name=args.gold_sheet,
                    allowed_row_indices=loaded_run.matched_row_indices,
                    scored_columns=set(schema.scored_columns) if schema.scored_columns else None,
                    excluded_columns=set(schema.excluded_columns) if schema.excluded_columns else None,
                )
                gold_cache[cache_key] = gold_dataset
            score_result = score_run(
                loaded_run,
                gold_dataset,
                schema,
                text_judges=text_judges,
                judge_configs=judge_configs,
            )
            summary = build_run_summary(loaded_run, gold_dataset, score_result.scored_cells)
        except ContractError as exc:
            summary = _build_unscored_summary(
                run_dir=run_dir,
                gold_path=gold_path,
                gold_sheet=args.gold_sheet,
                reason="invalid_run_bundle_contract",
                message=str(exc),
            )
            score_result = None
        except EvaluationError as exc:
            summary = _build_unscored_summary(
                run_dir=run_dir,
                gold_path=gold_path,
                gold_sheet=args.gold_sheet,
                reason="judge_failure" if "judge" in str(exc).lower() else "missing_required_eval_inputs",
                message=str(exc),
            )
            score_result = None
        summaries.append(summary)
        run_output_dir = output_layout.run_dir(summary.run_id)
        run_output_dir.mkdir(parents=True, exist_ok=True)
        write_scored_cells(run_output_dir, score_result.scored_cells if score_result is not None else [])
        write_judge_records(run_output_dir, score_result.judge_records if score_result is not None else [])
        write_run_summary(run_output_dir, summary)
        run_summary_paths.append(str((run_output_dir / "run_summary.json").resolve()))
        scored_cells_paths.append(str((run_output_dir / "scored_cells.jsonl").resolve()))
        if score_result is not None and score_result.judge_records:
            judge_records_paths.append(str((run_output_dir / "judge_records.jsonl").resolve()))
        if not args.json_output:
            print(f"Scored run {summary.run_id} -> {run_output_dir}")
    write_comparison_artifacts(output_layout.compare_root, summaries)
    comparison_paths = {
        "runs_comparison_csv": str((output_layout.compare_root / "runs_comparison.csv").resolve()),
        "runs_comparison_xlsx": str((output_layout.compare_root / "runs_comparison.xlsx").resolve()),
        "runs_comparison_parquet": str((output_layout.compare_root / "runs_comparison.parquet").resolve()),
    }
    if args.json_output:
        payload = {
            "schema_version": EVAL_STDOUT_SCHEMA_VERSION,
            "command": "evaluate",
            "status": "ok",
            "success": True,
            "output_dir": str(output_layout.root.resolve()),
            "per_run_dir": str(output_layout.per_run_root.resolve()),
            "compare_dir": str(output_layout.compare_root.resolve()),
            "run_count": len(summaries),
            "run_ids": [summary.run_id for summary in summaries],
            "run_summary_paths": run_summary_paths,
            "scored_cells_paths": scored_cells_paths,
            "judge_records_paths": judge_records_paths,
            "comparison_artifacts": comparison_paths,
        }
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        print(f"Wrote comparison artifacts -> {output_layout.compare_root}")
    return 0


def _handle_compare(args: argparse.Namespace) -> int:
    output_dir = args.out.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = load_summary_rows_from_directory(args.summaries.resolve())
    write_comparison_artifacts_from_rows(output_dir, rows)
    comparison_paths = {
        "runs_comparison_csv": str((output_dir / "runs_comparison.csv").resolve()),
        "runs_comparison_xlsx": str((output_dir / "runs_comparison.xlsx").resolve()),
        "runs_comparison_parquet": str((output_dir / "runs_comparison.parquet").resolve()),
    }
    if args.json_output:
        payload = {
            "schema_version": EVAL_STDOUT_SCHEMA_VERSION,
            "command": "compare",
            "status": "ok",
            "success": True,
            "summaries_input": str(args.summaries.resolve()),
            "output_dir": str(output_dir.resolve()),
            "row_count": len(rows),
            "comparison_artifacts": comparison_paths,
        }
        print(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    else:
        print(f"Wrote comparison artifacts -> {output_dir}")
    return 0


def build_judge_config(args: argparse.Namespace) -> JudgeConfig | None:
    configs = build_judge_configs(args)
    return configs.get("judge_a")


def build_judge_configs(args: argparse.Namespace) -> dict[str, JudgeConfig]:
    judge_model = getattr(args, "judge_model", None)
    judge_api_base = getattr(args, "judge_api_base", None)
    judge_model_b = getattr(args, "judge_model_b", None)
    judge_api_base_b = getattr(args, "judge_api_base_b", None)
    model_id = judge_model or os.environ.get("PAPER_EVAL_JUDGE_MODEL") or DEFAULT_JUDGE_MODEL_ID
    configs = {
        "judge_a": JudgeConfig(
            model_id=model_id,
            label="judge_a",
            provider=DEFAULT_JUDGE_PROVIDER,
            api_base=judge_api_base or os.environ.get("PAPER_EVAL_JUDGE_API_BASE") or DEFAULT_LM_STUDIO_API_BASE,
            api_key=os.environ.get("PAPER_EVAL_JUDGE_API_KEY"),
        )
    }
    model_id_b = judge_model_b or os.environ.get("PAPER_EVAL_JUDGE_MODEL_B")
    if model_id_b:
        configs["judge_b"] = JudgeConfig(
            model_id=model_id_b,
            label="judge_b",
            provider=DEFAULT_JUDGE_PROVIDER,
            api_base=judge_api_base_b or os.environ.get("PAPER_EVAL_JUDGE_API_BASE_B") or configs["judge_a"].api_base,
            api_key=os.environ.get("PAPER_EVAL_JUDGE_API_KEY_B") or os.environ.get("PAPER_EVAL_JUDGE_API_KEY"),
        )
    return configs


def build_text_judge(judge_config: JudgeConfig | None) -> LMStudioTextJudge | None:
    if judge_config is None:
        return None
    return LMStudioTextJudge(judge_config)


def build_text_judges(judge_configs: dict[str, JudgeConfig]) -> dict[str, LMStudioTextJudge]:
    return {
        label: judge
        for label, config in judge_configs.items()
        for judge in [build_text_judge(config)]
        if judge is not None
    }


def _build_unscored_summary(
    *,
    run_dir: Path,
    gold_path: Path,
    gold_sheet: str | None,
    reason: str,
    message: str,
) -> RunSummary:
    metrics = {
        "correctness": None,
        "correctness_mean": None,
        "correctness_judge_a": None,
        "correctness_judge_b": None,
        "correctness_abs_delta": None,
        "judge_disagreement": None,
        "contract_warning_count": 1,
        "scored": False,
        "unscored_reason": reason,
    }
    return RunSummary(
        run_id=run_dir.name,
        run_dir=run_dir,
        gold_source=gold_path,
        gold_sheet=gold_sheet,
        metrics=metrics,
        metadata={
            "run_id": run_dir.name,
            "run_dir": str(run_dir),
            "unscored_reason_detail": message,
            "extraction_contract_valid": False,
        },
        scored=False,
        unscored_reason=reason,
        unscored_reason_detail=message,
        contract_warnings=[message],
        join_diagnostics=[],
    )
