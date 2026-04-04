from __future__ import annotations

import math
import re
from typing import Any

from paper_eval.contracts import NormalizedNumber

_BOOLEAN_TRUE = {"true", "yes", "present", "positive", "1"}
_BOOLEAN_FALSE = {"false", "no", "absent", "negative", "0"}
_MULTISPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^0-9a-z]+")
_APPROX_PREFIX_RE = re.compile(r"^(~|≈|about\b|approx(?:\.|imately)?\b)")
_NUMBER_RE = r"[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?"
_RANGE_RE = re.compile(
    rf"^\s*(?P<left>{_NUMBER_RE})\s*(?:to|-|–|—)\s*(?P<right>{_NUMBER_RE})\s*$"
)
_NUMERIC_RE = re.compile(rf"^\s*(?P<value>{_NUMBER_RE})\s*$")


def normalize_whitespace(value: str) -> str:
    return _MULTISPACE_RE.sub(" ", value).strip()


def is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return normalize_whitespace(value) == ""
    return False


def normalize_boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    text = normalize_whitespace(str(value)).casefold()
    if text in _BOOLEAN_TRUE:
        return True
    if text in _BOOLEAN_FALSE:
        return False
    return None


def normalize_categorical(
    value: Any,
    *,
    aliases: dict[str, str] | None = None,
    allowed_values: list[str] | None = None,
) -> str | None:
    if is_empty_value(value):
        return None

    def canonicalize(text: str) -> str:
        text = normalize_whitespace(text).casefold()
        text = _PUNCT_RE.sub(" ", text)
        return normalize_whitespace(text)

    normalized = canonicalize(str(value))
    alias_map = {canonicalize(key): canonicalize(mapped) for key, mapped in (aliases or {}).items()}
    normalized = alias_map.get(normalized, normalized)

    if allowed_values:
        allowed_map = {canonicalize(item): canonicalize(item) for item in allowed_values}
        normalized = allowed_map.get(normalized, normalized)

    return normalized


def normalize_text_for_match(value: Any) -> str | None:
    if is_empty_value(value):
        return None
    text = normalize_whitespace(str(value)).casefold()
    text = _PUNCT_RE.sub(" ", text)
    return normalize_whitespace(text)


def text_overlap_diagnostics(gold_value: Any, proposed_value: Any) -> dict[str, Any]:
    normalized_gold = normalize_text_for_match(gold_value)
    normalized_proposed = normalize_text_for_match(proposed_value)
    gold_tokens = normalized_gold.split() if normalized_gold else []
    proposed_tokens = normalized_proposed.split() if normalized_proposed else []
    gold_token_set = set(gold_tokens)
    proposed_token_set = set(proposed_tokens)
    overlap_count = len(gold_token_set & proposed_token_set)
    union_count = len(gold_token_set | proposed_token_set)
    return {
        "normalized_exact_match": normalized_gold is not None and normalized_gold == normalized_proposed,
        "gold_token_count": len(gold_tokens),
        "proposed_token_count": len(proposed_tokens),
        "token_overlap_count": overlap_count,
        "token_overlap_ratio": None if union_count == 0 else overlap_count / union_count,
    }


def _parse_float(text: str) -> float:
    return float(text.replace(",", ""))


def normalize_numeric(value: Any) -> NormalizedNumber | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric_value = float(value)
        return NormalizedNumber(
            kind="scalar",
            lower=numeric_value,
            upper=numeric_value,
            approx=False,
            raw_text=str(value),
        )

    text = normalize_whitespace(str(value))
    if text == "":
        return None

    approx = False
    stripped = text
    approx_match = _APPROX_PREFIX_RE.match(stripped.casefold())
    if approx_match:
        approx = True
        stripped = stripped[approx_match.end() :].strip()

    range_match = _RANGE_RE.match(stripped)
    if range_match:
        left = _parse_float(range_match.group("left"))
        right = _parse_float(range_match.group("right"))
        lower, upper = sorted((left, right))
        return NormalizedNumber(
            kind="interval",
            lower=lower,
            upper=upper,
            approx=approx,
            raw_text=text,
        )

    numeric_match = _NUMERIC_RE.match(stripped)
    if numeric_match:
        numeric_value = _parse_float(numeric_match.group("value"))
        return NormalizedNumber(
            kind="scalar",
            lower=numeric_value,
            upper=numeric_value,
            approx=approx,
            raw_text=text,
        )

    return None
