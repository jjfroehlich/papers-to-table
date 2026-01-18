from pathlib import Path

import pytest

pd = pytest.importorskip("pandas")

from paper_table_agent.config import validate_schema_columns
from paper_table_agent.io.schema import load_schema


def test_load_schema(tmp_path: Path):
    df = pd.DataFrame(
        {
            "column_name": ["title", "authors"],
            "description": ["Paper title", "Authors list"],
            "group": ["identity", "identity"],
        }
    )
    path = tmp_path / "schema.xlsx"
    with pd.ExcelWriter(path) as writer:
        df.to_excel(writer, sheet_name="schema", index=False)
    specs = load_schema(path, "schema")
    assert specs[0].column_name == "title"
    assert specs[0].group == "identity"


def test_validate_schema_columns_missing():
    with pytest.raises(ValueError):
        validate_schema_columns(["title"], ["other"])
