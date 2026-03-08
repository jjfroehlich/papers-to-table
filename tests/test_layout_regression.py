import json
from pathlib import Path

from paper_table_agent.pdf.parsed_document import ParsedDocument, ParsedElement
from paper_table_agent.retrieval.chunking import build_chunks


def test_layout_regression_samples_emit_expected_typed_chunks():
    fixture = Path(__file__).resolve().parent / "fixtures" / "layout_samples.json"
    samples = json.loads(fixture.read_text(encoding="utf-8"))
    parsed = ParsedDocument(
        pdf_id="layout",
        title="Layout Fixture",
        page_text=[samples["multi_column"], samples["table_heavy"], samples["caption_heavy"]],
        elements=[
            ParsedElement("e1", "paragraph", samples["multi_column"], 1, 1, 1, heading="Introduction"),
            ParsedElement("e2", "table_region", samples["table_heavy"], 2, 2, 2, heading="Results"),
            ParsedElement("e3", "figure_caption", samples["caption_heavy"], 3, 3, 3, heading="Results"),
        ],
    )
    chunks = build_chunks(parsed.page_text, parsed_document=parsed, pdf_id="layout")
    types = {c.chunk_type for c in chunks}
    assert "table_region" in types
    assert "table_cell_summary" in types
    assert "figure_caption" in types
