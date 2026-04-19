# Deep Research on RAG Usage and Architecture Improvements for papers-to-table

## Executive summary

The app implements **retrieval-augmented extraction** in a way that matches the core *principle* of Retrieval-Augmented Generation (RAG): it **retrieves relevant passages from each parsed paper and injects them into the LLM prompt** to ground per-cell extraction. In the backend retrieval module, this is explicitly framed as “BM25-lite chunk retrieval from ParsedDocument,” with contextualized retrieval text and a “top‑k + neighbor window” assembly. fileciteturn7file0L1-L15

However, it is **not a “full RAG stack” in the modern industry sense** (persistent vector store + embedding retriever + reranker + hybrid fusion across a corpus). Retrieval is **ephemeral per document**, **lexical** (BM25-like), and the code states the MVP baseline does **not** include reranking or HyDE-style generation-assisted retrieval. fileciteturn7file0L337-L349 This still counts as RAG *principles* (retrieval-conditioned generation), but it is best described as **“within-document RAG”** rather than “RAG over an external knowledge base.” This distinction matters to the recommendations: the biggest wins come from improving *document representation → chunking → retrieval quality* rather than adding a heavyweight vector DB.

Architecturally, the project has a strong foundation for accuracy and reviewer trust: **structured-output negotiation**, bounded JSON repair, explicit provider-mode truth, artifact persistence, evidence typing and anchoring, and an evaluation-mode masking concept (to avoid leaking gold values). The provider’s structured-output negotiation explicitly probes `json_schema` then falls back to `json_object` when needed. fileciteturn13file0L370-L444

The most actionable improvements (preserving extraction accuracy) cluster into four themes:

- **Confirm/strengthen RAG components:** formalize retrieval indexing per parsed document; add optional dense retrieval (LM Studio supports embeddings endpoints), plus hybrid fusion (BM25 + dense + RRF) where it improves recall; optionally add HyDE as a query-side augmentation in a quality preset. citeturn2search0turn1search48turn1search9turn0search5  
- **Improve extraction accuracy:** better contextualized chunk text (beyond section prefixing), more table-aware retrieval units, schema-aware retrieval policies, and aligning evidence artifacts with evaluation validation. fileciteturn7file0L103-L137  
- **Simplify architecture:** reduce config drift (example config vs runtime defaults), consolidate artifacts needed for eval (especially evidence and page text), and unify “retrieval strategy” naming with what is implemented. fileciteturn36file0  
- **Reduce latency without accuracy loss:** reuse HTTP clients, precompute retrieval indices, add bounded concurrency (semaphores) for style profiles and extraction calls, and add caching keyed by prompt+document hashes.

## Repository-based architecture and data flow

The system is built as a local-first pipeline that produces a file-based run bundle and supports a review workflow. The runner code is a staged pipeline (validating → inputs → provider init → parse → match → style profiles → extraction) that persists run metadata and artifacts in a run directory. fileciteturn9file0

A “retrieval result” is produced for each (paper, column) pair and persisted as JSON under `retrieval/<pdf_id>/<column>.json`. fileciteturn7file0L371-L443

### Current pipeline stages and artifacts

```mermaid
flowchart TD
  U[User] --> FE[Frontend reviewer UI]
  FE -->|create run / poll status| BE[Backend API + runner]
  BE --> V[Validate config + snapshot]
  V --> P[Parse PDFs to ParsedDocument]
  P --> M[Match PDFs to table rows]
  M --> SP[Style profiles per column]
  SP --> R[Retrieve field passages per (pdf, column)]
  R --> X[LLM extraction per eligible cell]
  X --> A[Artifacts persisted to run bundle]
  A --> FE

  subgraph Run bundle (filesystem)
    A -->|run.json| RJ[run.json]
    A -->|proposals.jsonl| PJ[proposals/proposals.jsonl]
    A -->|evidence records| EV[evidence/*.json]
    A -->|retrieval context| RET[retrieval/<pdf>/<col>.json]
    A -->|parsed outputs| PAR[parsed/...]
    A -->|matching artifacts| MAT[matching/...]
    A -->|summaries| SUM[summaries/*.json]
  end
```

Key evidence-bearing design choices in the repos:

- Retrieval chunks are derived from parsed-document “blocks” (paragraphs, headings, captions, table regions, etc.) and are **contextualized** by prepending a `[Section: ...]` marker in `retrieval_text` while keeping `display_text` source-preserving for review. fileciteturn7file0L103-L137  
- Retrieval uses a **BM25-like** scoring function (“BM25-lite”) over tokenized chunk text and includes a **neighbor window** (previous/next by reading order) to preserve local context. fileciteturn7file0L245-L326  
- The provider layer is designed around an OpenAI-compatible LM Studio endpoint and probes `/v1/models` plus structured-output behavior. fileciteturn13file0L287-L444  
- Structured output is enforced with a bounded recovery ladder: parse JSON, retry with stronger instruction once, then minimal JSON repair before failing. fileciteturn13file0L483-L528  

Some repository “research notes” discuss richer retrieval (dense retrieval, reranking, HyDE, RRF), but the retrieval implementation in `backend/app/retrieval.py` explicitly states the MVP baseline does not include reranking or HyDE. fileciteturn7file0L337-L349 This gap should be treated as **planned/aspirational unless implemented elsewhere** (and in this inspection, the core backend retrieval module is lexical-only).

## RAG assessment and retrieval design

### What counts as RAG here

In the canonical RAG formulation, a generator model is conditioned on retrieved passages from a non-parametric store, often a dense vector index. citeturn0search5 The app follows the same high-level flow—**retrieve relevant textual evidence, then generate**—but with important constraints:

- Retrieval is **within-document** (chunks from the same PDF/Paper), not “knowledge base over many sources.”  
- Retrieval is **lexical BM25-like**, not embedding-based.  
- There is **no persistent vector store** in the code path inspected; retrieval is computed from parsed blocks and scored per query. fileciteturn7file0L245-L326  

This still reflects *RAG principles*, and it is arguably well-matched to the product goal (local-first, provenance-heavy extraction). The most valuable “RAG upgrades” are therefore those that improve **retrieval recall and grounding** while keeping the pipeline legible and auditable.

### Retrieval pipeline details

The retrieval module implements:

- Chunk building from parsed blocks, with a mapping from block types to chunk types (paragraph/section/caption/table_region/abstract/list_item). fileciteturn7file0L80-L105  
- Contextualization: for non-heading blocks under a current section, `retrieval_text` gets a section prefix; `display_text` remains unchanged for review. fileciteturn7file0L118-L136  
- A query builder that performs **light lexical “field-aware expansion”** and appends “Retrieval hints” for certain patterns (notably count-like fields). fileciteturn7file0L169-L227  
- BM25-lite scoring: compute IDF across chunks, score each chunk, take top_k, then add neighbor window slices. fileciteturn7file0L228-L326  
- A stated constraint: **“NO reranking, HyDE, or query expansion in MVP baseline.”** fileciteturn7file0L337-L349  

### Does it use vector stores or external knowledge?

No evidence of a vector store or embedding index appears in the actual runtime retrieval module. Instead, the system retrieves from the parsed paper’s own blocks. fileciteturn7file0L80-L137

If you want to “add RAG components” in the stricter sense (dense retrieval + vector index), a key enabling factor is that **LM Studio supports `/v1/embeddings`** via its OpenAI compatibility endpoints. citeturn2search0 That means you can implement dense retrieval locally without cloud dependencies, preserving the repo’s local-first approach.

### Is the current retrieval approach “best” for the task?

For **within-document grounding**, lexical BM25-like retrieval can be surprisingly effective, especially when the parser yields clean blocks and the schema/field names overlap with paper wording. BM25 is a classic high-performing baseline for document retrieval in the probabilistic relevance framework. citeturn1search7

But extracting scientific paper fields often fails when:

- terminology differs (synonyms, abbreviations, assay names),
- relevant facts are embedded in tables/figure captions,
- the answer is dispersed across sections and needs multi-hop context,
- the “best evidence” is not the most textually similar chunk.

This is where **hybrid sparse+dense retrieval**, optional **HyDE** (hypothetical document embeddings), and **rank fusion** (e.g., Reciprocal Rank Fusion) are known to improve retrieval recall and robustness. citeturn1search48turn1search9turn1search7

So: the approach is a solid baseline and consistent with the artifact-driven, auditable product shape, but it is **not the best-available retrieval approach** if the priority is maximum recall on difficult scientific signals.

## Extraction, prompting, and accuracy considerations

### LLM integration and prompt/contract strategy

The provider layer is designed to enforce structured output, which is critical for spreadsheet cell extraction because it prevents brittle post-parsing and makes evaluation more reliable.

In `backend/app/provider.py`, the adapter:

- probes `/v1/models` and confirms configured model IDs exist, failing fast if not, fileciteturn13file0L287-L368  
- probes structured output support in `json_schema` mode first and then tries `json_object` if `json_schema` fails, fileciteturn13file0L370-L444  
- uses a bounded structured-output recovery ladder: parse → one “stronger instruction” retry → limited JSON repair → fail. fileciteturn13file0L483-L528  

This design is consistent with best practice when you need deterministic contracts and reproducible evaluation.

LM Studio’s OpenAI compatibility docs confirm the endpoints the code expects (`/v1/models`, `/v1/chat/completions`, `/v1/embeddings`) and the standard approach of pointing client base URLs to `http://localhost:1234/v1`. citeturn2search0

### Chunking and context-window strategy

The system’s “context window” strategy is chunk-based:

- It creates one chunk per parsed block (with some type mapping), fileciteturn7file0L80-L137  
- selects top-k chunks, then adds a neighbor window around each selected chunk, preserving page and reading order. fileciteturn7file0L245-L326  

This is a reasonable accuracy-friendly design: it tends to keep the LLM’s context locally coherent.

Where it can be improved (without changing the overall paradigm) is the **representation of retrieval text**: currently, contextualization appears to be primarily section-prefixing. fileciteturn7file0L118-L136 Many scientific extraction failures are better addressed by adding stable context prefixes such as page number, element type (caption/table), and local heading hierarchy, while keeping display text unchanged for review.

### Parsing quality as the upstream accuracy lever

The workflow depends heavily on parser output: block segmentation, reading order, table region detection, caption extraction, and OCR fallback.

The repositories’ intended parser stack includes Docling and PDFium bindings, and OCR fallback. fileciteturn41file0 External documentation supports why this matters:

- Docling’s goal is to convert documents into structured data with tables, formulas, and reading order, which directly impacts chunk quality. citeturn2search7turn3search1  
- OCRmyPDF adds an OCR text layer to scanned PDFs, improving text accessibility for downstream extraction. citeturn3search2turn3search3  

### Likely error modes and accuracy trade-offs

Based on the code contracts and evaluation tooling shape, the major accuracy risks are:

- **Retrieval miss**: relevant evidence never reaches the LLM prompt, leading to `unclear` or hallucinated `found` states (mitigated partially by anti-guessing + evidence anchoring).  
- **Table flattening**: table regions as raw text may lose header/row structure, leading to wrong numeric associations (group/value confusion).  
- **Evidence anchoring mismatch**: extracted “quotes” may not be locatable in normalized page text, degrading trust and evaluation anchor validation. The eval tool explicitly checks for locatable quote text in page text when available. fileciteturn29file0L1-L88  
- **Provider throughput bottlenecks**: structured, high-token prompts may be slow with large local models; repeated HTTP client creation increases overhead. fileciteturn13file0L287-L444  

## Evaluation harness and metrics in the eval repo

The eval repository defines a run-bundle loader and scoring pipeline that can:

- load runs if they contain `run.json` and `proposals/proposals.jsonl`, fileciteturn44file0L13-L20  
- score structured fields deterministically (boolean/categorical/numeric) and optionally judge text fields with an LLM-based text judge, fileciteturn27file0L1-L26  
- validate evidence anchors by checking whether a quoted snippet is locatable in the stored page text, producing outcomes such as `anchor_valid`, `anchor_invalid`, or `evidence_present_but_unvalidated`. fileciteturn29file0L1-L88  

The eval repo’s judge implementation is itself structured-output based: it requests JSON only with a verdict and a short rationale label. fileciteturn26file0L1-L23

### Important interoperability observation

The eval loader prioritizes sidecar evidence formats like `evidence/evidence.jsonl`, `evidence/evidence.json`, or `support/evidence.jsonl`, and page-text files like `evidence/page_text.json`. fileciteturn44file0L14-L26

If the main app persists evidence primarily as **many individual JSON files** (one per evidence ID) without an evidence manifest, evaluation will likely load proposals but have limited evidence context—making “anchor validity” metrics degrade into “missing/unvalidated” even when the system produced evidence. This is not necessarily a model-quality issue; it can be an artifact-contract mismatch. The simplest fix is to **emit an evidence manifest** matching what the eval loader expects, while keeping per-evidence JSON files for the UI.

## Recommendations, experiments, and migration plan

### Current design vs recommended changes

| Area | Current design (repo evidence) | What it does well | Recommended change (preserve accuracy) | Expected impact | Effort |
|---|---|---|---|---|---|
| RAG / retrieval scope | Within-document retrieval over parsed paper blocks; BM25-lite; neighbor window fileciteturn7file0L245-L326 | Easy provenance; no external KB; auditable | Keep within-document grounding but add optional dense retrieval + hybrid fusion (BM25 + dense + RRF) using local embeddings | Higher recall on synonym-heavy fields; fewer `unclear` | Medium |
| Vector store / embeddings | None in inspected runtime path | Simplicity | Add lightweight per-run/per-doc embedding index (in-memory or file-cached) instead of a full DB | Better retrieval robustness with manageable complexity | Medium |
| Retrieval contextualization | Section prefixing in `retrieval_text` fileciteturn7file0L118-L136 | Keeps display text clean for review | Extend retrieval_text with deterministic context prefixes (page, chunk type, heading path; table/caption markers) | Better disambiguation; fewer wrong-section hits | Low–Medium |
| Prompt contract | Structured output with bounded recovery | Reliability; easier eval | Make token budgets/config consistent; add per-field-type prompt templates if needed | Fewer truncations; more stable outputs | Low |
| Provider / transport | Probes structured output; uses httpx AsyncClient in multiple calls fileciteturn13file0L287-L444 | Good capability truth | Reuse a single AsyncClient per provider; enable keep-alive + concurrency limits | Lower latency; higher throughput | Low |
| Eval interoperability | Eval validates evidence anchoring using page text if present fileciteturn29file0L1-L88 | Evidence-aware metrics | Emit `evidence/evidence.jsonl` (manifest) + `evidence/page_text.json` when available | Metrics reflect reality; easier debugging | Low |
| Parsing performance | Docling is intended; can use multi-threaded pipelines per docs | Quality lever | Align parsing with Docling’s standard pipeline options; add parser health metrics | Better upstream structure | Medium |

### Prioritized recommendations

#### Confirming and strengthening RAG components

First priority is not “add a vector DB,” but to **make retrieval a first-class, explicit subsystem**:

1. **Formalize a per-PDF retrieval index object** created once after parsing: list of chunks, cached tokenization, cached IDF, and (optional) embeddings. In code terms, replace the current “build chunks each retrieval call” flow with `RetrievalIndex.build(doc_dict)` then `index.retrieve(query, top_k, …)`. This preserves output equivalence while enabling caching and hybrid retrieval later. The current implementation rebuilds chunks and recomputes IDF per query. fileciteturn7file0L228-L326  
2. **Add optional dense retrieval** using local embeddings. LM Studio explicitly supports `/v1/embeddings`, so you can use an embedding model locally and fuse results with BM25. citeturn2search0  
3. **Hybrid fusion with RRF**: combine BM25 ranking and dense ranking using Reciprocal Rank Fusion, which is designed to outperform single rankers and is simple to implement. citeturn1search9  
4. Keep HyDE (hypothetical document embeddings) behind a **quality preset** rather than as a default baseline, because it adds extra model calls and can hallucinate (by design). HyDE’s role is query expansion for dense retrieval. citeturn1search48  

#### Improving extraction accuracy

Accuracy improvements that keep the current reviewer-first product shape:

1. **Contextualized chunk indexing beyond section prefixing**: include stable prefixes like `[Page: 7] [Type: caption] [Section: Results > …]` in `retrieval_text`, and keep `display_text` unchanged. The design already separates the two texts. fileciteturn7file0L103-L137  
2. **Table-aware retrieval units**: treat `table_region` chunks as structured artifacts (headers, row labels, cell summaries) rather than raw flattened text. Docling supports table detection and structured conversion concepts, which you can leverage to emit a more structured `table_region` representation. citeturn2search7turn3search1  
3. **Schema-aware retrieval policy**: apply different retrieval heuristics based on field type and column description. For example, numeric fields can bias toward tables/captions; categorical organism fields bias toward Methods; figure-heavy outcomes bias toward captions/figure mentions. The current query builder already includes some field-aware hints (count-like detection). fileciteturn7file0L169-L227  
4. **Evidence artifact alignment** with evaluation: emit page text mappings to support anchor validation when feasible. The eval validator expects quote text and page index and tries to locate quote snippets in page text. fileciteturn29file0L1-L88  

#### Simplifying architecture and reducing drift

1. **Make “retrieval.strategy” truthful**: if the only implemented strategy is BM25-lite over typed chunks, rename the strategy accordingly (or implement real semantic retrieval when strategy says semantic). This reduces operator confusion and mismatched expectations. fileciteturn36file0  
2. **Consolidate evidence export formats**: keep per-evidence JSON (good for UI), but also write an `evidence/evidence.jsonl` manifest and optionally `evidence/page_text.json` so the eval repo can validate anchors and compute evidence quality metrics without special-casing. The eval loader already searches for these filenames. fileciteturn44file0L14-L26  
3. **Stable “effective config” reporting**: persist a resolved config section (including derived defaults like real max_tokens used per request) so performance comparisons and run-to-run reproducibility are easier.

#### Reducing latency and improving throughput

These changes should not affect extraction correctness if implemented carefully:

1. **Reuse an HTTP client**: the provider code opens `httpx.AsyncClient` in multiple methods. fileciteturn13file0L287-L444 Refactor so a single client is created per provider instance (keep-alive enabled), with proper close at shutdown.  
2. **Bounded concurrency for extraction**: move from “per-cell await sequentially” to an async worker pool with a semaphore (e.g., concurrency=2–4) to avoid overloading LM Studio while improving throughput.  
3. **Precompute retrieval index** per PDF: compute chunks + tokenization + IDF once, then score per query. This also makes “recall rescue” able to reuse the same scored list (first pass uses top_N; rescue uses top_N+Δ).  
4. **Cache style profile generation** by schema hash + column name + prompt hash (this is especially valuable in repeated eval runs).  
5. **Profiling instrumentation**: persist per-stage timing and per-provider token counts. LM Studio provides usage metadata in responses in many OpenAI-compatible stacks; capturing this gives direct feedback on cost/time drivers. fileciteturn26file0L79-L132  
6. **Optional model distillation / tiered models**: keep the high-accuracy model for final extraction, but allow small models for style profiling and judge tasks. This reduces latency while preserving extraction accuracy because the “critical” step remains on the high-quality model.

### Suggested experiments and validation metrics

To validate changes while protecting accuracy, run experiments through the eval repo and add a small set of “retrieval quality” diagnostics to the run bundle.

Recommended metrics (additive, not replacing existing):

- **End-to-end correctness** (already supported): overall accuracy; structured-field accuracy; text-field judge accuracy. fileciteturn27file0L1-L26  
- **Coverage metrics**: proportion of gold-present cells that produced any proposal vs missing proposal. fileciteturn27file0L49-L114  
- **Evidence quality metrics**: anchor_valid rate, evidence_present_but_unvalidated rate, missing_evidence rate. fileciteturn29file0L1-L88  
- **Latency metrics**: per-stage time (parse/match/retrieval/extraction), per-cell extraction latency distribution (p50/p95), provider request counts.  
- **Retrieval diagnostics (new)**: for each cell, record (a) retrieval mode, (b) number of table/caption chunks included, (c) whether the primary evidence came from retrieved content vs fallback.

Experiment matrix (high signal-to-effort):

- Retrieval ablation: BM25-only vs BM25 + contextual prefixes vs BM25 + dense vs BM25+dense+RRF.  
- Context assembly ablation: neighbor window size 0 vs 1 vs 2, and typed-chunk inclusion rules.  
- Model ablation: keep extraction model fixed; vary style-profile model tier and judge model tier.  
- OCR+parser ablation: with/without OCR fallback on the same scanned subset (when available), to confirm parser is the limiter. citeturn3search2turn3search3  

### Migration plan with estimated effort and risk

Effort estimates assume a single engineer familiar with the repo; actual effort depends on test coverage goals and local model variability.

**Phase: Artifact + evaluation alignment**  
Deliverables: `evidence/evidence.jsonl` manifest; optional `evidence/page_text.json`; ensure eval repo can validate evidence anchors.  
Effort: 1–3 days.  
Risk: Low. Main risk is mismatched page numbering conventions; mitigate with a small “evidence contract test” in both repos. fileciteturn29file0L40-L88  

**Phase: Provider throughput improvements**  
Deliverables: persistent `httpx.AsyncClient`; concurrency-limited extraction worker pool; stage timing logs.  
Effort: 2–5 days.  
Risk: Low–Medium (concurrency introduces nondeterministic ordering; mitigate by preserving deterministic artifact naming and indexing).

**Phase: Retrieval index refactor**  
Deliverables: `RetrievalIndex` built once per parsed doc; cached IDF/tokenization; reuse for recall-rescue expansions.  
Effort: 4–10 days.  
Risk: Medium (bugs could silently change chunk ordering/selection). Mitigate by snapshot tests on retrieval artifacts. fileciteturn7file0L371-L443  

**Phase: Hybrid retrieval (optional dense + RRF)**  
Deliverables: embedding generation via LM Studio `/v1/embeddings`; dense index per PDF; fusion with BM25 using RRF; quality preset toggles.  
Effort: 1–3 weeks.  
Risk: Medium–High (embedding model choice and normalization affect quality; also GPU/CPU costs vary widely). Use small evaluation subsets and keep as opt-in quality mode. citeturn2search0turn1search9turn1search48  

**Phase: Table-aware extraction inputs**  
Deliverables: structured table-region summaries; schema-aware policies; specialized prompt fragments for table-derived fields.  
Effort: 2–5 weeks.  
Risk: High (table parsing variability can create brittle heuristics). Mitigate by keeping table-aware context additive, not replacing paragraph-based retrieval, until proven. citeturn2search7turn3search1  

## Bottom line

The app **does use RAG principles** in a technically meaningful way: retrieval over parsed paper chunks (with contextualization and neighbor window) is used to ground subsequent structured-output LLM extraction. fileciteturn7file0L245-L326 This aligns with the core motivation of RAG—improve factuality and provenance by conditioning generation on retrieved evidence. citeturn0search5

It is also intentionally a **lightweight, local-first, auditable** variant of RAG: lexical BM25-like retrieval, no vector store, no reranking/HyDE by default, explicit artifact persistence, and bounded structured-output recovery. fileciteturn7file0L337-L349 fileciteturn13file0L483-L528

To preserve extraction accuracy while advancing toward best-in-class performance, the recommended path is: **(1) align artifacts + eval, (2) fix performance bottlenecks that don’t affect correctness, (3) strengthen retrieval representation and indexing, (4) add opt-in hybrid retrieval, (5) invest in table-aware structured inputs**—in that order.