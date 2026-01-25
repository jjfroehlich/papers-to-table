from paper_table_agent.graph.extraction import _apply_evidence_rules
from paper_table_agent.llm.models import EvidenceQuote, ProposalItem


def test_apply_evidence_rules_repairs_missing_chunk_id():
    proposal = ProposalItem(
        column="Metric",
        proposed_value="42",
        status="found",
        confidence=0.9,
        evidence=[EvidenceQuote(quote="42", page=1, chunk_id=None)],
        needs_more_evidence=None,
        flags={},
        rationale="",
    )
    _apply_evidence_rules(
        proposal,
        {
            "chunk-1": {
                "text": "42",
                "page_start": 1,
                "page_end": 1,
            }
        },
    )
    assert proposal.status == "found"
    assert proposal.proposed_value == "42"
    assert proposal.flags.get("evidence_quality") == "strong"


def test_apply_evidence_rules_accepts_valid_quote():
    proposal = ProposalItem(
        column="Metric",
        proposed_value="42",
        status="found",
        confidence=0.9,
        evidence=[EvidenceQuote(quote="42", page=1, chunk_id="chunk-1")],
        needs_more_evidence=None,
        flags={},
        rationale="",
    )
    _apply_evidence_rules(
        proposal,
        {
            "chunk-1": {
                "text": "Value was 42 in the results.",
                "page_start": 1,
                "page_end": 1,
            }
        },
    )
    assert proposal.status == "found"
    assert proposal.proposed_value == "42"
    assert proposal.flags["validation_mode"] == "exact"


def test_apply_evidence_rules_accepts_normalized_quote():
    proposal = ProposalItem(
        column="Metric",
        proposed_value="classifiers achieved",
        status="found",
        confidence=0.9,
        evidence=[EvidenceQuote(quote="classifiers achieved", page=1, chunk_id="chunk-1")],
        needs_more_evidence=None,
        flags={},
        rationale="",
    )
    _apply_evidence_rules(
        proposal,
        {
            "chunk-1": {
                "text": "classifiersachieved",
                "text_raw": "classifiersachieved",
                "page_start": 1,
                "page_end": 1,
            }
        },
    )
    assert proposal.status == "found"
    assert proposal.flags["validation_mode"] == "normalized"


def test_apply_evidence_rules_accepts_chunk_id_unicode_dash():
    proposal = ProposalItem(
        column="Metric",
        proposed_value="42",
        status="found",
        confidence=0.9,
        evidence=[EvidenceQuote(quote="42", page=1, chunk_id="chunk‑1")],
        needs_more_evidence=None,
        flags={},
        rationale="",
    )
    _apply_evidence_rules(
        proposal,
        {
            "chunk-1": {
                "text": "Value was 42 in the results.",
                "page_start": 1,
                "page_end": 1,
            }
        },
    )
    assert proposal.status == "found"
    assert proposal.flags["validation_mode"] == "exact"


def test_apply_evidence_rules_salvages_quote_span():
    chunk_text = "The accuracy was 42 percent in the results section."
    proposal = ProposalItem(
        column="Metric",
        proposed_value="42%",
        status="found",
        confidence=0.9,
        evidence=[EvidenceQuote(quote="accuracy ... 42%", page=1, chunk_id="chunk-1")],
        needs_more_evidence=None,
        flags={},
        rationale="",
    )
    _apply_evidence_rules(
        proposal,
        {
            "chunk-1": {
                "text": chunk_text,
                "text_raw": chunk_text,
                "page_start": 1,
                "page_end": 1,
            }
        },
    )
    assert proposal.evidence[0].quote in chunk_text
    assert "quote_salvaged" in proposal.flags.get("evidence_validation_errors", [])
