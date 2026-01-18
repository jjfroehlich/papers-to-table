# Paper Table Agent

Local-first batch PDF → table proposals with evidence, plus post-run row review.

## Purpose + use-cases

Paper Table Agent helps you:

- **Backfill missing fields** in a literature table from PDFs with evidence-backed proposals.
- **Verify locked cells** (optional) without overwriting existing values.
- **Audit and export** decisions with a row-by-row review flow.

Typical use-cases:

- Meta-analysis tables (methods, outcomes, cohort details).
- Rapid review spreadsheets with many empty columns.
- Maintaining a canonical table while keeping a proposal/audit trail.

## Status

- **Core pipeline**: PDF parsing, two-pass matching, retrieval (query expansion + HyDE + rerank), and proposal extraction run end-to-end with checkpoints.
- **Review/Export**: row review with Prev/Next navigation, evidence highlights, and export workflow.
- **UI stability**: Streamlit launches through the CLI using subprocess (no bootstrap runtime errors).

Near-term to-do:

- Retrieval quality tuning (swap in stronger dense embedding + reranker models).
- Evidence locator robustness for complex PDFs and OCR-heavy scans.

## Installation
- Have LM Studio installed and get a good model, for example gpt-oss-20b. Set the Context length, under settings, for instance change it from 4,096 to 32,000. 

```bash
python --version  # requires >=3.10
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
```

> **Streamlit version pin**
>
> Streamlit is pinned to `1.32.2` to avoid runtime session errors. Use `paper-table-agent ui` (CLI launches Streamlit via `python -m streamlit run`).

## How to run
### 1) Start LM Studio
### 2) Start the UI

```bash
paper-table-agent ui
```

The Run tab uses dropdowns for tables and PDF folders. Completed runs automatically appear in Review and Export.

### 3) Run the batch pipeline (CLI)

Generate a starter config:

```bash
paper-table-agent init-config --output run_config.json
```

Example config:

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

Run:

```bash
paper-table-agent run --config run_config.json
```

Resume or stop a run:

```bash
paper-table-agent resume --run_dir runs/<timestamp>__<table>/
paper-table-agent stop --run_dir runs/<timestamp>__<table>/
```

Export decisions:

```bash
paper-table-agent export --run_dir runs/<timestamp>__<table>/
```

## How extraction is made reliable

1. **Two-pass matching (Title + Authors first)**
   - Pass A uses RapidFuzz title scoring + author last-name overlap; year is a small tie-breaker.
   - If **exactly one** candidate crosses the threshold, we match deterministically.
   - Otherwise, we invoke the LLM on the top K candidates only.

2. **Hybrid retrieval pipeline (state-of-the-art patterns)**
   - BM25 + dense retrieval + reranking.
   - Multi-query expansion and HyDE for recall.
   - Reciprocal-rank fusion and top-K context packing.

3. **Validation + JSON repair**
   - LLM JSON is strictly validated.
   - Invalid JSON triggers a repair prompt, then is recorded as an error (no silent drops).

4. **Quote substring constraint + highlights**
   - Proposed values must cite evidence quotes + page numbers.
   - Highlights use PyMuPDF `search_for` with fallback to `locator_hint` keywords and token-based bounding boxes.

5. **Needs-more-evidence semantics**
   - Proposals are flagged if evidence is missing, indirect, or cannot be highlighted.
   - These are surfaced prominently in review filters.

This aligns with state-of-the-art retrieval-augmented extraction: hybrid search, reranking, query expansion, and evidence-grounded generation.

## Input schema sheet

Provide a `schema` sheet with at least:

- `column_name`
- `description`
- optional `group`, `priority`

## Repository structure

```
paper_table_agent/
  ui/          # Streamlit UI and run registry
  store/       # SQLite persistence + schema
  io/          # XLSX/CSV/schema readers
  pdf/         # PDF parsing, OCR, highlighting
  retrieval/   # indexing and retrieval pipeline
  llm/         # OpenAI-compatible client + prompts
  graph/       # LangGraph workflow orchestration
  prompts/     # prompt templates for LLM steps
```

## Troubleshooting

- **Streamlit startup errors**: use `paper-table-agent ui` (subprocess launch) and ensure Streamlit is pinned to 1.32.2.
- **OCR**: install optional OCR extras if you need hi-res OCR:
  ```bash
  pip install -e .[ocr]
  ```
- **LLM JSON failures**: enable `mock_mode` with canned JSON payloads for tests, or inspect errors in `runs/<...>/logs/errors.jsonl`.
