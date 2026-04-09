from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from paper_eval.contracts import NormalizedNumber
from paper_eval.normalize import normalize_numeric, normalize_text_for_match

_NUMBER_TOKEN_RE = re.compile(r"[-+]?(?:\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)(?:[eE][-+]?\d+)?")


@dataclass(frozen=True)
class StructuredSupportProxyResult:
    status: str
    matched_evidence_ids: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    @property
    def was_evaluated(self) -> bool:
        return self.status in {"supported", "unsupported"}


def evaluate_structured_support_proxy(
    *,
    field_type: str,
    proposed_value: Any,
    normalized_proposed: Any,
    evidence_items: list[Any],
    page_text_by_page: dict[int, str],
) -> StructuredSupportProxyResult:
    """Lightweight proxy for whether structured values appear in cited evidence text.

    This remains intentionally narrow: it only checks whether the normalized proposed
    value is directly recoverable from quote text or cited page text. It is additive
    diagnostic signal, not a replacement for correctness or anchor validation.
    """
    if field_type not in {"boolean", "categorical", "numeric"}:
        return StructuredSupportProxyResult(status="not_applicable")
    if normalized_proposed is None:
        return StructuredSupportProxyResult(
            status="unvalidated",
            diagnostics={"reason": "normalized_proposed_missing"},
        )

    evidence_texts = _collect_evidence_texts(evidence_items, page_text_by_page)
    if not evidence_texts:
        return StructuredSupportProxyResult(
            status="unvalidated",
            diagnostics={"reason": "no_searchable_evidence_text"},
        )

    matched_evidence_ids: list[str] = []
    for evidence_id, text in evidence_texts:
        if _supports_value(field_type, normalized_proposed, text):
            if evidence_id:
                matched_evidence_ids.append(evidence_id)

    if matched_evidence_ids:
        return StructuredSupportProxyResult(
            status="supported",
            matched_evidence_ids=matched_evidence_ids,
            diagnostics={"searched_evidence_count": len(evidence_texts)},
        )

    return StructuredSupportProxyResult(
        status="unsupported",
        diagnostics={"searched_evidence_count": len(evidence_texts)},
    )


def _collect_evidence_texts(
    evidence_items: list[Any],
    page_text_by_page: dict[int, str],
) -> list[tuple[str | None, str]]:
    texts: list[tuple[str | None, str]] = []
    for evidence in evidence_items:
        evidence_id = getattr(evidence, "evidence_id", None)
        quote_text = getattr(evidence, "quote_text", None)
        if isinstance(quote_text, str) and quote_text.strip():
            texts.append((evidence_id, quote_text))

        raw = getattr(evidence, "raw", {}) or {}
        source_text = raw.get("source_text") if isinstance(raw, dict) else None
        if isinstance(source_text, str) and source_text.strip():
            texts.append((evidence_id, source_text))

        page = getattr(evidence, "page", None)
        if isinstance(page, int):
            page_text = page_text_by_page.get(page)
            if isinstance(page_text, str) and page_text.strip():
                texts.append((evidence_id, page_text))
    return texts


def _supports_value(field_type: str, normalized_proposed: Any, text: str) -> bool:
    normalized_text = normalize_text_for_match(text)
    if not normalized_text:
        return False
    if field_type == "boolean":
        return _boolean_supported(bool(normalized_proposed), normalized_text)
    if field_type == "categorical":
        return str(normalized_proposed) in normalized_text
    if field_type == "numeric":
        return _numeric_supported(normalized_proposed, text)
    return False


def _boolean_supported(value: bool, normalized_text: str) -> bool:
    true_terms = {"true", "yes", "present", "positive"}
    false_terms = {"false", "no", "absent", "negative"}
    terms = true_terms if value else false_terms
    return any(term in normalized_text.split() or f" {term} " in f" {normalized_text} " for term in terms)


def _numeric_supported(normalized_proposed: Any, text: str) -> bool:
    left = _coerce_normalized_number(normalized_proposed)
    if left is None:
        return False
    candidate_numbers = []
    for match in _NUMBER_TOKEN_RE.finditer(text):
        candidate = normalize_numeric(match.group(0))
        if candidate is not None:
            candidate_numbers.append(candidate)
    if not candidate_numbers:
        return False
    for candidate in candidate_numbers:
        if _numeric_overlap(left, candidate):
            return True
    return False


def _numeric_overlap(left: NormalizedNumber, right: NormalizedNumber) -> bool:
    return not (left.upper < right.lower or right.upper < left.lower)


def _coerce_normalized_number(value: Any) -> NormalizedNumber | None:
    if isinstance(value, NormalizedNumber):
        return value
    if isinstance(value, dict):
        try:
            return NormalizedNumber(
                kind=str(value.get("kind") or "scalar"),
                lower=float(value["lower"]),
                upper=float(value["upper"]),
                approx=bool(value.get("approx", False)),
                raw_text=value.get("raw_text"),
            )
        except (KeyError, TypeError, ValueError):
            return None
    return None