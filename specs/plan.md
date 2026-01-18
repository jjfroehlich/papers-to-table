# plan.md — Paper Table Agent (LangGraph)

Batch PDF→Table proposals with evidence + post-run row review

## 1) Purpose

Implement the system described in `spec.md` as a local-first, easy-to-run app with:

* a **Batch Run** phase (parse → match → retrieve → extract → store proposals)
* a **Review** phase (row-by-row accept/reject/revise with PDF evidence highlighting)
* **Exports** (updated table copy + audit + mapping report)

This plan is structured for spec-driven development and can be converted into `tasks.md` later.

---

## 2) Guiding principles

1. **Durability first**: Every unit of work (per PDF, per group) must be checkpointed and resumable.
2. **Evidence first**: Proposals without strong evidence are explicitly flagged.
3. **Local-first**: Default runs offline (LM Studio / Ollama), but supports cloud (OpenAI-compatible) by configuration.
4. **Two-phase UX**: Run everything → then review only at the end.
5. **Make failures visible**: Clear status, counts, and reports (mapping report, failed PDFs, duplicates, needs-more-evidence).

---

## 3) Implementation milestones

### Milestone 0 — Repo skeleton + configuration (foundation)

**Deliverables**

* Project scaffold with clear run folder layout
* Config model(s) and default `run_config.json`
* CLI entrypoint + Streamlit app skeleton with “Run / Review / Export” tabs
* SQLite schema created and migrations strategy defined

**Key tasks**

* Create top-level package structure:

  * `paper_table_agent/` (core)
  * `paper_table_agent/ui/` (streamlit)
  * `paper_table_agent/graph/` (langgraph)
  * `paper_table_agent/io/` (xlsx/csv, schema)
  * `paper_table_agent/pdf/` (parsing + highlighting)
  * `paper_table_agent/retrieval/` (indexing + retrieval)
  * `paper_table_agent/llm/` (provider abstraction)
  * `paper_table_agent/store/` (sqlite layer)
* Define `RunConfig` (Pydantic) with:

  * paths (table, schema sheet name, pdf folder, run dir)
  * provider (base_url, api_key optional, model names)
  * matching params (topK, threshold, year tolerance)
  * extraction params (groups, max chunks, confidence thresholds)
  * retrieval mode (max-success vs fast)
  * OCR enable (bool) + thresholds
* Implement run directory creation:

  * `runs/<timestamp>__<table_name>/...`
* Implement SQLite schema:

  * `pdfs`, `rows`, `matches`, `proposals`, `reviews`, `locks`, `events/errors`
* Add a small “demo run” mode that populates DB from stub inputs (no LLM yet).

**Definition of done**

* `streamlit run app.py` opens UI, creates a run directory, initializes DB.

---

### Milestone 1 — Table + schema ingestion + locking rules

**Deliverables**

* XLSX read/write (primary)
* CSV read (secondary; no schema sheet)
* Schema sheet reader (colname + description + optional group/priority)
* Lock map computed (non-empty and not `" "`)

**Key tasks**

* Implement table adapter:

  * load XLSX into memory (pandas/openpyxl)
  * store row ids and raw values
  * write updated XLSX copy later
* Implement schema ingestion:

  * schema sheet with: `column_name`, `description`, optional `group`, `priority`
  * validate schema columns exist in table (or mark “schema-only” columns)
* Implement lock rules:

  * default empty values list includes `" "` special-case: treat as empty/unlocked
  * store locks in DB (`locks` table) or compute on the fly and persist
* Add UI mapping of special columns:

  * Title column, Authors column, Year column
  * Provide defaults if common names detected, else user selects.

**Definition of done**

* App can load a real XLSX + schema sheet and show row/column summary + lock counts.

---

### Milestone 2 — PDF parsing MVP + OCR fallback plumbing

**Deliverables**

* Per-PDF stable ID (sha1) + metadata (path, pages)
* Text extraction per page (fast path)
* Token/word extraction with bounding boxes (layout-aware path)
* OCR fallback hook (optional) with clear flags in DB (even if OCR not fully tuned yet)

**Key tasks**

* Integrate parsing components (incrementally):

  1. **PyMuPDF**: per-page text, page count, and search support
  2. **pdfplumber**: words/tokens with bbox and page mapping
  3. Structured header extraction input preparation (first 1–2 pages text + tokens)
* Store parse artifacts:

  * `artifacts/parsed/<pdf_id>.json` containing:

    * page_text[]
    * tokens[] (text, page, bbox)
* OCR fallback strategy:

  * If extracted text length is too low or mostly empty pages, mark `needs_ocr=true`
  * For MVP: route to a placeholder OCR module that can be enabled later
  * Persist OCR decision + status in DB.

**Definition of done**

* App can ingest PDFs, parse them, and store per-page text + tokens, and show parse stats.

---

### Milestone 3 — Two-pass matching (PDF → row) + mapping report

**Deliverables**

* LLM-based header metadata extraction (title/authors/year) with evidence quotes/pages
* Pass 1 deterministic shortlist (fuzzy title + author overlap)
* Pass 2 LLM adjudication (choose row_id or ambiguous)
* 1-to-1 enforcement + duplicate detection
* Mapping report export (HTML + CSV)

**Key tasks**

* Implement LLM provider abstraction:

  * OpenAI-compatible client with base_url (LM Studio/Ollama/cloud)
  * JSON-mode prompting + strict parsing with retries
* Header extraction prompt:

  * input: first pages text, optionally top tokens
  * output: title, authors list, year, evidence quote(s) + page, confidence
* Candidate shortlist:

  * normalize titles
  * RapidFuzz topK title match
  * optional author overlap score on last names
  * year filter ±1 if year available
* Adjudication prompt:

  * provide extracted header + evidence
  * provide candidate rows (id, title, authors, year)
  * output: row_id or ambiguous + top candidates + confidence
* Store in DB:

  * `matches` (status proposed/needs_review)
  * duplicates flagged if same row assigned by multiple pdfs above threshold
* Mapping report generator:

  * counts summary
  * table of PDF vs row side-by-side with confidence + snippets
  * duplicates section + ambiguous section

**Definition of done**

* Given a folder of PDFs + table, system produces a mapping report with reasonable matches and flags.

---

### Milestone 4 — Retrieval/indexing “max success rate” pipeline (core RAG)

**Deliverables**

* Per-PDF micro-index (hybrid: BM25 + embeddings)
* Multi-query expansion + HyDE + fusion + reranking
* Context packaging with page-aware chunk IDs
* Retrieval evaluation tools (debug UI panel for “why did we retrieve this?”)

**Key tasks**

* Define chunking:

  * multi-granularity nodes: paragraph/section/page window
  * each chunk includes: text, page range, chunk_id, source type (section/page/table)
* Build sparse index:

  * BM25 (e.g., rank-bm25 or equivalent) over chunks
* Build dense index:

  * embeddings model (local) with caching
  * store vectors per chunk
* Reranker:

  * cross-encoder reranker model (local if possible)
  * rerank topN combined results
* Multi-query + HyDE:

  * query variants from column/group description
  * HyDE hypothetical passage for embedding-based retrieval
  * fuse results using reciprocal rank fusion
* Context packaging:

  * choose topM chunks + neighbor expansion
  * ensure each chunk keeps page metadata and can be traced back for evidence
* Add “fast mode” toggle:

  * disables HyDE and reduces reranking depth for speed (but keep max-success default)

**Definition of done**

* Retrieval consistently surfaces relevant chunks for diverse columns in test PDFs and is inspectable.

---

### Milestone 5 — Extraction engine (grouped) + proposals store

**Deliverables**

* Extraction per column group using retrieval context
* Proposals written to SQLite with evidence objects + needs-more-evidence flag
* Locked cells respected
* Optional Verify mode produces verification items (no edits)

**Key tasks**

* Column grouping implementation (configurable):

  * `groups = [{name, columns[]}]`
* Example selection:

  * For each column, sample N filled examples from other rows (read-only)
* Extraction prompt template:

  * row context (title/authors/year)
  * locked cells as context
  * group schema descriptions
  * examples (column → example value)
  * retrieved chunks (with page labels and chunk IDs)
  * output: per-column proposal objects
* Evidence discipline:

  * require at least one quote + page for status=found
  * store quote + page + locator hint (substring) + chunk_id
* Needs-more-evidence heuristics:

  * quote missing, too generic, or cannot be located reliably
  * derived metric without clear support
  * retrieval confidence low
* Validation layer:

  * ensure JSON conforms
  * ensure not proposing for locked cells
  * ensure value is text (string) or null
* Store proposals (and verification items if enabled)

**Definition of done**

* Batch run completes for a set of PDFs, proposals are populated for missing cells with evidence.

---

### Milestone 6 — Review UI (row-by-row) + PDF highlighting

**Deliverables**

* Review tab shows one row at a time with all proposals
* Accept/Reject/Revise stored in `reviews`
* Evidence PDF viewer with highlight rectangles in most cases
* Jump-to-page + show evidence snippets

**Key tasks**

* Review navigation:

  * search by title/row_id
  * filters: needs_more_evidence, low confidence, ambiguous mapping, duplicates
* Proposal cards per column:

  * current value, proposed value, status, confidence, flags
  * evidence quotes list with page
  * Accept/Reject/Revise controls
* Highlight engine:

  * primary: locate evidence substring on specified page using PyMuPDF search
  * fallback 1: normalize whitespace and search shortened substrings
  * fallback 2: use pdfplumber token bboxes to approximate span (token-level matching)
  * store resolved highlight rectangles for caching
* Display:

  * render annotated page image OR create temporary annotated PDF copy for viewing
  * ensure page-level rendering is responsive

**Definition of done**

* Reviewer can process a row end-to-end, with highlights working for most evidence items.

---

### Milestone 7 — Export/apply decisions + audit logs

**Deliverables**

* Export updated table XLSX (copy) applying accepted + revised proposals only
* Export audit log CSV
* Export match map CSV and mapping report HTML

**Key tasks**

* Apply logic:

  * accepted: write proposed value to output table
  * revised: write reviewer value to output table
  * rejected: do nothing
* Keep original table unchanged; output to `exports/updated_table.xlsx`
* Audit log includes:

  * run_id, pdf_id, row_id, column, old_value, proposed_value, decision, final_value, evidence refs, timestamps
* Export summary reports:

  * coverage per column
  * counts by status/flags/confidence bands

**Definition of done**

* One click export produces updated XLSX + audit CSV that matches review decisions.

---

## 4) Architecture outline

### 4.1 Components

* **UI**: Streamlit (Run / Review / Export)
* **Orchestration**: LangGraph graph with checkpoints
* **Store**: SQLite + artifact files
* **PDF parsing**: PyMuPDF + pdfplumber (+ OCR module)
* **Retrieval**: per-PDF hybrid index + reranker
* **LLM client**: OpenAI-compatible (LM Studio / Ollama / cloud)

### 4.2 LangGraph graph layout (high level)

* `load_inputs → ingest_table → ingest_pdfs → parse_pdf → build_index → extract_header → shortlist → adjudicate → extract_groups (loop) → validate → store → next_pdf → finalize`

Checkpoint after:

* each PDF parsed
* each match stored
* each group extraction stored

---

## 5) Testing strategy

### 5.1 Unit tests

* locking rules (`" "` is empty)
* schema parsing/validation
* PDF parsing smoke tests on small PDFs
* fuzzy matching scoring

### 5.2 Integration tests

* end-to-end run on a small fixture set:

  * 3–5 PDFs
  * 10-row table with known matches
* deterministic “mock LLM” mode:

  * returns canned JSON for header/extraction to test pipeline stability

### 5.3 Highlight tests

* verify evidence substring can be located and rectangles produced on common PDF encodings
* ensure fallback token matching works on line-break disrupted text

### 5.4 Regression fixtures

* maintain a small corpus of tricky PDFs:

  * multi-column author lists
  * ligatures/hyphenation
  * table-heavy results
  * partial scans (OCR path)

---

## 6) Risks and mitigations

1. **Highlighting fails due to PDF encoding**

   * Mitigation: token-bbox fallback; flag needs_more_evidence; allow page-only fallback with prominent UI warning.

2. **Matching collisions / duplicates**

   * Mitigation: strict 1-to-1 enforcement rules + mapping report + review filters.

3. **Slow “max success” retrieval**

   * Mitigation: caching; pre-index once per PDF; add “fast mode” toggle; parallelize indexing/extraction with configurable concurrency.

4. **Local model JSON reliability**

   * Mitigation: strict schema validation + retries; smaller prompts; per-group extraction; optional use of stronger cloud model.

---

## 7) Default decisions (can be changed later)

* Default file format: **XLSX**
* Review mode: **row-by-row**
* Run mode: extract even if mapping is `needs_review`, but mark proposals `mapping_dependent=true`
* Retrieval: **max success rate** mode enabled by default
* Values: **text only**
* Locked: all non-empty except `" "`.

---

## 8) Next step: convert this plan into tasks.md

Once you confirm this plan, we’ll break each milestone into:

* atomic tasks
* acceptance checks
* suggested file changes
* test checkpoints
* prompts/templates checklist

(That becomes `tasks.md` for the coding assistant to execute.)
