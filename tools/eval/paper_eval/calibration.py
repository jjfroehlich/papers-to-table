from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Iterable

from paper_eval.contracts import STRUCTURED_FIELD_TYPES
from paper_eval.errors import ContractError


def build_structured_calibration_report(inputs: Iterable[Path], *, example_limit: int = 5) -> dict[str, Any]:
    scored_cell_paths = _discover_scored_cell_paths(inputs)
    structured_scored_count = 0
    failures: list[dict[str, Any]] = []
    for path in scored_cell_paths:
        for row in _load_jsonl(path):
            if row.get("record_kind") != "gold_cell":
                continue
            if row.get("field_type") not in STRUCTURED_FIELD_TYPES:
                continue
            if row.get("was_scored") is not True:
                continue
            structured_scored_count += 1
            if row.get("is_correct") is False:
                failures.append({**row, "_scored_cells_path": str(path)})

    by_field_type = Counter(str(row.get("field_type") or "unknown") for row in failures)
    by_kind = Counter(_failure_kind(row) for row in failures)
    by_column: dict[tuple[str, str], dict[str, Any]] = {}
    by_kind_rows: dict[str, dict[str, Any]] = {}
    examples_by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in failures:
        field_type = str(row.get("field_type") or "unknown")
        column_name = str(row.get("column_name") or "<missing>")
        kind = _failure_kind(row)
        eligible = bool(row.get("adjudication_eligible"))

        column_key = (column_name, field_type)
        column_row = by_column.setdefault(
            column_key,
            {
                "column_name": column_name,
                "field_type": field_type,
                "structured_deterministic_failure_count": 0,
                "structured_adjudication_eligible_count": 0,
                "failure_kind_counts": Counter(),
            },
        )
        column_row["structured_deterministic_failure_count"] += 1
        column_row["failure_kind_counts"][kind] += 1
        if eligible:
            column_row["structured_adjudication_eligible_count"] += 1

        kind_row = by_kind_rows.setdefault(
            kind,
            {
                "deterministic_failure_kind": kind,
                "structured_deterministic_failure_count": 0,
                "structured_adjudication_eligible_count": 0,
                "field_type_counts": Counter(),
            },
        )
        kind_row["structured_deterministic_failure_count"] += 1
        kind_row["field_type_counts"][field_type] += 1
        if eligible:
            kind_row["structured_adjudication_eligible_count"] += 1

        if len(examples_by_kind[kind]) < example_limit:
            examples_by_kind[kind].append(_example_row(row, kind))

    by_column_rows = sorted(
        (_finalize_counter_fields(row, ["failure_kind_counts"]) for row in by_column.values()),
        key=lambda item: (
            -int(item["structured_adjudication_eligible_count"]),
            -int(item["structured_deterministic_failure_count"]),
            str(item["column_name"]),
        ),
    )
    by_kind_summary_rows = sorted(
        (_finalize_counter_fields(row, ["field_type_counts"]) for row in by_kind_rows.values()),
        key=lambda item: (-int(item["structured_deterministic_failure_count"]), str(item["deterministic_failure_kind"])),
    )
    eligible_count = sum(1 for row in failures if row.get("adjudication_eligible") is True)
    return {
        "scored_cells_paths": [str(path) for path in scored_cell_paths],
        "scored_cells_path_count": len(scored_cell_paths),
        "structured_scored_cell_count": structured_scored_count,
        "structured_deterministic_failure_count": len(failures),
        "structured_adjudication_eligible_count": eligible_count,
        "structured_adjudication_eligible_failure_rate": _ratio(eligible_count, len(failures)),
        "structured_adjudication_eligible_rate": _ratio(eligible_count, len(failures)),
        "failure_counts_by_field_type": dict(sorted(by_field_type.items())),
        "failure_counts_by_kind": dict(sorted(by_kind.items())),
        "top_columns_by_eligible_failure_count": by_column_rows,
        "failure_kinds": by_kind_summary_rows,
        "examples_by_kind": dict(sorted(examples_by_kind.items())),
    }


def write_structured_calibration_report(output_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "structured_calibration_summary.json"
    columns_path = output_dir / "structured_calibration_by_column.csv"
    kinds_path = output_dir / "structured_calibration_by_kind.csv"
    examples_path = output_dir / "structured_calibration_examples.csv"

    summary_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(
        columns_path,
        report.get("top_columns_by_eligible_failure_count", []),
        fieldnames=[
            "column_name",
            "field_type",
            "structured_deterministic_failure_count",
            "structured_adjudication_eligible_count",
            "failure_kind_counts",
        ],
    )
    _write_csv(
        kinds_path,
        report.get("failure_kinds", []),
        fieldnames=[
            "deterministic_failure_kind",
            "structured_deterministic_failure_count",
            "structured_adjudication_eligible_count",
            "field_type_counts",
        ],
    )
    _write_csv(
        examples_path,
        [
            example
            for examples in (report.get("examples_by_kind", {}) or {}).values()
            for example in examples
        ],
        fieldnames=[
            "deterministic_failure_kind",
            "adjudication_eligible",
            "field_type",
            "column_name",
            "row_id",
            "gold_value",
            "proposed_value",
            "scored_cells_path",
        ],
    )
    return {
        "summary_json": str(summary_path.resolve()),
        "by_column_csv": str(columns_path.resolve()),
        "by_kind_csv": str(kinds_path.resolve()),
        "examples_csv": str(examples_path.resolve()),
    }


def _discover_scored_cell_paths(inputs: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    paths: list[Path] = []
    for raw_path in inputs:
        path = raw_path.resolve()
        if not path.exists():
            raise ContractError(f"Calibration input does not exist: {path}")
        candidates: list[Path]
        if path.is_file():
            candidates = [path]
        elif path.is_dir():
            candidates = [path / "scored_cells.jsonl", *sorted(path.glob("**/scored_cells.jsonl"))]
        else:
            raise ContractError(f"Calibration input is neither a file nor a directory: {path}")
        for candidate in candidates:
            if not candidate.is_file():
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                paths.append(resolved)
    if not paths:
        raise ContractError("No scored_cells.jsonl files were found in calibration inputs.")
    return sorted(paths)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except JSONDecodeError as exc:
            raise ContractError(f"Invalid JSON in {path} line {line_number}: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise ContractError(f"Expected object records in {path} line {line_number}.")
        rows.append(row)
    return rows


def _failure_kind(row: dict[str, Any]) -> str:
    return str(row.get("deterministic_failure_kind") or "unclassified_structured_failure")


def _example_row(row: dict[str, Any], kind: str) -> dict[str, Any]:
    return {
        "deterministic_failure_kind": kind,
        "adjudication_eligible": bool(row.get("adjudication_eligible")),
        "field_type": row.get("field_type"),
        "column_name": row.get("column_name"),
        "row_id": row.get("row_id"),
        "gold_value": row.get("gold_value"),
        "proposed_value": row.get("proposed_value"),
        "scored_cells_path": row.get("_scored_cells_path"),
    }


def _finalize_counter_fields(row: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    finalized = dict(row)
    for key in keys:
        value = finalized.get(key)
        if isinstance(value, Counter):
            finalized[key] = dict(sorted(value.items()))
    return finalized


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], *, fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    ordered_fieldnames = list(fieldnames or [])
    for row in rows:
        for key in row:
            if key not in ordered_fieldnames:
                ordered_fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ordered_fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator
