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
    match_score: float | None = None
    page_height: float | None = None


def locate_quote(
    pdf_path: str,
    quote: str,
    page_number: int,
    locator_hint: str | None = None,
    tokens: Sequence[dict[str, object]] | None = None,
    *,
    allow_fuzzy: bool = True,
) -> HighlightResult:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)
    page_height = float(page.rect.height)
    hits = page.search_for(quote, flags=_search_flags())
    rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
    if rects:
        doc.close()
        return HighlightResult(rects=rects, found=True, strategy="exact", match_score=1.0, page_height=page_height)
    if tokens:
        rect, score = _match_tokens(quote, page_number, tokens)
        if rect:
            doc.close()
            return HighlightResult(
                rects=[rect],
                found=True,
                strategy="tokens_exact",
                match_score=score,
                page_height=page_height,
            )
    if not allow_fuzzy:
        doc.close()
        return HighlightResult(rects=[], found=False, strategy="missing", match_score=None, page_height=page_height)
    normalized = _normalize_quote_search(quote)
    hits = page.search_for(normalized, flags=_search_flags())
    rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
    if rects:
        doc.close()
        return HighlightResult(
            rects=rects,
            found=True,
            strategy="normalized",
            match_score=1.0,
            page_height=page_height,
        )
    normalized_chunk = _normalize_chunk_quote(quote)
    if normalized_chunk and normalized_chunk != normalized:
        hits = page.search_for(normalized_chunk, flags=_search_flags())
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            return HighlightResult(
                rects=rects,
                found=True,
                strategy="normalized_chunk_text",
                match_score=1.0,
                page_height=page_height,
            )
    fragment_hit, fragment_text = _search_fragments(page, quote)
    if fragment_hit:
        doc.close()
        match_score = fuzz.partial_ratio(quote, fragment_text) / 100.0 if fragment_text else None
        return HighlightResult(
            rects=fragment_hit,
            found=True,
            strategy="fragment",
            match_score=match_score,
            page_height=page_height,
        )
    page_match = _best_page_text_match(quote, page.get_text("text"))
    if page_match:
        match_text, strategy = page_match
        hits = page.search_for(match_text)
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            match_score = fuzz.partial_ratio(quote, match_text) / 100.0 if match_text else None
            return HighlightResult(
                rects=rects,
                found=True,
                strategy=strategy,
                match_score=match_score,
                page_height=page_height,
            )
    if locator_hint:
        hits = page.search_for(locator_hint, flags=_search_flags())
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            match_score = fuzz.partial_ratio(quote, locator_hint) / 100.0 if quote else None
            return HighlightResult(
                rects=rects,
                found=True,
                strategy="locator_hint",
                match_score=match_score,
                page_height=page_height,
            )
        normalized_hint = _normalize_quote_search(locator_hint)
        hits = page.search_for(normalized_hint, flags=_search_flags())
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            match_score = fuzz.partial_ratio(quote, locator_hint) / 100.0 if quote else None
            return HighlightResult(
                rects=rects,
                found=True,
                strategy="locator_hint_normalized",
                match_score=match_score,
                page_height=page_height,
            )
        fragment_hit, fragment_text = _search_fragments(page, locator_hint)
        if fragment_hit:
            doc.close()
            match_score = fuzz.partial_ratio(quote, fragment_text) / 100.0 if fragment_text else None
            return HighlightResult(
                rects=fragment_hit,
                found=True,
                strategy="locator_hint_fragment",
                match_score=match_score,
                page_height=page_height,
            )
    if tokens:
        rect, score = _match_tokens_fuzzy(quote, page_number, tokens)
        if rect:
            doc.close()
            return HighlightResult(
                rects=[rect],
                found=True,
                strategy="token_fuzzy",
                match_score=score,
                page_height=page_height,
            )
    doc.close()
    return HighlightResult(rects=[], found=False, strategy="missing", match_score=None, page_height=page_height)


def locate_quote_span(page_text: str, quote: str) -> tuple[int, int, str, float] | None:
    if not page_text or not quote:
        return None
    exact_idx = page_text.find(quote)
    if exact_idx != -1:
        return exact_idx, exact_idx + len(quote), "text_exact", 1.0
    normalized_page, mapping = _normalize_with_mapping(page_text)
    normalized_quote = _normalize_quote_search(quote)
    if not normalized_quote:
        return None
    normalized_idx = normalized_page.find(normalized_quote)
    if normalized_idx != -1:
        start = mapping[normalized_idx]
        end = mapping[min(normalized_idx + len(normalized_quote) - 1, len(mapping) - 1)] + 1
        return start, end, "text_normalized", 0.9
    return None


def salvage_quote_from_tokens(
    quote: str,
    page_number: int,
    tokens: Sequence[dict[str, object]] | None,
    threshold: int = 78,
) -> tuple[str | None, list[float] | None, str, float | None]:
    if not quote or not tokens:
        return None, None, "missing", None
    page_tokens = [
        token
        for token in tokens
        if int(token.get("page", 0)) == page_number and token.get("text")
    ]
    if not page_tokens:
        return None, None, "missing", None
    quote_words = _normalize_words(quote)
    if not quote_words:
        return None, None, "missing", None
    normalized_tokens = [_normalize_words(str(token["text"])) for token in page_tokens]
    flattened = [words[0] for words in normalized_tokens if words]
    if not flattened:
        return None, None, "missing", None
    exact_span = _find_exact_span(quote_words, flattened)
    if exact_span:
        rect = _token_span_rect(page_tokens, exact_span)
        quote_text = " ".join(str(token["text"]) for token in page_tokens[exact_span[0] : exact_span[1]])
        return quote_text, rect, "token_salvage_exact", 1.0
    best_span, best_score = _find_fuzzy_span(quote_words, flattened, threshold)
    if best_span is None:
        return None, None, "missing", None
    rect = _token_span_rect(page_tokens, best_span)
    quote_text = " ".join(str(token["text"]) for token in page_tokens[best_span[0] : best_span[1]])
    return quote_text, rect, "token_salvage_fuzzy", best_score / 100.0


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
) -> tuple[list[float] | None, float | None]:
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
        return None, None
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
            return None, None
        return [min(xs0), min(ys0), max(xs1), max(ys1)], 1.0
    if _split_quote_fragments(quote):
        return _match_token_fragments(quote, page_number, tokens)
    return None, None


def _normalize_words(text: str) -> list[str]:
    cleaned = normalize_text(text)
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", cleaned).strip().lower()
    return [word for word in cleaned.split() if word]


def _normalize_quote_search(text: str) -> str:
    normalized = normalize_unicode(text)
    normalized = normalized.replace("\u00ad", "")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _normalize_chunk_quote(text: str) -> str:
    normalized = normalize_text(text)
    return normalized.replace("\u00ad", "").strip()


def _search_flags() -> int:
    flags = 0
    for name in ("TEXT_DEHYPHENATE", "TEXT_PRESERVE_LIGATURES", "TEXT_PRESERVE_WHITESPACE"):
        flags |= getattr(fitz, name, 0)
    return flags


def _normalize_with_mapping(text: str) -> tuple[str, list[int]]:
    normalized_chars: list[str] = []
    mapping: list[int] = []
    for idx, char in enumerate(text):
        normalized = normalize_unicode(char)
        if normalized.isspace():
            if normalized_chars and normalized_chars[-1] != " ":
                normalized_chars.append(" ")
                mapping.append(idx)
            continue
        for normalized_char in normalized:
            normalized_chars.append(normalized_char)
            mapping.append(idx)
    normalized_text = "".join(normalized_chars)
    return normalized_text, mapping


def _split_quote_fragments(text: str) -> list[str]:
    if not text or ("..." not in text and "…" not in text):
        return []
    parts = re.split(r"(?:\\.{3}|…)", text or "")
    return [part.strip() for part in parts if len(part.strip()) >= 6]


def _search_fragments(page: fitz.Page, text: str) -> tuple[list[list[float]], str]:
    fragments = _split_quote_fragments(text)
    for fragment in fragments:
        hits = page.search_for(fragment)
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            return rects, fragment
        normalized_fragment = _normalize_quote_search(fragment)
        if normalized_fragment and normalized_fragment != fragment:
            hits = page.search_for(normalized_fragment)
            rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
            if rects:
                return rects, fragment
    return [], ""


def _match_token_fragments(
    quote: str,
    page_number: int,
    tokens: Sequence[dict[str, object]],
) -> tuple[list[float] | None, float | None]:
    fragments = _split_quote_fragments(quote)
    if not fragments:
        return None, None
    for fragment in fragments:
        rect, score = _match_tokens(fragment, page_number, tokens)
        if rect:
            return rect, score
    return None, None


def _match_tokens_fuzzy(
    quote: str,
    page_number: int,
    tokens: Sequence[dict[str, object]],
    threshold: int = 78,
) -> tuple[list[float] | None, float | None]:
    quote_words = _normalize_words(quote)
    if not quote_words:
        return None, None
    page_tokens = [
        token
        for token in tokens
        if int(token.get("page", 0)) == page_number and token.get("text")
    ]
    normalized_tokens = [_normalize_words(str(token["text"])) for token in page_tokens]
    flattened = [words[0] for words in normalized_tokens if words]
    if not flattened:
        return None, None
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
        return None, None
    matched = page_tokens[best_span[0] : best_span[1]]
    xs0 = [token["bbox"][0] for token in matched if token.get("bbox")]
    ys0 = [token["bbox"][1] for token in matched if token.get("bbox")]
    xs1 = [token["bbox"][2] for token in matched if token.get("bbox")]
    ys1 = [token["bbox"][3] for token in matched if token.get("bbox")]
    if not xs0 or not ys0 or not xs1 or not ys1:
        return None, None
    return [min(xs0), min(ys0), max(xs1), max(ys1)], best_score / 100.0


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


def _best_page_text_match(quote: str, page_text: str, threshold: int = 80) -> tuple[str, str] | None:
    if not quote or not page_text:
        return None
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return None
    for line in lines:
        if quote in line:
            return line, "page_text_exact"
    normalized_quote = _normalize_quote_search(quote)
    for line in lines:
        if normalized_quote and normalized_quote in _normalize_quote_search(line):
            return line, "page_text_normalized"
    best_line = ""
    best_score = 0
    for line in lines:
        score = fuzz.partial_ratio(normalized_quote, _normalize_quote_search(line))
        if score > best_score:
            best_score = score
            best_line = line
    if best_score >= threshold and best_line:
        return best_line, "page_text_fuzzy"
    return None


def assess_highlight_rects(
    quote: str,
    rects: list[list[float]],
    page_height: float | None,
    match_score: float | None,
) -> tuple[bool, str | None]:
    if not rects:
        return False, "no_rects"
    if match_score is not None and match_score < 0.6:
        return False, "match_score_too_low"
    quote_words = _normalize_words(quote)
    word_count = len(quote_words)
    if word_count and len(rects) > max(12, word_count * 4):
        return False, "rejected_rect_explosion"
    if page_height:
        y0 = min(rect[1] for rect in rects)
        y1 = max(rect[3] for rect in rects)
        if (y1 - y0) / page_height > 0.3:
            return False, "rejected_page_span"
    return True, None
