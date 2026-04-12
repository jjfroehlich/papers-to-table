from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from paper_eval.contracts import ColumnSchema, EvaluatorSchema, NumericTolerance
from paper_eval.errors import ContractError


DEFAULT_EXCLUDED_SCORE_COLUMNS = ["Title", "Authors", "Publication Year"]


def _normalize_optional_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return list(value)


def _normalize_optional_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    return dict(value)


def _parse_numeric_tolerance(payload: dict[str, Any] | None) -> NumericTolerance | None:
    if not payload:
        return None
    if not isinstance(payload, dict):
        raise ContractError("Numeric tolerance configuration must be an object when provided.")
    return NumericTolerance(
        abs_tol=float(payload.get("abs_tol", payload.get("abs", 0.0))),
        rel_tol=float(payload.get("rel_tol", payload.get("rel", 0.0))),
    )


def load_schema(path: Path | None) -> EvaluatorSchema:
    if path is None:
        return EvaluatorSchema()

    if not path.exists():
        raise ContractError(f"Schema file does not exist: {path}")
    if not path.is_file():
        raise ContractError(f"Schema path is not a file: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except JSONDecodeError as exc:
        raise ContractError(f"Invalid JSON in schema file {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ContractError("Schema file must contain a JSON object at the top level.")
    columns_payload = payload.get("columns", {})
    if not isinstance(columns_payload, (dict, list)):
        raise ContractError("Schema 'columns' must be either an object keyed by column name or a list of column objects.")
    columns: dict[str, ColumnSchema] = {}
    if isinstance(columns_payload, list):
        iterable = []
        for index, item in enumerate(columns_payload, start=1):
            if not isinstance(item, dict):
                raise ContractError(f"Schema column entry #{index} must be an object.")
            name = item.get("name")
            if not isinstance(name, str) or not name.strip():
                raise ContractError(f"Schema column entry #{index} is missing required field 'name'.")
            iterable.append((name, item))
    else:
        iterable = columns_payload.items()

    for column_name, item in iterable:
        if not isinstance(item, dict):
            raise ContractError(f"Schema column '{column_name}' must be an object.")
        columns[column_name] = ColumnSchema(
            name=column_name,
            field_type=item.get("field_type"),
            description=item.get("description"),
            allowed_values=_normalize_optional_list(item.get("allowed_values")),
            aliases=_normalize_optional_dict(item.get("aliases")),
            scoring_policy=item.get("scoring_policy"),
            numeric_tolerance=_parse_numeric_tolerance(item.get("numeric_tolerance")),
        )

    global_tolerance = _parse_numeric_tolerance(
        payload.get("global_numeric_tolerance") or payload.get("numeric_tolerance")
    ) or NumericTolerance()

    scored_columns = _normalize_optional_list(payload.get("scored_columns") or payload.get("target_columns"))
    excluded_columns = _normalize_optional_list(payload.get("excluded_columns")) or list(DEFAULT_EXCLUDED_SCORE_COLUMNS)

    return EvaluatorSchema(
        columns=columns,
        global_numeric_tolerance=global_tolerance,
        scored_columns=[str(value) for value in scored_columns if str(value).strip()],
        excluded_columns=[str(value) for value in excluded_columns if str(value).strip()],
    )
