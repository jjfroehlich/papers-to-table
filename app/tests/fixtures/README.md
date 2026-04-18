# Test Fixtures

This directory contains canonical fixtures used in automated tests and as example inputs for development runs.

## Structure

```
fixtures/
  tables/
    literature_fixture.xlsx          - Main workbook with embedded table data
    literature_fixture_schema.csv    - Column schema (column_name, description)
    literature_fixture_table.csv     - Table export as BOM-encoded CSV
  papers/
    paper_1.pdf                      - Matched to row 1 in the fixture table
    paper_2.pdf                      - Matched to row 2 in the fixture table
    paper_3.pdf                      - Matched to row 3 in the fixture table
    paper_4.pdf                      - Matched to row 4 in the fixture table
    unmatched_1.pdf                  - Intentionally unmatched; tests unmatched-PDF handling
```

## Table format

The fixture table (`literature_fixture.xlsx` / `literature_fixture_table.csv`) contains rows representing scientific publications. Required metadata columns:

| Column            | Role                                        |
|-------------------|---------------------------------------------|
| Title             | Publication title — used for row matching   |
| Authors           | Author list — used for row matching         |
| Publication Year  | Year of publication — used for row matching |

All other columns are extraction targets.

## Schema format

The schema CSV (`literature_fixture_schema.csv`) maps column names to descriptions:

```csv
column_name,description
Title,"Title of the publication, to identify the publication."
Authors,"List of authors, used to identify the publication."
...
```

Every schema entry must have both `column_name` and `description` populated.

## Canonical config

The root `config.example.json` points to these fixtures and is used by backend tests and the documented happy-path workflow.

## Notes

- The CSV files use UTF-8-BOM encoding (Excel default). The backend loading code handles BOM stripping automatically.
- `unmatched_1.pdf` is intentional; tests that expect unmatched PDFs to be detected correctly should include it.
- Do not modify the fixture files without updating the corresponding test assertions.
