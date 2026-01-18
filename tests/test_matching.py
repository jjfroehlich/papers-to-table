import pytest

pytest.importorskip("rapidfuzz")

from paper_table_agent.graph.matching import shortlist_candidates
from paper_table_agent.llm.models import HeaderExtractionResult


def test_shortlist_candidates():
    header = HeaderExtractionResult(title="Deep Learning in Biology")
    rows = [
        {"row_id": "1", "title": "Deep Learning in Biology", "authors": "A", "year": "2020"},
        {"row_id": "2", "title": "Shallow Nets", "authors": "B", "year": "2019"},
    ]
    candidates = shortlist_candidates(header, rows, top_k=2)
    assert candidates[0].row_id == "1"
