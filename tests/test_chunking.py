from paper_table_agent.pdf.parsed_document import ParsedDocument, ParsedElement
from paper_table_agent.retrieval.chunking import build_chunks


def test_typed_chunk_generation_and_retrieval_text():
    parsed = ParsedDocument(
        pdf_id="p1",
        title="Test Paper",
        page_text=["Abstract text"],
        elements=[
            ParsedElement("e1", "abstract", "Abstract content", 1, 1, 1),
            ParsedElement("e2", "figure_caption", "Figure 1. Caption", 1, 1, 2, heading="Results"),
            ParsedElement("e3", "reference_block", "[1] Ref", 1, 1, 3),
        ],
    )
    chunks = build_chunks(parsed.page_text, parsed_document=parsed, pdf_id="p1")
    types = {c.chunk_type for c in chunks}
    assert {"abstract", "figure_caption", "reference_block"}.issubset(types)
    assert all("type:" in c.retrieval_text for c in chunks)
    assert all(c.text_raw for c in chunks)
