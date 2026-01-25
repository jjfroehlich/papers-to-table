from types import SimpleNamespace

from paper_table_agent.graph.runner import _build_column_query
from paper_table_agent.text.normalization import normalize_chunk_id, normalize_str_for_prompt


def test_normalize_str_for_prompt_filters_nan() -> None:
    assert normalize_str_for_prompt(None) == ""
    assert normalize_str_for_prompt(float("nan")) == ""
    assert normalize_str_for_prompt(" nan ") == ""
    assert normalize_str_for_prompt("—") == ""
    assert normalize_str_for_prompt("Value") == "Value"


def test_normalize_chunk_id_unifies_unicode_dash() -> None:
    assert normalize_chunk_id("para‑2‑1") == "para-2-1"


def test_build_column_query_omits_empty_examples() -> None:
    spec = SimpleNamespace(column_name="Metric", description="Accuracy value")
    row_context = {"title": "Paper Title", "authors": None, "year": "2024"}
    examples_map = {"Metric": [{"value": "nan"}, {"value": ""}]}
    query = _build_column_query(spec, row_context, examples_map)
    assert "examples:" not in query
    assert "row:" in query
