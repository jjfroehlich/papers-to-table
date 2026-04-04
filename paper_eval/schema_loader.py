from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from paper_eval.contracts import ColumnSchema, EvaluatorSchema, NumericTolerance


def _parse_numeric_tolerance(payload: dict[str, Any] | None) -> NumericTolerance | None:
    if not payload:
        return None
    return NumericTolerance(
        abs_tol=float(payload.get("abs_tol", payload.get("abs", 0.0))),
        rel_tol=float(payload.get("rel_tol", payload.get("rel", 0.0))),
    )


def load_schema(path: Path | None) -> EvaluatorSchema:
    if path is None:
        return EvaluatorSchema()

    payload = json.loads(path.read_text(encoding="utf-8"))
    columns_payload = payload.get("columns", {})
    columns: dict[str, ColumnSchema] = {}
    if isinstance(columns_payload, list):
        iterable = ((item["name"], item) for item in columns_payload)
    else:
        iterable = columns_payload.items()

    for column_name, item in iterable:
        columns[column_name] = ColumnSchema(
            name=column_name,
            field_type=item.get("field_type"),
            allowed_values=list(item.get("allowed_values", [])),
            aliases=dict(item.get("aliases", {})),
            scoring_policy=item.get("scoring_policy"),
            numeric_tolerance=_parse_numeric_tolerance(item.get("numeric_tolerance")),
        )

    global_tolerance = _parse_numeric_tolerance(
        payload.get("global_numeric_tolerance") or payload.get("numeric_tolerance")
    ) or NumericTolerance()

    return EvaluatorSchema(columns=columns, global_numeric_tolerance=global_tolerance)
