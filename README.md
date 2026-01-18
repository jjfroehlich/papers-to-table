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
- **Run UX**: schema source selection, run naming, model routing, and validation gates reduce setup friction.
- **Review UX**: two-panel row review with filters, stepper navigation, and evidence highlights + re-locate tools.
- **Settings/Advanced**: provider/model routing with LM Studio model registry + diagnostics are available in the UI.

Near-term to-do:

- Evaluate embedding + reranker model pairs for best retrieval quality.
- Evidence locator robustness for complex PDFs and OCR-heavy scans.
- Diagnostics surfacing for LLM I/O (prompt/response/validation errors).

## Installation
- Have LM Studio installed and download the models you want to use:
  - **Extraction**: `gpt-oss-20b`
  - **Embeddings**: `nomic-embed-text-v1.5`
  - **Reranking**: another embedding-capable model such as `bge-small-en-v1.5`
- In LM Studio settings, raise the context length (e.g., 4,096 → 32,000).

```bash
python --version  # requires >=3.10
python -m venv .venv
source .venv/Scripts/activate
pip install -e .
```

> **Streamlit version pin**
>
> Streamlit is pinned to `1.32.2` to avoid runtime session errors. Use `paper-table-agent ui` (CLI launches Streamlit via `python -m streamlit run`).

## Quickstart

### 1) Start your model backend

- **LM Studio** (OpenAI-compatible): set `provider.base_url` to `http://localhost:1234/v1`.
- **Ollama** (OpenAI-compatible): set `provider.base_url` to `http://localhost:11434/v1`.
- **Cloud** (OpenAI-compatible): set `provider.base_url` + `provider.api_key` and model names.

If you use LM Studio, open **Settings → Refresh model list** so dropdowns only show models that are currently loaded in LM Studio.

### 2) Start the UI

```bash
paper-table-agent ui
```

The Run tab uses path inputs, dropdowns, and validation indicators to configure runs. Completed runs appear in Review.

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
  "schema_path": null,
  "run_name": "sample-run",
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
    "model_header": "local-header",
    "model_match": "local-match",
    "model_extract": "local-extract",
    "model_query_helper": "local-helper",
    "mock_mode": false,
    "mock_payloads_path": null
  },
  "matching": {
    "top_k": 10,
    "confidence_threshold": 0.75,
    "confidence_margin": 0.05,
    "year_tolerance": 1
  },
  "extraction": {
    "groups": [],
    "examples_per_col": 3,
    "max_chunks": 20,
    "retry_on_unclear": true,
    "retry_extra_chunks": 6
  },
  "retrieval": {
    "top_k": 12,
    "rerank_k": 12,
    "max_context_chunks": 16,
    "max_context_tokens": 1800,
    "query_variants": 4,
    "use_query_expansion": true,
    "use_hyde": true,
    "rrf_k": 60,
    "embedding_backend": "tfidf",
    "embedding_model": null,
    "reranker_backend": "tfidf",
    "reranker_model": null,
    "use_reranker": true
  },
  "ocr": {
    "enable_ocr": true,
    "ocr_trigger_min_chars_per_page": 400
  },
  "grobid": {
    "enable_grobid": false,
    "server_url": "http://localhost:8070",
    "parse_references": false
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

## Configuration (models, embeddings, reranker)

**Model routing**

- `provider.model_header`: header extraction (title/authors/year).
- `provider.model_match`: match adjudication.
- `provider.model_extract`: group extraction (proposals).
- `provider.model_query_helper`: query expansion + HyDE.

**Retrieval tuning**

- `retrieval.embedding_backend`: `tfidf` or `lmstudio`.
- `retrieval.embedding_model`: model ID used for LM Studio embeddings (required when backend is `lmstudio`).
- `retrieval.reranker_backend`: `tfidf` or `lmstudio`.
- `retrieval.reranker_model`: model ID used for LM Studio reranking embeddings (required when backend is `lmstudio`).
- `retrieval.use_reranker`: enable/disable reranking.

When using the LM Studio reranker backend, choose an embedding-capable model (reranking uses cosine similarity over embeddings).

Example LM Studio retrieval settings:

```json
{
  "retrieval": {
    "embedding_backend": "lmstudio",
    "embedding_model": "nomic-embed-text-v1.5",
    "reranker_backend": "lmstudio",
    "reranker_model": "bge-small-en-v1.5",
    "use_reranker": true
  }
}
```

**Caching strategy**

- Per-PDF retrieval indexes cached under `runs/.../artifacts/retrieval_indexes/<pdf_id>/`.
- Highlight rectangles cached in proposal evidence JSON.
- LangGraph checkpoints persisted to resume runs without duplication.

## GROBID integration (optional)

When enabled, GROBID provides structured **metadata** (title/authors/abstract) to improve header extraction and **section segmentation** to improve retrieval chunking. Reference parsing is optional. If GROBID is unavailable, the system falls back to PyMuPDF/pdfplumber parsing.

## Run directory layout + resume

```
runs/
  <timestamp>__<table_name>/
    run_config.json
    proposals.sqlite
    COMPLETED
    PAUSE
    exports/
    artifacts/
      parsed/
      ocr/
      retrieval_indexes/
    logs/
```

Resume a run with `paper-table-agent resume --run_dir runs/<timestamp>__<table>/`.

## How extraction is made reliable

1. **Two-pass matching (Title + Authors first)**
   - Pass A uses RapidFuzz title scoring + author last-name overlap; year is a small tie-breaker.
   - If **one candidate** clears the threshold **by margin**, we match deterministically.
   - Otherwise, we invoke the LLM on the top K candidates only (validated + repair retry).

2. **Hybrid retrieval pipeline (state-of-the-art patterns)**
   - BM25 + dense retrieval + reranking.
   - Multi-query expansion and HyDE for recall.
   - Reciprocal-rank fusion and top-K context packing.
   - Tuning knobs: `top_k`, `rerank_k`, `query_variants`, `use_reranker`.

3. **Validation + JSON repair**
   - LLM JSON is strictly validated.
   - Invalid JSON triggers a repair prompt and is recorded (no silent drops).

4. **Quote substring constraint + highlights**
   - Proposed values must cite evidence quotes + page numbers.
   - Highlights use PyMuPDF `search_for`, fallback to `locator_hint`, then OCR token bounding boxes if OCR is enabled.
   - If highlight resolution fails, the page is still shown and `needs_more_evidence=true` is set.

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
- **GROBID**: optional and OFF by default. Enable with `grobid.enable_grobid=true` and run a local GROBID server:
  ```bash
  docker run --rm -p 8070:8070 grobid/grobid:0.8.0
  ```
- **LLM JSON failures**: enable `mock_mode` with canned JSON payloads for tests, or inspect errors in `runs/<...>/logs/errors.jsonl`.
