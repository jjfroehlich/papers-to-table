from __future__ import annotations

import csv
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterable

from paper_eval.aggregate import comparison_row_from_summary
from paper_eval.errors import ContractError
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
    _write_csv(summary_csv_path, [comparison_row_from_summary(summary)])


def write_comparison_artifacts(path: Path, summaries: Iterable[RunSummary]) -> list[dict[str, Any]]:
    rows = [comparison_row_from_summary(summary) for summary in summaries]
    csv_path = path / "runs_comparison.csv"
    xlsx_path = path / "runs_comparison.xlsx"
    parquet_path = path / "runs_comparison.parquet"
    _write_csv(csv_path, rows)
    _write_xlsx(xlsx_path, rows)
    _write_parquet(parquet_path, rows)
    return rows


def write_comparison_artifacts_from_rows(path: Path, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = list(rows)
    csv_path = path / "runs_comparison.csv"
    xlsx_path = path / "runs_comparison.xlsx"
    parquet_path = path / "runs_comparison.parquet"
    _write_csv(csv_path, rows)
    _write_xlsx(xlsx_path, rows)
    _write_parquet(parquet_path, rows)
    return rows


def load_summary_rows_from_directory(path: Path) -> list[dict[str, Any]]:
    summary_files: list[Path] = []
    if path.is_file():
        summary_files = [path]
    else:
        summary_files = sorted(path.glob("*/run_summary.json"))
    rows: list[dict[str, Any]] = []
    for summary_path in summary_files:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        row = {
            "run_id": payload["run_id"],
            "run_dir": payload["run_dir"],
            "gold_source": payload["gold_source"],
            "gold_sheet": payload.get("gold_sheet"),
            "contract_warning_count": len(payload.get("contract_warnings", [])),
            "join_diagnostic_count": len(payload.get("join_diagnostics", [])),
            "contract_warnings": json.dumps(payload.get("contract_warnings", [])),
            "join_diagnostics": json.dumps(payload.get("join_diagnostics", [])),
        }
        row.update(payload.get("metadata", {}))
        row.update(payload.get("metrics", {}))
        rows.append(row)
    if not rows:
        raise ContractError(f"No run_summary.json files were found under {path}.")
    return rows


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


def _write_xlsx(path: Path, rows: list[dict[str, Any]]) -> None:
    try:
        from openpyxl import Workbook
    except ModuleNotFoundError as exc:
        raise ContractError("XLSX outputs require openpyxl; install requirements.txt before writing XLSX artifacts.") from exc

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "runs_comparison"
    fieldnames = _fieldnames(rows)
    worksheet.append(fieldnames)
    for row in rows:
        worksheet.append([_csv_value(row.get(field)) for field in fieldnames])
    workbook.save(path)


def _write_parquet(path: Path, rows: list[dict[str, Any]]) -> None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise ContractError("Parquet outputs require pyarrow; install the evaluator dependencies first.") from exc

    fieldnames = _fieldnames(rows)
    normalized_rows = [{field: _csv_value(row.get(field)) for field in fieldnames} for row in rows]
    table = pa.Table.from_pylist(normalized_rows)
    pq.write_table(table, path)


def _flatten_scored_cell(cell: ScoredCell) -> dict[str, Any]:
    payload = _to_serializable(cell)
    payload["diagnostic_flags"] = "|".join(payload["diagnostic_flags"])
    payload["diagnostics"] = json.dumps(payload["diagnostics"], sort_keys=True)
    if isinstance(payload.get("normalized_gold"), (dict, list)):
        payload["normalized_gold"] = json.dumps(payload["normalized_gold"], sort_keys=True)
    if isinstance(payload.get("normalized_proposed"), (dict, list)):
        payload["normalized_proposed"] = json.dumps(payload["normalized_proposed"], sort_keys=True)
    return payload


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    return fieldnames


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
