from __future__ import annotations

import re
from typing import Iterable

from paper_eval.contracts import EvidenceItem, EvidenceValidationResult

_WHITESPACE_RE = re.compile(r"\s+")


def validate_evidence_anchors(
    evidence_items: Iterable[EvidenceItem],
    *,
    page_text_by_page: dict[int, str] | None = None,
    page_count: int | None = None,
) -> EvidenceValidationResult:
    items = list(evidence_items)
    if not items:
        return EvidenceValidationResult(
            outcome="missing_evidence",
            anchor_valid=False,
            evidence_present_but_unvalidated=False,
            diagnostics={"evidence_item_count": 0},
        )

    page_text_by_page = page_text_by_page or {}
    item_diagnostics: list[dict[str, object]] = []
    saw_present_but_unvalidated = False
    saw_invalid_anchor = False

    for item in items:
        item_result = _validate_single_anchor(
            item,
            page_text_by_page=page_text_by_page,
            page_count=page_count,
        )
        item_diagnostics.append(item_result)
        if item_result["outcome"] == "anchor_valid":
            return EvidenceValidationResult(
                outcome="anchor_valid",
                anchor_valid=True,
                evidence_present_but_unvalidated=False,
                diagnostics={
                    "evidence_item_count": len(items),
                    "validated_evidence_item_count": 1,
                    "evidence_items": item_diagnostics,
                },
            )
        if item_result["outcome"] == "evidence_present_but_unvalidated":
            saw_present_but_unvalidated = True
        elif item_result["outcome"] == "anchor_invalid":
            saw_invalid_anchor = True

    if saw_present_but_unvalidated:
        outcome = "evidence_present_but_unvalidated"
    elif saw_invalid_anchor:
        outcome = "anchor_invalid"
    else:
        outcome = "missing_evidence"

    return EvidenceValidationResult(
        outcome=outcome,
        anchor_valid=False,
        evidence_present_but_unvalidated=outcome == "evidence_present_but_unvalidated",
        diagnostics={
            "evidence_item_count": len(items),
            "validated_evidence_item_count": 0,
            "evidence_items": item_diagnostics,
        },
    )


def _validate_single_anchor(
    item: EvidenceItem,
    *,
    page_text_by_page: dict[int, str],
    page_count: int | None,
) -> dict[str, object]:
    page = item.page
    quote_text = (item.quote_text or "").strip()
    diagnostic = {
        "evidence_id": item.evidence_id,
        "page": page,
        "quote_text": quote_text,
        "outcome": "missing_evidence",
        "reason": None,
    }

    if page is None or page <= 0:
        diagnostic["outcome"] = "anchor_invalid"
        diagnostic["reason"] = "missing_or_invalid_page"
        return diagnostic
    if not quote_text:
        diagnostic["outcome"] = "anchor_invalid"
        diagnostic["reason"] = "missing_quote_text"
        return diagnostic
    if page_count is not None and page > page_count:
        diagnostic["outcome"] = "anchor_invalid"
        diagnostic["reason"] = "page_out_of_bounds"
        return diagnostic

    source_text = _resolve_source_text(item, page_text_by_page)
    if source_text is None:
        diagnostic["outcome"] = "evidence_present_but_unvalidated"
        diagnostic["reason"] = "no_persisted_text_available"
        return diagnostic

    if _quote_is_locatable(quote_text, source_text):
        diagnostic["outcome"] = "anchor_valid"
        diagnostic["reason"] = "quote_located"
        return diagnostic

    normalized_source_text = _resolve_normalized_source_text(item)
    if normalized_source_text is not None and _quote_is_locatable(quote_text, normalized_source_text):
        diagnostic["outcome"] = "anchor_valid"
        diagnostic["reason"] = "normalized_quote_located"
        return diagnostic

    diagnostic["outcome"] = "evidence_present_but_unvalidated"
    diagnostic["reason"] = "quote_not_locatable"
    return diagnostic


def _resolve_source_text(item: EvidenceItem, page_text_by_page: dict[int, str]) -> str | None:
    raw = item.raw
    for key in ("page_text", "page_content", "source_text", "text"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value
    if item.page is None:
        return None
    value = page_text_by_page.get(item.page)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _resolve_normalized_source_text(item: EvidenceItem) -> str | None:
    value = item.raw.get("normalized_source_text")
    if isinstance(value, str) and value.strip():
        return value
    return None


def _quote_is_locatable(quote_text: str, source_text: str) -> bool:
    normalized_quote = _normalize_search_text(quote_text)
    normalized_source = _normalize_search_text(source_text)
    return bool(normalized_quote) and normalized_quote in normalized_source


def _normalize_search_text(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", value).strip().casefold()
