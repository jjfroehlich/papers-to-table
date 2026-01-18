# Spec: Paper Table Agent (LangGraph) — Batch PDF→Table Proposals with Evidence + Post-Run Row Review

This spec updates the previous version using your feedback:

* 1-to-1 mapping (with duplicate detection + mapping report)
* authors as full comma-separated list
* year tolerance ±1 (title/authors primary)
* lock policy: any non-empty cell is locked **except** a single space `" "` counts as empty
* optional **Verify mode** for locked cells
* all values stored as **text**
* OCR fallback included
* review by **row**
* local-first with Ollama/LM Studio, optional cloud provider (OpenAI-compatible)
* schema descriptions in a separate XLSX sheet
* highlight rectangles required in most cases
* add: **two-pass matching** and **Needs more evidence** flag
* retrieval/chunking upgraded to a “best-practice / state-of-the-art” pipeline (hybrid + multi-query + reranking + hierarchical summaries)

---

## 0) What we’re building

A local-first app that:

1. **Ingests a table** (XLSX/CSV) where each row is one publication and columns include at least title/authors/year.
2. **Ingests a folder of PDFs** (filenames unreliable).
3. For each PDF, **extracts title/authors/year from the PDF itself** and matches it to a row via two-pass matching.
4. For each matched (or tentatively matched) row, **extracts missing values** for ~35 columns and stores them as **proposals** (never edits the original table during the run).
5. Every proposed cell value includes **evidence** (quote(s) + page + highlight rectangles). If evidence is weak, proposal is flagged **Needs more evidence**.
6. After the run completes, you review **row-by-row** in a UI: Accept / Reject / Revise proposals, with the PDF displayed and evidence highlighted.
7. Exports an updated table copy + audit logs.

---

## 1) Goals / Non-goals

### Goals

* Process the full PDF set placed in the folder (subset allowed; missing PDFs are OK).
* Don’t stop early: complete batch run; persist checkpoints; resumable.
* Evidence-first extraction: quotes + page + highlight rectangles in most cases.
* Row-based review after the run.

### Non-goals (MVP)

* No internet-based matching (Crossref/OpenAlex/PubMed) for row assignment.
* No multi-user system.
* No training/fine-tuning required.

---

## 2) Inputs / Outputs

### Inputs

* **Table**: XLSX preferred. CSV supported.
* **Schema sheet** (in the XLSX): a separate sheet, e.g. `schema`, containing:

  * `column_name`
  * `description`
  * optional `group`, `priority`
  * optional `evidence_required` (default true)
  * optional `empty_values` (default: `["", "NA", "N/A", "null", "-", " "]` but note `" "` is special: counts as empty and therefore *not* locked)
* **PDF folder**: user places only PDFs to work on.

### Outputs (per run)

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
        <pdf_id>.json          # structured parse with page text + layout tokens
      ocr/
        <pdf_id>/...           # only if OCR used
      retrieval_indexes/
        <pdf_id>/...           # per-pdf hybrid indexes
      thumbnails/
    logs/
      run.log
      errors.jsonl
```

---

## 3) Core policies

### 3.1 Locking (default)

* Any cell is **locked** if it is non-empty **and not exactly** `" "` (single space).
* Locked cells are never overwritten during extraction.

### 3.2 Verify mode (optional)

A mode where locked cells are **not changed**, but the system produces **verification items**:

* status: `supports` | `contradicts` | `unclear`
* evidence quote(s) + page + highlight
* short rationale

Verification results are reviewed alongside proposals, row-by-row.

### 3.3 Values as text

All proposals stored and exported as text (even if numeric). This keeps Excel behavior predictable and avoids type disputes.

---

## 4) Matching PDF → Row (1-to-1, two-pass)

### 4.1 PDF header extraction

For each PDF, extract candidate metadata from the PDF content:

* title
* authors (best-effort full list)
* year (optional; ±1 tolerance)
* evidence for title/authors (quote + page)
* confidence

Parsing uses structured text extraction first (see §7), then LLM just *interprets*, not “guesses”.

### 4.2 Two-pass matching

**Pass 1 (deterministic shortlist)**

* Normalize title strings.
* Use fuzzy matching (RapidFuzz) to score against all table titles; take top K (default 10). ([rapidfuzz.github.io][1])
* Optionally incorporate author overlap score (token-set/Jaccard on last names) to break ties.

**Pass 2 (LLM adjudication)**
Provide the LLM:

* extracted PDF title/authors/year + evidence quotes
* candidate rows (row_id, title, authors, year)
  LLM outputs:
* selected `row_id` or `ambiguous`
* top 3 candidates + rationale
* confidence

### 4.3 1-to-1 enforcement + duplicates detection

Default assumption: one PDF ↔ one row.

* If multiple PDFs map to the same row above threshold:

  * keep the highest-confidence assignment
  * flag the others as duplicates
  * surface in mapping report + review UI as “Needs user attention”
* If a PDF is ambiguous:

  * store `needs_review` mapping
  * extraction can still proceed (configurable). Default: proceed but mark proposals as “mapping-dependent”.

### 4.4 Mapping report (end of mapping sub-phase)

Before/alongside extraction (but without requiring user intervention), generate a report:

* PDFs processed / matched / ambiguous / failed
* duplicates detected
* for each matched PDF:

  * extracted title/authors/year vs table row title/authors/year side-by-side
  * confidence + evidence snippets
    This addresses your request for a mapping summary.

---

## 5) Extraction → Proposals (missing cells only)

### 5.1 Column grouping

Split ~35 columns into groups (configurable), e.g.:

* Identity & system
* Perturbation / intervention
* Methods
* Data types & readouts
* Main quantitative results
* Notes / limitations

Each group is extracted separately to reduce failure and improve evidence quality.

### 5.2 Proposal record

For each (row_id, column):

* proposed_value (text or null)
* status: `found` | `inferred` | `not_found`
* confidence (0–1)
* evidence[]:

  * quote (short)
  * page number
  * locator strategy: exact quote / fuzzy span / token bbox reference
  * highlight rectangles (bounding boxes), when available
* flags:

  * `needs_more_evidence` (boolean)
  * `mapping_dependent` (boolean)
* rationale (short; only for inferred/derived)

### 5.3 Needs more evidence flag

A proposal is flagged if:

* quote is too indirect/ambiguous,
* quote cannot be reliably located for highlighting,
* the value is derived but supporting text is weak.

These are prioritized in review.

---

## 6) Review UI (row-by-row, post-run)

### 6.1 Technology choice

* **Streamlit** (fast MVP) with PDF viewing via `st.pdf` or `streamlit-pdf-viewer`. ([Streamlit Docs][2])

### 6.2 Row review layout

For a selected row:

* Row header: title/authors/year
* Mapping panel: linked PDF, mapping confidence, duplicates warnings
* Current values (locked cells shown read-only)
* Proposed updates list (one card per column):

  * proposed value
  * evidence snippets + page
  * “jump to page”
  * Accept / Reject / Revise
  * indicator if Needs more evidence

### 6.3 PDF highlighting requirement

* Display PDF page and draw highlight rectangles for evidence spans (most cases).
  Implementation uses PyMuPDF search + highlight annotations, falling back to layout-token-based bbox matching when exact substring search fails. ([pymupdf.readthedocs.io][3])

---

## 7) Parsing + Retrieval (state-of-the-art / best success rate)

You asked for the “best, state-of-the-art approach” to maximize success. This section is the main upgrade.

### 7.1 Parsing pipeline (best-effort structured representation)

We build a **multi-layer parse** so retrieval and highlighting work well:

1. **GROBID** (scientific-PDF-focused) to TEI XML:

   * extracts structured header (title/authors/affiliations), abstract, sections, references. ([grobid.readthedocs.io][4])
2. **Layout-aware text tokens**:

   * Use pdfplumber to extract words with coordinates (bbox), enabling robust highlighting even when text extraction differs from rendered text. ([GitHub][5])
3. **PyMuPDF page text + search**:

   * fast per-page text plus `search_for()` support for highlighting by substring. ([pymupdf.readthedocs.io][3])
4. **Tables extraction (optional but recommended for success)**:

   * Use Unstructured `partition_pdf(..., strategy="hi_res", infer_table_structure=True)` to detect layout and tables; can run locally with `unstructured[local-inference]`. ([docs.unstructured.io][6])
   * Optional fallback/augmentation for tables: Camelot / tabula-py. ([camelot-py.readthedocs.io][7])

**Output**: per PDF, we store:

* page_text (per page)
* sectioned_text (from GROBID)
* tokens[] with (text, page, bbox)
* table objects (cells + page + bbox if available)

### 7.2 Indexing strategy (per-PDF “micro-index”)

Instead of one global index, build a **micro-index per PDF** (PDFs are self-contained; this improves precision and keeps evidence local).

Each PDF micro-index contains nodes of multiple granularities:

* token/line-level “quote candidates” (small)
* paragraph chunks (medium)
* section chunks (large)
* optional hierarchical summaries (see 7.5)

### 7.3 Hybrid retrieval backbone (offline-friendly)

Use a **hybrid** of sparse + dense + reranking:

* **Sparse**: BM25 over chunk text (fast recall).
* **Dense / multi-function embeddings**: BGE-M3 recommended because it supports dense + sparse + multi-vector (ColBERT-like) retrieval in one model family. ([arXiv][8])
* **Reranking** (critical for precision):

  * BGE reranker (cross-encoder) over top-N retrieved chunks. ([bge-model.com][9])
  * Optional: Jina reranker v2 (if preferred/available). ([Hugging Face][10])
* Optional advanced: **ColBERT/late-interaction** reranking for hard queries (especially short “keyphrase-like” queries), if you decide to integrate it. ([arXiv][11])

### 7.4 Query-time “best success rate” retrieval (multi-query + HyDE + fusion)

For each extraction group (and sometimes per column), we do:

1. **Query construction**

   * Base query from column description + row context (paper title, key terms).
2. **Multi-query expansion (RAG-Fusion)**

   * LLM generates N query variants that target different phrasings and synonyms.
   * Retrieve per query, then **reciprocal-rank-fuse** results. ([arXiv][12])
3. **HyDE retrieval**

   * LLM generates a *hypothetical answer passage* (not used as truth) → embed it → retrieve semantically aligned real chunks. ([arXiv][13])
4. **Hybrid retrieval union**

   * Combine: BM25 topK + dense topK + (optional) multi-vector topK.
5. **Rerank**

   * Cross-encoder rerank to final topM (e.g., 12–25).
6. **Context packaging**

   * Include the final chunks plus a small “neighborhood” window (previous/next chunk or same-page adjacency) to preserve missing context.
7. **Evidence-first extraction**

   * The LLM must only propose values that can be tied to specific retrieved chunks and quoted.

This pipeline (multi-query + HyDE + hybrid + rerank) is deliberately heavy because your goal is maximum success rate, not minimal compute.

### 7.5 Hierarchical retrieval for long papers (RAPTOR-style, optional “max recall” mode)

For papers where critical info is spread out, add a hierarchical tree:

* cluster chunks → summarize → embed summaries recursively
* retrieve from both summary nodes and leaf nodes at inference time

This is inspired by RAPTOR’s recursive summarization tree approach. ([arXiv][14])

Pragmatic implementation:

* enable per-PDF if PDF > X pages or if initial retrieval confidence is low.

### 7.6 OCR fallback

If the PDF is scanned or text extraction fails:

* Use Unstructured `strategy="hi_res"` (layout model) and fall back to OCR-only when needed. ([docs.unstructured.io][6])
* Store OCR outputs separately and mark proposals as OCR-derived (for review caution).

---

## 8) LangGraph orchestration (durable, resumable)

### 8.1 Why LangGraph

* resumable batch runs with checkpointing/persistence. ([LangChain Docs][15])
* supports interrupts/HITL patterns, though in this app we mainly use it for reliability rather than mid-run review. ([LangChain Docs][16])

### 8.2 Graph phases

**Phase A: Load & Validate**

* load table
* load schema sheet
* compute lock map
* enumerate PDFs, compute pdf_id

**Phase B: Parse & Index (per PDF)**

* parse PDF (GROBID + layout tokens + page text; OCR fallback)
* build per-PDF hybrid indexes

**Phase C: Mapping (per PDF)**

* extract header metadata
* pass 1 shortlist (RapidFuzz)
* pass 2 adjudication (LLM)
* store match + mapping report data
* detect duplicates

**Phase D: Extraction (per PDF per group)**

* retrieve context using §7 pipeline
* propose values for missing cells only
* attach evidence + highlight locators
* apply needs_more_evidence rules
* store proposals

**Phase E: Finalize**

* write mapping report
* mark run complete
* export proposal dumps

Checkpoint after each PDF.

---

## 9) Model/provider abstraction (local-first, cloud optional)

### 9.1 OpenAI-compatible API everywhere

Support a single provider interface: OpenAI-compatible base_url + key.

* **LM Studio** exposes OpenAI-compatible endpoints. ([LM Studio][17])
* **Ollama** offers OpenAI compatibility (noting it may be “experimental” depending on version). ([Ollama][18])
* Cloud providers (OpenAI, others) also work under the same interface.

### 9.2 Model roles

* “Extractor” model: good at strict JSON + evidence discipline.
* “Retriever helper” model: query expansion + HyDE generation.
* “Reranker” model: cross-encoder (non-LLM).

Defaults for offline:

* Local LLM for extraction + HyDE/query expansion
* Local embeddings + reranker (GPU helps)

---

## 10) Export & Audit

### Exports

* updated_table.xlsx (apply accepted/revised only)
* audit_log.csv (proposal→decision lineage)
* pdf_row_matches.csv (mapping + confidence + duplicates)
* mapping_report.html

Audit log includes:

* run_id
* pdf_id, row_id
* column
* old_value
* proposed_value
* evidence (quote/page)
* decision + final_value
* timestamps

---

## 11) Acceptance criteria

* **Mapping report** exists and includes counts + side-by-side comparisons.
* Locked cells unchanged (unless Verify mode, which only adds verification items).
* Every `found` proposal has evidence with page and highlight rectangles for most cases.
* Needs-more-evidence proposals are flagged and filterable.
* Review is row-by-row and exports produce a clean updated table.

---

## 12) Remaining clarifications (please answer)

1. **Which exact column headers** in your table represent:

   * title
   * authors
   * year
     (We’ll support a UI “column mapping” selector, but need defaults.)

2. **What should happen if a PDF matches a row that already has many non-empty cells**:

   * still extract missing cells only (default), or
   * also run Verify mode automatically for that row?

3. **Duplicate policy** when two PDFs appear to be the same paper:

   * keep both as “duplicates” needing manual resolution (default), or
   * auto-deduplicate by identical title+authors similarity above a threshold?

4. **Evidence strictness**:

   * If we cannot reliably place highlight rectangles (rare PDFs with weird encoding), is it acceptable to store page + quote only and flag Needs more evidence?

5. **Performance preference**:

   * “Max success rate even if slow” (default implied), or do you want a “fast mode” toggle?

---

[1]: https://rapidfuzz.github.io/RapidFuzz/?utm_source=chatgpt.com "RapidFuzz 3.14.3 documentation"
[2]: https://docs.streamlit.io/develop/api-reference/media/st.pdf?utm_source=chatgpt.com "st.pdf - Streamlit Docs"
[3]: https://pymupdf.readthedocs.io/en/latest/page.html?utm_source=chatgpt.com "Page - PyMuPDF documentation"
[4]: https://grobid.readthedocs.io/en/latest/Principles/?utm_source=chatgpt.com "How GROBID works"
[5]: https://github.com/jsvine/pdfplumber?utm_source=chatgpt.com "jsvine/pdfplumber: Plumb a PDF for detailed ..."
[6]: https://docs.unstructured.io/open-source/core-functionality/partitioning?utm_source=chatgpt.com "Partitioning"
[7]: https://camelot-py.readthedocs.io/?utm_source=chatgpt.com "Camelot: PDF Table Extraction for Humans — Camelot 1.0.9 ..."
[8]: https://arxiv.org/abs/2402.03216?utm_source=chatgpt.com "BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation"
[9]: https://bge-model.com/bge/bge_reranker.html?utm_source=chatgpt.com "BGE-Reranker — BGE documentation"
[10]: https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual?utm_source=chatgpt.com "jinaai/jina-reranker-v2-base-multilingual"
[11]: https://arxiv.org/abs/2004.12832?utm_source=chatgpt.com "ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT"
[12]: https://arxiv.org/abs/2402.03367?utm_source=chatgpt.com "[2402.03367] RAG-Fusion: a New Take on Retrieval- ..."
[13]: https://arxiv.org/abs/2212.10496?utm_source=chatgpt.com "Precise Zero-Shot Dense Retrieval without Relevance Labels"
[14]: https://arxiv.org/abs/2401.18059?utm_source=chatgpt.com "RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval"
[15]: https://docs.langchain.com/oss/python/langgraph/persistence?utm_source=chatgpt.com "Persistence - Docs by LangChain"
[16]: https://docs.langchain.com/oss/python/langgraph/interrupts?utm_source=chatgpt.com "Interrupts - Docs by LangChain"
[17]: https://lmstudio.ai/docs/developer/openai-compat?utm_source=chatgpt.com "OpenAI Compatibility Endpoints | LM Studio Docs"
[18]: https://ollama.com/blog/openai-compatibility?utm_source=chatgpt.com "OpenAI compatibility · Ollama Blog"