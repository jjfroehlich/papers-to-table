from pathlib import Path

import pytest

from paper_table_agent.config import OcrConfig
from paper_table_agent.graph.runner import _parse_sanity_metrics
from paper_table_agent.pdf.parser import parse_pdf
from paper_table_agent.pdf.parser import _strip_repeated_headers


def test_parsing_preserves_spaces_and_token_lengths() -> None:
    pytest.importorskip("fitz")
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    parsed = parse_pdf(fixture_pdf)
    assert parsed.page_text, "Expected parsed text for fixture PDF"
    assert any(" " in page for page in parsed.page_text), "Expected spaces in parsed text"

    metrics = _parse_sanity_metrics(parsed.page_text, parsed.tokens, OcrConfig())
    assert metrics["whitespace_ratio"] >= 0.04, "Whitespace ratio too low; tokens may be glued"
    assert metrics["avg_token_length"] <= 18.0, "Average token length too high; tokens may be glued"


def test_strip_repeated_headers() -> None:
    pages = [
        "Journal of Tests\nPage 1 of 2\nBody line A",
        "Journal of Tests\nPage 2 of 2\nBody line B",
    ]
    cleaned, stats = _strip_repeated_headers(pages)
    assert "Journal of Tests" not in cleaned[0]
    assert "Page 1 of 2" not in cleaned[0]
    assert "Page 2 of 2" not in cleaned[1]
    assert stats["removed_count"] >= 2
