from __future__ import annotations

from typing import Any

import pandas as pd

from paper_table_agent.config import DEFAULT_EMPTY_VALUES


def select_examples(
    dataframe: pd.DataFrame,
    columns: list[str],
    max_per_column: int,
) -> dict[str, list[dict[str, Any]]]:
    examples: dict[str, list[dict[str, Any]]] = {col: [] for col in columns}
    for col in columns:
        if col not in dataframe.columns:
            continue
        non_empty = dataframe[~dataframe[col].isin(DEFAULT_EMPTY_VALUES)]
        if non_empty.empty:
            continue
        indices = list(non_empty.index)
        if len(indices) <= max_per_column:
            selected = indices
        else:
            step = (len(indices) - 1) / max(1, max_per_column - 1)
            selected = sorted({indices[int(round(i * step))] for i in range(max_per_column)})
        for row_index in selected:
            row = non_empty.loc[row_index]
            examples[col].append(
                {
                    "row_index": int(row_index),
                    "value": str(row[col]),
                }
            )
    return examples
