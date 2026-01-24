from pathlib import Path

import pytest

from paper_table_agent.pdf.highlight import locate_quote


def test_locate_quote_finds_bbox_in_fixture_pdf() -> None:
    fitz = pytest.importorskip("fitz")
    _ = fitz
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    result = locate_quote(str(fixture_pdf), "Minimal Paper", 1, tokens=[])
    assert result.found
    assert result.rects
