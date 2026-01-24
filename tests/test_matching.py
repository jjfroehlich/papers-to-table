import pytest

pytest.importorskip("rapidfuzz")

from paper_table_agent.graph.matching import deterministic_match, shortlist_candidates, _validate_adjudication
from paper_table_agent.llm.models import AdjudicationResult, HeaderExtractionResult


def test_shortlist_candidates():
    header = HeaderExtractionResult(title="Deep Learning in Biology", authors=["Ada Lovelace"])
    rows = [
        {"row_id": "1", "title": "Deep Learning in Biology", "authors": "Ada Lovelace", "year": "2020", "doi": ""},
        {"row_id": "2", "title": "Shallow Nets", "authors": "B", "year": "2019", "doi": ""},
    ]
    candidates = shortlist_candidates(header, rows, top_k=2, year_tolerance=1)
    assert candidates[0].row_id == "1"


def test_shortlist_candidates_prefers_doi_match():
    header = HeaderExtractionResult(
        title="Shared Title",
        authors=["Ada Lovelace"],
        doi="10.1234/abc",
    )
    rows = [
        {"row_id": "1", "title": "Shared Title", "authors": "Ada Lovelace", "year": "2020", "doi": "10.1234/abc"},
        {"row_id": "2", "title": "Shared Title", "authors": "Ada Lovelace", "year": "2020", "doi": ""},
    ]
    candidates = shortlist_candidates(header, rows, top_k=2, year_tolerance=1)
    assert candidates[0].row_id == "1"


def test_deterministic_match_threshold():
    header = HeaderExtractionResult(title="Gene Editing", authors=["Ada Lovelace"])
    rows = [
        {"row_id": "1", "title": "Gene Editing", "authors": "Ada Lovelace", "year": "2021", "doi": ""},
        {"row_id": "2", "title": "Gene Editing", "authors": "Alan Turing", "year": "2021", "doi": ""},
    ]
    candidates = shortlist_candidates(header, rows, top_k=2, year_tolerance=1)
    result = deterministic_match(header, candidates, threshold=0.95, margin=0.05)
    assert result is not None
    assert result.status == "unmatched"


def test_deterministic_match_margin():
    header = HeaderExtractionResult(title="Single Winner", authors=["Ada Lovelace"])
    rows = [
        {"row_id": "1", "title": "Single Winner", "authors": "Ada Lovelace", "year": "2022", "doi": ""},
        {"row_id": "2", "title": "Different Study", "authors": "Ada", "year": "2022", "doi": ""},
    ]
    candidates = shortlist_candidates(header, rows, top_k=2, year_tolerance=1)
    result = deterministic_match(header, candidates, threshold=0.5, margin=0.05)
    assert result is not None
    assert result.status == "matched"


def test_adjudication_requires_row_id_only_for_matched():
    candidates = [
        type(
            "Candidate",
            (),
            {"row_id": "1"},
        )(),
        type(
            "Candidate",
            (),
            {"row_id": "2"},
        )(),
    ]
    result = AdjudicationResult(row_id="1", status="ambiguous", confidence=0.5, top_candidates=[])
    valid, reason = _validate_adjudication(result, candidates)
    assert not valid
    assert "row_id" in reason
