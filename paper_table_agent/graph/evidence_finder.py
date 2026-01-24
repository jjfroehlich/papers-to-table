from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from rapidfuzz import fuzz, process

from paper_table_agent.pdf.highlight import locate_quote
from paper_table_agent.text.normalization import normalize_for_matching


@dataclass
class EvidenceSearchResult:
    evidence: list[dict[str, Any]]
    evidence_quality: str
    highlight_success: bool


def find_evidence_for_proposals(
    proposals: list[dict[str, Any]],
    chunks: list[dict[str, Any]],
    page_text: Sequence[str] | None,
    tokens: Sequence[dict[str, object]] | None,
    pdf_path: str,
) -> list[dict[str, Any]]:
    for proposal in proposals:
        flags = proposal.setdefault("flags", {})
        evidence_quality = flags.get("evidence_quality") or proposal.get("evidence_quality")
        evidence_items = proposal.get("evidence") or []
        if evidence_quality == "strong" and evidence_items:
            _ensure_highlights(evidence_items, tokens, pdf_path)
            continue
        search_hints = flags.get("search_hints") or proposal.get("search_hints") or []
        if proposal.get("proposed_value"):
            search_hints = [proposal["proposed_value"]] + list(search_hints)
        search_hints = _dedupe([hint for hint in search_hints if str(hint).strip()])
        result = _search_evidence(
            search_hints,
            chunks,
            page_text,
            tokens,
            pdf_path,
        )
        if result.evidence:
            proposal["evidence"] = result.evidence
            flags["evidence_quality"] = result.evidence_quality
            flags["needs_more_evidence"] = result.evidence_quality != "strong"
            flags["evidence_finder_used"] = True
        else:
            flags["evidence_quality"] = evidence_quality or "none"
            flags["needs_more_evidence"] = True
    return proposals


def _search_evidence(
    hints: list[str],
    chunks: list[dict[str, Any]],
    page_text: Sequence[str] | None,
    tokens: Sequence[dict[str, object]] | None,
    pdf_path: str,
) -> EvidenceSearchResult:
    if not hints:
        return EvidenceSearchResult(evidence=[], evidence_quality="none", highlight_success=False)
    best_chunk, best_hint, best_score = _find_best_chunk(hints, chunks)
    if not best_chunk or not best_hint:
        return EvidenceSearchResult(evidence=[], evidence_quality="none", highlight_success=False)
    quote, quality = _extract_quote(best_hint, best_chunk)
    evidence = [
        {
            "quote": quote,
            "page": best_chunk.get("page_start"),
            "chunk_id": best_chunk.get("chunk_id"),
            "chunk_idx": best_chunk.get("chunk_idx"),
            "chunk_pk": best_chunk.get("chunk_pk"),
            "locator_hint": best_hint,
        }
    ]
    highlight_success = _ensure_highlights(evidence, tokens, pdf_path)
    if not highlight_success and page_text:
        evidence[0]["page"] = evidence[0].get("page") or _find_page_from_text(quote, page_text)
    return EvidenceSearchResult(
        evidence=evidence,
        evidence_quality="strong" if quality == "exact" else "weak",
        highlight_success=highlight_success,
    )


def _find_best_chunk(hints: list[str], chunks: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None, float]:
    best_chunk = None
    best_hint = None
    best_score = 0.0
    for hint in hints:
        normalized_hint = normalize_for_matching(hint)
        if not normalized_hint:
            continue
        for chunk in chunks:
            text_norm = str(chunk.get("text_norm") or chunk.get("text") or "")
            if normalized_hint in normalize_for_matching(text_norm):
                return chunk, hint, 1.0
        corpus = {str(chunk.get("chunk_id")): str(chunk.get("text") or "") for chunk in chunks}
        match = process.extractOne(hint, corpus, scorer=fuzz.partial_ratio)
        if match and match[1] > best_score:
            best_score = float(match[1]) / 100.0
            best_chunk = next((chunk for chunk in chunks if str(chunk.get("chunk_id")) == match[2]), None)
            best_hint = hint
    return best_chunk, best_hint, best_score


def _extract_quote(hint: str, chunk: dict[str, Any]) -> tuple[str, str]:
    text_raw = str(chunk.get("text_raw") or chunk.get("text") or "")
    if hint in text_raw:
        return _trim_quote(text_raw, hint), "exact"
    text_norm = str(chunk.get("text_norm") or chunk.get("text") or "")
    if hint in text_norm:
        return _trim_quote(text_norm, hint), "normalized"
    return _trim_quote(text_raw or text_norm, hint), "approx"


def _trim_quote(text: str, hint: str, max_len: int = 240) -> str:
    if not text:
        return hint
    if hint in text:
        start = text.find(hint)
        end = min(len(text), start + len(hint) + 80)
        snippet = text[max(0, start - 40) : end].strip()
        return snippet
    return text[:max_len].strip() if text else hint


def _ensure_highlights(
    evidence_items: list[dict[str, Any]],
    tokens: Sequence[dict[str, object]] | None,
    pdf_path: str,
) -> bool:
    highlight_success = False
    for evidence in evidence_items:
        quote = evidence.get("quote") or ""
        page = evidence.get("page")
        if not quote or not page:
            continue
        highlight = locate_quote(
            pdf_path,
            quote,
            int(page),
            locator_hint=evidence.get("locator_hint"),
            tokens=tokens,
        )
        evidence["rects"] = highlight.rects
        evidence["highlight_status"] = "highlighted" if highlight.found else "not_found"
        evidence["highlight_strategy"] = highlight.strategy
        highlight_success = highlight_success or highlight.found
    return highlight_success


def _find_page_from_text(quote: str, page_text: Sequence[str]) -> int | None:
    normalized_quote = normalize_for_matching(quote)
    if not normalized_quote:
        return None
    for idx, text in enumerate(page_text):
        if normalized_quote in normalize_for_matching(text):
            return idx + 1
    return None


def _dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = str(item).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result
