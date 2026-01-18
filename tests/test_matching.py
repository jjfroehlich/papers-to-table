import pytest

pytest.importorskip("rapidfuzz")

from paper_table_agent.graph.matching import deterministic_match, shortlist_candidates
from paper_table_agent.llm.models import HeaderExtractionResult


def test_shortlist_candidates():
    header = HeaderExtractionResult(title="Deep Learning in Biology", authors=["Ada Lovelace"])
    rows = [
        {"row_id": "1", "title": "Deep Learning in Biology", "authors": "Ada Lovelace", "year": "2020"},
        {"row_id": "2", "title": "Shallow Nets", "authors": "B", "year": "2019"},
    ]
    candidates = shortlist_candidates(header, rows, top_k=2, year_tolerance=1)
    assert candidates[0].row_id == "1"


def test_deterministic_match_threshold():
    header = HeaderExtractionResult(title="Gene Editing", authors=["Ada Lovelace"])
    rows = [
        {"row_id": "1", "title": "Gene Editing", "authors": "Ada Lovelace", "year": "2021"},
        {"row_id": "2", "title": "Gene Editing", "authors": "Alan Turing", "year": "2021"},
    ]
    candidates = shortlist_candidates(header, rows, top_k=2, year_tolerance=1)
    result = deterministic_match(header, candidates, threshold=0.8)
    assert result is None
