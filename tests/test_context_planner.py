from __future__ import annotations

from paper_table_agent.config import ExtractionConfig
from paper_table_agent.graph.context_planner import _trim_fulltext


def test_fulltext_trimming_drops_references_first() -> None:
    config = ExtractionConfig()
    text = "\n".join(
        [
            "Introduction",
            "We describe the method.",
            "Acknowledgements",
            "Thanks to collaborators.",
            "References",
            "1. Example Ref",
        ]
    )
    trimmed, _sections, steps = _trim_fulltext(text, config)
    assert "References" not in trimmed
    assert "Acknowledgements" not in trimmed
    assert "drop_references" in steps

from paper_table_agent.pdf.parsed_document import ParsedDocument, ParsedElement


def test_plan_context_uses_typed_elements_for_fulltext(tmp_path):
    from paper_table_agent.graph.context_planner import plan_context
    from paper_table_agent.config import ExtractionConfig
    from paper_table_agent.llm.client import LlmClient, LlmConfig

    extract = LlmClient(LlmConfig(mode="stub", base_url="http://localhost:1234/v1", api_key=None, model="gpt-oss-test", max_prompt_tokens=8000))
    helper = LlmClient(LlmConfig(mode="stub", base_url="http://localhost:1234/v1", api_key=None, model="gpt-oss-test"))
    cfg = ExtractionConfig()
    cfg.thinking_models = ["gpt-oss-test"]
    parsed = ParsedDocument("pdf1", "Title", ["x"], [ParsedElement("e1", "figure_caption", "Figure 1 caption", 1, 1, 1)])
    plan, payload = plan_context(
        "pdf1",
        ["x"],
        [{"name": "Outcome", "description": "desc"}],
        {"title": "row"},
        extract,
        helper,
        cfg,
        tmp_path,
        parsed_document=parsed,
    )
    assert "<figure_caption" in payload
    assert plan.element_diagnostics and plan.element_diagnostics["element_counts"].get("figure_caption") == 1
