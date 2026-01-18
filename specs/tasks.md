# tasks.md — Paper Table Agent (LangGraph)

Batch PDF→Table proposals with evidence + post-run row review

This tasks file is designed for spec-driven development:

* small, reviewable diffs
* each task has clear acceptance criteria
* test-first where feasible
* checkpoints and artifacts are explicit
* minimize rework by building vertical slices early

> Conventions
>
> * “AC” = Acceptance Criteria
> * “SMOKE” = minimal command to prove it works
> * “Artifacts” = files DB rows outputs expected
> * Keep prompts/templates versioned under `paper_table_agent/prompts/`
> * Prefer feature flags for optional “max success” retrieval modes until stable.

---

## v0.2 Improvements (stability + UX overhaul)

### [x] T13.1 Streamlit startup stability + version pin

**Work**

* Launch Streamlit via subprocess (`python -m streamlit run`) instead of bootstrap.
* Pin Streamlit to a known good version in `pyproject.toml`.
* Document the startup workaround in README.

**AC**

* `paper-table-agent ui` launches without bootstrap errors.

---

### [x] T13.2 Two-pass matching updates (title+authors primary)

**Work**

* Pass A: RapidFuzz title scoring + author last-name overlap; year as low-weight tie-breaker.
* Deterministic rule: exactly one candidate above threshold → matched.
* Pass B: LLM adjudication (matched|ambiguous|unmatched) only when needed.
* Store shortlist + LLM candidates for reporting.

**AC**

* Mapping report includes matched/ambiguous/unmatched counts and candidate tables.

---

### [x] T13.3 Unified proposal schema + persistence

**Work**

* Ensure one proposal record per column in each extraction group.
* Store verify results in proposals with unified schema.
* Add error proposals when LLM parsing fails (no silent drops).

**AC**

* Review tab always lists proposals for each extracted column.

---

### [x] T13.4 UI run registry + dropdown-only selections

**Work**

* Run registry listing available tables, PDF folders, and completed runs.
* Dropdown-only selection for run/table/pdf/column/query.
* Review row-by-row with Prev/Next navigation, manual edit, and PDF side panel.

**AC**

* Completed runs appear in Review tab automatically after run completion.

---

### [x] T13.5 Robust JSON repair + diagnostics

**Work**

* Validate JSON, retry with repair prompt if invalid.
* Record parsing errors with diagnostics in errors/events.

**AC**

* LLM JSON failures are captured and do not silently drop results.

---

### [x] T13.6 Tests (matching, schema validation, UI registry)

**Work**

* Update matching unit tests for new scoring rules.
* Add schema validation unit test.
* Add integration smoke test for run registry listing.

**AC**

* `pytest -q` covers new tests.

---

### [x] T13.7 README + CHANGELOG refresh

**Work**

* Update README with new purpose, structure, run instructions, and reliability section.
* Update CHANGELOG for v0.2 improvements.

**AC**

* Docs reflect current behavior and troubleshooting guidance.

---

## 0) Repo setup & guardrails (foundation)

### [x] T0.1 Create project scaffold

**Work**

* Create package structure:

  * `paper_table_agent/`

    * `__init__.py`
    * `config.py`
    * `cli.py`
    * `ui/app.py`
    * `store/` (sqlite)
    * `io/` (xlsx/csv/schema)
    * `pdf/` (parsing, highlight)
    * `retrieval/` (chunking, index, rerank)
    * `llm/` (OpenAI-compatible client)
    * `graph/` (LangGraph workflow)
    * `prompts/` (json prompt templates)
    * `utils/`
* Add `pyproject.toml` with dependencies and console scripts:

  * `paper-table-agent` → `paper_table_agent.cli:main`
* Add `README.md` minimal usage.

**AC**

* `pip install -e .` succeeds.
* `paper-table-agent --help` prints commands.
* `streamlit run paper_table_agent/ui/app.py` launches.

**SMOKE**

* Start UI; it shows placeholder tabs Run/Review/Export.

---

### [x] T0.2 Add run directory + logging + versioning

**Work**

* Implement `RunPaths` utility that creates:

  * `runs/<timestamp>__<table_stem>/...` folder tree
* Add structured logging:

  * `logs/run.log`
  * `logs/errors.jsonl`
* Add “prompt version hash” capture:

  * record git commit hash if available + prompt template versions in `run_config.json`

**AC**

* Starting a new run creates the folder tree and `run_config.json` + log file.

**Artifacts**

* `runs/<...>/run_config.json`
* `runs/<...>/logs/run.log`

---

### [x] T0.3 Define RunConfig (Pydantic) and config validation

**Work**

* Create `RunConfig` with:

  * `table_path`, `schema_sheet_name`, `schema_mode`
  * `pdf_folder`
  * `title_col`, `authors_col`, `year_col` (UI-selectable)
  * locking rules: `treat_single_space_as_empty=true`
  * modes: `verify_mode=false`, `fast_mode=false`, `max_success_mode=true`
  * provider: `base_url`, `api_key`, `model_extract`, `model_query_helper`
  * matching: `topK=10`, `conf_threshold=0.75`, `year_tolerance=1`
  * extraction: `groups`, `examples_per_col=3`, `max_chunks=20`
  * OCR: `enable_ocr=true`, `ocr_trigger_min_chars_per_page=...`
  * concurrency: `max_workers=1` (set >1 later)
* Validate paths exist and schema columns are present.

**AC**

* Invalid configs fail with actionable error messages in UI and CLI.

---

## 1) Data store (SQLite) and persistence

### [x] T1.1 Implement SQLite schema + migrations

**Work**

* Create `paper_table_agent/store/schema.sql` and migration runner.
* Tables:

  * `pdfs(pdf_id TEXT PK, path TEXT, sha1 TEXT, n_pages INT, status TEXT, error TEXT, created_at)`
  * `rows(row_id TEXT PK, row_index INT, title TEXT, authors TEXT, year TEXT, status TEXT)`
  * `locks(row_id TEXT, column TEXT, locked INT, reason TEXT, PRIMARY KEY(row_id,column))`
  * `matches(match_id TEXT PK, pdf_id TEXT, row_id TEXT, confidence REAL, status TEXT, evidence_json TEXT, rationale TEXT, created_at)`
  * `proposals(proposal_id TEXT PK, pdf_id TEXT, row_id TEXT, column TEXT, proposed_value TEXT, status TEXT, confidence REAL, evidence_json TEXT, reasoning TEXT, flags_json TEXT, created_at)`
  * `reviews(review_id TEXT PK, proposal_id TEXT, decision TEXT, final_value TEXT, note TEXT, reviewed_at)`
  * `events(event_id TEXT PK, level TEXT, event_type TEXT, payload_json TEXT, created_at)`
* Provide `Store` API with typed methods.

**AC**

* DB initializes in run folder and tables exist.
* Insert/select functions covered by minimal unit tests.

**SMOKE**

* `paper-table-agent init-db --run_dir ...` creates `proposals.sqlite`.

---

### [x] T1.2 Checkpointing strategy (LangGraph + DB)

**Work**

* Decide and implement:

  * primary persistence: SQLite for business state (pdf status, proposals, matches)
  * LangGraph checkpointer: store minimal workflow cursor (current pdf index etc.)
* Implement a “resume” mechanism that:

  * skips PDFs with `status=processed`
  * retries failed PDFs optionally.

**AC**

* Kill run mid-way; resume continues without duplicating proposals.

---

## 2) Table + schema ingestion + locks

### [x] T2.1 XLSX table reader/writer (primary)

**Work**

* Implement in `io/xlsx.py`:

  * load workbook
  * read data sheet (configurable; default first sheet)
  * preserve formatting as much as practical by writing to a copy (MVP: values-only acceptable)
* Create stable `row_id`:

  * prefer existing ID column if user selects, else use row index (string) + run hash.

**AC**

* Loads XLSX; shows row count, column list, and preview (first 5 rows) in UI.

---

### [x] T2.2 Schema sheet reader (separate sheet with colnames + description)

**Work**

* Implement `io/schema.py`:

  * read schema sheet with `column_name`, `description`, optional `group`, `priority`
  * validate column_name exists in data columns
  * build `ColumnSpec` list
* Group derivation:

  * if group missing, assign `ungrouped`
  * allow UI to auto-group by priority later

**AC**

* UI shows schema summary: groups, number of columns, missing descriptions warnings.

---

### [x] T2.3 Lock map generation

**Work**

* Define “empty”:

  * `""`, `None`, common NA tokens
  * special: exactly `" "` counts as empty (unlocked)
* Compute locks for every (row, col) where cell is locked.
* Write to `locks` table.

**AC**

* Locked count matches expectation for a sample workbook.
* Extraction engine later cannot overwrite locked cells.

**Tests**

* Unit tests for `" "` behavior.

---

## 3) PDF ingestion + parsing + artifacts

### [x] T3.1 Enumerate PDFs and compute stable IDs

**Work**

* Walk folder (non-recursive by default; configurable).
* Compute sha1 of bytes (streaming).
* Store in `pdfs` table with status `pending`.

**AC**

* UI shows PDF count and a small list preview.
* Re-running enumeration does not duplicate rows (idempotent by sha1).

---

### [x] T3.2 Parse PDFs (fast text + page count) using PyMuPDF

**Work**

* Extract:

  * `n_pages`
  * `page_text[page]` (text-only)
* Store to `artifacts/parsed/<pdf_id>_pymupdf.json` (or combined artifact).

**AC**

* For typical text PDFs, first page text length >0.
* Parsing errors are captured in `errors.jsonl` and pdf status set to failed.

---

### [x] T3.3 Layout tokens with bounding boxes using pdfplumber

**Work**

* Extract words/tokens with:

  * page number
  * bbox (x0,y0,x1,y1)
  * text
* Store to `artifacts/parsed/<pdf_id>_tokens.jsonl` or compressed JSON.

**AC**

* Tokens exist for typical PDFs; used later for highlighting fallback.

---

### [x] T3.4 OCR fallback module (optional in MVP; plumbed end-to-end)

**Work**

* Implement OCR trigger:

  * if average chars/page below threshold OR too many empty pages
* Integrate OCR strategy using Unstructured hi_res (local inference).
* Store OCR outputs and mark parse source in DB.

**AC**

* If OCR is disabled, system still runs.
* If OCR enabled and a “scanned” test PDF is provided, it extracts some text and proceeds.

---

## 4) LLM provider abstraction (local-first, cloud optional)

### [x] T4.1 OpenAI-compatible client wrapper

**Work**

* Implement `llm/client.py`:

  * base_url + api_key optional
  * chat completion with system/user messages
  * strict JSON mode where supported; else “JSON-only” with validation+retry
* Add retry policy:

  * parse failure retry with smaller context
  * backoff
* Implement “dry-run / mock” mode for tests.

**AC**

* Works with LM Studio endpoint config.
* Works with cloud OpenAI-compatible if key provided (manual test).

---

### [x] T4.2 Prompt templates + versioning

**Work**

* Add `prompts/`:

  * `match_header_extract.md`
  * `match_adjudicate.md`
  * `extract_group.md`
  * `verify_cell.md` (optional)
  * `query_expand.md`
  * `hyde.md`
* Add prompt loader with version hash.

**AC**

* Prompts are editable without changing code.
* Run config captures prompt hashes.

---

## 5) Two-pass matching pipeline + mapping report

### [x] T5.1 Header extraction (title/authors/year) with evidence

**Work**

* Implement `graph/nodes/extract_pdf_header.py`:

  * input: first 1–2 pages text + minimal token hints
  * output JSON:

    * title, authors list, year (optional)
    * evidence quotes + page
    * confidence
* Store as an event payload and reuse for adjudication.

**AC**

* Produces usable title/authors for a sample set.
* Evidence quote is short and page-referenced.

---

### [x] T5.2 Pass 1 shortlist (RapidFuzz + author overlap)

**Work**

* Precompute normalized row titles and author last-name sets.
* For each PDF header:

  * fuzzy title ranking topK
  * compute author overlap score for tie-breaking
  * optional year filter ±1 if year known

**AC**

* Candidate list includes correct row for a known test fixture.

---

### [x] T5.3 Pass 2 LLM adjudication + 1-to-1 enforcement

**Work**

* Adjudication prompt returns:

  * chosen row_id OR ambiguous
  * top 3 candidates + rationale
  * confidence
* Store in `matches` table.
* Enforce 1-to-1:

  * if multiple PDFs choose same row above threshold:

    * best confidence retained as primary (status proposed)
    * others flagged duplicate (status needs_review + flag)

**AC**

* Duplicate detection visible in mapping report + review filters.

---

### [x] T5.4 Generate mapping report (HTML + CSV)

**Work**

* Create `exports/mapping_report.html`:

  * summary counts: matched/ambiguous/failed/duplicates
  * table: PDF extracted header vs table row fields
  * show evidence snippets
* Export `pdf_row_matches.csv` with mapping status and flags.

**AC**

* Report renders in a browser and is readable.
* CSV exports correct counts.

---

## 6) State-of-the-art retrieval pipeline (max success rate)

> Build retrieval as a standalone module with a debug interface early.
> Retrieval quality is the biggest lever on extraction success.

### [x] T6.1 Chunking (multi-granularity) with page mapping

**Work**

* Build chunk objects:

  * `chunk_id`, `text`, `page_start`, `page_end`, `source` (section/page/table), `neighbors`
* Sources:

  * page text chunks (page-level)
  * paragraph chunks (split by blank lines / heuristics)
  * (optional later) section chunks from GROBID
* Store chunks per PDF to `artifacts/retrieval_indexes/<pdf_id>/chunks.jsonl`.

**AC**

* Each chunk is traceable to page(s).
* Neighbor expansion works (prev/next chunk IDs exist).

---

### [x] T6.2 Sparse index (BM25) per PDF

**Work**

* Build BM25 over chunks text.
* Persist index artifacts (or cache computed arrays).

**AC**

* Query returns topK chunks with scores deterministically.

---

### [x] T6.3 Dense embeddings per PDF (offline-friendly) + cache

**Work**

* Choose embedding model config (local by default).
* Compute embeddings for chunks and store in:

  * `artifacts/retrieval_indexes/<pdf_id>/embeddings.npy`
  * metadata mapping chunk_id→row index
* Add cache guard: skip if exists and hash matches.

**AC**

* Dense retrieval returns relevant chunks for a simple query.

---

### [x] T6.4 Reranker (cross-encoder) over topN

**Work**

* Integrate reranker model locally if possible.
* API: `rerank(query, candidate_texts) -> scores`
* Apply to fused candidate list.

**AC**

* Reranking changes ordering in reasonable ways in test queries.

---

### [x] T6.5 Multi-query expansion + RAG-Fusion

**Work**

* Implement:

  * query generator prompt producing N variants
  * for each query: retrieve (BM25 + dense)
  * fuse results using reciprocal rank fusion
* Make N configurable (default 4–8).

**AC**

* Fusion improves recall on a small retrieval benchmark set (manual eval).

---

### [x] T6.6 HyDE retrieval

**Work**

* Implement HyDE:

  * create hypothetical answer passage for the group/column query
  * embed HyDE text and retrieve dense results
  * union with other retrieval sets before rerank

**AC**

* HyDE helps for at least one known “hard field” in a test fixture.

---

### [x] T6.7 Context packaging + neighborhood expansion

**Work**

* After rerank:

  * pick topM chunks
  * add neighbor chunks (prev/next or same-page)
  * cap total tokens
* Produce final context bundle with:

  * chunks list (id, page range, text)

**AC**

* Context bundle is within size limits and keeps page metadata.

---

### [x] T6.8 Retrieval debug panel in UI (developer tool)

**Work**

* Add UI section (hidden under “Advanced”) to:

  * input a query
  * choose a PDF
  * show retrieved chunks with scores and page ranges

**AC**

* Makes it easy to diagnose missing fields.

---

## 7) Extraction engine (grouped) + evidence discipline

### [x] T7.1 Define extraction groups from schema

**Work**

* If schema provides `group`, build groups; else default group all columns.
* UI lets user reorder groups and run subset of groups.

**AC**

* Groups appear in Run settings and are persisted.

---

### [x] T7.2 Example selection from existing filled cells

**Work**

* For each column, select up to N example rows where:

  * cell is non-empty (and not `" "`)
* Provide examples as (row title + example value) to the prompt.

**AC**

* Examples show diverse formats and help the model mirror conventions.

---

### [x] T7.3 Group extraction node (LLM) → proposals

**Work**

* For each matched PDF+row+group:

  * compute list of target columns that are unlocked + empty
  * run retrieval pipeline for group (or per-column if configured)
  * call extraction prompt
  * validate JSON
  * store proposals with:

    * proposed_value (text)
    * evidence_json (quotes, page, locator hints)
    * confidence
    * flags_json: needs_more_evidence, mapping_dependent
* Implement needs-more-evidence rules:

  * missing quote or page
  * cannot locate highlight rectangle in later step (initially set “unknown”; finalize later)
  * overly generic quote (heuristics)
  * inferred value with weak derivation

**AC**

* Produces proposals only for unlocked/empty cells.
* Every `found` proposal includes quote+page.

---

### [x] T7.4 Verify mode (optional) for locked cells

**Work**

* When verify mode enabled:

  * for locked cells (or selected columns), retrieve context and produce:

    * supports/contradicts/unclear
    * evidence quote+page
* Store as proposals with a different proposal type or in `events`.

**AC**

* Verify mode does not alter locked values.
* Review UI can display verification items per row.

---

### [x] T7.5 Evidence locator resolution (precompute highlights)

**Work**

* Implement a post-processing step (can run during batch):

  * attempt to locate each evidence quote on the specified page:

    1. PyMuPDF exact/normalized substring search
    2. shortened substring search
    3. token-based approximate matching using pdfplumber tokens
  * store rectangles in evidence_json if found
  * if not found: set needs_more_evidence = true and record reason

**AC**

* Highlight rectangles exist for most proposals on typical PDFs.
* Failures are visible and flagged.

---

## 8) LangGraph workflow end-to-end

### [x] T8.1 Define graph state + node wiring

**Work**

* Implement LangGraph graph with nodes:

  * load_inputs
  * ingest_table_schema
  * enumerate_pdfs
  * parse_pdf
  * build_index
  * extract_header
  * shortlist_candidates
  * adjudicate_match
  * extract_groups (loop)
  * resolve_evidence_locators
  * mark_pdf_done
  * finalize_run
* Ensure checkpoint after each PDF.

**AC**

* End-to-end run processes all PDFs and produces populated DB tables.

---

### [x] T8.2 Resume + stop controls

**Work**

* UI controls:

  * Start new run
  * Resume run (select run dir)
  * Stop gracefully (sets a flag checked between PDFs)
* Ensure resume reads DB status and continues.

**AC**

* Stop mid-run leaves DB consistent.
* Resume continues without duplication.

---

## 9) Review UI (row-by-row) with PDF highlight

### [x] T9.1 Review navigation and filters

**Work**

* Review tab:

  * select row (search by title)
  * show mapping status (ambiguous, duplicates)
  * show “needs_more_evidence” counts
* Filter rows:

  * only rows with proposals
  * only ambiguous mapping
  * only duplicates
  * only needs_more_evidence

**AC**

* User can quickly reach problematic rows.

---

### [x] T9.2 Proposal cards with Accept/Reject/Revise

**Work**

* For each proposal (sorted by group/priority):

  * show current value (from table) + proposed value
  * show confidence + flags
  * show evidence list with page jump
  * buttons:

    * Accept
    * Reject
    * Revise (editable textbox + optional note)
* Persist decisions in `reviews`.

**AC**

* Decisions persist across UI refresh.
* Accepted values (including manual edits) override proposed values on export.

---

### [x] T9.3 PDF viewer + highlight rendering

**Work**

* Display PDF (page selector):

  * show rectangles for selected proposal’s evidence
* Provide:

  * “Jump to evidence page”
  * “Copy quote”
* If rectangles missing:

  * show warning and mark needs_more_evidence visually

**AC**

* Highlight rectangles visible for most proposals.
* Fallback behavior is clear.

---

## 10) Export/apply decisions + audit

### [x] T10.1 Apply decisions and produce updated XLSX copy

**Work**

* Generate `exports/updated_table.xlsx`:

  * copy original table
  * apply accepted proposals
* apply accepted proposals with final_value when provided
  * never apply rejected
* Values as text.

**AC**

* Output table reflects review decisions exactly.
* Original input file remains unchanged.

---

### [x] T10.2 Audit log + proposal dumps

**Work**

* Export:

  * `exports/audit_log.csv`
  * `exports/proposals.jsonl`
  * keep `pdf_row_matches.csv`
* Audit includes:

  * run_id, pdf_id, row_id, column
  * old_value, proposed_value, decision, final_value
  * evidence (quote, page, rectangles present)
  * timestamps

**AC**

* Audit is comprehensive and machine-readable.

---

## 11) Quality, tests, and benchmarks

### [x] T11.1 Unit tests

**Work**

* Add `pytest` suite:

  * lock rules (`" "` special-case)
  * schema parsing
  * fuzzy matching shortlist stability
  * evidence locator (mock small PDFs)

**AC**

* CI/local run passes quickly.

---

### [x] T11.2 Integration test fixture

**Work**

* Create `tests/fixtures/`:

  * small XLSX + schema
  * 3–5 small PDFs (or generate minimal PDFs for tests)
* Add “mock LLM” mode returning fixed JSON so tests don’t require models.

**AC**

* `pytest -q` runs end-to-end pipeline in mock mode.

---

### [x] T11.3 Retrieval sanity benchmark (developer workflow)

**Work**

* Add a simple benchmark script:

  * user provides a PDF + a set of target questions (columns)
  * script prints top retrieved chunks before and after rerank
* Store benchmark outputs in run artifacts for debugging.

**AC**

* Makes retrieval regressions visible.

---

## 12) Packaging & UX polish

### [x] T12.1 Single-command launch

**Work**

* Ensure CLI supports:

  * `paper-table-agent ui`
  * `paper-table-agent run --config run_config.json`
  * `paper-table-agent export --run_dir ...`
* Provide sample config template generator.

**AC**

* A new user can install and start UI in 2 commands.

---

### [x] T12.2 Documentation

**Work**

* README sections:

  * Installation (local models and cloud)
  * LM Studio + Ollama setup examples (OpenAI-compatible endpoints)
  * Input XLSX schema sheet format
  * Run/Review/Export workflow
  * Troubleshooting (OCR, highlighting, ambiguous matches)

**AC**

* Docs are sufficient to run without reading code.

---

## 13) Stretch tasks (after MVP is stable)

### [ ] S1 Add GROBID integration for richer structure

* Use GROBID TEI to enhance section chunking and header parsing.

### [ ] S2 Add table structure extraction improvements

* Table extraction pipeline with Unstructured hi_res + fallback to Camelot.

### [ ] S3 Concurrency

* Parallelize per-PDF parsing/indexing/extraction with rate-limit aware scheduling.

### [ ] S4 “Fast mode” vs “Max success mode” tuning panel

* Provide clear speed/quality tradeoffs.

---

## Definition of MVP (minimum shippable)

MVP is complete when:

1. The app loads XLSX + schema sheet, computes locks, enumerates PDFs.
2. Parses PDFs (text + tokens), matches PDFs to rows with report.
3. Extracts at least one group of columns with evidence quotes+pages.
4. Stores proposals in SQLite and supports resume.
5. Review UI supports row-by-row accept/reject/revise and shows PDF with highlights for most evidence.
6. Export produces updated XLSX + audit log.

---
