# Spec: Paper Table Agent — Unified Spec

## Product summary

Paper Table Agent is a local-first PDF→Spreadsheet assistant. You provide a table and a PDF folder; the agent matches PDFs to rows, proposes values for missing cells with evidence, and lets you review decisions row-by-row in a minimal Run/Review UI.

This unified spec consolidates the best functional requirements from earlier versions with the latest minimal UI/UX iteration. It prioritizes **accurate extraction with evidence** while keeping the app **fast, logical, and user-friendly** during row-by-row review.

Paper Table Agent is a local-first PDF→Spreadsheet filling assistant for literature curation. You give it (1) one spreadsheet where each row is a paper and (2) a folder of PDFs. The agent matches PDFs to rows, then fills only missing cells by proposing values with evidence (page + verbatim quote + highlight). It never overwrites existing non-empty cells. After the run, you use a simple Review flow to step through only the rows where a PDF was matched and approve/reject each proposed cell while viewing the highlighted quote in the PDF.
Under the hood, extraction is evidence-first retrieval + constrained generation (multi-query retrieval and query “hypothesis” techniques can improve recall/accuracy) and is designed to be resumable and auditable.

---

## 0) Goals

- **High extraction accuracy**: prioritize evidence-backed values for most cells.
- **Trustworthy proposals**: every proposal is traceable to page + quote + highlight (or clearly marked as weak/uncertain).
- **Low-friction review**: row-by-row decisions with fast navigation and minimal typing.
- **Local-first reliability**: resumable batch runs, deterministic pipelines, and durable storage.
- **Scalable UI**: responsive even for large runs with thousands of rows/proposals.

## 0.1) Product philosophy

- The app should do the **best possible job automatically** with fixed, high-quality defaults.
- UI **does not expose tuning knobs** (models, retrieval presets, OCR/GROBID toggles).
- All parameters are tuned in a single config file after testing, not in the UI.

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

Primary artifacts (always written):

```
runs/
  <timestamp>__<table_name>/
    run_config.json
    proposals.sqlite
    run_report.json
    exports/
      updated_table.xlsx
      audit_log.csv
      pdf_row_matches.csv
```

Optional/debug artifacts (behind a debug flag):

```
    exports/
      proposals.jsonl
      mapping_report.html
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
- Verification results are reviewed alongside proposals, row-by-row, and shown as **Verify** items with the locked cell value displayed read-only.
- Review decisions still use **exactly three actions** (Accept / Accept-with-edit / Reject):
  - **Accept** confirms the model’s verification status (supports/contradicts/unclear) with no cell edits.
  - **Accept-with-edit** allows overriding the verification status (supports/contradicts/unclear) and adding a note, while keeping the locked cell value unchanged.
  - **Reject** marks the verification outcome as `unclear` and flags it for follow-up; locked cells are never edited.

### 3.3 Values as text

- All proposals stored and exported as **text**, even if numeric.

### 3.4 Evidence requirement + validation (P0)

- **No proposed value without quote + page + chunk_id.**
- **Quote must be a verbatim substring of the referenced retrieved chunk** (chunk_id stored in DB).
- Validation modes:
  - `exact`: verbatim substring match.
  - `normalized`: substring match after normalizing whitespace, hyphenation line breaks, and ligatures.
- Persist `validation_mode` and `validation_reason` in the DB and surface them via diagnostics when needed.
- Each retrieved chunk stores a page range (page_start/page_end); **evidence.page must fall within the chunk range**, and locators operate on evidence.page.
- If evidence is missing, invalid, or cannot be located, force `status=unclear` and `needs_more_evidence=true`.
- Evidence validation errors are persisted (error_type, reason) with the proposal record.

### 3.5 Proposal persistence (P0)

- **Never drop records**: for every requested column, persist a proposal record even if unclear/no_evidence or model output malformed.
- Persist structured error metadata: `error_type`, `raw_output` snippet, `repair_attempted`, and `validation_errors`.

### 3.6 Run diagnostics artifact (P0)

- Each run writes a **run_report.json** with run_id, input paths, mapping counts, proposal counts, errors, and sanity-check diagnostics.
- Run-level sanity check: if matched PDFs > 0 and proposals == 0, mark the run **FAILED** with a reason + likely causes.
- `paper-table-agent bundle --run_dir <run_dir>` produces `run_bundle.zip` containing run_report, mapping report, logs, and exports.
- run_report must include: matched counts, proposal counts, error counts, and the run status.

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
- **Consistency guardrails (P0)**:
  - If `status=ambiguous`, `row_id` must be null.
  - If `row_id` is present, `status=matched`.
  - Ambiguous is forbidden when only one plausible candidate exists; coerce to matched and log a warning.

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
- For each PDF: **side-by-side extracted metadata vs row metadata**, confidence, evidence snippets, candidate table.

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

### 5.1.1 Prompting schema usage (P0)

- Always include the **schema description per column** in prompts.
- Include **1–3 existing non-empty values** as examples for each column using a deterministic, representative selection (evenly spaced across non-empty rows, capped per column).
- Include **row context** (Title/Authors/Year + key columns).

### 5.2 Proposal record

For each (row_id, column):

- proposed_value (text or null)
- status: `found | inferred | not_found` (or `supports | contradicts | unclear` for verify)
- confidence (0–1)
- evidence[]:
  - quote (short)
  - page number (must be within chunk page range)
  - chunk_id (retrieved chunk reference)
  - locator_hint (substring)
  - highlight rectangles (bbox) when available
  - highlight_status (`highlighted | not_found | missing_quote_or_page`) + strategy
- needs_more_evidence (boolean)
- mapping_dependent (boolean)
- rationale (short; required for inferred/derived)
- verification_status (`supports | contradicts | unclear`)
- verification_needs_more_evidence (boolean)
- verification_rationale (short)

### 5.3 Needs-more-evidence rules

Flag if:
- quote is indirect/ambiguous
- highlight cannot be located
- value is derived but support is weak

### 5.4 Automatic verification (P0)

- After proposal extraction, run a verification pass that checks whether evidence supports the proposed value.
- Set `verification_status` to `supports | contradicts | unclear` and mark `verification_needs_more_evidence` accordingly.
- Use verification status to prioritize review, but never hide proposals for empty cells.

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

### 6.4.1 Retrieval profile (P0, single “optimal”)

- **Single optimal profile (BEST)** (no UI presets):
  - topK=20, rerank topN=20
  - query_variants=6, HyDE=on
  - max_context_chunks=24, max_context_tokens=2400
  - second-pass retry on unclear = **on** (extra_chunks=10)
- Rationale: HyDE + multi-query expansion with reciprocal rank fusion, plus optional hierarchical retrieval, improves retrieval recall/quality in evidence-first pipelines.【[HyDE](https://arxiv.org/abs/2212.10496)】【[RAG-Fusion/RRF](https://arxiv.org/abs/2305.14688)】【[RAPTOR](https://arxiv.org/abs/2307.11778)】
- **Fallback behavior**:
- If embeddings or reranker are not configured, fall back to **BM25-only + no rerank**; log a warning and record the fallback mode in events.

### 6.5 Hierarchical retrieval (optional “max recall” mode)

- RAPTOR-style clustering + recursive summaries when PDFs are long or low-confidence.

### 6.6 OCR fallback

- If extraction fails or PDF is scanned:
  - Unstructured `strategy="hi_res"` + OCR.
  - OCR-derived proposals are flagged.
  - See Unstructured hi_res/OCR strategy docs for provenance and behavior.【[Unstructured hi_res](https://unstructured-io.github.io/unstructured/bricks/partition.html#hi-res-strategy)】

### 6.7 Highlight locator algorithm (P0)

Ordered steps:
1. Exact quote search on target page.
2. Normalized whitespace search.
3. Locator_hint keyword search (raw + normalized).
4. **pdfplumber token alignment** (word-box search).
5. **OCR token alignment** (when OCR tokens available).
6. Fail with `not_found` and set `needs_more_evidence=true`.

Highlight rectangles are cached in DB and reused in Review.

---

## 7) LangGraph orchestration

Nodes:

`load_table → parse_pdf → extract_header → match_row → build_index → extract_group(s) → persist_results → finalize`

- Checkpoint after each PDF and each group extraction.
- LLM calls use strict JSON validation + one repair retry.
- LangGraph persistence/checkpointing enables resumable, human-in-the-loop workflows.【[LangGraph Persistence](https://langchain-ai.github.io/langgraph/how-tos/persistence/)】

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

### 8.1 Configuration (single source of truth)

- All settings live in **one config file** (pydantic settings/run_config.json).
- UI reads defaults from the config file but **does not** expose model/parameter controls.
- CLI uses the same config object; overrides must still pass through the single config file.

---

## 9) UI/UX requirements

### 9.1 Global UI principles

- Navigation: **Run | Review** only.
- Minimal UI chrome with clear empty states.
- Persistent session state for selected run/row/column index.
- No tuning knobs or provider selectors in the UI.
- Explicitly de-scope Advanced/Settings/Help tabs and review filters (confidence range, column multi-select, heavy search).

### 9.2 Run screen (minimal)

Inputs:
- **Table path** (default from config file; editable text input).
- **PDF folder path** (default from config file; editable text input).
- “Browse” helper is an **in-app path picker** (directory/file browser widget), not an uploader.

Buttons:
- **Start Run**
- **Open run folder**

Progress:
- Minimal status line: **Running / Done / Failed**.
- Optional “current PDF” display.

### 9.3 Review screen (minimal step-through)

Primary interaction:
- Step through **matched rows**, then **columns** needing decisions for that row.
- For each proposal: show **column name**, **current value**, **proposed value**, **evidence quote(s)+page**, and **PDF with highlight**.
- Three decisions only: **Accept / Accept-with-edit / Reject**.
- Auto-advance enabled by default.

Navigation controls:
- Prev/Next row, Prev/Next column, **Next undecided**, and keyboard shortcuts (j/k/a/e/r).
- Small “remaining items” counter.

Constraints:
- Only show columns that need a decision: empty cell OR verification contradicts/unclear.
- No confidence filtering.
- No search.
- No column multi-select.
- `needs_more_evidence` stays internal (optional badge only).

---

## 10) Non-functional requirements

- Handles large runs:
  - Lazy-load proposals per row.
  - Avoid rendering huge tables.
- Never lose decisions: persist to DB immediately.
- Back/forward navigation without losing state.
- Error-resilient: clear empty states, no hard crashes.
- Privacy/security: core flow runs **offline**; if internet is enabled, restrict to configured LLM endpoints only.

---

## 11) Export & audit

Exports:
- updated_table.xlsx (apply accepted/revised only)
- audit_log.csv (proposal → decision lineage)
- pdf_row_matches.csv (diagnostic mapping summary)
- mapping_report.html (debug-only)

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

- `pip install -e ".[test]"` works, and `pytest -q` passes.
- Streamlit UI launches (`paper-table-agent ui`) with **Run** and **Review** only.
- Two-pass matching works when year is missing; duplicates flagged.
- Matching JSON is internally consistent (no ambiguous+row_id).
- **Every column** persists a proposal record (even error/unclear/no_evidence).
- Every proposal has evidence or is clearly marked unclear/needs_more_evidence.
- Evidence validation enforces quote+page+chunk_id and substring match.
- run_report includes run_id, inputs, mapping counts, proposal counts, error counts, and run status.
- pdf_row_matches.csv exists and includes side-by-side metadata + candidate table; mapping_report.html only when debug is enabled.
- Decisions persist immediately in Review.
- UI exposes **no** model/retrieval/OCR/GROBID knobs; config is single source of truth.
- Outputs are simplified to proposals.sqlite + run_report.json + updated_table.xlsx + audit_log.csv + pdf_row_matches.csv.
- README updated to reflect workflow and configuration.
