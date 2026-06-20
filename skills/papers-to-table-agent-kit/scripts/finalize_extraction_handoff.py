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

from review_package_common import (  # noqa: E402
    evidence_path,
    extraction_summary_path,
    filled_table_path,
    load_review_input,
    proposals_path,
    review_input_path,
    validation_report_path,
    read_json,
)


REVIEW_QUESTION = "Do you want to review the results in the browser interface?"
QUALITY_WARNING_MARKERS = (
    "generic proposal-level rationale",
    "reuse the same evidence set",
)


def _path_label(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return str(path)


def _quality_warnings(report: dict[str, Any]) -> list[str]:
    warnings = [str(item) for item in report.get("warnings", []) if item]
    authoring = report.get("authoring")
    if isinstance(authoring, dict):
        warnings.extend(str(item) for item in authoring.get("warnings", []) if item)
    return [warning for warning in warnings if any(marker in warning for marker in QUALITY_WARNING_MARKERS)]


def inspect_run(run_dir: Path, output_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    output_dir = output_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    payload: dict[str, Any] = {}

    try:
        payload = load_review_input(run_dir)
    except Exception as exc:
        errors.append(str(exc))

    filled_path = filled_table_path(run_dir, payload) if payload else run_dir / f"{run_dir.name}_filled.csv"
    required_paths = [
        review_input_path(run_dir),
        proposals_path(run_dir),
        evidence_path(run_dir),
        validation_report_path(run_dir),
        extraction_summary_path(run_dir),
        filled_path,
    ]
    for path in required_paths:
        if not path.exists():
            errors.append(f"Missing required handoff artifact: {_path_label(path, output_dir)}")

    validation_status = "missing"
    report: dict[str, Any] = {}
    if validation_report_path(run_dir).exists():
        try:
            report_value = read_json(validation_report_path(run_dir))
            if isinstance(report_value, dict):
                report = report_value
                validation_status = "ok" if report.get("ok") is True else "failed"
            else:
                errors.append(f"validation_report.json must contain an object: {validation_report_path(run_dir)}")
        except Exception as exc:
            errors.append(f"Cannot read validation_report.json: {exc}")

    if report.get("ok") is not True:
        errors.append(f"Validation report is not ok for run: {run_dir}")
    quality_warnings = _quality_warnings(report)
    if quality_warnings:
        errors.extend(
            f"Unresolved provenance-quality warning in {run_dir.name}: {warning}" for warning in quality_warnings
        )
    warnings.extend(str(item) for item in report.get("warnings", []) if item)

    return {
        "run_dir": str(run_dir),
        "output_dir": str(output_dir),
        "filled_table_path": str(filled_path),
        "validation_status": validation_status,
        "errors": errors,
        "warnings": warnings,
    }


def finalize_handoff(output_dir: Path, run_dirs: list[Path]) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    runs = [inspect_run(run_dir, output_dir) for run_dir in run_dirs]
    errors = [error for run in runs for error in run["errors"]]
    warnings = [warning for run in runs for warning in run["warnings"]]
    return {
        "schema_version": "papers_to_table.handoff_check.v1",
        "ok": not errors,
        "output_dir": str(output_dir),
        "runs": runs,
        "errors": errors,
        "warnings": warnings,
        "review_question": REVIEW_QUESTION,
        "required_final_prompt": REVIEW_QUESTION,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify extraction artifacts before the final papers-to-table handoff.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output workspace containing final filled CSVs.")
    parser.add_argument("--run", required=True, action="append", type=Path, help="Run directory. Repeat for multiple runs.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable handoff check results.")
    args = parser.parse_args(argv)

    result = finalize_handoff(args.output_dir, args.run)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"handoff_ok: {result['ok']}")
        print(f"output_dir: {result['output_dir']}")
        for run in result["runs"]:
            print(f"run_dir: {run['run_dir']}")
            print(f"filled_table_path: {run['filled_table_path']}")
            print(f"validation_status: {run['validation_status']}")
        for error in result["errors"]:
            print(f"ERROR: {error}")
        for warning in result["warnings"]:
            print(f"WARNING: {warning}")
        print(result["required_final_prompt"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
