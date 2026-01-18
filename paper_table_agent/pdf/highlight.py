from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import fitz


@dataclass
class HighlightResult:
    rects: list[list[float]]
    found: bool
    strategy: str


def locate_quote(pdf_path: str, quote: str, page_number: int) -> HighlightResult:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)
    hits = page.search_for(quote)
    rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
    if rects:
        return HighlightResult(rects=rects, found=True, strategy="exact")
    normalized = " ".join(quote.split())
    hits = page.search_for(normalized)
    rects = [[hit.x0, hit.y0, hit.x1, hit.y1] for hit in hits]
    if rects:
        return HighlightResult(rects=rects, found=True, strategy="normalized")
    return HighlightResult(rects=[], found=False, strategy="missing")


def apply_highlights(pdf_path: str, page_number: int, rects: Iterable[list[float]]) -> bytes:
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number - 1)
    for rect in rects:
        annotation = page.add_highlight_annot(fitz.Rect(rect))
        annotation.update()
    return doc.tobytes()
