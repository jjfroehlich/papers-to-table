# Paper Table Agent — `plan.md`

## Purpose

This document defines the technical approach for implementing the product requirements in `spec.md`.

It is the technical counterpart to the product specification:

- `spec.md` defines **what** the product must do and **why**.
- `plan.md` defines **how** the system will satisfy those requirements.
- `research.md` holds supporting detail that should not overload either the product spec or this plan.

This plan is intentionally opinionated. It chooses a concrete MVP architecture so implementation can proceed without drifting into a general-purpose RAG platform, a chat product, or an overcomplicated agent framework.

---

## Relationship to other documents

- `spec.md` is the source of truth for user-facing requirements and acceptance criteria.
- `research.md` records the research and tradeoffs behind the decisions in this plan.

Additional supporting notes, runbooks, or a future task breakdown may be added later if they become useful, but they are not required MVP artifacts.

---

## Definition of done

Implementation for this phase is complete when the system satisfies the functional requirements and acceptance criteria in `spec.md` and the following technical outcomes are true:

1. A user can run an end-to-end workflow:
   - load table + schema + PDF folder
   - parse documents
   - match PDFs to rows
   - generate schema-driven proposals with evidence
   - review proposals in a dedicated UI
   - export an updated workbook and audit log

2. PDFs are normalized into one internal parsed-document contract that downstream systems use regardless of parser backend.

3. Evidence remains reviewable and auditable even when retrieval uses contextualized text.

4. Run artifacts, proposal state, review decisions, and exports are persisted in a reproducible local-first manner.

5. The implementation supports structured-output-first extraction with graceful downgrade when providers lack strong schema support.

6. Diagnostics explain failures and low-quality results without requiring developers to inspect raw prompts manually.

7. Verify mode works end-to-end:
   - proposes values for already-filled cells
   - exposes them in review
   - allows reviewed export changes
   - produces reviewer-outcome summaries automatically

8. The first shipping system remains focused on the paper-to-table review workflow and does not expand into a chat-first, multi-user, or SaaS platform.

---

## Constraints and non-goals

### Constraints

- Local-first operation in this phase.
- Single-user local browser app operation is sufficient for MVP.
- Human review is required before spreadsheet updates.
- UI remains minimal and task-focused.
- Pipeline must preserve auditable run artifacts.
- Parser, model, and retrieval backends must remain replaceable behind stable contracts.
- Provider/model behavior must be transparent enough for users to know whether a run stayed local or used cloud services.

### Non-goals

- No hosted backend or SaaS deployment in this phase.
- No multi-user collaboration workflow in v1.
- No broad chat-oriented document assistant features.
- No graph-first orchestration unless the workflow later clearly requires it.
- No giant user-facing config surface.
- No assumption that more fallback layers automatically improve the product.

---

## Technical decisions and rationale

### TD-1: The product is a workflow application, not a general RAG chat app

The system will be implemented as a focused workflow service plus review UI, not as a conversational RAG product.

**Rationale:**
The core user journey is table ingestion, proposal generation, review, and audited export. A chat-centric architecture would add surface area without helping the main task.

---

### TD-2: Use a deterministic staged runner, not graph-first orchestration

The initial system will use a mostly deterministic staged pipeline with a few LLM-assisted steps:

- paper metadata extraction
- ambiguous row adjudication
- schema-driven proposal extraction
- optional evidence recovery
- optional figure fallback

**Rationale:**
The workflow is structured and auditable. The prior implementation showed that graph orchestration added less value than expected around a mostly sequential loop. The rewrite should stay simple for MVP: one run executes straight through, and an interrupted run is restarted as a new run rather than resumed in place.

---

### TD-3: Use one main parser first, with a stable parser contract

All parser outputs must normalize into a shared `ParsedDocument` contract, but the shipping MVP should begin with one main parser rather than a multi-parser runtime.

**Rationale:**
Parser abstraction is valuable; multi-parser runtime complexity is not justified as a baseline. The parser contract prevents lock-in while preserving a simpler default path.

---

### TD-4: Parser baseline is Docling + PDFium via pypdfium2

The primary ingestion stack for MVP will be:

- **Docling** as the main parser
- **PDFium via pypdfium2** as the low-level PDF backend for rendering, crop extraction, text search, and evidence anchoring
- a small internal abstraction layer that isolates backend-specific code

**Rationale:**
Docling is currently the strongest main parser candidate for structured scientific PDF parsing, layout awareness, figure handling, and table support. PDFium provides a strong low-level foundation for page rendering, geometry, and evidence display with a more favorable licensing posture than MuPDF/PyMuPDF.

**Note:**
GROBID remains an optional later enrichment path if measured lift justifies it.

---

### TD-5: Filesystem artifact bundles are the canonical MVP state

The system will use:

- per-run artifact folders in the output directory as the canonical run record
- JSON files inside each run bundle for proposals, review state, diagnostics, summaries, and export bookkeeping

**Rationale:**
For a local-first, single-user MVP, artifact bundles are simpler, easier to inspect, and easier to debug than introducing a database. This keeps state reproducible without adding operational complexity that the product does not yet need.

---

### TD-6: Export generates a new workbook, not an in-place workbook patch

The system will export a new updated workbook plus audit log rather than mutating arbitrary workbooks in place.

**Rationale:**
Workbook fidelity is difficult to guarantee across complex Excel features. A generated export is safer, easier to validate, and more auditable.

**Implementation direction:**
Use `openpyxl` as the main XLSX round-trip engine. Guarantee cell-content preservation only plus changed-cell highlighting. Do not promise preservation of workbook behavior or advanced sheet structure.

---

### TD-7: Use structured outputs first, with LM Studio localhost API as the initial provider

LLM interaction will be schema-first using typed contracts. The initial supported provider path is LM Studio via its localhost API, with each cell request returning structured JSON plus page-grounded evidence. Other providers can be added later behind the same contract.

**Rationale:**
The extraction path depends on predictable proposal and evidence objects. LM Studio matches the local-first MVP boundary while preserving a clean contract for future provider expansion.

---

### TD-8: Review requires a dedicated queue-first local browser app

The review product surface will be a dedicated Run/Review application delivered as a local browser app, not a notebook or chat interface. Tauri is only a possible future packaging option, not an MVP shell requirement.

**Rationale:**
The main value of the product is human verification of proposed spreadsheet updates with visible evidence.

**Interaction model:**
Queue/list of proposals + focused detail pane + custom PDF.js evidence viewer.

---

### TD-9: MVP evaluation is reviewer-outcome-based

The MVP will evaluate performance primarily through reviewer outcomes rather than an automated correctness score across heterogeneous field types.

**Rationale:**
The product already requires human review. Reviewer decisions are the most trustworthy MVP measure of usefulness, while automated verify-mode scoring across mixed field types is still an open research problem.

---

### TD-10: Existing filled cells feed a preprocessing LLM that produces structured style profiles

Existing filled cells should be processed per column through a preprocessing LLM that generates a structured style/format profile. That profile may guide output shape, tone, and detail level, but raw filled cells must not be passed as semantic few-shot exemplars to extraction prompts by default.

**Rationale:**
This keeps the benefit of column-specific output shaping while avoiding heuristic-only format inference and avoiding direct semantic anchoring to historical cell content.

---

### TD-11: Figure support is in scope, but the heavier reasoning-plus-vision path is tightly scoped

Figure-aware fallback is in MVP, but the heavier reasoning-plus-vision path should run only when the field is likely figure- or table-derived, text retrieval failed, or the user explicitly requests a fallback. Figure-derived proposals remain review-first and are evaluated through normal human reviewer outcomes rather than separate automated figure scoring.

**Rationale:**
This keeps visual extraction available where it is likely to help while avoiding multimodal escalation as a baseline behavior.

**Implementation direction:**
The routing decision may be made by the extraction path itself, including an LLM-assisted decision, provided it stays within those scoped triggers and does not escalate all pages or all fields to vision by default.

---

## Alternatives considered

### A-1: Generic RAG/chat platform foundation

**Alternative:** Build on a generic RAG/chat platform and extend it.

**Rejected because:**
The review/export workflow would become an awkward extension rather than the product core.

---

### A-2: Multi-agent or graph-first orchestration first

**Alternative:** Use LangGraph or an equivalent orchestration layer as the center of the architecture.

**Rejected because:**
The initial workflow is mostly sequential and structured. Heavy orchestration would add complexity before it improves quality.

---

### A-3: Multi-parser runtime by default

**Alternative:** Use a parser matrix from day one.

**Rejected because:**
A clean parser abstraction is valuable, but baseline multi-parser runtime complexity is not yet justified.

---

### A-4: Database-first architecture

**Alternative:** Store all intermediate state only in a database.

**Rejected because:**
Filesystem artifacts are too important for reproducibility, debugging, and export packaging.

---

### A-5: In-place workbook editing

**Alternative:** Patch the original workbook directly.

**Rejected because:**
Workbook fidelity risks are too high for arbitrary real-world workbooks.

---

## Supporting notes

This plan depends on `research.md` for supporting tradeoffs and decisions. Additional implementation notes, runbooks, or a future task breakdown can be added later if they become useful. Optional ADRs may still be useful for decisions that evolve, especially:
  - low-level PDF backend
  - runtime/background jobs
  - workbook fidelity policy
  - UI stack

---

## System architecture overview

## High-level architecture

The system will consist of five major layers:

1. **Local web frontend UI**
   - local browser app
   - Run and Review views
   - queue-first proposal review
   - PDF/page/figure evidence display

2. **API and application service layer**
   - receives UI requests
   - creates runs
   - exposes run/proposal/review/export data
   - serves artifacts and document views

3. **Pipeline runner and background job layer**
   - executes parse/match/extract/evidence/export stages
   - writes checkpoints and artifacts
   - updates run/proposal state

4. **Parsing/retrieval/extraction layer**
   - parser adapters
   - low-level PDF rendering/anchoring
   - retrieval/indexing
   - extraction and figure fallback

5. **Persistence layer**
   - filesystem run artifacts
   - JSON state files within each run bundle

---

## Proposed implementation stack

### Frontend
- **React**
- **TypeScript**
- **Vite**
- **Tailwind CSS**
- **shadcn/ui** or similarly lightweight component approach
- **TanStack Table**
- **TanStack Virtual**

### PDF viewer
- **Raw/custom PDF.js** in the UI layer
- app-managed overlay system for highlights and evidence regions
- optional overlay behavior modeled after tools such as react-pdf-highlighter

### Backend / service layer
- **Python**
- **FastAPI**

### Background jobs
- no queue by default in MVP
- app-owned staged execution first
- optional **Huey + SqliteHuey** background jobs later if UI responsiveness requires async execution

### Persistence
- filesystem artifact directories
- JSON files for proposals, reviews, diagnostics, summaries, and run metadata
- no database required for MVP

### Initial LLM provider
- **LM Studio localhost API**

### Main parser
- **Docling**

### Low-level PDF layer
- **pypdfium2 / PDFium**

### OCR fallback
- **OCRmyPDF** with **Tesseract**, producing a searchable PDF artifact before normal parsing when a PDF is scanned or text-inaccessible

### XLSX export
- **openpyxl**

---

## End-to-end technical flow

1. Load table, schema, PDF folder, and configuration.
2. Validate standardized metadata columns (`Title`, `Authors`, `Publication Year`).
3. Normalize schema, identify missing/already-filled/verify-eligible cells, and build per-column style profiles from existing filled cells.
4. Inventory PDFs and create run records.
5. Detect scanned or text-inaccessible PDFs and run OCR fallback when needed.
6. Parse PDFs through the parser stack and normalize outputs into `ParsedDocument`.
7. Extract grounded metadata for row matching.
8. Match PDFs to rows using deterministic scoring and fallback adjudication.
9. Block ambiguous or duplicate-row conflicts from extraction.
10. Build retrieval indexes from typed chunks and table-aware units where available.
11. Select a context strategy for each matched PDF.
12. Run schema-driven extraction to produce one best proposal per target cell.
13. Validate evidence and run one narrow evidence-location pass where needed.
14. Run figure-aware fallback only when the field is likely figure- or table-derived, text retrieval failed or remained insufficient, or the user explicitly requested fallback.
15. Persist proposals, evidence, diagnostics, and review state as JSON artifacts.
16. Present proposals in the review UI with queue, filters, and evidence display.
17. Record review decisions.
18. Export accepted changes into a new XLSX workbook and audit log.
19. Compute reviewer-outcome run summaries and Verify-mode reviewer-outcome summaries.
20. Write final run diagnostics and artifacts.

---

## UI architecture

## MVP interaction model

The review UI will use a **queue-first / list-detail** design.

### Main review workspace

The main review surface should include:

- a proposal queue or list
- a selected proposal detail pane
- a PDF evidence viewer
- progress counters
- filters
- decision controls

### Proposal queue

The queue should support filtering by:
- row
- column
- PDF
- evidence status
- figure-based evidence
- ambiguous/unmatched match status

### Detail pane

The detail view should show:
- row context
- target column definition
- current cell value if in Verify mode
- proposed value
- support state
- concise rationale or calculation
- primary evidence item
- expandable secondary evidence items

### Evidence viewer

For text evidence:
- show quote text
- show page
- show highlight when available
- fall back to quote + page when highlight fails

For figure evidence:
- show crop first
- show caption directly attached
- allow full-page inspection

### Progress and decision affordances

The UI should show:
- total proposals
- reviewed proposals
- accepted as-is
- accepted with edit
- rejected
- pending / undecided

### MVP keyboard affordances

The MVP should support:
- next/previous proposal navigation
- accept current proposal
- reject current proposal
- focus proposed-value edit control
- open or focus the evidence viewer

### Bulk actions

MVP should support a bulk accept action, but the safest product interpretation is:
- apply bulk acceptance to a visible, filtered subset
- require explicit confirmation

The default MVP behavior should apply bulk acceptance only to the currently visible filtered subset.

---

## API and service architecture

The FastAPI layer should expose a small stable set of application-facing endpoints such as:

- create/list/get runs
- get run summary
- list proposals with filters
- get proposal detail
- submit review decision
- inspect unmatched/ambiguous PDFs
- request export
- fetch export bundle
- fetch evaluation/reviewer summary
- fetch document pages/crops/highlights

The service layer should remain thin and should not duplicate pipeline logic. It should read and update per-run JSON artifacts rather than depending on a database.

---

## Pipeline architecture

## Guiding principle

The pipeline should be **stage-based and explicit**, with a clear default path and a small number of limited fallbacks.

## Main stages

### Stage 1 — Ingest
- load table/schema/config
- validate metadata columns
- fingerprint inputs
- build per-column style/format profiles from existing filled cells using a preprocessing LLM before extraction prompts are assembled
- create run record

### Stage 2 — Parse
- run OCR fallback for scanned/text-inaccessible PDFs when needed
- parse PDFs using the main parser
- generate normalized parsed-document artifacts
- generate low-level page render/crop support as needed
- compute parsing diagnostics

### Stage 3 — Match
- extract header/paper metadata
- perform deterministic matching
- run fallback adjudication only for plausible ambiguous cases
- block ambiguous and duplicate-row conflicts

### Stage 4 — Build retrieval context
- create typed chunks
- create contextualized `retrieval_text`
- create table-aware retrieval units if available
- cache per-document retrieval artifacts

### Stage 5 — Extract
- run schema-driven extraction
- one best proposal per target cell
- structured-output-first
- one primary context strategy plus one fallback only

### Stage 6 — Validate evidence
- validate evidence anchors
- if needed, run one narrow evidence-location step
- preserve weak-but-reviewable proposals

### Stage 7 — Figure fallback
- run only when needed
- use scoped visual context
- produce figure-marked evidence

### Stage 8 — Review persistence
- proposals available in UI
- decisions stored as JSON artifacts in an append-only audit-friendly format

### Stage 9 — Export
- generate new XLSX workbook
- write audit log
- preserve original workbook untouched

### Stage 10 — Summaries
- write reviewer-outcome summaries
- write Verify-mode summaries
- write run diagnostics

---

## Parser strategy

## Objective

Create a robust scientific-PDF ingestion layer that preserves structure for retrieval while keeping enough source fidelity for evidence display and highlighting.

## Baseline parser stack

### Primary parser
- Docling

### Low-level PDF support
- pypdfium2 / PDFium

### OCR fallback
- OCRmyPDF + Tesseract, writing searchable-PDF artifacts before the normal parse path when needed

### Optional later enrichment
- GROBID if measured lift justifies it

## Parser contract requirements

All parser outputs must normalize into one `ParsedDocument` contract.

Minimum internal fields should include:
- document identity
- metadata
- pages
- typed elements
- source-preserving text
- normalized text
- table regions
- figure/caption links when available
- provenance links
- geometry if available

## Storage rule

Parser-native outputs should be stored as artifacts for debugging and reproducibility even if downstream systems consume only the normalized representation.

---

## Matching strategy

## Objective

Match each PDF to the most likely row while minimizing incorrect row assignment.

## Approach

### Pass 1 — Deterministic scoring
Use publication metadata signals such as:
- title similarity
- author overlap
- year tolerance
- identifiers when available

### Pass 2 — Model adjudication
Use only for plausible ambiguous cases.

### Conflict policy
- if match remains ambiguous: block extraction
- if two or more PDFs match the same row: block all involved until manual cleanup

### User visibility
Unmatched, ambiguous, and duplicate-row-conflict PDFs must remain visible in the UI.

---

## Retrieval strategy

## Objective

Improve extraction quality by retrieving over contextualized typed chunks while keeping reviewer-visible evidence anchored to source-preserving text.

## Retrieval units

The retrieval layer may index:
- abstract chunks
- section header chunks
- paragraph chunks
- figure-caption chunks
- table-region chunks
- table-cell summary units when available
- reference blocks when useful

## Retrieval text versus display text

Retrieval may use contextualized `retrieval_text`, but evidence display and quote validation must use source-preserving text.

## Baseline retrieval philosophy

The default retrieval stack should be intentionally narrow:

- typed chunking
- contextualized text
- sparse or simple baseline retrieval
- table-aware units where useful

Advanced helpers such as:
- dense embeddings
- reranking
- HyDE
- query expansion

should remain optional and must prove lift before becoming baseline.

## Context strategy

The runner should start with:
- one primary context strategy
- one fallback

The current preferred direction is:
- primary: focused retrieval-based extraction
- fallback: broader full-document context for cases where retrieval is insufficient or not applicable

Memory-mode summarization is not baseline MVP behavior.

---

## Extraction strategy

## Objective

Generate schema-driven proposals with enough context to maximize usefulness while preserving trust and inspectability.

## Behavior

- column-driven extraction
- at most one best proposal per target cell per run
- value-first behavior retained
- structured-output-first
- concise rationale/calculation when the value is derived

## LLM interaction model

The extraction path should be:

- parse once per paper
- retrieve relevant passages or figure context
- ask the model per target cell
- require structured JSON output per proposal
- store page-grounded evidence with each proposal

## Verify mode

Verify mode is not a separate extraction architecture. It is the same extraction flow applied to already-filled cells with different review/export/evaluation semantics.

## Format/style guidance

The extraction layer should use a per-column preprocessing LLM step that turns existing filled cells into a structured style/format profile. Extraction should consume only that profile, not raw examples. The profile may guide output shape, tone, and level of detail, but:
- content must remain grounded in the current PDF
- style guidance must not act as semantic evidence
- raw filled cells must not be injected into extraction prompts by default
- heuristic-only format inference is not the baseline path

---

## Evidence strategy

## Objective

Preserve plausible values while making evidence quality visible, recoverable, and reviewable.

## MVP evidence contract

The evidence model should be narrower and stricter than in the old system.

### Text proposals
Preferred:
- quote + page + highlight

Fallback reviewable state:
- quote + page

### Figure proposals
Preferred minimum:
- crop + caption + page access

### Review emphasis
- one primary evidence item by default
- expandable secondary evidence items

## Validation and recovery

MVP should use:
- one strict evidence validator
- one simple locator/recovery path

Do not build a broad salvage ladder by default.

---

## Figure strategy

## Objective

Support figure-derived proposals in MVP while keeping visual extraction explicitly review-first.

## Trigger policy

Figure fallback should run when:
- the field is likely figure- or table-derived
- text retrieval failed or remained insufficient
- the user explicitly requests a fallback
- parser output identified candidate figure-bearing regions

## Review policy

Figure-derived proposals must:
- be clearly labeled as figure-based
- display crop + caption + full-page access
- remain subject to human review

## Evaluation boundary

MVP does not require a separate automated figure-evaluation track. Figure-derived proposals should remain identifiable in artifacts and the UI, but usefulness is judged through the same human review outcomes as other proposals.

---

## Export strategy

## Objective

Produce safe, review-authorized outputs without mutating the original source workbook.

## Planned behavior

- always export XLSX
- preserve original workbook untouched
- preserve accepted cell content only
- highlight changed cells
- include audit log

## Engine

- use `openpyxl`

## Workbook fidelity policy

The MVP export promise is cell-content preservation only plus highlighting of changed cells, not workbook-behavior fidelity.

Guaranteed:
- accepted cell values are written into the exported XLSX
- unchanged cell content is carried forward
- changed cells are visually highlighted
- formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, and similar workbook features are not guaranteed

Out of guarantee:
- formulas
- filters
- frozen panes
- hidden rows or columns
- merged cells
- conditional formatting
- comments
- named ranges
- charts
- shapes
- images or drawings
- macros

This boundary should be documented explicitly and treated as the stable MVP contract.

---

## Persistence strategy

## Objective

Support local-first auditability and inspectability with the smallest coherent persistence model.

## Canonical persistence model

### Filesystem artifacts
Canonical run bundle:
- input snapshots/fingerprints
- parser outputs
- retrieval artifacts
- run metadata JSON
- proposals JSON
- evidence JSON
- review decisions JSON
- diagnostics JSON
- exports
- summary/report JSON

## Ownership rule

The run directory is the canonical audit bundle and the only required MVP persistence mechanism.

The MVP does not need pause/resume semantics within a run. If a run is interrupted, the partial artifacts may remain for inspection, and a new attempt should create a new run directory.

---

## Runtime and background jobs

## Objective

Run the pipeline simply and predictably without reintroducing graph-runtime complexity.

## Recommended MVP shape

- app-owned staged runner
- execute synchronously inside the FastAPI service first
- no job queue required by default
- add **Huey + SqliteHuey** first if async execution becomes a practical necessity

## Why this shape

It keeps:
- execution simple
- local deployment simple
- workflow ownership in the app
- queue complexity low

while keeping the first implementation simple and inspectable.

For MVP, the runner is single-pass: once started, it runs until completion or interruption. Interrupted runs remain as incomplete artifacts, and a new attempt creates a new run directory.

---

## Model/provider strategy

## Objective

Keep proposal extraction robust across local and external providers.

## Approach

- typed request/response contracts
- structured-output-first execution
- structured JSON per proposal as the stable contract
- prompt-only JSON fallback when required for future providers

## Initial provider decision

The initial provider path is LM Studio via its localhost API. The plan should assume local execution by default and treat other providers as later extensions behind the same interface.

## Transparency

The system should record and surface:
- provider name
- model name
- whether the run stayed local or used cloud providers

At minimum this should appear in the normal run summary.

The normal run summary should include:
- provider name
- model name
- whether execution stayed local or used cloud services
- PDFs processed
- matched, unmatched, and ambiguous PDF counts
- proposals generated
- proposals reviewed
- accepted as-is, accepted with edit, and rejected counts
- accepted change count
- warning flags for limited review or weak evidence situations

---

## Evaluation and measurement strategy

## Objective

Measure usefulness honestly in MVP without overcommitting to brittle automated scoring.

## MVP measurement model

Use reviewer-outcome statistics as the primary product-level measurement:

- reviewed proposal count
- accepted as-is count/rate
- accepted with edit count/rate
- rejected count/rate
- proposal coverage
- per-column reviewer outcome breakdown
- evidence display success
- matched/unmatched/ambiguous counts

## Verify mode semantics

Verify mode should:
- expose already-filled-cell proposals to review
- allow accepted edits to export
- contribute to reviewer-outcome summaries automatically

It does **not** require a sophisticated automated correctness score in MVP. In MVP, Verify mode supports review and reporting, not benchmark-grade scoring.

## Measurement integrity

Always distinguish:
- proposal production
- evidence presence
- reviewer acceptance
- evaluation emptiness/skips

Never let zero-evaluable-target runs masquerade as normal scored runs. Leakage-safe benchmark design can be deferred until a later phase because MVP does not depend on automated verification scoring.

---

## Testing strategy

## Core layers

### Unit tests
- parser normalization
- matching logic
- chunk typing
- retrieval text construction
- evidence validation
- export transformation
- provider capability routing

### Integration tests
- end-to-end stub run
- review API and UI smoke
- export generation
- figure fallback path
- Verify mode flow

### Deterministic offline tests
Use stub/mock providers and deterministic fixtures by default.

### Live integration tests
Keep opt-in only.

## Fixture strategy

Maintain a compact fixture set that covers:
- easy papers
- table-heavy papers
- figure-heavy papers
- ambiguous matching
- weak evidence
- no-value cases
- Verify-mode reviewed cells

---

## Implementation phases

## P0 — Core workflow foundation
- finalize parser contract
- implement ingest + validate inputs
- implement per-column style-profile preprocessing
- implement main parser + low-level PDF fallback
- implement OCR fallback for scanned PDFs
- implement matching
- implement proposal/evidence persistence
- implement queue-first Run/Review UI skeleton
- implement XLSX export + audit log
- implement reviewer-outcome summaries
- implement Verify mode basic flow

## P1 — Retrieval and review hardening
- typed chunking
- contextualized retrieval text
- table-aware retrieval artifacts
- narrow evidence validator + locator
- figure fallback
- review filters, counters, and progress UX

## P2 — Measured extensions
- optional parser enrichments
- optional retrieval helpers if they prove lift
- optional richer figure handling
- optional automated Verify-mode scoring research prototype
- optional stronger diagnostics and developer tooling

---

## Risks and mitigations

### R-1: Parser normalization drift
**Mitigation:** one normalized contract, adapter tests, stored raw artifacts.

### R-2: Evidence anchoring brittleness
**Mitigation:** PDFium low-level backend, strict evidence contract, one simple locator path, fallback quote+page reviewability.

### R-3: Figure scope too broad for reliable MVP behavior
**Mitigation:** review-first figure UX, explicit fallback triggers, visible figure-based evidence, and human reviewer judgment as the governing quality check.

### R-4: Workbook fidelity expectations exceed implementation reality
**Mitigation:** explicitly document the content-only export boundary and the non-guaranteed workbook features.

### R-5: Provider incompatibility or weak structured output
**Mitigation:** capability probes, typed validation, prompt-only fallback.

### R-6: Runtime complexity grows back through helper passes
**Mitigation:** helper passes remain opt-in until measured lift is shown.

### R-7: Config sprawl reappears
**Mitigation:** keep user-facing config small; keep policy/internal tuning separate; avoid exposing every experimental knob.

---

## Open technical questions

- [RESOLVED: MVP uses PDFium via pypdfium2 as the low-level PDF backend, wrapped behind a small internal abstraction layer so backend-specific code stays isolated.]
- [RESOLVED: If synchronous execution proves insufficient, Huey + SqliteHuey is the first background-job layer to add.]

---

## Concise implementation summary

Paper Table Agent will be implemented as a local-first workflow application with:

- a React local browser UI
- PDF.js in the frontend and PDFium/pypdfium2 in the backend
- one main parser first, behind a normalized parser contract
- OCRmyPDF plus Tesseract as the scanned-PDF fallback
- typed retrieval units and source-preserving evidence
- a deterministic app-owned staged runner executed synchronously first inside FastAPI, with Huey + SqliteHuey as the first likely async addition if needed
- filesystem artifact bundles and JSON state files as the complete MVP persistence layer, with no database required
- reviewer-outcome-based MVP evaluation
- a preprocessing LLM that turns existing filled cells into structured style profiles
- figure-aware fallback with tightly scoped reasoning-plus-vision escalation
- new XLSX export plus audit log with cell-content preservation only and changed-cell highlighting

This keeps the system aligned with its real purpose: trustworthy, human-reviewed extraction from scientific papers into structured tables.
