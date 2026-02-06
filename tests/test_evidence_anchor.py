from __future__ import annotations

from paper_table_agent.graph.evidence_finder import _extract_quote
from paper_table_agent.graph.extraction import _apply_evidence_rules
from paper_table_agent.llm.models import EvidenceQuote, ProposalItem
from paper_table_agent.pdf.highlight import locate_quote_span


def test_evidence_quotes_use_space_preserving_text() -> None:
    chunk = {
        "chunk_id": "chunk-1",
        "chunk_idx": 1,
        "chunk_pk": "pk-1",
        "page_start": 1,
        "page_end": 1,
        "text": "The sample size was 48,391 participants in total.",
        "text_raw": "The sample size was 48,391 participants in total.",
        "text_norm": "Thesamplesizewas48391participantsintotal.",
    }
    quote, _quality = _extract_quote("48,391", chunk, numeric_required=True, numeric_hint={"proposed_value": "48,391"})
    assert quote in chunk["text_raw"]
    assert " " in quote


def test_quote_locator_finds_span() -> None:
    page_text = "The sample size was 48,391 participants in total."
    span = locate_quote_span(page_text, "48,391 participants")
    assert span is not None
    start, end, strategy, _score = span
    assert page_text[start:end] == "48,391 participants"
    assert strategy in {"text_exact", "text_normalized"}


def test_found_values_require_anchored_quote() -> None:
    proposal = ProposalItem(
        column="Sample size",
        proposed_value="48391",
        status="found",
        confidence=0.9,
        evidence=[
            EvidenceQuote(
                quote_text="The sample size was 12 participants.",
                page=1,
                chunk_id="chunk-1",
            )
        ],
    )
    chunk_lookup = {
        "chunk-1": {
            "text": "The sample size was 12 participants.",
            "text_raw": "The sample size was 12 participants.",
            "text_norm": "Thesamplesizewas12participants.",
            "page_start": 1,
            "page_end": 1,
            "chunk_pk": "pk-1",
            "chunk_idx": 1,
        }
    }
    _apply_evidence_rules(proposal, chunk_lookup)
    assert proposal.status == "inferred"
    assert proposal.flags.get("found_unanchored_downgraded") is True
