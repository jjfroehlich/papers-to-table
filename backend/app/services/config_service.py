from __future__ import annotations

from pathlib import Path
import json
from typing import Any

import pandas as pd

from ..models import RunConfig

REQUIRED_META_COLUMNS = {"Title", "Authors", "Publication Year"}
REQUIRED_SCHEMA_COLUMNS = {"column_name", "description"}


class ConfigValidationError(ValueError):
    pass


def load_and_resolve_config(config_path: Path) -> RunConfig:
    if not config_path.exists():
        raise ConfigValidationError(f"Config path does not exist: {config_path}")
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    config = RunConfig.model_validate(payload)
    return config


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() in {".xlsx", ".xlsm", ".xls"}:
        return pd.read_excel(path)
    raise ConfigValidationError(f"Unsupported table format: {path}")


def _read_schema(path: Path | None) -> pd.DataFrame:
    if path is None:
        raise ConfigValidationError("schema_path is required in this Batch 1 implementation")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    return pd.read_excel(path)


def classify_cells(table_df: pd.DataFrame, target_columns: list[str], verify_mode: bool, placeholders: list[str]) -> dict[str, int]:
    placeholder_set = {p.strip().lower() for p in placeholders}
    missing = 0
    filled = 0
    skipped = 0
    for _, row in table_df.iterrows():
        for column in target_columns:
            if column not in row:
                skipped += 1
                continue
            value = row[column]
            is_empty = pd.isna(value) or str(value).strip() == ""
            if not is_empty and str(value).strip().lower() in placeholder_set:
                is_empty = True
            if is_empty:
                missing += 1
            elif verify_mode:
                filled += 1
    return {"missing": missing, "filled": filled, "skipped": skipped}


def validate_inputs(config: RunConfig) -> dict[str, Any]:
    table_path = Path(config.paths.table_path)
    schema_path = Path(config.paths.schema_path) if config.paths.schema_path else None
    pdf_dir = Path(config.paths.pdf_dir)

    for path in [table_path, pdf_dir] + ([schema_path] if schema_path else []):
        if path is None:
            continue
        if not path.exists():
            raise ConfigValidationError(f"Configured path does not exist: {path}")

    table_df = _read_table(table_path)
    if not REQUIRED_META_COLUMNS.issubset(table_df.columns):
        raise ConfigValidationError(
            f"Input table must include metadata columns: {sorted(REQUIRED_META_COLUMNS)}"
        )

    schema_df = _read_schema(schema_path)
    if not REQUIRED_SCHEMA_COLUMNS.issubset(schema_df.columns):
        raise ConfigValidationError(
            f"Schema must include columns: {sorted(REQUIRED_SCHEMA_COLUMNS)}"
        )

    target_columns = [str(c) for c in schema_df["column_name"].dropna().tolist()]
    eligibility = classify_cells(
        table_df=table_df,
        target_columns=target_columns,
        verify_mode=config.review.verify_mode,
        placeholders=config.review.placeholder_values,
    )
    pdf_count = len(list(pdf_dir.glob("*.pdf")))

    return {
        "table_path": str(table_path),
        "schema_path": str(schema_path) if schema_path else None,
        "pdf_dir": str(pdf_dir),
        "pdf_count": pdf_count,
        "row_count": int(len(table_df)),
        "target_column_count": int(len(target_columns)),
        "verify_mode": config.review.verify_mode,
        "eligible_missing_cells": eligibility["missing"],
        "eligible_filled_cells": eligibility["filled"],
    }
