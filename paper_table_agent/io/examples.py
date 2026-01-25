from __future__ import annotations

from typing import Any

import pandas as pd
from paper_table_agent.text.normalization import normalize_str_for_prompt


def select_examples(
    dataframe: pd.DataFrame,
    columns: list[str],
    max_per_column: int,
) -> dict[str, list[dict[str, Any]]]:
    examples: dict[str, list[dict[str, Any]]] = {col: [] for col in columns}
    for col in columns:
        if col not in dataframe.columns:
            continue
        indices = []
        for row_index, value in dataframe[col].items():
            if normalize_str_for_prompt(value):
                indices.append(row_index)
        if not indices:
            continue
        if len(indices) <= max_per_column:
            selected = indices
        else:
            step = (len(indices) - 1) / max(1, max_per_column - 1)
            selected = sorted({indices[int(round(i * step))] for i in range(max_per_column)})
        for row_index in selected:
            value = normalize_str_for_prompt(dataframe.at[row_index, col])
            if not value:
                continue
            examples[col].append({"row_index": int(row_index), "value": value})
    return examples
