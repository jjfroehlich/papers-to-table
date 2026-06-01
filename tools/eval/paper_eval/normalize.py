from __future__ import annotations

import math
import re
from typing import Any

from paper_eval.contracts import NormalizedNumber

_BOOLEAN_TRUE = {"true", "yes", "present", "positive", "1"}
_BOOLEAN_FALSE = {"false", "no", "absent", "negative", "0"}
_CLEAR_BOOLEAN_TRUE = {"true", "yes", "present", "positive"}
_CLEAR_BOOLEAN_FALSE = {"false", "no", "absent", "negative"}
_MULTISPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^0-9a-z]+")
_APPROX_PREFIX_RE = re.compile(r"^(~|≈|about\b|approx(?:\.|imately)?\b)")
_NUMBER_RE = r"[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?"
_RANGE_RE = re.compile(
    rf"^\s*(?P<left>{_NUMBER_RE})\s*(?:to|-|–|—)\s*(?P<right>{_NUMBER_RE})\s*$"
)
_NUMERIC_RE = re.compile(rf"^\s*(?P<value>{_NUMBER_RE})\s*$")
_NUMERIC_TOKEN_RE = re.compile(_NUMBER_RE)
_INEQUALITY_RE = re.compile(r"(<=|>=|<|>|≤|≥)")
_PLUS_MINUS_RE = re.compile(r"(±|\+/-)")
_RANGE_LIKE_RE = re.compile(rf"{_NUMBER_RE}\s*(?:to|-|–|—)\s*{_NUMBER_RE}")
_BOOLEAN_CUE_RE = re.compile(
    r"(^\s*[+-]\s*$|\+/-|"
    r"\b(?:y|n|yes|no|true|false|present|absent|positive|negative|"
    r"detected|undetected|reported|unreported|available|unavailable)\b)",
    re.IGNORECASE,
)


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


def is_clear_boolean_value(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if value is None or isinstance(value, (int, float)):
        return False
    text = normalize_whitespace(str(value)).casefold()
    return text in _CLEAR_BOOLEAN_TRUE or text in _CLEAR_BOOLEAN_FALSE


def boolean_format_diagnostics(value: Any) -> dict[str, Any]:
    text = "" if value is None else normalize_whitespace(str(value))
    normalized = normalize_boolean(value)
    return {
        "parse_success": normalized is not None,
        "normalized_value": normalized,
        "clear_boolean_vocabulary": is_clear_boolean_value(value),
        "boolean_like_cue": bool(text and _BOOLEAN_CUE_RE.search(text)),
    }


def canonicalize_category_text(value: Any) -> str | None:
    if is_empty_value(value):
        return None
    text = normalize_whitespace(str(value)).casefold()
    text = _PUNCT_RE.sub(" ", text)
    return normalize_whitespace(text)


def normalize_categorical(
    value: Any,
    *,
    aliases: dict[str, str] | None = None,
    allowed_values: list[str] | None = None,
) -> str | None:
    if is_empty_value(value):
        return None

    def canonicalize(text: str) -> str:
        return canonicalize_category_text(text) or ""

    normalized = canonicalize(str(value))
    alias_map = {canonicalize(key): canonicalize(mapped) for key, mapped in (aliases or {}).items()}
    normalized = alias_map.get(normalized, normalized)

    if allowed_values:
        allowed_map = {canonicalize(item): canonicalize(item) for item in allowed_values}
        normalized = allowed_map.get(normalized, normalized)

    return normalized


def categorical_format_diagnostics(
    value: Any,
    *,
    aliases: dict[str, str] | None = None,
    allowed_values: list[str] | None = None,
) -> dict[str, Any]:
    raw_canonical = canonicalize_category_text(value)
    alias_map = {
        (canonicalize_category_text(key) or ""): (canonicalize_category_text(mapped) or "")
        for key, mapped in (aliases or {}).items()
    }
    alias_target = alias_map.get(raw_canonical or "")
    normalized = normalize_categorical(value, aliases=aliases, allowed_values=allowed_values)
    allowed_canonical = {canonicalize_category_text(item) for item in (allowed_values or [])}
    text = "" if value is None else normalize_whitespace(str(value))
    token_count = len((raw_canonical or "").split())
    return {
        "raw_canonical": raw_canonical,
        "normalized_value": normalized,
        "alias_hit": alias_target is not None,
        "alias_target": alias_target,
        "allowed_value_match": normalized in allowed_canonical if allowed_values else None,
        "list_like": bool(re.search(r"[,;/|]|\band\b", text, re.IGNORECASE)) and token_count > 1,
    }


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


def numeric_format_diagnostics(value: Any) -> dict[str, Any]:
    text = "" if value is None else normalize_whitespace(str(value))
    normalized = normalize_numeric(value)
    numeric_tokens = _NUMERIC_TOKEN_RE.findall(text)
    has_alpha_unit = bool(re.search(rf"{_NUMBER_RE}\s*[A-Za-zµμ]+", text))
    return {
        "parse_success": normalized is not None,
        "normalized_value": normalized.to_dict() if normalized else None,
        "numeric_token_count": len(numeric_tokens),
        "has_numeric_token": bool(numeric_tokens),
        "has_percent": "%" in text,
        "has_unit": has_alpha_unit,
        "has_inequality": bool(_INEQUALITY_RE.search(text)),
        "has_plus_minus": bool(_PLUS_MINUS_RE.search(text)),
        "range_like": bool(_RANGE_LIKE_RE.search(text)),
        "list_like": len(numeric_tokens) > 1 and bool(re.search(r"[,;]", text)) and not _RANGE_LIKE_RE.search(text),
    }


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
