from paper_table_agent.pdf.parsed_document import ParsedDocument, ParsedElement
from paper_table_agent.retrieval.chunking import build_chunks


def test_table_region_emits_summary_chunk():
    parsed = ParsedDocument(
        pdf_id="p2",
        title="Table Study",
        page_text=["Table 1\nA 1\nB 2"],
        elements=[ParsedElement("e1", "table_region", "Table 1\nA 1\nB 2", 1, 1, 1)],
    )
    chunks = build_chunks(parsed.page_text, parsed_document=parsed, pdf_id="p2")
    assert any(c.chunk_type == "table_region" for c in chunks)
    assert any(c.chunk_type == "table_cell_summary" for c in chunks)
