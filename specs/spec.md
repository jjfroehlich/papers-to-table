# Spec: Paper Table Agent — Unified Functional + UI/UX Spec (v0.6)

This unified spec consolidates the best functional requirements from earlier versions with the latest UI/UX iteration. It prioritizes **accurate extraction with evidence** while keeping the app **fast, logical, and user-friendly** during row-by-row review.

---

## 0) Goals

- **High extraction accuracy**: prioritize evidence-backed values for most cells.
- **Trustworthy proposals**: every proposal is traceable to page + quote + highlight (or clearly marked as weak/uncertain).
- **Low-friction review**: row-by-row decisions with fast navigation and minimal typing.
- **Local-first reliability**: resumable batch runs, deterministic pipelines, and durable storage.
- **Scalable UI**: responsive even for large runs with thousands of rows/proposals.

---

## 1) What we’re building

A local-first app that:

1. **Ingests a table** (XLSX/CSV), where each row is one publication (title/authors/year are required columns).
2. **Ingests a folder of PDFs** (filenames are unreliable).
3. **Extracts title/authors/year** from each PDF and matches it to a row via two-pass matching.
4. **Extracts missing values** for schema-defined columns into **proposals** (never edits the original table during a run).
5. Attaches **evidence** (quote + page + highlight rectangles) to proposals; weak evidence is flagged.
6. Provides **post-run row-by-row review** with Accept / Accept-with-edit / Reject decisions.
7. Exports an updated table copy + audit logs + mapping reports.

---

## 2) Inputs & outputs

### 2.1 Inputs

- **Table**: XLSX preferred; CSV supported.
- **Schema sheet** (within XLSX or separate file):
  - `column_name`
  - `description`
  - optional `group`, `priority`
  - optional `evidence_required` (default true)
  - optional `empty_values` (default includes `""`, `"NA"`, `"N/A"`, `"null"`, `"-"`, `" "`)
- **PDF folder**: user-provided; PDFs only.

### 2.2 Outputs (per run)

```
runs/
  <timestamp>__<table_name>/
    run_config.json
    proposals.sqlite
    exports/
      updated_table.xlsx
      audit_log.csv
      pdf_row_matches.csv
      proposals.jsonl
      mapping_report.html
    artifacts/
      parsed/
        <pdf_id>.json
      ocr/
        <pdf_id>/...
      retrieval_indexes/
        <pdf_id>/...
      thumbnails/
    logs/
      run.log
      errors.jsonl
```

---

## 3) Core policies

### 3.1 Locking (default)

- Any cell is **locked** if it is non-empty and not exactly `" "` (single space).
- Locked cells are never overwritten during extraction.

### 3.2 Verify-only mode (optional)

- Locked cells are not changed, but the system produces **verification items**:
  - status: `supports | contradicts | unclear`
  - evidence quote(s) + page + highlight
  - rationale (short)
- Verification results are reviewed alongside proposals, row-by-row.

### 3.3 Values as text

- All proposals stored and exported as **text**, even if numeric.

### 3.4 Evidence requirement (P0)

- **No proposed value without quote + page.**
- If evidence is missing or cannot be located, mark as `unclear` and `needs_more_evidence=true`.
- Every column in the target group produces a proposal record (even `unclear`/`no_evidence`).

---

## 4) Matching PDF → Row (two-pass, deterministic-first)

### 4.1 Header extraction

- Extract title, full author list, and year from PDF content.
- Evidence includes quote + page for title/authors.
- Parsing uses structured extraction first; LLMs interpret but do not guess.

### 4.2 Two-pass matching

**Pass 1 — deterministic shortlist**

- RapidFuzz title similarity + author last-name overlap score.
- Year is optional, used as a small tie-breaker bonus (±1 tolerance).
- Deterministic rule: if the top candidate is above threshold **by margin** and unique → `matched` without LLM.

**Pass 2 — LLM adjudication (only when needed)**

- Input: extracted metadata + evidence + candidate rows.
- Output (strict JSON):
  - `status`: `matched | ambiguous | unmatched`
  - `row_id` when matched
  - `top_candidates[]` (row_id, title, authors, year, score)
  - confidence + evidence notes
- LLM output is validated; one repair retry permitted.

### 4.3 1-to-1 enforcement + duplicate detection

- Default assumption: one PDF ↔ one row.
- If multiple PDFs match the same row:
  - keep highest-confidence assignment
  - flag others as duplicates
  - surface in mapping report + review UI
- If ambiguous:
  - store `needs_review` mapping
  - extraction may proceed but proposals are `mapping_dependent`.

### 4.4 Mapping report

- PDFs processed / matched / ambiguous / unmatched.
- Duplicates detected.
- For each PDF: extracted metadata vs row metadata, confidence, evidence snippets, candidate table.

---

## 5) Extraction → proposals (missing cells only)

### 5.1 Column grouping

Split schema columns into groups (configurable) to improve extraction quality, e.g.:
- Identity & system
- Perturbation / intervention
- Methods
- Data types & readouts
- Quantitative results
- Notes / limitations

### 5.2 Proposal record

For each (row_id, column):

- proposed_value (text or null)
- status: `found | inferred | not_found` (or `supports | contradicts | unclear` for verify)
- confidence (0–1)
- evidence[]:
  - quote (short)
  - page number
  - locator_hint (substring)
  - highlight rectangles (bbox) when available
- needs_more_evidence (boolean)
- mapping_dependent (boolean)
- rationale (short; required for inferred/derived)

### 5.3 Needs-more-evidence rules

Flag if:
- quote is indirect/ambiguous
- highlight cannot be located
- value is derived but support is weak

---

## 6) Parsing + retrieval pipeline (best-practice, accuracy-first)

### 6.1 Parsing layers

- **GROBID (optional)**: structured header + sections + references.
- **Layout-aware tokens**: pdfplumber words with coordinates for robust highlighting.
- **PyMuPDF**: page text + `search_for()` for fast substring search.
- **Table extraction (optional)**: Unstructured `partition_pdf` with table inference; fallback Camelot/Tabula where available.

### 6.2 Indexing strategy

- Build a **per-PDF micro-index** with multi-granularity chunks:
  - token/line-level
  - paragraph
  - section
  - optional hierarchical summaries

### 6.3 Hybrid retrieval backbone

- **Sparse**: BM25
- **Dense**: multi-function embeddings (e.g., BGE-M3)
- **Reranker**: cross-encoder reranking over top-N

### 6.4 Query-time retrieval (max success rate)

- Multi-query expansion (RAG-Fusion).
- HyDE retrieval for semantic alignment.
- Hybrid union + rerank to final top M.
- Add context neighborhood to preserve adjacency.
- Evidence-first extraction: LLM can only propose values tied to retrieved chunks.

### 6.5 Hierarchical retrieval (optional “max recall” mode)

- RAPTOR-style clustering + recursive summaries when PDFs are long or low-confidence.

### 6.6 OCR fallback

- If extraction fails or PDF is scanned:
  - Unstructured `strategy="hi_res"` + OCR.
  - OCR-derived proposals are flagged.

---

## 7) LangGraph orchestration

Nodes:

`load_table → parse_pdf → extract_header → match_row → build_index → extract_group(s) → persist_results → finalize`

- Checkpoint after each PDF and each group extraction.
- LLM calls use strict JSON validation + one repair retry.

---

## 8) Model/provider abstraction (local-first, cloud optional)

- OpenAI-compatible provider interface for all LLM calls.
- Local providers: **LM Studio**, **Ollama**.
- Cloud providers: any OpenAI-compatible endpoint.

Model roles:
- Header extraction model
- Match adjudication model
- Extraction model
- Query expansion / HyDE model
- Embedding backend + model
- Reranker backend + model

---

## 9) UI/UX requirements

### 9.1 Global UI principles

- Navigation: **Run | Review | Advanced | Settings | Help**.
- Layout:
  - Top bar: app title + selected run + status chip.
  - Left rail: navigation + context selectors.
  - Main: working panels.
- Persistent session state for selected run/row/proposal index.
- Clear empty states and no hard failures.

### 9.2 Run tab (batch execution)

**Run configuration panel**

- Table input path with browse helper (show filename + last modified).
- PDF folder path with browse helper.
- Schema source: use schema sheet or separate schema file.
- Run name: auto-generated, editable.
- Mode: Propose (default) or Verify-only.
- Locked cells policy: read-only display.
- Model dropdowns: extraction LLM + embedding backend/model + reranker backend/model.
- Retrieval strength: Fast | Balanced | Thorough.
- OCR fallback toggle (off by default).
- GROBID toggle + URL.

**Validation UX**

- Required fields show green check / red warning.
- Start run disabled until minimum fields are valid.

**Run execution panel**

- Progress: overall bar, step label, current PDF.
- Live logs: filter by errors/warnings/info.
- Actions: Pause, Resume, Stop (graceful, keep partial results).
- Completion summary: matched/ambiguous/unmatched counts, proposals count, needs_more_evidence count, run duration, “Go to Review”.
- Artifacts path with “Copy path”.

### 9.3 Review tab (row-by-row)

**Top bar**

- Run selector (completed runs only).
- Filters: status, confidence range, columns (multi-select).
- Search: column names + proposed values + evidence quote.
- Row navigation: Prev/Next, jump, “Row X of Y”.

**Left panel**

- Row context card: Title/Authors/Year + key schema columns.
- Mapping status: matched row + PDF metadata side-by-side; candidates if ambiguous.
- Proposal stepper: Prev/Next + optional keyboard shortcuts.
- Proposal card: column name, current value, proposed value (editable on accept+edit), status chips, evidence summary.
- Decision controls: Accept / Accept-with-edit / Reject.
- Add note + Needs-more-evidence toggle.
- Auto-advance (default on).

**Right panel**

- PDF viewer shows cited page and highlights evidence rectangles when available.
- Evidence list: quote, page, “Go to location”, “Try re-locate” when highlight fails.
- OCR confidence shown when applicable.

**Completion**

- Row completion % + “Mark row complete”.
- Run completion % + “Export updated table” gated by confirmation.

### 9.4 Advanced tab

- Dropdown selectors: run, PDF, row, column, retrieval query.
- Panels: matching diagnostics, retrieval diagnostics, LLM I/O, evidence locator.

### 9.5 Settings tab

- Provider selection: LM Studio | Ollama | OpenAI-compatible cloud.
- Model routing: header extraction, match adjudication, extraction, query expansion, embedding backend/model, reranker backend/model.
- Performance: concurrency, JSON repair retries, caching toggles.

### 9.6 Help / Troubleshooting

- “How to get started in 3 steps”.
- Common failure modes and checks.
- Links to run folder, logs, DB.

---

## 10) Non-functional requirements

- Handles large runs:
  - Lazy-load proposals per row.
  - Avoid rendering huge tables.
- Never lose decisions: persist to DB immediately.
- Back/forward navigation without losing state.
- Error-resilient: clear empty states, no hard crashes.

---

## 11) Export & audit

Exports:
- updated_table.xlsx (apply accepted/revised only)
- audit_log.csv (proposal → decision lineage)
- pdf_row_matches.csv (mapping + confidence + duplicates)
- mapping_report.html

Audit log includes:
- run_id
- pdf_id, row_id
- column
- old_value
- proposed_value
- evidence (quote/page)
- decision + final_value
- timestamps

---

## 12) Definition of done

- Two-pass matching works when year is missing; duplicates flagged.
- Every proposal has evidence or is clearly marked unclear/needs_more_evidence.
- Proposals are persisted per-column and visible in Review.
- Review UI supports stepper, filters, PDF highlights, immediate persistence.
- Advanced tab exposes matching/retrieval/LLM diagnostics.
- Settings tab supports provider/model routing + performance controls.
- Help tab includes onboarding + troubleshooting.
- README updated to reflect new workflow and configuration.
