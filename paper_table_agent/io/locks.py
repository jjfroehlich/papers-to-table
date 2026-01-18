from __future__ import annotations

from typing import Iterable

import pandas as pd

from paper_table_agent.config import DEFAULT_EMPTY_VALUES


def is_empty(value: object, empty_values: Iterable[str] | None = None) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    text = str(value)
    empties = set(empty_values or DEFAULT_EMPTY_VALUES)
    return text in empties


def build_locks(dataframe: pd.DataFrame, empty_values: Iterable[str] | None = None) -> list[dict[str, object]]:
    locks: list[dict[str, object]] = []
    for row_index, row in dataframe.iterrows():
        for column in dataframe.columns:
            value = row[column]
            locked = not is_empty(value, empty_values)
            if locked:
                locks.append(
                    {
                        "row_id": str(row_index),
                        "column": str(column),
                        "locked": 1,
                        "reason": "non-empty",
                    }
                )
    return locks
