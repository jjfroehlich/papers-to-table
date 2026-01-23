# Paper Table Agent

Local-first batch PDF → table proposals with evidence, plus post-run row review.
Paper Table Agent is a local-first PDF→Spreadsheet filling assistant for literature curation. You give it (1) one spreadsheet where each row is a paper and (2) a folder of PDFs. The agent matches PDFs to rows, then fills only missing cells by proposing values with evidence (page + verbatim quote + highlight). It never overwrites existing non-empty cells. After the run, you use a simple Review flow to step through only the rows where a PDF was matched and approve/reject each proposed cell while viewing the highlighted quote in the PDF.
Under the hood, extraction is evidence-first retrieval + constrained generation (multi-query retrieval and query “hypothesis” techniques can improve recall/accuracy) and is designed to be resumable and auditable.

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
- **Run UX**: minimal inputs (table path + PDF folder) with a built-in path picker.
- **Review UX**: row → column step-through with three decisions and evidence highlights.
- **Configuration**: single config file controls models, retrieval, OCR, and diagnostics; UI does not expose tuning knobs.

Near-term to-do:

- Evaluate embedding + reranker model pairs for best retrieval quality.
- Evidence locator robustness for complex PDFs and OCR-heavy scans.
- Diagnostics surfacing for LLM I/O (prompt/response/validation errors).

## Installation
- Install **LM Studio** or **Ollama** and download the models you want to use:
  - **Extraction**: `gpt-oss-20b` (or equivalent)
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

### 2) Start the UI

```bash
paper-table-agent ui
```

The Run tab uses only table + PDF paths. Completed runs appear in Review.

### 2.5) Smoke test with stub providers (no external LLMs)

```bash
paper-table-agent run --config tests/fixtures/stub_run_config.json
```

This uses deterministic stub providers + tiny fixture data so you can verify proposals and review flow without LM Studio/Ollama.

### 3) Run the batch pipeline (CLI)

Generate a starter config:

```bash
paper-table-agent init-config --output run_config.json
```

All models/retrieval/OCR settings live in this single config file; the UI does not expose tuning knobs.

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
    "mode": "openai",
    "base_url": "http://localhost:1234/v1",
    "api_key": null,
    "model_header": "local-header",
    "model_match": "local-match",
    "model_extract": "local-extract",
    "model_query_helper": "local-helper",
    "max_prompt_chars": 26000,
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
    "retry_extra_chunks": 10
  },
  "retrieval": {
    "top_k": 20,
    "rerank_k": 20,
    "max_context_chunks": 24,
    "max_context_tokens": 2400,
    "query_variants": 6,
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
  "output": {
    "debug_reports": false
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

Create a run bundle (report + exports + logs):

```bash
paper-table-agent bundle --run_dir runs/<timestamp>__<table>/
```

## Configuration (models, embeddings, reranker)

All model/retrieval settings live in the single `run_config.json` file. The UI reads defaults but does not override them.

**Model routing**

- `provider.mode`: `openai` (default) or `mock` for deterministic test runs.
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

When using the LM Studio reranker backend, choose an embedding-capable model (reranking uses cosine similarity over embeddings). If embeddings or reranker models are missing, the system falls back to TF-IDF and disables reranking with a warning.

**Retrieval profile**

- Single “optimal” profile (topK=20, rerank=20, query_variants=6, HyDE on, retry on unclear).

Example LM Studio retrieval settings:

```json
{
  "retrieval": {
    "embedding_backend": "lmstudio",
    "embedding_model": "text-embedding-nomic-embed-text-v1.5-embedding",
    "reranker_backend": "lmstudio",
    "reranker_model": "text-embedding-bge-small-en-v1.5",
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
    run_report.json
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
   - Proposed values must cite evidence quotes + page numbers + `chunk_id`.
   - Quotes must be a verbatim substring of the retrieved chunk.
   - Highlights use PyMuPDF `search_for`, fallback to `locator_hint`, then token alignment.
   - If highlight resolution fails, the page is still shown and `needs_more_evidence=true` is set.

5. **Needs-more-evidence semantics**
   - Proposals are flagged if evidence is missing, indirect, or cannot be highlighted.
   - Review shows a small badge but does not add a fourth decision.

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
- **LLM JSON failures**: set `provider.mode` to `mock` with canned JSON payloads for tests, or inspect errors in `runs/<...>/logs/errors.jsonl`.
