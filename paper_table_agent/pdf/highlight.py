from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Sequence

import fitz

from paper_table_agent.text.normalization import normalize_text

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
    normalized = normalize_text(quote)
    hits = page.search_for(normalized)
    rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
    if rects:
        doc.close()
        return HighlightResult(rects=rects, found=True, strategy="normalized")
    if locator_hint:
        hits = page.search_for(locator_hint)
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            return HighlightResult(rects=rects, found=True, strategy="locator_hint")
        normalized_hint = normalize_text(locator_hint)
        hits = page.search_for(normalized_hint)
        rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
        if rects:
            doc.close()
            return HighlightResult(rects=rects, found=True, strategy="locator_hint_normalized")
    if tokens:
        rect = _match_tokens(quote, page_number, tokens)
        if rect:
            doc.close()
            return HighlightResult(rects=[rect], found=True, strategy="tokens")
    doc.close()
    return HighlightResult(rects=[], found=False, strategy="missing")


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
    return None


def _normalize_words(text: str) -> list[str]:
    cleaned = normalize_text(text)
    cleaned = re.sub(r"[^0-9A-Za-z]+", " ", cleaned).strip().lower()
    return [word for word in cleaned.split() if word]
