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
        specs.append(
            ColumnSpec(
                column_name=column_name,
                description=str(row["description"]).strip(),
                group=str(row.get("group", "ungrouped") or "ungrouped"),
                priority=str(row.get("priority") or ""),
                column_key=normalize_key(column_name),
            )
        )
    return specs


def group_columns(specs: list[ColumnSpec]) -> dict[str, list[ColumnSpec]]:
    grouped: dict[str, list[ColumnSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.group or "ungrouped", []).append(spec)
    return grouped
