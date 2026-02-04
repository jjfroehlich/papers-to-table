from pathlib import Path

from paper_table_agent.graph.evidence_finder import find_evidence_for_proposals


def test_fallback_evidence_attached_when_missing() -> None:
    fixtures = Path(__file__).resolve().parent / "fixtures" / "pdfs"
    pdf_path = fixtures / "minimal_paper.pdf"
    proposals = [
        {
            "proposal_id": "p1",
            "pdf_id": "pdf-1",
            "row_id": "1",
            "column": "Outcome",
            "proposed_value": "42",
            "status": "found",
            "confidence": 0.8,
            "evidence": [],
            "flags": {},
        }
    ]
    chunks = [
        {
            "chunk_id": "page-1",
            "chunk_idx": 1,
            "chunk_pk": "pk-1",
            "text": "The outcome improved significantly with a reported value of 42 in the results section.",
            "text_raw": "The outcome improved significantly with a reported value of 42 in the results section.",
            "text_norm": "outcome improved significantly reported value 42 results section",
            "page_start": 1,
            "page_end": 1,
        }
    ]
    refreshed = find_evidence_for_proposals(proposals, chunks, page_text=None, tokens=None, pdf_path=str(pdf_path))
    evidence_items = refreshed[0].get("evidence") or []
    flags = refreshed[0].get("flags") or {}
    assert evidence_items
    assert flags.get("needs_more_evidence") is True
    assert flags.get("evidence_finder_attempted") is True


def test_rejects_too_short_highlight_quote() -> None:
    fixtures = Path(__file__).resolve().parent / "fixtures" / "pdfs"
    pdf_path = fixtures / "minimal_paper.pdf"
    proposals = [
        {
            "proposal_id": "p2",
            "pdf_id": "pdf-1",
            "row_id": "1",
            "column": "Outcome",
            "proposed_value": "b",
            "status": "found",
            "confidence": 0.8,
            "evidence": [
                {
                    "quote": "b",
                    "page": 1,
                    "chunk_id": "page-1",
                }
            ],
            "flags": {"evidence_quality": "strong"},
        }
    ]
    chunks = [
        {
            "chunk_id": "page-1",
            "chunk_idx": 1,
            "chunk_pk": "pk-1",
            "text": "Minimal Paper",
            "text_raw": "Minimal Paper",
            "text_norm": "minimal paper",
            "page_start": 1,
            "page_end": 1,
        }
    ]
    refreshed = find_evidence_for_proposals(proposals, chunks, page_text=None, tokens=None, pdf_path=str(pdf_path))
    evidence_items = refreshed[0].get("evidence") or []
    assert evidence_items
    assert evidence_items[0].get("highlight_status") == "failed"
    assert evidence_items[0].get("highlight_rejection_reason") == "quote_too_short"
