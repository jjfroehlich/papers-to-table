from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from paper_table_agent.text.normalization import normalize_key

@dataclass
class ColumnSpec:
    column_name: str
    description: str
    group: str = "ungrouped"
    priority: str | None = None
    column_key: str = ""
    source: str | None = None
    in_paper: bool | None = None
    metadata_only: bool | None = None


def _coerce_bool(value: object) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "1", "y"}:
        return True
    if text in {"false", "no", "0", "n"}:
        return False
    return None


def load_schema(path: Path, sheet_name: str) -> list[ColumnSpec]:
    if path.suffix.lower() == ".csv":
        dataframe = pd.read_csv(path)
    else:
        dataframe = pd.read_excel(path, sheet_name=sheet_name)
    required = {"column_name", "description"}
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(f"Schema sheet missing required columns: {sorted(missing)}")
    specs: list[ColumnSpec] = []
    for _, row in dataframe.iterrows():
        column_name = str(row["column_name"]).strip()
        source = str(row.get("source") or "").strip() or None
        specs.append(
            ColumnSpec(
                column_name=column_name,
                description=str(row["description"]).strip(),
                group=str(row.get("group", "ungrouped") or "ungrouped"),
                priority=str(row.get("priority") or ""),
                column_key=normalize_key(column_name),
                source=source,
                in_paper=_coerce_bool(row.get("in_paper")) if "in_paper" in dataframe.columns else None,
                metadata_only=_coerce_bool(row.get("metadata_only"))
                if "metadata_only" in dataframe.columns
                else None,
            )
        )
    return specs


def group_columns(specs: list[ColumnSpec]) -> dict[str, list[ColumnSpec]]:
    grouped: dict[str, list[ColumnSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.group or "ungrouped", []).append(spec)
    return grouped
