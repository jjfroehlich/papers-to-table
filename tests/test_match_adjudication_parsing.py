from __future__ import annotations

from paper_table_agent.graph import matching
from paper_table_agent.llm.models import AdjudicationResult


def test_adjudication_tolerates_string_candidates_and_evidence() -> None:
    candidates = [
        matching.RowCandidate(
            row_id="row-1",
            title="Paper A",
            authors="Doe",
            year="2024",
            doi="10.1234/example",
            score=0.92,
            title_score=0.9,
            author_score=0.9,
            year_bonus=0.02,
            doi_bonus=0.0,
        )
    ]
    payload = {
        "row_id": "row-1",
        "status": "matched",
        "top_candidates": [
            "row-1",
            '{"row_id": "row-2", "score": 0.31, "title": "Paper B"}',
        ],
        "confidence": 0.92,
        "rationale": "Match on title",
        "evidence_items": [
            "Title match evidence",
            {"quote_text": "Paper A"},
        ],
    }
    result = AdjudicationResult.model_validate(payload)
    valid, reason = matching._validate_adjudication(result, candidates)
    assert valid, reason
    assert result.top_candidates[0]["row_id"] == "row-1"
    assert result.evidence[0].quote == "Title match evidence"
