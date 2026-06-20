#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from review_package_common import reviewed_table_name, safe_filename  # noqa: E402


SCRATCH_DIRNAME = "scratch_delete_after_success"
SCRATCH_ROOT_MARKER = ".papers_to_table_scratch_root"
SCRATCH_RUN_MARKER = ".papers_to_table_scratch"


def prepare_output_workspace(output_dir: Path, run_ids: list[str]) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    runs_dir = output_dir / "runs"
    scratch_root = output_dir / SCRATCH_DIRNAME
    logs_root = output_dir / "logs"
    for path in (output_dir, runs_dir, scratch_root, logs_root):
        path.mkdir(parents=True, exist_ok=True)
    (scratch_root / SCRATCH_ROOT_MARKER).write_text("papers-to-table scratch root\n", encoding="utf-8")

    runs: list[dict[str, str]] = []
    for raw_run_id in run_ids:
        run_id = safe_filename(raw_run_id, "run")
        filled_name = f"{run_id}_filled.csv"
        runs.append(
            {
                "run_id": run_id,
                "run_dir": str(runs_dir / run_id),
                "scratch_dir": str(scratch_root / run_id),
                "log_dir": str(logs_root / run_id),
                "output_table_path": str(output_dir / filled_name),
                "reviewed_table_path": str(output_dir / reviewed_table_name(output_dir, {"output_table_name": filled_name})),
            }
        )
        Path(runs[-1]["run_dir"]).mkdir(parents=True, exist_ok=True)
        scratch_dir = Path(runs[-1]["scratch_dir"])
        scratch_dir.mkdir(parents=True, exist_ok=True)
        (scratch_dir / SCRATCH_RUN_MARKER).write_text("delete-after-success scratch\n", encoding="utf-8")
        Path(runs[-1]["log_dir"]).mkdir(parents=True, exist_ok=True)

    return {
        "output_dir": str(output_dir),
        "runs_dir": str(runs_dir),
        "scratch_dir": str(scratch_root),
        "logs_dir": str(logs_root),
        "runs": runs,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a tidy papers-to-table output workspace.")
    parser.add_argument("--output-dir", required=True, type=Path, help="User-visible output folder for final CSVs and organized run artifacts.")
    parser.add_argument("--run-id", action="append", default=[], help="Run identifier. Repeat for multiple runs.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable workspace paths.")
    args = parser.parse_args(argv)

    result = prepare_output_workspace(args.output_dir, args.run_id)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    print(f"output_dir: {result['output_dir']}")
    print(f"runs_dir: {result['runs_dir']}")
    print(f"scratch_dir: {result['scratch_dir']}")
    print(f"logs_dir: {result['logs_dir']}")
    for run in result["runs"]:
        print(f"{run['run_id']}:")
        print(f"  run_dir: {run['run_dir']}")
        print(f"  output_table_path: {run['output_table_path']}")
        print(f"  scratch_dir: {run['scratch_dir']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
