# Paper Table Agent

Local-first batch PDF → table proposals with evidence, plus post-run row review.

## Status

- **Core scaffold**: package, CLI, Streamlit UI, and SQLite storage.
- **Batch pipeline**: PDF parsing, matching, retrieval (query expansion + HyDE + rerank), and proposal extraction are wired end-to-end with LangGraph checkpoints.
- **Review/Export**: row review + export flow is available via UI and CLI, with PDF evidence highlights.

Known gaps to improve in future iterations:
- Retrieval quality tuning (swap in stronger dense embedding + reranker models).
- Evidence locator robustness for complex PDFs and OCR-heavy scans.

## Requirements
- LM Studio installed. 

## Installation

```bash
python --version  # requires >=3.10
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
```

## Configuration (use with LM Studio)
Set the models in 
```bash
paper_table_agent/config.py
```
For example
```bash
    model_extract: str = "gpt-oss-20b"
    model_query_helper: str = "gpt-oss-20b"
```

## Usage

### Start LM Studio and load required models (e.g. gpt-oss-20b)

### Run UI

```bash
paper-table-agent ui
```

### Run batch pipeline (CLI)

Generate a starter config:

```bash
paper-table-agent init-config --output run_config.json
```

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
  "retrieval": {
    "top_k": 12,
    "rerank_k": 12,
    "max_context_chunks": 16,
    "max_context_tokens": 1800,
    "query_variants": 4,
    "use_query_expansion": true,
    "use_hyde": true,
    "rrf_k": 60
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

### Resume or stop a run

```bash
paper-table-agent resume --run_dir runs/<timestamp>__<table>/
paper-table-agent stop --run_dir runs/<timestamp>__<table>/
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
