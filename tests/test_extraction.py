from paper_table_agent.graph.extraction import _apply_evidence_rules
from paper_table_agent.llm.models import EvidenceQuote, ProposalItem


def test_apply_evidence_rules_rejects_missing_chunk_id():
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
    _apply_evidence_rules(proposal, {"chunk-1": "42"})
    assert proposal.status == "unclear"
    assert proposal.proposed_value is None
    assert "evidence_validation_errors" in proposal.flags


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
    _apply_evidence_rules(proposal, {"chunk-1": "Value was 42 in the results."})
    assert proposal.status == "found"
    assert proposal.proposed_value == "42"
