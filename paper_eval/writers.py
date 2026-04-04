from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable

from paper_eval.contracts import RunSummary, ScoredCell


def write_scored_cells(path: Path, scored_cells: Iterable[ScoredCell]) -> None:
    scored_cells = list(scored_cells)
    jsonl_path = path / "scored_cells.jsonl"
    csv_path = path / "scored_cells.csv"
    _write_jsonl(jsonl_path, scored_cells)
    _write_csv(csv_path, (_flatten_scored_cell(cell) for cell in scored_cells))


def write_run_summary(path: Path, summary: RunSummary) -> None:
    summary_json_path = path / "run_summary.json"
    summary_csv_path = path / "run_summary.csv"
    summary_payload = {
        "run_id": summary.run_id,
        "run_dir": str(summary.run_dir),
        "gold_source": str(summary.gold_source),
        "gold_sheet": summary.gold_sheet,
        "metrics": summary.metrics,
        "metadata": summary.metadata,
        "contract_warnings": summary.contract_warnings,
        "join_diagnostics": summary.join_diagnostics,
    }
    summary_json_path.write_text(json.dumps(summary_payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_csv(summary_csv_path, [_flatten_summary(summary)])


def _write_jsonl(path: Path, rows: Iterable[Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(_to_serializable(row), sort_keys=True))
            handle.write("\n")


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(value) for key, value in row.items()})


def _flatten_scored_cell(cell: ScoredCell) -> dict[str, Any]:
    payload = _to_serializable(cell)
    payload["diagnostic_flags"] = "|".join(payload["diagnostic_flags"])
    payload["diagnostics"] = json.dumps(payload["diagnostics"], sort_keys=True)
    if isinstance(payload.get("normalized_gold"), (dict, list)):
        payload["normalized_gold"] = json.dumps(payload["normalized_gold"], sort_keys=True)
    if isinstance(payload.get("normalized_proposed"), (dict, list)):
        payload["normalized_proposed"] = json.dumps(payload["normalized_proposed"], sort_keys=True)
    return payload


def _flatten_summary(summary: RunSummary) -> dict[str, Any]:
    row = {
        "run_id": summary.run_id,
        "run_dir": str(summary.run_dir),
        "gold_source": str(summary.gold_source),
        "gold_sheet": summary.gold_sheet,
        "contract_warning_count": len(summary.contract_warnings),
        "join_diagnostic_count": len(summary.join_diagnostics),
        "contract_warnings": json.dumps(summary.contract_warnings),
        "join_diagnostics": json.dumps(summary.join_diagnostics),
    }
    row.update(summary.metadata)
    row.update(summary.metrics)
    return row


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _to_serializable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _to_serializable(item) for key, item in asdict(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _to_serializable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_serializable(item) for item in value]
    return value
