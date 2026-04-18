from __future__ import annotations

from typing import Any

from paper_eval.contracts import ComparisonResult, NumericTolerance
from paper_eval.normalize import normalize_boolean, normalize_categorical, normalize_numeric


def compare_boolean(gold_value: Any, proposed_value: Any) -> ComparisonResult:
    normalized_gold = normalize_boolean(gold_value)
    normalized_proposed = normalize_boolean(proposed_value)
    return ComparisonResult(
        is_correct=normalized_gold is not None and normalized_gold == normalized_proposed,
        normalized_gold=normalized_gold,
        normalized_proposed=normalized_proposed,
        diagnostics={},
    )


def compare_categorical(
    gold_value: Any,
    proposed_value: Any,
    *,
    aliases: dict[str, str] | None = None,
    allowed_values: list[str] | None = None,
) -> ComparisonResult:
    normalized_gold = normalize_categorical(
        gold_value,
        aliases=aliases,
        allowed_values=allowed_values,
    )
    normalized_proposed = normalize_categorical(
        proposed_value,
        aliases=aliases,
        allowed_values=allowed_values,
    )
    return ComparisonResult(
        is_correct=normalized_gold is not None and normalized_gold == normalized_proposed,
        normalized_gold=normalized_gold,
        normalized_proposed=normalized_proposed,
        diagnostics={"allowed_values": list(allowed_values or [])},
    )


def _scalar_window(reference_value: float, tolerance: NumericTolerance) -> float:
    return max(tolerance.abs_tol, abs(reference_value) * tolerance.rel_tol)


def compare_numeric(
    gold_value: Any,
    proposed_value: Any,
    *,
    tolerance: NumericTolerance,
) -> ComparisonResult:
    normalized_gold = normalize_numeric(gold_value)
    normalized_proposed = normalize_numeric(proposed_value)
    diagnostics: dict[str, Any] = {"tolerance": tolerance.to_dict()}

    if normalized_gold is None or normalized_proposed is None:
        return ComparisonResult(
            is_correct=False,
            normalized_gold=normalized_gold.to_dict() if normalized_gold else None,
            normalized_proposed=normalized_proposed.to_dict() if normalized_proposed else None,
            diagnostics=diagnostics,
        )

    diagnostics["gold_numeric"] = normalized_gold.to_dict()
    diagnostics["proposed_numeric"] = normalized_proposed.to_dict()

    if normalized_gold.is_scalar and normalized_proposed.is_scalar:
        gold_scalar = normalized_gold.center
        proposed_scalar = normalized_proposed.center
        absolute_error = abs(proposed_scalar - gold_scalar)
        relative_error = None if gold_scalar == 0 else absolute_error / abs(gold_scalar)
        allowed_error = _scalar_window(gold_scalar, tolerance)
        diagnostics.update(
            {
                "absolute_error": absolute_error,
                "relative_error": relative_error,
                "allowed_error": allowed_error,
            }
        )
        return ComparisonResult(
            is_correct=absolute_error <= allowed_error,
            normalized_gold=normalized_gold.to_dict(),
            normalized_proposed=normalized_proposed.to_dict(),
            diagnostics=diagnostics,
        )

    overlap_lower = max(normalized_gold.lower, normalized_proposed.lower)
    overlap_upper = min(normalized_gold.upper, normalized_proposed.upper)
    overlap = overlap_lower <= overlap_upper

    if not overlap:
        gap = max(
            normalized_proposed.lower - normalized_gold.upper,
            normalized_gold.lower - normalized_proposed.upper,
            0.0,
        )
        allowed_gap = _scalar_window(normalized_gold.center, tolerance)
        diagnostics.update({"interval_overlap": False, "gap": gap, "allowed_gap": allowed_gap})
        is_correct = gap <= allowed_gap
    else:
        diagnostics.update({"interval_overlap": True, "gap": 0.0, "allowed_gap": 0.0})
        is_correct = True

    return ComparisonResult(
        is_correct=is_correct,
        normalized_gold=normalized_gold.to_dict(),
        normalized_proposed=normalized_proposed.to_dict(),
        diagnostics=diagnostics,
    )
