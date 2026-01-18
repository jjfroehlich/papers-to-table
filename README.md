# Paper Table Agent

Local-first batch PDF → table proposals with evidence, plus post-run row review.

## Status

- **Core scaffold**: package, CLI, Streamlit UI, and SQLite storage.
- **Batch pipeline**: PDF parsing, matching, retrieval, and proposal extraction are wired end-to-end.
- **Review/Export**: row review + export flow is available via UI and CLI.

Known gaps to improve in future iterations:
- Retrieval quality tuning (dense embedding + reranker models).
- Evidence locator robustness for complex PDFs.

## Installation

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
```

## Usage

### Run UI

```bash
paper-table-agent ui
```

### Run batch pipeline (CLI)

Create a run config JSON (example):

```json
{
  "table_path": "data/table.xlsx",
  "schema_sheet_name": "schema",
  "schema_mode": "sheet",
  "pdf_folder": "data/pdfs",
  "title_col": "Title",
  "authors_col": "Authors",
  "year_col": "Year",
  "treat_single_space_as_empty": true,
  "verify_mode": false,
  "fast_mode": false,
  "max_success_mode": true,
  "provider": {
    "base_url": "http://localhost:1234/v1",
    "api_key": null,
    "model_extract": "local-extract",
    "model_query_helper": "local-helper",
    "mock_mode": false,
    "mock_payloads_path": null
  },
  "matching": {
    "top_k": 10,
    "confidence_threshold": 0.75,
    "year_tolerance": 1
  },
  "extraction": {
    "groups": [],
    "examples_per_col": 3,
    "max_chunks": 20
  },
  "ocr": {
    "enable_ocr": true,
    "ocr_trigger_min_chars_per_page": 400
  },
  "max_workers": 1
}
```

```bash
paper-table-agent run --config run_config.json
```

### Export decisions

```bash
paper-table-agent export --run_dir runs/<timestamp>__<table>/
```

## Input schema sheet

Provide a `schema` sheet with at least:

- `column_name`
- `description`
- optional `group`, `priority`

## Troubleshooting

- **OCR**: install optional OCR extras if you need hi-res OCR:
  ```bash
  pip install -e .[ocr]
  ```
- **LLM JSON failures**: use `mock_mode` with canned JSON payloads for testing.

## Repository layout

```
paper_table_agent/
  ui/
  store/
  io/
  pdf/
  retrieval/
  llm/
  graph/
  prompts/
```
