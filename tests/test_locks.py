import pytest

pd = pytest.importorskip("pandas")

from paper_table_agent.io.locks import is_empty


def test_single_space_is_empty():
    assert is_empty(" ")
    assert is_empty("")
    assert not is_empty("x")


def test_nan_is_empty():
    assert is_empty(float("nan"))
    assert is_empty(pd.NA)
