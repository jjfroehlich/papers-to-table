from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable, Sequence

from rapidfuzz import fuzz, process

from paper_table_agent.pdf.highlight import assess_highlight_rects, locate_quote, salvage_quote_from_tokens
from paper_table_agent.text.normalization import normalize_for_matching, normalize_chunk_id


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
    column_chunks: dict[str, list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    chunk_lookup = _build_chunk_lookup(chunks)
    for proposal in proposals:
        flags = proposal.setdefault("flags", {})
        evidence_quality = flags.get("evidence_quality") or proposal.get("evidence_quality")
        evidence_items = proposal.get("evidence") or []
        for evidence in evidence_items:
            evidence.setdefault("pdf_id", proposal.get("pdf_id"))
        highlight_success = False
        highlight_failure = False
        if evidence_items:
            highlight_success = _ensure_highlights(
                evidence_items,
                tokens,
                pdf_path,
                page_text,
                chunk_lookup,
                proposal=proposal,
            )
            highlight_failure = not highlight_success
        needs_finder = bool(
            flags.get("needs_more_evidence")
            or flags.get("evidence_validation_errors")
            or not evidence_items
            or evidence_quality in {"weak", "none"}
            or highlight_failure
        )
        attempted = False
        succeeded = False
        backfilled = 0
        if not needs_finder and evidence_quality == "strong" and evidence_items:
            flags["evidence_finder_attempted"] = False
            continue
        search_hints = flags.get("search_hints") or proposal.get("search_hints") or []
        if proposal.get("column"):
            search_hints = [proposal["column"]] + list(search_hints)
        column_description = flags.get("column_description")
        if column_description:
            search_hints = [column_description] + list(search_hints)
        if proposal.get("proposed_value"):
            search_hints = [proposal["proposed_value"]] + list(search_hints)
        search_hints = _dedupe([hint for hint in search_hints if str(hint).strip()])
        search_chunks = chunks
        if column_chunks and proposal.get("column") in column_chunks:
            search_chunks = column_chunks[proposal["column"]] or chunks
        attempted = True
        result = _search_evidence(
            search_hints,
            search_chunks,
            page_text,
            tokens,
            pdf_path,
            proposal=proposal,
        )
        if result.evidence:
            proposal["evidence"] = result.evidence
            for evidence in proposal["evidence"]:
                evidence.setdefault("pdf_id", proposal.get("pdf_id"))
            flags["evidence_quality"] = result.evidence_quality
            flags["needs_more_evidence"] = result.evidence_quality != "strong"
            flags["evidence_finder_used"] = True
            succeeded = True
            backfilled += len(result.evidence)
        else:
            fallback = _fallback_evidence_from_chunks(search_hints, search_chunks, proposal)
            if fallback:
                _ensure_highlights(
                    fallback,
                    tokens,
                    pdf_path,
                    page_text,
                    _build_chunk_lookup(search_chunks),
                    proposal=proposal,
                )
                proposal["evidence"] = fallback
                flags["evidence_quality"] = "weak"
                flags["needs_more_evidence"] = True
                flags["evidence_finder_used"] = True
                succeeded = True
                backfilled += len(fallback)
            else:
                flags["evidence_quality"] = evidence_quality or "none"
                flags["needs_more_evidence"] = True
        flags["evidence_finder_attempted"] = attempted
        flags["evidence_finder_succeeded"] = succeeded
        flags["evidence_backfilled_count"] = backfilled
    return proposals


def _search_evidence(
    hints: list[str],
    chunks: list[dict[str, Any]],
    page_text: Sequence[str] | None,
    tokens: Sequence[dict[str, object]] | None,
    pdf_path: str,
    proposal: dict[str, Any] | None = None,
) -> EvidenceSearchResult:
    if not hints:
        return EvidenceSearchResult(evidence=[], evidence_quality="none", highlight_success=False)
    best_chunk, best_hint, best_score = _find_best_chunk(hints, chunks)
    if not best_chunk or not best_hint:
        return EvidenceSearchResult(evidence=[], evidence_quality="none", highlight_success=False)
    numeric_required = _needs_numeric_snippet(proposal)
    quote, quality = _extract_quote(best_hint, best_chunk, numeric_required=numeric_required, numeric_hint=proposal)
    if quality != "exact" and not _quote_matches_hints(quote, hints):
        return EvidenceSearchResult(evidence=[], evidence_quality="none", highlight_success=False)
    page = best_chunk.get("page_start")
    chunk_id = best_chunk.get("chunk_id")
    source_ref = None
    if chunk_id:
        source_ref = f"chunk_id:{chunk_id}"
    elif page:
        source_ref = f"page:{page}"
    evidence = [
        {
            "quote": quote,
            "quote_text": quote,
            "source_ref": source_ref,
            "anchor_id": chunk_id or (f"page-{page}" if page else None),
            "page": page,
            "chunk_id": chunk_id,
            "chunk_idx": best_chunk.get("chunk_idx"),
            "chunk_pk": best_chunk.get("chunk_pk"),
            "locator_hint": best_hint,
            "pdf_id": proposal.get("pdf_id") if proposal else None,
        }
    ]
    highlight_success = _ensure_highlights(evidence, tokens, pdf_path, page_text, _build_chunk_lookup(chunks))
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
        if best_score < 0.85:
            for chunk in chunks:
                chunk_text = str(chunk.get("text_norm") or chunk.get("text") or "")
                score = fuzz.partial_ratio(hint, chunk_text) / 100.0
                if score > best_score:
                    best_score = score
                    best_chunk = chunk
                    best_hint = hint
    return best_chunk, best_hint, best_score


def _extract_quote(
    hint: str,
    chunk: dict[str, Any],
    *,
    numeric_required: bool = False,
    numeric_hint: dict[str, Any] | None = None,
) -> tuple[str, str]:
    text_raw = str(chunk.get("text_raw") or chunk.get("text") or "")
    if numeric_required:
        numeric_quote = _extract_numeric_snippet(text_raw, numeric_hint)
        if numeric_quote:
            return numeric_quote, "numeric"
    if hint in text_raw:
        return _trim_quote(text_raw, hint), "exact"
    text_norm = str(chunk.get("text_norm") or chunk.get("text") or "")
    if numeric_required:
        numeric_quote = _extract_numeric_snippet(text_norm, numeric_hint)
        if numeric_quote:
            return numeric_quote, "numeric"
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
    page_text: Sequence[str] | None,
    chunk_lookup: dict[str, dict[str, Any]],
    proposal: dict[str, Any] | None = None,
) -> bool:
    highlight_success = False
    for evidence in evidence_items:
        _apply_anchor_id(evidence, chunk_lookup, page_text)
        _apply_source_ref(evidence, chunk_lookup)
        quote = _get_quote_text(evidence)
        page = evidence.get("page")
        if not evidence.get("source_ref"):
            if evidence.get("chunk_id"):
                evidence["source_ref"] = f"chunk_id:{evidence.get('chunk_id')}"
            elif page:
                evidence["source_ref"] = f"page:{page}"
        if not evidence.get("anchor_id"):
            if evidence.get("chunk_id"):
                evidence["anchor_id"] = evidence.get("chunk_id")
            elif page:
                evidence["anchor_id"] = f"page-{page}"
        if not page:
            page = _page_from_chunk(evidence, chunk_lookup)
            if page:
                evidence["page"] = page
        if not page and page_text:
            page = _find_best_page_for_quote(quote or evidence.get("locator_hint"), page_text)
            if page:
                evidence["page"] = page
        if not quote or not page:
            evidence["highlight_status"] = "missing_quote_or_page"
            evidence["highlight_strategy"] = "missing"
            continue
        allowed, reason = _quote_quality_floor(quote, proposal)
        if not allowed:
            evidence["highlight_status"] = "failed"
            evidence["highlight_strategy"] = "skipped_low_quality"
            evidence["highlight_rejection_reason"] = reason
            evidence["rects"] = []
            continue
        highlight = locate_quote(
            pdf_path,
            quote,
            int(page),
            locator_hint=evidence.get("locator_hint"),
            tokens=tokens,
        )
        rects = highlight.rects
        strategy = highlight.strategy
        match_score = highlight.match_score
        if not highlight.found and tokens:
            salvage_quote, salvage_rect, salvage_strategy, salvage_score = salvage_quote_from_tokens(
                quote or evidence.get("locator_hint") or "",
                int(page),
                tokens,
            )
            if salvage_quote and salvage_rect:
                _set_quote_text(evidence, salvage_quote)
                rects = [salvage_rect]
                strategy = salvage_strategy
                match_score = salvage_score
        accept, rejection_reason = assess_highlight_rects(
            quote,
            rects,
            highlight.page_height,
            match_score,
        )
        evidence["highlight_match_score"] = match_score
        if not accept:
            evidence["rects"] = []
            evidence["highlight_status"] = "failed"
            evidence["highlight_strategy"] = strategy
            evidence["highlight_rejection_reason"] = rejection_reason
            continue
        evidence["rects"] = rects
        evidence["highlight_status"] = "highlighted" if rects else "not_found"
        evidence["highlight_strategy"] = strategy
        highlight_success = highlight_success or bool(rects)
    return highlight_success


def _find_page_from_text(quote: str, page_text: Sequence[str]) -> int | None:
    normalized_quote = normalize_for_matching(quote)
    if not normalized_quote:
        return None
    for idx, text in enumerate(page_text):
        if normalized_quote in normalize_for_matching(text):
            return idx + 1
    return None


def _find_best_page_for_quote(quote: str | None, page_text: Sequence[str]) -> int | None:
    if not quote:
        return None
    best_page = None
    best_score = 0
    for idx, text in enumerate(page_text):
        score = fuzz.partial_ratio(quote, text)
        if score > best_score:
            best_score = score
            best_page = idx + 1
    if best_score < 60:
        return _find_page_from_text(quote, page_text)
    return best_page


def _build_chunk_lookup(chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        chunk_id = normalize_chunk_id(str(chunk.get("chunk_id") or ""))
        if not chunk_id:
            continue
        lookup[chunk_id] = chunk
    return lookup


def _page_from_chunk(evidence: dict[str, Any], chunk_lookup: dict[str, dict[str, Any]]) -> int | None:
    chunk_id = normalize_chunk_id(str(evidence.get("chunk_id") or ""))
    if chunk_id and chunk_id in chunk_lookup:
        page = chunk_lookup[chunk_id].get("page_start")
        return int(page) if page is not None else None
    chunk_idx = evidence.get("chunk_idx")
    if chunk_idx:
        for chunk in chunk_lookup.values():
            if chunk.get("chunk_idx") == chunk_idx:
                page = chunk.get("page_start")
                return int(page) if page is not None else None
    return None


def _apply_anchor_id(
    evidence: dict[str, Any],
    chunk_lookup: dict[str, dict[str, Any]],
    page_text: Sequence[str] | None,
) -> None:
    anchor_id = str(evidence.get("anchor_id") or "").strip()
    if not anchor_id:
        return
    if anchor_id.startswith("page-"):
        try:
            page = int(anchor_id.split("-", 1)[1])
        except ValueError:
            return
        evidence.setdefault("page", page)
        if page_text and not _get_quote_text(evidence):
            if 0 < page <= len(page_text):
                _set_quote_text(evidence, page_text[page - 1][:240])
        return
    if anchor_id in chunk_lookup:
        chunk = chunk_lookup[anchor_id]
        evidence.setdefault("chunk_id", anchor_id)
        if chunk.get("page_start") and not evidence.get("page"):
            evidence["page"] = chunk.get("page_start")


def _apply_source_ref(evidence: dict[str, Any], chunk_lookup: dict[str, dict[str, Any]]) -> None:
    source_ref = str(evidence.get("source_ref") or "").strip()
    if not source_ref:
        return
    if source_ref.startswith("page:"):
        try:
            evidence["page"] = int(source_ref.split(":", 1)[1])
        except ValueError:
            return
        return
    if source_ref.startswith("chunk_id:"):
        evidence["chunk_id"] = source_ref.split(":", 1)[1]
        return
    if source_ref.startswith("chunk:"):
        evidence["chunk_id"] = source_ref.split(":", 1)[1]
        return
    if source_ref in chunk_lookup:
        evidence["chunk_id"] = source_ref


def _get_quote_text(evidence: dict[str, Any]) -> str:
    return str(evidence.get("quote_text") or evidence.get("quote") or evidence.get("quote_raw") or "").strip()


def _set_quote_text(evidence: dict[str, Any], quote: str) -> None:
    evidence["quote"] = quote
    evidence["quote_text"] = quote


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


def _quote_matches_hints(quote: str, hints: list[str]) -> bool:
    if not quote:
        return False
    normalized_quote = normalize_for_matching(quote)
    if not normalized_quote:
        return False
    for hint in hints:
        hint_norm = normalize_for_matching(str(hint))
        if not hint_norm:
            continue
        tokens = [token for token in hint_norm.split() if len(token) >= 4]
        if not tokens:
            continue
        if any(token in normalized_quote for token in tokens):
            return True
    return False


def _fallback_evidence_from_chunks(
    hints: list[str],
    chunks: list[dict[str, Any]],
    proposal: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not chunks:
        return []
    candidate = None
    if hints:
        candidate, _hint, _score = _find_best_chunk(hints, chunks)
    if candidate is None:
        candidate = chunks[0]
    text = str(candidate.get("text_raw") or candidate.get("text") or "")
    if not text:
        return []
    snippet = _first_sentence_snippet(text)
    page = candidate.get("page_start")
    chunk_id = candidate.get("chunk_id")
    source_ref = f"chunk_id:{chunk_id}" if chunk_id else (f"page:{page}" if page else None)
    evidence = [
        {
            "quote": snippet,
            "quote_text": snippet,
            "source_ref": source_ref,
            "anchor_id": chunk_id or (f"page-{page}" if page else None),
            "page": page,
            "chunk_id": chunk_id,
            "chunk_idx": candidate.get("chunk_idx"),
            "chunk_pk": candidate.get("chunk_pk"),
            "locator_hint": hints[0] if hints else None,
            "pdf_id": proposal.get("pdf_id") if proposal else None,
        }
    ]
    return evidence


def _first_sentence_snippet(text: str, max_len: int = 260) -> str:
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\\s+", text.strip())
    snippet = " ".join(sentences[:2]).strip()
    if not snippet:
        snippet = text.strip()
    return snippet[:max_len].strip()


def _quote_quality_floor(quote: str, proposal: dict[str, Any] | None = None) -> tuple[bool, str | None]:
    if not quote:
        return False, "missing_quote"
    cleaned = quote.strip()
    if len(cleaned) < 20 or len(cleaned.split()) < 5:
        return False, "quote_too_short"
    alnum = sum(1 for char in cleaned if char.isalnum())
    if alnum / max(len(cleaned), 1) < 0.3:
        return False, "quote_low_alnum"
    if _needs_numeric_snippet(proposal) and not any(char.isdigit() for char in cleaned):
        return False, "quote_missing_numeric"
    return True, None


def _needs_numeric_snippet(proposal: dict[str, Any] | None) -> bool:
    if not proposal:
        return False
    proposed_value = str(proposal.get("proposed_value") or "")
    if any(char.isdigit() for char in proposed_value):
        return True
    column = str(proposal.get("column") or "").lower()
    numeric_tokens = ("percent", "%", "rate", "ratio", "dose", "mg", "ml", "kg", "n ", "count", "number", "score")
    return any(token in column for token in numeric_tokens)


def _extract_numeric_snippet(text: str, proposal: dict[str, Any] | None = None) -> str | None:
    if not text:
        return None
    preferred = ""
    if proposal:
        preferred = str(proposal.get("proposed_value") or "")
    if preferred and preferred in text:
        return _trim_quote(text, preferred)
    match = re.search(r"\d[\d\.\,/%-]{0,20}", text)
    if not match:
        return None
    snippet = text[max(0, match.start() - 40) : min(len(text), match.end() + 40)].strip()
    return snippet if snippet else None
