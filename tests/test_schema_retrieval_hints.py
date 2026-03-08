from pathlib import Path

from paper_table_agent.io.schema import load_schema


def test_schema_retrieval_hint_column_loaded(tmp_path: Path):
    schema = tmp_path / "schema.csv"
    schema.write_text("column_name,description,retrieval_hint\nDose,Dose amount,table-first\n", encoding="utf-8")
    specs = load_schema(schema, "schema")
    assert specs[0].retrieval_hint == "table-first"
