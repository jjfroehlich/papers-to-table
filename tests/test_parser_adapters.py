from paper_table_agent.pdf.grobid import GrobidResult, grobid_to_parsed_document


def test_grobid_adapter_normalizes_parsed_document():
    result = GrobidResult(
        title="A title",
        authors=["A"],
        abstract="Abstract here",
        sections=[{"title": "Methods", "text": "Method text"}],
        references=["[1] Ref"],
    )
    parsed = grobid_to_parsed_document(result, "pdf1", ["Page one"])
    types = {el.element_type for el in parsed.elements}
    assert "abstract" in types
    assert "section_header" in types
    assert "paragraph" in types
    assert "reference_block" in types
