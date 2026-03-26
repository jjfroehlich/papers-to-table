# Paper Table Agent — `plan.md`

## Status

Batch 4 complete — review backend, summaries, export gating, and proposal filtering implemented.

**Implemented modules (Batch 1 + Batch 2 + Batch 3 + Batch 4):**
- `backend/app/schemas.py` — all enums and Pydantic models, including `status_flags` on `ProposalRecord`, `ProposalListItem`, `ProposalDetail`, `RecordDecisionRequest`, `BulkAcceptRequest`, `ProposalProgress`, `ExportCandidate`, `RunSummaryFull`
- `backend/app/ids.py` — deterministic ID generation
- `backend/app/artifacts.py` — run artifact bundle layout + I/O; `recompute_summaries` derives full counts, matching stats, provider info, and run-level status flags from artifact files
- `backend/app/config.py` — RunConfig, load/validate/snapshot
- `backend/app/ingest.py` — table/schema loading and cell classification
- `backend/app/lifecycle.py` — run state transitions
- `backend/app/runner.py` — staged runner, parse + match + style-profile + retrieval + extraction stages; `get_artifacts` helper
- `backend/app/main.py` — FastAPI endpoints including matching APIs, proposal-list/filter/detail, review-asset serving, decision recording, bulk-accept, progress, summary, recompute, export-candidates
- `backend/app/parsing.py` — ParsedDocument contract, DoclingParserAdapter (with BasicTextParser fallback), PDFiumBackend, OCR gate
- `backend/app/matching.py` — metadata extraction, deterministic scoring, match outcome assignment, duplicate-row conflict detection, artifact persistence
- `backend/app/style_profiles.py` — StyleProfile schema, per-column heuristic + optional LLM preprocessing, no-leakage enforcement, artifact persistence
- `backend/app/retrieval.py` — typed chunk generation (paragraph/section/caption/table), contextualized retrieval text, BM25-lite retrieval (top_k=6, neighbor window), artifact persistence
- `backend/app/provider.py` — ProviderAdapter ABC, LMStudioProvider (localhost API, capability probe, retry/error handling, vision support)
- `backend/app/extraction.py` — ExtractionRequest builder, text/vision JSON schemas, per-cell orchestrator, proposal+evidence serialization, evidence anchoring, recovery pass, figure fallback trigger/package, support-label mapping, Verify mode; `_compute_proposal_status_flags` (T068)
- `backend/app/review.py` — review decision persistence and audit history, `list_proposals` with filters, `bulk_accept`, `get_progress`, `get_export_candidates`

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

The core documentation set for this phase is `spec.md`, `plan.md`, and `research.md`. `tasks.md` becomes useful when implementation starts, and optional ADRs or runbooks should be added only if a concrete decision or operator workflow needs them.

## Implementation handoff rules

The intended implementation model for this repository is:

- `tasks.md` remains exhaustive, but execution should happen in the explicit batches defined there rather than as one giant undifferentiated pass.
- Each batch should be delivered as a polished, coherent slice that a later batch can safely build on.
- The JSON config file remains authoritative for advanced behavior and reproducibility.
- The browser UI owns the normal operator workflow for launch, status visibility, review, and export.
- The local onboarding path should stay clear and singular: start backend, start frontend, open the browser UI, supply a config path, start the run.
- If a batch changes operator-facing truth, update `README.md`, `spec.md`, `plan.md`, and `tasks.md` together in the same work pass.
- End-of-batch documentation updates are mandatory for operator-facing changes; `README.md` must trail implementation by zero batches, not by a later cleanup pass.
- `README.md` and any other user-facing docs must only describe commands, config behavior, lifecycle states, review actions, downloads, exports, and limitations that exist in the implemented slice.

---

## Definition of done

Implementation for this phase is complete when the system satisfies the functional requirements and acceptance criteria in `spec.md` and the following technical outcomes are true:

1. A user can run an end-to-end workflow:
   - start a run from the UI using a config file
   - understand the first valid next step even when no run exists yet
   - see the run move through ready/validating/running/completed-or-failed states
   - see coarse running progress as current stage plus current item when available
   - understand why review is unavailable while a run is still validating, running, or failed
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

9. The documented local startup path, browser-first operator workflow, and artifact/export behavior remain truthful and usable rather than drifting behind the implementation.

10. The shipped `README.md` and operator-facing documentation truthfully match the implemented app:
   - real startup commands
   - real config preparation and launch flow
   - real run lifecycle and review flow
   - real artifact, export, and download behavior
   - real limitations and unsupported cases
   - no speculative helpers or unimplemented workflows

---

## Constraints and non-goals

### Constraints

- Local-first operation in this phase.
- Single-user local browser app operation is sufficient for MVP.
- Human review is required before spreadsheet updates.
- UI remains minimal and task-focused, but not thin to the point that startup, lifecycle visibility, or review/export workflow becomes guesswork.
- The product must preserve one primary local onboarding/start path instead of expecting users to infer a preferred route from multiple equivalent but differently documented commands.
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

**Operator consequence:**
Runs are started through the API and executed under app-owned backend control using a lightweight in-process background mechanism for MVP, so the UI can remain the primary operator surface for launch and status tracking without requiring an external job framework.

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
- JSON files inside each run bundle for proposals, explicit review-decision records, diagnostics, summaries, and export bookkeeping

**Rationale:**
For a local-first, single-user MVP, artifact bundles are simpler, easier to inspect, and easier to debug than introducing a database. This keeps state reproducible without adding operational complexity that the product does not yet need.

---

### TD-6: Export generates a new workbook, not an in-place workbook patch

The system will export a new updated workbook plus audit log rather than mutating arbitrary workbooks in place.

**Rationale:**
Workbook fidelity is difficult to guarantee across complex Excel features. A generated export is safer, easier to validate, and more auditable.

**Implementation direction:**
Use `openpyxl` as the main XLSX round-trip engine. Guarantee content-only fidelity plus changed-cell highlighting. Do not promise preservation of workbook behavior or advanced sheet structure.

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
Queue/list of proposals + focused detail pane + custom PDF.js evidence viewer, with visible run/reviewer summary context in the main review workspace.

The same UI must also provide:
- a small run launcher centered on config-file path entry or selection
- a clear run setup summary derived from the resolved config snapshot
- visible lifecycle status and actionable failure messaging before review begins
- explicit pre-review empty/loading/warning states that tell the operator what to do next
- unresolved-match inspection that keeps PDF names and rationales visible without forcing the operator into raw artifact files

When switching runs, the UI may preserve the active queue filter, but proposal selection, proposal detail, and evidence-viewer state must always be refreshed for the currently loaded run.

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

Figure-aware fallback is in MVP, but the heavier reasoning-plus-vision path should run only when the field is likely figure- or table-derived, text retrieval failed, after text-first extraction remains insufficient after evidence recovery. Figure-derived proposals remain review-first and are evaluated through normal human reviewer outcomes rather than separate automated figure scoring.

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

This plan depends on `research.md` for supporting tradeoffs and decisions. Additional implementation notes, runbooks, or a future task breakdown can be added later if they become useful. The operator-facing README should preserve both architecture truth and practical onboarding steps so a new user can install dependencies, configure LM Studio, run the app, and understand artifact/export boundaries without reconstructing that flow from source. Optional ADRs may still be useful for decisions that evolve, especially:
  - low-level PDF backend
  - runtime/background jobs
  - workbook fidelity policy
  - UI stack

Implementation should normally proceed batch-by-batch according to `tasks.md`. The detailed task list remains exhaustive, but the practical implementation unit is a coherent batch with its own verification and doc-sync expectations.

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

3. **Pipeline runner and lightweight run-execution layer**
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

## MVP implementation stack

The MVP implementation stack is best understood in two layers.

### Core MVP architecture

- **Frontend UI**: React local browser app
- **Backend API**: small Python FastAPI service
- **PDF ingestion/parser**: Docling
- **Low-level PDF rendering/geometry**: PDFium via `pypdfium2`
- **PDF review viewer**: raw/custom PDF.js viewer with app-owned evidence/highlight overlays
- **LLM provider (MVP default)**: LM Studio localhost API
- **Persistence**: filesystem artifact bundles + JSON files only
- **Spreadsheet export**: `openpyxl`
- **OCR fallback**: OCR fallback path enabled for scanned/text-inaccessible PDFs
- **No database in MVP**
- **No desktop wrapper in MVP**
- **No background job framework by default in MVP**

### Practical default implementation choices

- **Frontend language/build**: TypeScript + Vite
- **UI components/layout**: app-owned React components plus repository-local CSS
- **Review queue/list**: app-owned queue/list-detail components; virtualization is optional only if measured proposal volume demands it

This section is intentionally explicit so the MVP does not drift back toward Tauri, SQLite, Huey, or other optional components as baseline requirements.

---

## One-config-file control model

The MVP uses a single JSON config file as the main control surface.

This config file is the source of truth for:

- inputs
- parser settings
- matching settings
- style-profile preprocessing
- retrieval settings
- model/provider settings
- figure fallback settings
- review settings
- export settings

The UI should not expose a large parameter-tuning surface in MVP. Advanced behavior is configured by editing the config file directly.

The UI should still expose enough config-derived context for safe operation: config path, resolved input locations, output location, Verify-mode status, and provider/model summary.

This split is intentional: the config file owns advanced behavior and reproducibility, while the UI owns launch, status visibility, review, artifact access, and first-run usability.

The config file should be sufficient to reproduce a run together with the input files and output artifact bundle.

---

## Pipeline stages

The MVP pipeline should run in these explicit stages:

1. **Load config and inputs**
   - read config
   - expose `ready` before starting, then `validating` while checking config and input readiness
   - load spreadsheet and schema
   - validate required metadata columns
   - detect missing and already-filled cells
2. **Build per-column style profiles**
   - read existing filled cells per column
   - run a preprocessing LLM step per column
   - produce a structured style/format profile for each column
3. **Parse PDFs once**
   - parse each PDF with Docling
   - generate normalized parsed-document artifacts
   - generate page/crop artifacts needed for review and figure fallback
   - trigger OCR fallback only when PDF text is inaccessible or clearly insufficient
4. **Match PDFs to rows**
   - extract grounded publication metadata
   - run deterministic matching
   - run fallback adjudication only for plausible ambiguous cases
   - block ambiguous matches
   - block duplicate-row PDF conflicts
5. **Build retrieval artifacts**
   - generate typed chunks
   - generate contextualized retrieval text
   - generate table-aware retrieval units when available
6. **Extract proposals per target cell**
   - gather row context, column definition, style profile, and retrieved context
   - prompt the model once per target cell
   - require structured JSON output
   - store one best proposal per target cell
7. **Validate and recover evidence**
   - validate page-grounded evidence
   - run one narrow recovery step if evidence is missing/weak/unusable
   - preserve weak-but-reviewable proposals
8. **Run scoped figure fallback when needed**
   - only when figure/table-derived evidence is likely, text retrieval failed, or text-first extraction remains insufficient after evidence recovery
   - use crop + caption + nearby text + full page as needed
9. **Write proposal artifacts**
   - write proposals, evidence, diagnostics, and run summaries as JSON artifacts
10. **Review in UI**
   - show resolved run setup context and direct access to config snapshot
   - keep the queue clearly non-actionable until the run is review-ready
   - queue-first review
   - record accept / accept-with-edit / reject / bulk-accept-visible-subset decisions
11. **Export**
   - generate new XLSX
   - apply accepted changes
   - highlight changed cells
   - write audit log
12. **Write reviewer-outcome summaries**
   - reviewed count
   - accepted-as-is
   - accepted-with-edit
   - rejected
   - per-column breakdown

This explicit stage list is the canonical implementation sequence for MVP.

---

## Traceability from product requirements to implementation

This plan should remain easy to audit against `spec.md`. The main requirement group to implementation mapping is:

- **FR-1 to FR-4** → ingest, parse, match, retrieval, and extraction stages plus parser and provider contracts.
- **FR-5 to FR-8** → extraction contracts, evidence validation, rationale display, and figure-fallback routing.
- **FR-9 to FR-11** → queue-first review UI, review-state persistence, export engine, and audit-log generation.
- **FR-12 to FR-14** → run summaries, diagnostics, completion semantics, and warning states for empty or weak runs.
- **NFRs / trust requirements** → local-first architecture, filesystem artifact bundles, provider transparency, inspectable evidence, and deterministic testing strategy.

When implementation changes one side of this mapping, the corresponding section in `spec.md` or `plan.md` should be updated in the same work pass.

---

## UI architecture

## MVP interaction model

The review UI will use a **queue-first / list-detail** design with an explicit three-pane layout plus visible run/reviewer summary context.

### Layout

- **Left pane**: proposal queue
- **Center pane**: proposal detail
- **Right pane**: evidence viewer
- **Summary/top context area**: run metrics, reviewer-outcome context, and direct artifact downloads
- **Top bar / queue controls**: progress counters, filters, and warning cues

### Proposal queue

The queue should support filtering by:
- row
- column
- PDF
- evidence status
- figure-based evidence
- ambiguous/unmatched match status

Default ordering should prioritize actionable undecided proposals before blocked, unresolved, or otherwise non-reviewable records.

Blocked and unresolved records should remain visible through queue ordering, filters, or dedicated warning/inspection surfaces, but they should not displace the main actionable review slice by default.

Proposal status, evidence source, and warning state should be distinguishable at a glance through clear labels, badges, or equivalent visual treatments.

### Proposal detail

The detail pane should show:
- row context
- target column definition
- current cell value if in Verify mode
- proposed value
- support state
- concise rationale or calculation
- primary evidence item
- expandable secondary evidence items

The action area should disable accept paths for blocked items or items without a reviewable proposed value while still allowing inspection and rejection.

### Evidence viewer

For text evidence:
- show quote text
- show page
- show highlight when available
- fall back to quote + page when highlight fails

Highlight overlays must come from actual parsed page geometry. Do not fabricate placeholder rectangles just to preserve a highlight-looking UI.

For figure evidence:
- show crop first
- show caption directly attached
- allow full-page inspection

### Summary and download context

The main review workspace should expose:
- run-summary context
- reviewer-summary context
- direct access to workbook, audit-log, run-summary, and reviewer-summary downloads

When those files are not available yet, the workspace should say so explicitly instead of presenting them as ready downloads.

The unresolved-match area remains inspect-only in MVP. It is a visibility and diagnosis surface, not a corrective-action workspace.

If no verified cells have been reviewed yet, keep per-column verify coverage visible only as evidence-coverage context with explicit wording that reviewer outcomes are not yet meaningful.

### Actions

The main review actions should be:
- accept
- accept with edit
- reject
- next
- previous
- bulk accept visible subset

### Progress and decision affordances

The top bar should show:
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

## Bulk review behavior

The MVP should support bulk acceptance only for the currently visible filtered subset of undecided proposals.

Bulk acceptance should require explicit user confirmation.

A global “accept everything blindly” action should not be the default MVP behavior.

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
- fetch direct run artifact downloads
- fetch reviewer-outcome summary
- fetch document pages/crops/highlights

The service layer should remain thin and should not duplicate pipeline logic. It should read and update per-run JSON artifacts rather than depending on a database.

---

## Pipeline architecture

## Guiding principle

The pipeline should be **stage-based and explicit**, with a clear default path and a small number of limited fallbacks.

The canonical stage list is defined in `## Pipeline stages` above. The sections that follow describe the main contracts and policies that each stage must obey.

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

## OCR fallback policy

OCR is fallback-only in MVP and should run only when PDF text is inaccessible or clearly insufficient.

The default OCR fallback is **OCRmyPDF**.

Born-digital PDFs remain the primary target and should not go through OCR unnecessarily.

OCR outputs must still be normalized into the same parsed-document contract as non-OCR documents.

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

The MVP retrieval defaults are:
- paragraph chunks
- section chunks
- caption chunks
- table-region chunks
- `top_k = 6`
- include captions/tables when relevant
- one neighbor window around selected text chunks

## Retrieval text versus display text

Retrieval may use contextualized `retrieval_text`, but evidence display and quote validation must use source-preserving text.

## Baseline retrieval philosophy

The default retrieval stack should be intentionally narrow:

- typed chunking
- contextualized text
- sparse or simple baseline retrieval
- table-aware units where useful
- no reranker in the MVP baseline
- no HyDE in the MVP baseline
- no query expansion in the MVP baseline

Advanced helpers must prove lift before becoming baseline behavior.

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
- one proposal JSON object per target cell per run
- value-first behavior retained
- structured-output-first
- concise rationale/calculation when the value is derived
- proposal states should include at least `found`, `inferred`, `unclear`, `blocked`, and `error`

## LLM interaction model

The MVP LLM interaction model is:

- parse once
- retrieve relevant passages
- ask the model per target cell
- require structured JSON output
- store page-grounded evidence

The extraction model should receive, at minimum:

- row context
- column name
- column description
- per-column style/format profile
- retrieved evidence context
- instructions for proposal state and evidence output

The model is allowed to:

- extract directly supported values
- derive values from calculations
- provide concise reviewer-facing rationale when inference or calculation is required

The model must not rely on hidden chain-of-thought as a product feature.

The MVP should use:

- one primary text-capable reasoning model through LM Studio
- one vision-capable model through LM Studio for figure fallback when needed

## Verify mode

Verify mode is not a separate extraction architecture. It is the same extraction flow applied to already-filled cells with different review/export/evaluation semantics.

## Style-profile preprocessing

Before extraction, the system should run a preprocessing LLM step per schema column over existing filled cells.

This step must produce a structured style/format profile that may include:

- expected output type
- expected length/detail level
- tone/style
- unit conventions
- whether outputs are terse, categorical, numeric, or explanatory

This profile is used only to shape output form.

It must not encode likely scientific content for the target cell.

Raw existing filled cells must not be injected into extraction prompts as semantic few-shot exemplars by default.

---

## Evidence strategy

## Objective

Preserve plausible values while making evidence quality visible, recoverable, and reviewable.

## MVP evidence contract

The evidence model should be narrower and stricter than in the old system. Each proposal should link to separate evidence objects rather than embedding every evidence detail directly into the proposal object.

### Proposal object shape in prose

Each proposal JSON object should include, at minimum:
- run identifier
- proposal identifier that remains unique within the run even if more than one PDF targets the same row/cell context
- row identifier
- column identifier
- proposal state
- proposed value
- rationale field
- calculation field when the value is derived
- primary evidence identifier
- secondary evidence identifiers when additional evidence exists

### Evidence object shape in prose

Each evidence object should capture, at minimum:
- evidence identifier
- source PDF
- page reference
- evidence type such as text quote, highlight, figure crop, or caption
- enough anchor information for the UI to render or fall back gracefully

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
- separate rationale and calculation fields for derived values

## Validation and recovery

MVP should use:
- one strict evidence validator
- one simple locator/recovery path

Do not build a broad salvage ladder by default.

---

## Table and figure handling strategy

### Tables

Tables are first-class evidence sources.

The system should:
- preserve table structure where possible during parsing
- generate table-aware retrieval units
- prefer table-derived context for fields likely to be answered from tabular results
- include nearby captions or narrative context when useful

### Figures

Figures are also first-class evidence sources, but figure reasoning is a scoped fallback path.

The MVP should:
- extract figure/caption relationships when available
- generate crops and page references for review
- use a vision-capable model only when:
  - the field appears likely figure/table-derived
  - text retrieval failed or remained insufficient
  - or text-first extraction remains insufficient after evidence recovery

Figure-derived proposals remain normal proposals, but their evidence source must be marked as figure-based.

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

The MVP export promise is content-only fidelity plus highlighting of changed cells, not workbook-behavior fidelity.

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

## Artifact bundle layout

The MVP persists state as a run-specific artifact bundle in the output directory.

The bundle should contain stable top-level categories such as:

- `run.json`
- `config.snapshot.json`
- `inputs/`
- `style_profiles/`
- `parsed/`
- `matching/`
- `retrieval/`
- `proposals/proposals.jsonl`
- `evidence/evidence.jsonl`
- `review/decisions.jsonl`
- `review/reviewer_summary.json`
- `exports/updated_table.xlsx`
- `exports/audit_log.csv`
- `logs/`

This artifact bundle is the canonical persisted state for MVP.

---

## Artifact bundle contract

The bundle layout is the canonical persistence mechanism, but not every JSON file needs to be treated as a stable interface. For MVP, the stable artifact categories for tooling, tests, and operator inspection are:

- run metadata and configuration snapshots
- parsed-document artifacts and parser diagnostics
- proposal and evidence JSON
- review decisions and decision history
- reviewer-outcome and run-summary JSON
- exported workbook and audit-log outputs

Lower-level intermediate files may still evolve as implementation details so long as these categories remain discoverable and semantically consistent.

---

## Ownership rule

The run directory is the canonical audit bundle and the only required MVP persistence mechanism.

The MVP does not need pause/resume semantics within a run. If a run is interrupted, the partial artifacts may remain for inspection, and a new attempt should create a new run directory.

Proposal identifiers must remain unique within a run, including blocked or unresolved cases where multiple PDFs may surface the same row/cell context.

Review decisions should be persisted as explicit records rather than only as proposal-state mutations so audit logs and summaries remain derivable from artifact data.

When an audit log includes a decision timestamp, that timestamp should come from the persisted review-decision record when one exists.

---

## Runtime and background jobs

## Objective

Run the pipeline simply and predictably without reintroducing graph-runtime complexity.

## Recommended MVP shape

- app-owned staged runner
- runs started through the API and executed under app-owned backend control using a lightweight in-process background mechanism
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

## Reviewer-outcome summaries

MVP run quality should be summarized primarily through reviewer outcomes rather than automated correctness scoring.

At minimum, the run summary should include:

- PDFs processed
- matched / unmatched / ambiguous PDFs
- target cells
- proposals generated
- reviewed proposals
- accepted-as-is
- accepted-with-edit
- rejected
- changed cells exported
- Verify mode on/off
- provider/model names
- local vs cloud status

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

Playwright/browser-based e2e startup should remain shell-independent: prepare fixture run data in a dedicated script first, then start backend and frontend with direct process spawning or Playwright global setup/teardown rather than shell heredocs or shell command chaining.

Browser-based test failures should distinguish environment/runtime problems from application failures whenever practical.

Screenshots, traces, or equivalent browser-failure artifacts are desirable where practical so review-workflow regressions are easier to diagnose.

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

Most previously blocking architecture questions are resolved for MVP. The remaining implementation-level questions to validate during delivery are:

- whether the first PDF evidence overlay should be fully custom or should borrow limited interaction patterns from existing highlighter libraries while keeping normalized anchors internal
- whether CSV input should receive additional import warnings when workbook-only fidelity expectations could confuse users
- how much saved-view or preset support is necessary in the first review queue without expanding into a large personalization surface
- if synchronous execution proves insufficient, whether Huey + SqliteHuey remains the right first background-job layer to adopt

These are intentionally narrow questions. They should not reopen the larger architectural choices already recorded in this plan.

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
- new XLSX export plus audit log with content-only fidelity plus changed-cell highlighting

This keeps the system aligned with its real purpose: trustworthy, human-reviewed extraction from scientific papers into structured tables.
