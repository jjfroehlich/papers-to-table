from __future__ import annotations

from paper_table_agent.graph.extraction import verify_proposals


def test_verify_proposals_downgrades_when_no_overlap() -> None:
    proposals = [
        {
            "column": "Outcome",
            "proposed_value": "High accuracy",
            "status": "found",
            "evidence": [{"quote_text": "The assay uses mice in vitro."}],
            "flags": {},
        }
    ]
    updated = verify_proposals(None, proposals)
    assert updated[0]["status"] == "inferred"
    assert updated[0]["flags"]["verification_needs_more_evidence"] is True


def test_verify_proposals_requires_numeric_overlap() -> None:
    proposals = [
        {
            "column": "Dose",
            "proposed_value": "12 mg",
            "status": "found",
            "evidence": [{"quote_text": "We used a dose of 8 mg for all mice."}],
            "flags": {},
        }
    ]
    updated = verify_proposals(None, proposals)
    assert updated[0]["status"] == "inferred"
    assert updated[0]["flags"]["verification_needs_more_evidence"] is True


def test_verify_proposals_accepts_numeric_match() -> None:
    proposals = [
        {
            "column": "Dose",
            "proposed_value": "12 mg",
            "status": "found",
            "evidence": [{"quote_text": "We used a dose of 12 mg for all mice."}],
            "flags": {},
        }
    ]
    updated = verify_proposals(None, proposals)
    assert updated[0]["status"] == "found"
    assert updated[0]["flags"]["verification_needs_more_evidence"] is False
