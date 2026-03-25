from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .config import RunConfig
from .ids import make_cell_id
from .schemas import InputSummary

REQUIRED_METADATA_COLUMNS = ["Title", "Authors", "Publication Year"]


class IngestError(ValueError):
    pass


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_xlsx(path: Path, sheet_name: str | None = None) -> list[dict[str, Any]]:
    workbook = load_workbook(path, data_only=True)
    sheet = workbook[sheet_name] if sheet_name else workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(h) if h is not None else "" for h in rows[0]]
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        records.append({headers[i]: row[i] for i in range(len(headers))})
    return records


def load_table(path: str) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix.lower() == ".csv":
        return _read_csv(source)
    if source.suffix.lower() in {".xlsx", ".xlsm"}:
        return _read_xlsx(source)
    raise IngestError(f"Unsupported table format: {source.suffix}")


def load_schema(table_path: str, schema_path: str | None) -> list[dict[str, Any]]:
    if schema_path:
        schema_file = Path(schema_path)
        if schema_file.suffix.lower() == ".csv":
            return _read_csv(schema_file)
        if schema_file.suffix.lower() in {".xlsx", ".xlsm"}:
            return _read_xlsx(schema_file)
        raise IngestError(f"Unsupported schema format: {schema_file.suffix}")

    table = Path(table_path)
    if table.suffix.lower() in {".xlsx", ".xlsm"}:
        return _read_xlsx(table, sheet_name="schema")

    raise IngestError("schema_path is required when table is not XLSX with a 'schema' sheet")


def validate_schema(schema_rows: list[dict[str, Any]]) -> None:
    if not schema_rows:
        raise IngestError("Schema is empty")
    required = {"column_name", "description"}
    for idx, row in enumerate(schema_rows, start=1):
        missing = [key for key in required if not str(row.get(key, "")).strip()]
        if missing:
            raise IngestError(f"Schema row {idx} is missing required fields: {', '.join(missing)}")


def validate_required_metadata_columns(table_rows: list[dict[str, Any]]) -> None:
    if not table_rows:
        raise IngestError("Input table has no rows")
    columns = set(table_rows[0].keys())
    missing = [column for column in REQUIRED_METADATA_COLUMNS if column not in columns]
    if missing:
        raise IngestError(
            f"Input table is missing required metadata columns: {', '.join(missing)}"
        )


def classify_cell_eligibility(
    table_rows: list[dict[str, Any]],
    schema_rows: list[dict[str, Any]],
    verify_mode: bool,
    placeholders: list[str],
) -> tuple[int, int, int, list[dict[str, str]]]:
    target_columns = [str(row["column_name"]) for row in schema_rows]
    missing_eligible = 0
    filled_eligible = 0
    ineligible = 0
    details: list[dict[str, str]] = []

    placeholder_set = {p for p in placeholders}
    for row_idx, row in enumerate(table_rows):
        row_id = str(row.get("Title") or f"row_{row_idx + 1}")
        for column in target_columns:
            raw = row.get(column)
            text = "" if raw is None else str(raw)
            normalized = text if text not in placeholder_set else ""
            empty = normalized.strip() == ""
            if empty:
                missing_eligible += 1
                status = "eligible_missing"
            elif verify_mode:
                filled_eligible += 1
                status = "eligible_filled_verify_mode"
            else:
                ineligible += 1
                status = "ineligible_already_filled"
            details.append({"cell_id": make_cell_id(row_id, column), "status": status})

    return missing_eligible, filled_eligible, ineligible, details


def build_input_summary(config: RunConfig) -> tuple[InputSummary, dict[str, Any]]:
    table_rows = load_table(config.paths.table_path)
    schema_rows = load_schema(config.paths.table_path, config.paths.schema_path)

    validate_schema(schema_rows)
    validate_required_metadata_columns(table_rows)

    missing_eligible, filled_eligible, ineligible, cell_details = classify_cell_eligibility(
        table_rows=table_rows,
        schema_rows=schema_rows,
        verify_mode=config.verify_mode,
        placeholders=config.placeholders_treated_as_empty,
    )

    targets = [str(row["column_name"]) for row in schema_rows]
    summary = InputSummary(
        table_path=config.paths.table_path,
        schema_path=config.paths.schema_path,
        pdf_dir=config.paths.pdf_dir,
        output_dir=config.paths.output_dir,
        verify_mode=config.verify_mode,
        target_columns=targets,
        row_count=len(table_rows),
        eligible_missing_cells=missing_eligible,
        eligible_filled_cells=filled_eligible,
        ineligible_cells=ineligible,
        placeholders_treated_as_empty=config.placeholders_treated_as_empty,
    )

    return summary, {
        "table_rows": table_rows,
        "schema_rows": schema_rows,
        "cell_eligibility": cell_details,
    }
