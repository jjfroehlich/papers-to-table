# Paper Table Agent — `plan.md`

## Purpose

This document defines the technical approach for implementing the product requirements in `spec.md`.

It is the technical counterpart to the product specification:

- `spec.md` defines **what** the product must do and **why**.
- `plan.md` defines **how** the system will satisfy those requirements.
- `data-model.md`, `contracts/`, `research.md`, and `tasks.md` hold supporting detail that should not overload either the product spec or this plan.

This plan is intentionally opinionated. It chooses a concrete MVP architecture so implementation can proceed without drifting into a general-purpose RAG platform, a chat product, or an overcomplicated agent framework.

---

## Relationship to other documents

- `spec.md` is the source of truth for user-facing requirements and acceptance criteria.
- `research.md` records the research and tradeoffs behind the decisions in this plan.
- `data-model.md` defines the core entities, relationships, and invariants.
- `contracts/` will define API and payload contracts derived from the data model.
- `tasks.md` will break this plan into executable implementation work.

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
- Single-user desktop/local operation is sufficient for MVP.
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
The workflow is structured and auditable. The prior implementation showed that graph orchestration added less value than expected around a mostly sequential loop. The rewrite should preserve resumability and checkpoints without making a graph framework central.

---

### TD-3: Use one main parser first, with a stable parser contract

All parser outputs must normalize into a shared `ParsedDocument` contract, but the shipping MVP should begin with one main parser rather than a multi-parser runtime.

**Rationale:**  
Parser abstraction is valuable; multi-parser runtime complexity is not justified as a baseline. The parser contract prevents lock-in while preserving a simpler default path.

---

### TD-4: Parser baseline is Docling + PDFium fallback

The primary ingestion stack for MVP will be:

- **Docling** as the main parser
- **PDFium via pypdfium2** as the low-level PDF layer for rendering, crop extraction, and evidence anchoring fallback

**Rationale:**  
Docling is currently the strongest main parser candidate for structured scientific PDF parsing, layout awareness, figure handling, and table support. PDFium provides a strong low-level foundation for page rendering, geometry, and evidence display with a more favorable licensing posture than MuPDF/PyMuPDF.

**Note:**  
GROBID remains an optional later enrichment path if measured lift justifies it.

---

### TD-5: Filesystem artifacts are canonical; SQLite is the operational store

The system will use:

- per-run artifact folders as the canonical run record
- SQLite as the operational query/review/checkpoint database

**Rationale:**  
This preserves local-first reproducibility while enabling efficient proposal/review queries and resumable workflows.

---

### TD-6: Export generates a new workbook, not an in-place workbook patch

The system will export a new updated workbook plus audit log rather than mutating arbitrary workbooks in place.

**Rationale:**  
Workbook fidelity is difficult to guarantee across complex Excel features. A generated export is safer, easier to validate, and more auditable.

**Implementation direction:**  
Use `openpyxl` as the main XLSX round-trip engine. Limit guaranteed fidelity to the main table sheet.

---

### TD-7: Use structured outputs first, with capability probes and graceful fallback

LLM interaction will be schema-first using typed contracts. Providers that do not support strong structured outputs will fall back to prompt-only JSON handling.

**Rationale:**  
The extraction path depends on predictable proposal and evidence objects, but the product must remain flexible across local and external providers.

---

### TD-8: Review requires a dedicated queue-first UI

The review product surface will be a dedicated Run/Review application, not a notebook or chat interface.

**Rationale:**  
The main value of the product is human verification of proposed spreadsheet updates with visible evidence.

**Interaction model:**  
Queue/list of proposals + focused detail pane + PDF evidence viewer.

---

### TD-9: MVP evaluation is reviewer-outcome-based

The MVP will evaluate performance primarily through reviewer outcomes rather than an automated correctness score across heterogeneous field types.

**Rationale:**  
The product already requires human review. Reviewer decisions are the most trustworthy MVP measure of usefulness, while automated verify-mode scoring across mixed field types is still an open research problem.

---

### TD-10: Existing filled cells may shape format, not content

Existing filled cells should not be used as semantic few-shot examples by default. They may be used only as non-binding style/format guidance under safeguards.

**Rationale:**  
This preserves possible benefits for output shape while reducing hallucination and evaluation leakage risks.

---

### TD-11: Figure support is in scope, but remains review-first

Figure-aware fallback is in MVP, including broad figure classes, but must remain explicitly review-oriented and separately monitored.

**Rationale:**  
The product scope includes figure-derived evidence, but research shows visual extraction is riskier and must be treated as a separate evidence lane with explicit UI support and metrics.

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

## Supporting documents generated from this plan

This plan assumes the following supporting documents exist or will be created:

- `research.md` — tool comparisons, export constraints, UI choices, measurement rationale, licensing notes
- `data-model.md` — core entities and relationships
- `contracts/` — API and JSON schemas
- `quickstart.md` — end-to-end manual validation flows
- `tasks.md` — executable implementation tasks derived from this plan
- optional ADRs for decisions that may evolve, especially:
  - low-level PDF backend
  - runtime/background jobs
  - workbook fidelity policy
  - UI stack

---

## System architecture overview

## High-level architecture

The system will consist of five major layers:

1. **Desktop shell and frontend UI**
   - local app shell
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
   - SQLite operational store

---

## Proposed implementation stack

### Desktop shell
- **Tauri 2**

### Frontend
- **React**
- **TypeScript**
- **Vite**
- **Tailwind CSS**
- **shadcn/ui** or similarly lightweight component approach
- **TanStack Table**
- **TanStack Virtual**

### PDF viewer
- **PDF.js** in the UI layer
- app-managed overlay system for highlights and evidence regions

### Backend / service layer
- **Python**
- **FastAPI**

### Background jobs
- **Huey**
- **SqliteHuey** for local queue storage

### Persistence
- **SQLite** operational store
- filesystem artifact directories

### Main parser
- **Docling**

### Low-level PDF layer
- **pypdfium2 / PDFium**

### XLSX export
- **openpyxl**

---

## End-to-end technical flow

1. Load table, schema, PDF folder, and configuration.
2. Validate standardized metadata columns (`Title`, `Authors`, `Publication Year`).
3. Normalize schema and identify missing, already-filled, and verify-eligible cells.
4. Inventory PDFs and create run records.
5. Parse PDFs through the parser stack and normalize outputs into `ParsedDocument`.
6. Extract grounded metadata for row matching.
7. Match PDFs to rows using deterministic scoring and fallback adjudication.
8. Block ambiguous or duplicate-row conflicts from extraction.
9. Build retrieval indexes from typed chunks and table-aware units where available.
10. Select a context strategy for each matched PDF.
11. Run schema-driven extraction to produce one best proposal per target cell.
12. Validate evidence and run one narrow evidence-location pass where needed.
13. Run figure-aware fallback where appropriate.
14. Persist proposals, evidence, diagnostics, and checkpoints.
15. Present proposals in the review UI with queue, filters, and evidence display.
16. Record review decisions.
17. Export accepted changes into a new XLSX workbook and audit log.
18. Compute reviewer-outcome run summaries and Verify-mode summaries.
19. Write final run diagnostics and artifacts.

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

### Bulk actions

MVP should support a bulk accept action, but the safest product interpretation is:
- apply bulk acceptance to a visible, filtered subset
- require explicit confirmation

**Open implementation point:** whether this is limited to the filtered subset or can apply globally.

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

The service layer should remain thin and should not duplicate pipeline logic.

---

## Pipeline architecture

## Guiding principle

The pipeline should be **stage-based and explicit**, with a clear default path and a small number of limited fallbacks.

## Main stages

### Stage 1 — Ingest
- load table/schema/config
- validate metadata columns
- fingerprint inputs
- create run record

### Stage 2 — Parse
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
- decisions stored immutably / append-only in spirit

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

## Verify mode

Verify mode is not a separate extraction architecture. It is the same extraction flow applied to already-filled cells with different review/export/evaluation semantics.

## Format/style guidance

The extraction layer may optionally use non-binding style/format guidance derived from existing cells, but:
- content must remain grounded in the current PDF
- style guidance must not act as semantic evidence
- low-risk field types should be preferred first

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
- text/table extraction produced nothing useful
- evidence remains weak
- retrieved context strongly points to figures/panels/captions
- parser identified candidate figure-bearing regions

## Review policy

Figure-derived proposals must:
- be clearly labeled as figure-based
- display crop + caption + full-page access
- remain subject to human review
- be monitored separately in reviewer-outcome summaries

## Monitoring

Track at minimum:
- figure-derived proposal count
- accepted as-is
- accepted with edit
- rejected
- edit burden
- review effort proxy if available
- breakdown by figure class if possible

---

## Export strategy

## Objective

Produce safe, review-authorized outputs without mutating the original source workbook.

## Planned behavior

- always export XLSX
- preserve original workbook untouched
- preserve formatting for the main table sheet
- highlight changed cells
- include audit log

## Engine

- use `openpyxl`

## Workbook fidelity policy

Guarantees should be explicitly limited to the main table sheet.

Advanced workbook artifacts outside that boundary should remain:
- best-effort
- or explicitly unsupported

This boundary must be documented clearly before implementation is finalized.

---

## Persistence strategy

## Objective

Support local-first resumability, auditability, and inspectability.

## Canonical persistence model

### Filesystem artifacts
Canonical run bundle:
- input snapshots/fingerprints
- parser outputs
- retrieval artifacts
- logs
- diagnostics
- exports
- review/evaluation summaries

### SQLite operational store
Operational/query layer:
- runs
- PDFs
- matches
- proposals
- evidence
- review decisions
- checkpoints
- export records

## Ownership rule

The run directory is the canonical audit bundle.  
SQLite is the operational store for the application.

---

## Runtime and background jobs

## Objective

Run long stages asynchronously without reintroducing graph-runtime complexity.

## Recommended MVP shape

- app-owned staged runner
- Huey + SqliteHuey for background execution
- stage boundaries as checkpoint boundaries
- explicit resume-from-stage behavior

## Why this shape

It keeps:
- execution simple
- local deployment simple
- workflow ownership in the app
- queue complexity low

while still supporting non-blocking execution.

---

## Model/provider strategy

## Objective

Keep proposal extraction robust across local and external providers.

## Approach

- typed request/response contracts
- capability probes for structured-output support
- structured-output-first execution
- prompt-only JSON fallback when required

## Transparency

The system should record and surface:
- provider name
- model name
- whether the run stayed local or used cloud providers

At minimum this should appear in the normal run summary.

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

It does **not** require a sophisticated automated correctness score in MVP.

## Measurement integrity

Always distinguish:
- proposal production
- evidence presence
- reviewer acceptance
- evaluation emptiness/skips

Never let zero-evaluable-target runs masquerade as normal scored runs.

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
- implement main parser + low-level PDF fallback
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
- figure-derived proposal monitoring

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
**Mitigation:** review-first figure UX, separate figure-derived metrics, monitor reviewer acceptance/edit/reject rates by figure source and figure class.

### R-4: Workbook fidelity expectations exceed implementation reality
**Mitigation:** explicitly document main-sheet fidelity guarantees and non-guaranteed features.

### R-5: Provider incompatibility or weak structured output
**Mitigation:** capability probes, typed validation, prompt-only fallback.

### R-6: Runtime complexity grows back through helper passes
**Mitigation:** helper passes remain opt-in until measured lift is shown.

### R-7: Config sprawl reappears
**Mitigation:** keep user-facing config small; keep policy/internal tuning separate; avoid exposing every experimental knob.

---

## Open technical questions

- [NEEDS CLARIFICATION: What exact workbook fidelity guarantees are contractual for the main table sheet in MVP?]
- [NEEDS CLARIFICATION: Is pypdfium2/PDFium the final locked-in low-level PDF backend, or do we keep a formal pluggable abstraction from day one?]
- [NEEDS CLARIFICATION: Do we use raw PDF.js with a custom evidence layer, or a higher-level viewer wrapper/SDK?]
- [NEEDS CLARIFICATION: Is Huey + SqliteHuey sufficient after packaging/progress/resume testing, or do we need a different runtime choice?]
- [NEEDS CLARIFICATION: Which field types may safely use format/style guidance from existing cells in MVP?]
- [NEEDS CLARIFICATION: What exact run-summary fields are mandatory for normal users vs only visible in advanced logs?]
- [NEEDS CLARIFICATION: What figure taxonomy and figure-derived metrics are mandatory for MVP monitoring?]
- [NEEDS CLARIFICATION: Do full parsed elements live in SQLite, or only in artifacts with chunk/state projections stored in DB?]
- [NEEDS CLARIFICATION: What OCR sidecar is the fallback choice for scanned PDFs?]

---

## Concise implementation summary

Paper Table Agent will be implemented as a local-first workflow application with:

- a Tauri-based desktop shell
- a React queue-first review UI
- PDF.js in the frontend and PDFium/pypdfium2 in the backend
- one main parser first, behind a normalized parser contract
- typed retrieval units and source-preserving evidence
- a deterministic staged runner with Huey-backed background execution
- filesystem artifacts plus SQLite operational state
- reviewer-outcome-based MVP evaluation
- optional style/format guidance instead of semantic few-shot examples
- figure-aware fallback with separate figure-derived monitoring
- new XLSX export plus audit log, preserving the main table sheet as promised

This keeps the system aligned with its real purpose: trustworthy, human-reviewed extraction from scientific papers into structured tables.