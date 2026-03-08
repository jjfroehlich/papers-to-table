from pathlib import Path

from paper_table_agent.pdf.parser import parse_pdf


def test_parse_pdf_emits_parsed_document_fixture():
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    parsed = parse_pdf(fixture_pdf)
    assert parsed.parsed_document is not None
    assert parsed.parsed_document.elements
    assert parsed.parsed_document.element_type_counts().get("paragraph", 0) >= 1
