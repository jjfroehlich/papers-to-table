from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SearchSpaceError(ValueError):
    pass


@dataclass(frozen=True)
class SearchSpace:
    prompt_bundle_ids: list[str]
    text_model_ids: list[str]
    vision_model_ids: list[str]
    numeric_knobs: dict[str, list[float | int]]


def _numeric_values_from_definition(defn: dict[str, Any]) -> list[float | int]:
    if "values" in defn:
        values = defn["values"]
        if not isinstance(values, list) or not values:
            raise SearchSpaceError("numeric knob values must be a non-empty array")
        if not all(isinstance(v, (int, float)) for v in values):
            raise SearchSpaceError("numeric knob values must be numeric")
        return values

    for key in ["min", "max", "step"]:
        if key not in defn:
            raise SearchSpaceError("numeric knob must provide values or min/max/step")

    min_v = defn["min"]
    max_v = defn["max"]
    step = defn["step"]
    if not all(isinstance(v, (int, float)) for v in [min_v, max_v, step]):
        raise SearchSpaceError("min/max/step must be numeric")
    if step <= 0:
        raise SearchSpaceError("step must be positive")
    if max_v < min_v:
        raise SearchSpaceError("max must be >= min")

    values: list[float | int] = []
    current = min_v
    while current <= max_v + 1e-12:
        values.append(int(current) if float(current).is_integer() else round(float(current), 10))
        current = current + step
    return values


def load_search_space(config: dict[str, Any]) -> SearchSpace:
    raw = config.get("search_space", {})
    if not isinstance(raw, dict):
        raise SearchSpaceError("search_space must be an object")

    prompt_bundle_ids = list(raw.get("prompt_bundle_ids", []))
    text_model_ids = list(raw.get("text_model_ids", []))
    vision_model_ids = list(raw.get("vision_model_ids", []))

    for key, values in [
        ("prompt_bundle_ids", prompt_bundle_ids),
        ("text_model_ids", text_model_ids),
        ("vision_model_ids", vision_model_ids),
    ]:
        if not isinstance(values, list):
            raise SearchSpaceError(f"{key} must be an array")
        if not all(isinstance(v, str) for v in values):
            raise SearchSpaceError(f"{key} must contain only strings")

    numeric_knobs_raw = raw.get("numeric_knobs", {})
    if not isinstance(numeric_knobs_raw, dict):
        raise SearchSpaceError("search_space.numeric_knobs must be an object")

    numeric_knobs: dict[str, list[float | int]] = {}
    for knob_name, knob_def in numeric_knobs_raw.items():
        if not isinstance(knob_name, str) or not knob_name:
            raise SearchSpaceError("numeric knob name must be non-empty string")
        if not isinstance(knob_def, dict):
            raise SearchSpaceError(f"numeric knob definition must be object: {knob_name}")
        numeric_knobs[knob_name] = _numeric_values_from_definition(knob_def)

    return SearchSpace(
        prompt_bundle_ids=prompt_bundle_ids,
        text_model_ids=text_model_ids,
        vision_model_ids=vision_model_ids,
        numeric_knobs=numeric_knobs,
    )
