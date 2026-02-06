from __future__ import annotations

from pathlib import Path

from paper_table_agent.config import ExtractionConfig
from paper_table_agent.graph.context_planner import plan_context
from paper_table_agent.graph.extraction import GroupContext, extract_group
from paper_table_agent.llm.client import LlmClient, LlmConfig
from paper_table_agent.pdf.highlight import locate_quote, locate_quote_span
from paper_table_agent.pdf.parser import parse_pdf


def test_fulltext_context_plan_and_extraction_with_spans(tmp_path: Path) -> None:
    fixture_pdf = Path(__file__).resolve().parent / "fixtures" / "pdfs" / "minimal_paper.pdf"
    parsed = parse_pdf(fixture_pdf)
    extract_client = LlmClient(
        LlmConfig(
            mode="stub",
            base_url="http://localhost:1234/v1",
            api_key=None,
            model="gpt-oss-test",
            max_prompt_tokens=8000,
        )
    )
    helper_client = LlmClient(
        LlmConfig(
            mode="stub",
            base_url="http://localhost:1234/v1",
            api_key=None,
            model="gpt-oss-test",
        )
    )
    extraction_config = ExtractionConfig()
    extraction_config.thinking_models = ["gpt-oss-test"]
    column_payloads = [{"col_id": 1, "name": "Title", "description": "Paper title", "examples": []}]
    row_context = {"row_id": "1", "title": ""}
    plan, context_payload = plan_context(
        pdf_id="pdf-1",
        page_text=parsed.page_text,
        column_payloads=column_payloads,
        row_context=row_context,
        extract_client=extract_client,
        helper_client=helper_client,
        extraction_config=extraction_config,
        run_dir=tmp_path,
    )
    assert plan.mode == "fulltext"
    group = GroupContext(
        name="title",
        columns=["Title"],
        schema={"Title": "Paper title"},
        examples={},
        columns_payload=column_payloads,
        column_id_map={1: "Title"},
        column_key_map={"title": "Title"},
    )
    extraction = extract_group(
        extract_client,
        row_context,
        group,
        chunks_by_column={"Title": []},
        mapping_dependent=False,
        pdf_id="pdf-1",
        context_mode=plan.mode,
        context_payload=context_payload,
        page_text=parsed.page_text,
    )
    assert extraction.proposals
    evidence = extraction.proposals[0].evidence
    assert evidence
    quote = evidence[0].quote
    span = locate_quote_span(parsed.page_text[0], quote)
    assert span is not None
    result = locate_quote(str(fixture_pdf), quote, 1, tokens=parsed.tokens, allow_fuzzy=False)
    assert result.found
