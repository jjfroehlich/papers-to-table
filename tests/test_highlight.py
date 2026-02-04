from pathlib import Path

import pytest

from paper_table_agent.pdf.highlight import assess_highlight_rects, locate_quote, salvage_quote_from_tokens


def test_locate_quote_finds_bbox_in_fixture_pdf() -> None:
    fitz = pytest.importorskip("fitz")
    _ = fitz
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    result = locate_quote(str(fixture_pdf), "Minimal Paper", 1, tokens=[])
    assert result.found
    assert result.rects


def test_locate_quote_handles_ellipsis_fragments() -> None:
    fitz = pytest.importorskip("fitz")
    _ = fitz
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    result = locate_quote(str(fixture_pdf), "Minimal … Paper", 1, tokens=[])
    assert result.found
    assert result.rects


def test_salvage_quote_from_tokens_finds_span() -> None:
    tokens = [
        {"text": "Minimal", "page": 1, "bbox": [0.0, 0.0, 10.0, 10.0]},
        {"text": "Paper", "page": 1, "bbox": [12.0, 0.0, 22.0, 10.0]},
    ]
    quote, rect, strategy, score = salvage_quote_from_tokens("Minimal … Paper", 1, tokens)
    assert quote == "Minimal Paper"
    assert rect == [0.0, 0.0, 22.0, 10.0]
    assert strategy.startswith("token_salvage")
    assert score is not None


def test_rejects_page_spanning_rects() -> None:
    rects = [[0.0, 0.0, 10.0, 400.0]]
    quote = "This is a sufficiently long quote for the highlight guard check."
    accept, reason = assess_highlight_rects(quote, rects, page_height=500.0, match_score=0.9)
    assert not accept
    assert reason == "page_span_too_large"
