from __future__ import annotations

import argparse
import json
from pathlib import Path

from .benchmarks import load_benchmarks
from .bundle import build_candidate_from_dict
from .overnight import generate_overnight_report
from .proposal_tables import write_proposal_tables
from .results import ResultsWriter
from .search_space import load_search_space
from .settings import load_config
from .study import evaluate_candidate_suite, run_compare_mode, run_optimize_mode, summarize
from .utils import read_json
from .validation import validate_preflight


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paper-optimizer")
    sub = parser.add_subparsers(dest="command", required=True)

    preflight = sub.add_parser("preflight", help="Validate config and benchmark wiring without launching candidates")
    preflight.add_argument("--config", type=Path, required=True)

    optimize = sub.add_parser("optimize", help="Run compare or optimize study")
    optimize.add_argument("--study-type", choices=["compare", "optimize"], required=True)
    optimize.add_argument("--config", type=Path, required=True)
    optimize.add_argument("--out", type=Path, required=True)
    optimize.add_argument("--suite", help="Benchmark suite id from config.benchmark_suites")
    optimize.add_argument("--replicates", type=int, help="Override config replicates.count")

    eval_candidate = sub.add_parser("evaluate-candidate", help="Evaluate one candidate against a benchmark suite")
    eval_candidate.add_argument("--config", type=Path, required=True)
    eval_candidate.add_argument("--candidate-file", type=Path, required=True)
    eval_candidate.add_argument("--suite", required=True, help="Benchmark suite id such as smoke_suite or dev_suite")
    eval_candidate.add_argument("--out", type=Path, required=True)

    summarize_cmd = sub.add_parser("summarize", help="Rebuild summaries and plots from saved artifacts")
    summarize_cmd.add_argument("--config", type=Path, required=True)
    summarize_cmd.add_argument("--experiment", type=Path, required=True)

    proposals_cmd = sub.add_parser("proposal-tables", help="Export proposal and scored-cell inspection tables")
    proposals_cmd.add_argument("--experiment", type=Path, required=True)

    overnight_cmd = sub.add_parser("overnight-report", help="Build a combined overnight aggregate table and report")
    overnight_cmd.add_argument("--manifest", type=Path, required=True)

    return parser


def _cmd_optimize(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    if args.replicates is not None:
        if args.replicates <= 0:
            raise ValueError("--replicates must be a positive integer")
        config.setdefault("replicates", {})["count"] = args.replicates
    benchmarks = load_benchmarks(config)
    search_space = load_search_space(config)
    validate_preflight(config, benchmarks, require_holdout=False)

    if args.study_type == "compare":
        run_compare_mode(config, benchmarks, args.out, suite_id=args.suite)
    else:
        run_optimize_mode(config, benchmarks, search_space, args.out, suite_id=args.suite)


def _cmd_preflight(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    benchmarks = load_benchmarks(config)
    validate_preflight(config, benchmarks, require_holdout=False)
    print(
        json.dumps(
            {
                "ok": True,
                "schema_version": config["schema_version"],
                "experiment_id": config["experiment_id"],
                "benchmarks": sorted(benchmarks.manifests.keys()),
                "benchmark_suites": sorted(config.get("benchmark_suites", {}).keys()),
                "splits": dict(sorted(benchmarks.split_to_id.items())),
            },
            sort_keys=True,
        )
    )


def _cmd_evaluate_candidate(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    benchmarks = load_benchmarks(config)
    validate_preflight(config, benchmarks, require_holdout=False)

    payload = read_json(args.candidate_file)
    candidate = build_candidate_from_dict(
        payload.get("candidate_id", "cand_9999"),
        payload,
        parent_candidate_id=payload.get("parent_candidate_id"),
        round_index=payload.get("round_index"),
    )

    writer = ResultsWriter(args.out)
    writer.write_experiment_manifest(
        {
            "schema_version": config["schema_version"],
            "experiment_id": config["experiment_id"],
            "study_type": "single",
            "suite_id": args.suite,
        }
    )
    result = evaluate_candidate_suite(
        config,
        experiment_dir=args.out,
        candidate=candidate,
        suite_id=args.suite,
        study_type="single",
        decision="evaluated",
        reason="single_candidate_eval",
        writer=writer,
    )
    writer.append_result(result)


def _cmd_summarize(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    benchmarks = load_benchmarks(config)
    validate_preflight(config, benchmarks, require_holdout=False, experiment_dir=args.experiment)
    summarize(config, args.experiment)


def _cmd_overnight_report(args: argparse.Namespace) -> None:
    generate_overnight_report(args.manifest)


def _cmd_proposal_tables(args: argparse.Namespace) -> None:
    manifest = write_proposal_tables(args.experiment)
    print(json.dumps(manifest, sort_keys=True))


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "optimize":
        _cmd_optimize(args)
    elif args.command == "preflight":
        _cmd_preflight(args)
    elif args.command == "evaluate-candidate":
        _cmd_evaluate_candidate(args)
    elif args.command == "summarize":
        _cmd_summarize(args)
    elif args.command == "overnight-report":
        _cmd_overnight_report(args)
    elif args.command == "proposal-tables":
        _cmd_proposal_tables(args)
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main()
