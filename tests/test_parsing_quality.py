from pathlib import Path

import pytest

from paper_table_agent.config import OcrConfig
from paper_table_agent.graph.runner import _parse_sanity_metrics
from paper_table_agent.pdf.parser import parse_pdf


def test_parsing_preserves_spaces_and_token_lengths() -> None:
    pytest.importorskip("fitz")
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    parsed = parse_pdf(fixture_pdf)
    assert parsed.page_text, "Expected parsed text for fixture PDF"
    assert any(" " in page for page in parsed.page_text), "Expected spaces in parsed text"

    metrics = _parse_sanity_metrics(parsed.page_text, parsed.tokens, OcrConfig())
    assert metrics["whitespace_ratio"] >= 0.04, "Whitespace ratio too low; tokens may be glued"
    assert metrics["avg_token_length"] <= 18.0, "Average token length too high; tokens may be glued"
