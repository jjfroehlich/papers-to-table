from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class ColumnSpec:
    column_name: str
    description: str
    group: str = "ungrouped"
    priority: str | None = None


def load_schema(path: Path, sheet_name: str) -> list[ColumnSpec]:
    dataframe = pd.read_excel(path, sheet_name=sheet_name)
    required = {"column_name", "description"}
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(f"Schema sheet missing required columns: {sorted(missing)}")
    specs: list[ColumnSpec] = []
    for _, row in dataframe.iterrows():
        specs.append(
            ColumnSpec(
                column_name=str(row["column_name"]).strip(),
                description=str(row["description"]).strip(),
                group=str(row.get("group", "ungrouped") or "ungrouped"),
                priority=str(row.get("priority") or ""),
            )
        )
    return specs


def group_columns(specs: list[ColumnSpec]) -> dict[str, list[ColumnSpec]]:
    grouped: dict[str, list[ColumnSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.group or "ungrouped", []).append(spec)
    return grouped
