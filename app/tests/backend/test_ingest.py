"""Tests for spreadsheet loading, schema loading, and cell eligibility."""
from __future__ import annotations

import csv
import io
import pathlib

import openpyxl
import pandas as pd
import pytest

from backend.app.ingest import (
    REQUIRED_METADATA_COLS,
    TRIVIAL_PLACEHOLDERS,
    classify_cell_eligibility,
    get_eligible_cells,
    is_trivial_placeholder,
    load_schema,
    load_table,
    validate_metadata_columns,
    validate_schema_columns,
    xlsx_data_start_row,
)

FIXTURE_TABLE = "tests/fixtures/tables/literature_fixture.xlsx"
FIXTURE_TABLE_CSV = "tests/fixtures/tables/literature_fixture_table.csv"
FIXTURE_SCHEMA = "tests/fixtures/tables/literature_fixture_schema.csv"


class TestLoadTable:
    def test_xlsx_has_required_columns(self):
        df = load_table(FIXTURE_TABLE)
        for col in ["Title", "Authors", "Publication Year"]:
            assert col in df.columns

    def test_xlsx_has_rows(self):
        df = load_table(FIXTURE_TABLE)
        assert len(df) > 0

    def test_csv_bom_safe(self):
        df = load_table(FIXTURE_TABLE_CSV)
        # BOM-safe loading: first column should not have BOM prefix
        assert "Authors" in df.columns
        assert "\ufeffAuthors" not in df.columns

    def test_csv_has_rows(self):
        df = load_table(FIXTURE_TABLE_CSV)
        assert len(df) > 0

    def test_returns_dataframe(self):
        df = load_table(FIXTURE_TABLE)
        assert isinstance(df, pd.DataFrame)

    def test_all_cells_are_strings(self):
        df = load_table(FIXTURE_TABLE)
        for col in df.columns:
            for val in df[col]:
                assert isinstance(val, str), f"Non-string in column {col}: {val!r}"


class TestLoadSchema:
    def test_loads_from_csv(self):
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        assert len(schema) > 0

    def test_schema_entries_have_required_fields(self):
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        for entry in schema:
            assert "column_name" in entry
            assert "description" in entry

    def test_schema_has_metadata_columns(self):
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        col_names = {s["column_name"] for s in schema}
        assert "Title" in col_names
        assert "Authors" in col_names

    def test_schema_none_path_empty_list(self, tmp_path):
        # No schema_path and no Schema sheet in XLSX
        schema = load_schema(None, str(tmp_path / "nonexistent.xlsx"))
        assert schema == []

    def test_loads_improved_description_alias_from_csv(self, tmp_path: pathlib.Path):
        schema_path = tmp_path / "schema.csv"
        schema_path.write_text(
            "column_name,improved_description\n"
            "Species,Animal species used in the assay\n",
            encoding="utf-8",
        )

        schema = load_schema(str(schema_path), str(tmp_path / "table.xlsx"))

        assert schema == [
            {
                "column_name": "Species",
                "description": "Animal species used in the assay",
                "field_type": None,
                "allowed_values": None,
            }
        ]

    def test_loads_inline_schema_row_from_xlsx_when_no_schema_path(self, tmp_path: pathlib.Path):
        workbook_path = tmp_path / "inline.xlsx"
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.append(["Title", "Authors", "Publication Year", "Species", "Model system"])
        sheet.append([
            "Exact title of the publication",
            "Full author list of the paper",
            "4-digit year of publication",
            "Species of origin of the biological system being assayed",
            "Experimental system in which the assay was performed",
        ])
        sheet.append(["Paper A", "Smith", "2024", "human", "HEK293T"])
        workbook.save(workbook_path)

        schema = load_schema(None, str(workbook_path))

        assert xlsx_data_start_row(str(workbook_path)) == 3
        assert schema[0]["column_name"] == "Title"
        assert schema[0]["description"] == "Exact title of the publication"
        assert any(entry["column_name"] == "Species" for entry in schema)


class TestInlineSchemaTableLayout:
    def test_load_table_skips_inline_description_row(self, tmp_path: pathlib.Path):
        workbook_path = tmp_path / "inline.xlsx"
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.append(["Title", "Authors", "Publication Year", "Species"])
        sheet.append([
            "Exact title of the publication",
            "Full author list of the paper",
            "4-digit year of publication",
            "Species of origin of the biological system being assayed",
        ])
        sheet.append(["Paper A", "Smith", "2024", "human"])
        sheet.append(["Paper B", "Jones", "2023", "mouse"])
        workbook.save(workbook_path)

        df = load_table(str(workbook_path))

        assert list(df["Title"]) == ["Paper A", "Paper B"]
        assert xlsx_data_start_row(str(workbook_path)) == 3


class TestValidateMetadataColumns:
    def test_ok_with_fixture(self):
        df = load_table(FIXTURE_TABLE)
        errors = validate_metadata_columns(df)
        assert errors == []

    def test_missing_title(self):
        df = pd.DataFrame({"Authors": ["A"], "Publication Year": ["2020"]})
        errors = validate_metadata_columns(df)
        assert any("Title" in e for e in errors)

    def test_missing_authors(self):
        df = pd.DataFrame({"Title": ["T"], "Publication Year": ["2020"]})
        errors = validate_metadata_columns(df)
        assert any("Authors" in e for e in errors)

    def test_missing_publication_year(self):
        df = pd.DataFrame({"Title": ["T"], "Authors": ["A"]})
        errors = validate_metadata_columns(df)
        assert any("Publication Year" in e for e in errors)

    def test_all_missing(self):
        df = pd.DataFrame({"Other": ["x"]})
        errors = validate_metadata_columns(df)
        assert len(errors) == 3


class TestValidateSchemaColumns:
    def test_ok_with_valid_schema(self):
        schema = [
            {"column_name": "Title", "description": "Title of the paper"},
            {"column_name": "Abstract", "description": "Abstract text"},
        ]
        errors = validate_schema_columns(schema)
        assert errors == []

    def test_missing_column_name(self):
        schema = [{"column_name": "", "description": "Some description"}]
        errors = validate_schema_columns(schema)
        assert len(errors) > 0

    def test_missing_description(self):
        schema = [{"column_name": "Col", "description": ""}]
        errors = validate_schema_columns(schema)
        assert len(errors) > 0


class TestIsTrivialPlaceholder:
    def test_trivial_values(self):
        for val in ["n/a", "N/A", "tbd", "TBD", "-", "--", "unknown", "none", "?"]:
            assert is_trivial_placeholder(val), f"Expected trivial: {val!r}"

    def test_non_trivial_values(self):
        for val in ["Some value", "HEK293T", "2020", "Yes", "No"]:
            assert not is_trivial_placeholder(val), f"Expected non-trivial: {val!r}"

    def test_empty_string_not_trivial(self):
        # empty string is handled by classify_cell_eligibility separately
        assert not is_trivial_placeholder("")


class TestClassifyCellEligibility:
    def test_empty_string_eligible(self):
        assert classify_cell_eligibility("") == "eligible"

    def test_whitespace_eligible(self):
        assert classify_cell_eligibility("   ") == "eligible"

    def test_trivial_placeholder(self):
        assert classify_cell_eligibility("n/a") == "placeholder"
        assert classify_cell_eligibility("TBD") == "placeholder"

    def test_filled_not_verify_mode(self):
        assert classify_cell_eligibility("HEK293T") == "already_filled"

    def test_filled_with_verify_mode(self):
        assert classify_cell_eligibility("HEK293T", verify_mode=True) == "eligible"

    def test_placeholder_with_verify_mode(self):
        assert classify_cell_eligibility("n/a", verify_mode=True) == "placeholder"


class TestGetEligibleCells:
    def test_returns_list(self):
        df = load_table(FIXTURE_TABLE)
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        cells = get_eligible_cells(df, schema, verify_mode=False)
        assert isinstance(cells, list)

    def test_cell_structure(self):
        df = load_table(FIXTURE_TABLE)
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        cells = get_eligible_cells(df, schema, verify_mode=False)
        assert len(cells) > 0
        for cell in cells[:5]:  # check a sample
            assert "row_id" in cell
            assert "row_index" in cell
            assert "column_name" in cell
            assert "current_value" in cell
            assert "eligibility" in cell

    def test_metadata_cols_excluded(self):
        df = load_table(FIXTURE_TABLE)
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        cells = get_eligible_cells(df, schema, verify_mode=False)
        for cell in cells:
            assert cell["column_name"] not in {"Title", "Authors", "Publication Year"}

    def test_verify_mode_includes_more_cells(self):
        df = load_table(FIXTURE_TABLE)
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        normal = get_eligible_cells(df, schema, verify_mode=False)
        verify = get_eligible_cells(df, schema, verify_mode=True)
        assert len(verify) >= len(normal)

    def test_row_ids_deterministic(self):
        df = load_table(FIXTURE_TABLE)
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        cells1 = get_eligible_cells(df, schema, verify_mode=False)
        cells2 = get_eligible_cells(df, schema, verify_mode=False)
        ids1 = {c["row_id"] for c in cells1}
        ids2 = {c["row_id"] for c in cells2}
        assert ids1 == ids2
