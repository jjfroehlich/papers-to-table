from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

import fitz
from rapidfuzz import fuzz

from paper_table_agent.text.normalization import normalize_text, normalize_unicode

@dataclass
class HighlightResult:
    rects: list[list[float]]
    found: bool
    strategy: str


def locate_quote(
    pdf_path: str,
    quote: str,
    page_number: int,
    locator_hint: str | None = None,
    tokens: Sequence[dict[str, object]] | None = None,
) -> HighlightResult:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)
    hits = page.search_for(quote)
    rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
    if rects:
        doc.close()
        return HighlightResult(rects=rects, found=True, strategy="exact")
    normalized = _normalize_quote_search(quote)
    hits = page.search_for(normalized)
    rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
    if rects:
        doc.close()
        return HighlightResult(rects=rects, found=True, strategy="normalized")
    fragment_hit = _search_fragments(page, quote)
    if fragment_hit:
        doc.close()
        return HighlightResult(rects=fragment_hit, found=True, strategy="fragment")
    if locator_hint:
        hits = page.search_for(locator_hint)
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            return HighlightResult(rects=rects, found=True, strategy="locator_hint")
        normalized_hint = _normalize_quote_search(locator_hint)
        hits = page.search_for(normalized_hint)
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            return HighlightResult(rects=rects, found=True, strategy="locator_hint_normalized")
        fragment_hit = _search_fragments(page, locator_hint)
        if fragment_hit:
            doc.close()
            return HighlightResult(rects=fragment_hit, found=True, strategy="locator_hint_fragment")
    if tokens:
        rect = _match_tokens(quote, page_number, tokens)
        if rect:
            doc.close()
            return HighlightResult(rects=[rect], found=True, strategy="tokens")
        rect = _match_tokens_fuzzy(quote, page_number, tokens)
        if rect:
            doc.close()
            return HighlightResult(rects=[rect], found=True, strategy="token_fuzzy")
    doc.close()
    return HighlightResult(rects=[], found=False, strategy="missing")


def salvage_quote_from_tokens(
    quote: str,
    page_number: int,
    tokens: Sequence[dict[str, object]] | None,
    threshold: int = 78,
) -> tuple[str | None, list[float] | None, str]:
    if not quote or not tokens:
        return None, None, "missing"
    page_tokens = [
        token
        for token in tokens
        if int(token.get("page", 0)) == page_number and token.get("text")
    ]
    if not page_tokens:
        return None, None, "missing"
    quote_words = _normalize_words(quote)
    if not quote_words:
        return None, None, "missing"
    normalized_tokens = [_normalize_words(str(token["text"])) for token in page_tokens]
    flattened = [words[0] for words in normalized_tokens if words]
    if not flattened:
        return None, None, "missing"
    exact_span = _find_exact_span(quote_words, flattened)
    if exact_span:
        rect = _token_span_rect(page_tokens, exact_span)
        quote_text = " ".join(str(token["text"]) for token in page_tokens[exact_span[0] : exact_span[1]])
        return quote_text, rect, "token_salvage_exact"
    best_span, best_score = _find_fuzzy_span(quote_words, flattened, threshold)
    if best_span is None:
        return None, None, "missing"
    rect = _token_span_rect(page_tokens, best_span)
    quote_text = " ".join(str(token["text"]) for token in page_tokens[best_span[0] : best_span[1]])
    return quote_text, rect, "token_salvage_fuzzy"


def apply_highlights(pdf_path: str, page_number: int, rects: Iterable[list[float]]) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)
    for rect in rects:
        annotation = page.add_highlight_annot(fitz.Rect(rect))
        annotation.update()
    data = doc.tobytes()
    doc.close()
    return data


def render_page_image(pdf_path: str, page_number: int, rects: Iterable[list[float]]) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)
    for rect in rects:
        annotation = page.add_highlight_annot(fitz.Rect(rect))
        annotation.update()
    pix = page.get_pixmap(dpi=144)
    data = pix.tobytes("png")
    doc.close()
    return data


def _match_tokens(
    quote: str,
    page_number: int,
    tokens: Sequence[dict[str, object]],
) -> list[float] | None:
    quote_words = _normalize_words(quote)
    if not quote_words:
        return _match_token_fragments(quote, page_number, tokens)
    page_tokens = [
        token
        for token in tokens
        if int(token.get("page", 0)) == page_number and token.get("text")
    ]
    normalized_tokens = [_normalize_words(str(token["text"])) for token in page_tokens]
    flattened = [words[0] for words in normalized_tokens if words]
    if not flattened:
        return None
    for start in range(len(flattened)):
        if flattened[start] != quote_words[0]:
            continue
        window = flattened[start : start + len(quote_words)]
        if window != quote_words:
            continue
        matched = page_tokens[start : start + len(quote_words)]
        xs0 = [token["bbox"][0] for token in matched if token.get("bbox")]
        ys0 = [token["bbox"][1] for token in matched if token.get("bbox")]
        xs1 = [token["bbox"][2] for token in matched if token.get("bbox")]
        ys1 = [token["bbox"][3] for token in matched if token.get("bbox")]
        if not xs0 or not ys0 or not xs1 or not ys1:
            return None
        return [min(xs0), min(ys0), max(xs1), max(ys1)]
    if _split_quote_fragments(quote):
        return _match_token_fragments(quote, page_number, tokens)
    return None


def _normalize_words(text: str) -> list[str]:
    cleaned = normalize_text(text)
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", cleaned).strip().lower()
    return [word for word in cleaned.split() if word]


def _normalize_quote_search(text: str) -> str:
    normalized = normalize_unicode(text)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _split_quote_fragments(text: str) -> list[str]:
    if not text or ("..." not in text and "…" not in text):
        return []
    parts = re.split(r"(?:\\.{3}|…)", text or "")
    return [part.strip() for part in parts if len(part.strip()) >= 6]


def _search_fragments(page: fitz.Page, text: str) -> list[list[float]]:
    fragments = _split_quote_fragments(text)
    for fragment in fragments:
        hits = page.search_for(fragment)
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            return rects
        normalized_fragment = _normalize_quote_search(fragment)
        if normalized_fragment and normalized_fragment != fragment:
            hits = page.search_for(normalized_fragment)
            rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
            if rects:
                return rects
    return []


def _match_token_fragments(
    quote: str,
    page_number: int,
    tokens: Sequence[dict[str, object]],
) -> list[float] | None:
    fragments = _split_quote_fragments(quote)
    if not fragments:
        return None
    for fragment in fragments:
        rect = _match_tokens(fragment, page_number, tokens)
        if rect:
            return rect
    return None


def _match_tokens_fuzzy(
    quote: str,
    page_number: int,
    tokens: Sequence[dict[str, object]],
    threshold: int = 78,
) -> list[float] | None:
    quote_words = _normalize_words(quote)
    if not quote_words:
        return None
    page_tokens = [
        token
        for token in tokens
        if int(token.get("page", 0)) == page_number and token.get("text")
    ]
    normalized_tokens = [_normalize_words(str(token["text"])) for token in page_tokens]
    flattened = [words[0] for words in normalized_tokens if words]
    if not flattened:
        return None
    window_size = min(max(len(quote_words), 3), 12)
    best_score = 0
    best_span = None
    for start in range(len(flattened) - window_size + 1):
        window = flattened[start : start + window_size]
        score = fuzz.ratio(" ".join(quote_words), " ".join(window))
        if score > best_score:
            best_score = score
            best_span = (start, start + window_size)
    if best_score < threshold or best_span is None:
        return None
    matched = page_tokens[best_span[0] : best_span[1]]
    xs0 = [token["bbox"][0] for token in matched if token.get("bbox")]
    ys0 = [token["bbox"][1] for token in matched if token.get("bbox")]
    xs1 = [token["bbox"][2] for token in matched if token.get("bbox")]
    ys1 = [token["bbox"][3] for token in matched if token.get("bbox")]
    if not xs0 or not ys0 or not xs1 or not ys1:
        return None
    return [min(xs0), min(ys0), max(xs1), max(ys1)]


def _find_exact_span(quote_words: list[str], tokens: list[str]) -> tuple[int, int] | None:
    if not quote_words:
        return None
    window_size = len(quote_words)
    for start in range(len(tokens) - window_size + 1):
        if tokens[start : start + window_size] == quote_words:
            return (start, start + window_size)
    return None


def _find_fuzzy_span(
    quote_words: list[str],
    tokens: list[str],
    threshold: int,
) -> tuple[tuple[int, int] | None, int]:
    if not quote_words:
        return None, 0
    min_size = max(len(quote_words) - 2, 3)
    max_size = min(len(quote_words) + 2, 12)
    best_score = 0
    best_span = None
    target = " ".join(quote_words)
    for window_size in range(min_size, max_size + 1):
        for start in range(len(tokens) - window_size + 1):
            window = tokens[start : start + window_size]
            score = fuzz.ratio(target, " ".join(window))
            if score > best_score:
                best_score = score
                best_span = (start, start + window_size)
    if best_score < threshold:
        return None, best_score
    return best_span, best_score


def _token_span_rect(tokens: Sequence[dict[str, object]], span: tuple[int, int]) -> list[float] | None:
    matched = tokens[span[0] : span[1]]
    xs0 = [token["bbox"][0] for token in matched if token.get("bbox")]
    ys0 = [token["bbox"][1] for token in matched if token.get("bbox")]
    xs1 = [token["bbox"][2] for token in matched if token.get("bbox")]
    ys1 = [token["bbox"][3] for token in matched if token.get("bbox")]
    if not xs0 or not ys0 or not xs1 or not ys1:
        return None
    return [min(xs0), min(ys0), max(xs1), max(ys1)]
