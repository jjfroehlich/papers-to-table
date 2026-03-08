from paper_table_agent.ui.review_queue import apply_review_filters, risk_reasons, triage_score


def test_triage_and_filters():
    proposals = [
        {"proposal_id": "1", "status": "inferred", "flags": {"needs_more_evidence": True}},
        {"proposal_id": "2", "status": "found", "flags": {"table_derived": True, "table_evidence_present": False}},
        {"proposal_id": "3", "status": "found", "flags": {}},
    ]
    assert triage_score(proposals[0]) > triage_score(proposals[2])
    assert "weak_evidence" in risk_reasons(proposals[0])
    filtered = apply_review_filters(proposals, weak_evidence=True)
    assert [item["proposal_id"] for item in filtered] == ["1"]
