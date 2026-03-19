# Paper Table Agent — `tasks.md`

## Status

Implementation checklist for the full intended MVP.

## Purpose

This document turns `spec.md`, `research.md`, and `plan.md` into a concrete implementation task list for Codex.

It is intentionally exhaustive and describes the **full intended MVP implementation**, not a reduced sprint slice.
Tasks remain ordered by **dependency and architecture constraints**, not by human sprint scope reduction.
If a task below is part of the intended finished MVP, it stays in the list even if it feels like later-stage polish.

`spec.md` remains the source of truth for product requirements and acceptance criteria.
`plan.md` remains the source of truth for architecture and technical direction.
`tasks.md` defines the concrete implementation order.

## MVP architecture constraints

Preserve these constraints throughout implementation:

- local browser app, **not Tauri for MVP**
- **React** frontend
- small **Python FastAPI** backend
- **Docling** as main parser
- **PDFium via `pypdfium2`** as low-level PDF backend
- raw/custom **PDF.js** viewer
- **LM Studio localhost API** as the initial provider path
- **filesystem artifact bundles + JSON files only**
- **no database in MVP**
- **no background job framework by default in MVP**
- **content-only XLSX export**
- **reviewer-outcome summaries** in MVP
- **per-column preprocessing LLM** for style profiles
- **no raw semantic example injection by default**
- **scoped automatic figure fallback only**
- **no user-triggered figure fallback**

If implementation pressure suggests changing any of these constraints, update `spec.md` and `plan.md` first, then update this file in the same work pass.

## Working assumptions

- Tasks are listed in required dependency order unless a task explicitly says it is safe to parallelize.
- Later tasks may assume earlier tasks are complete.
- Keep contracts stable before adding orchestration complexity.
- Keep persistence logic centralized in the artifact subsystem rather than scattering ad hoc JSON reads and writes across the codebase.
- Keep prompt/request construction separate from orchestration logic.
- Resolve config defaults into one effective runtime config before snapshotting.
- Keep unsupported or out-of-scope features explicitly blocked so Codex does not silently broaden the MVP.

## Assumed repo shape

Use or map tasks onto a local-first repo shape such as:

- `backend/` — FastAPI app, staged runner, parsing/matching/retrieval/extraction/export logic
- `frontend/` — React review UI
- `tests/` — unit, integration, contract, and e2e tests
- `tests/fixtures/` — deterministic spreadsheet/PDF fixture corpus
- `docs/` — optional internal notes if needed

If the repo already uses different names, preserve the existing structure and map the tasks accordingly.

---

## Phase 0 — Foundation, contracts, config, identifiers, and deterministic test harness

**Goal:** establish stable schemas, stable identifiers, filesystem persistence, config behavior, and test scaffolding for the full MVP.

- [ ] **T001** Create the base project skeleton for `backend/`, `frontend/`, and `tests/`, plus a short root-level development note that describes the local-first architecture and canonical pipeline stages.

- [ ] **T002** Define the shared domain enums and common JSON/Pydantic/TypeScript schemas for at least:
  - run status
  - match outcome
  - proposal state
  - support label
  - evidence source type
  - review decision
  - warning/status category
  - provider locality (`local` vs `cloud`)

- [ ] **T003** Define and implement stable identifier generation for runs, PDFs, rows, cells, proposals, evidence items, and review decisions, including at minimum:
  - deterministic `cell_id`
  - stable `pdf_id` assignment within a run
  - proposal and evidence ids that are unique and traceable
  - stable review-decision ids linked back to proposal and cell context

- [ ] **T004** Implement the stable run artifact bundle layout with at least:
  - `run.json`
  - `config.snapshot.json`
  - `inputs/`
  - `style_profiles/`
  - `parsed/`
  - `matching/`
  - `retrieval/`
  - `proposals/`
  - `evidence/`
  - `review/`
  - `summaries/run_summary.json`
  - `summaries/reviewer_summary.json`
  - `exports/`
  - `logs/`

- [ ] **T005** Implement the artifact I/O helper layer:
  - shared helpers for writing and reading JSON snapshot files
  - shared helpers for appending and reading JSONL files
  - stable artifact-path generation inside a run bundle
  - lookup helpers for proposals, evidence, and review decisions by id
  - run-summary and reviewer-summary recomputation from artifact files
  - write behavior that is atomic enough for local single-user reliability

- [ ] **T006** Define the proposal JSON schema and contract for one proposal object per target cell per run, including at least:
  - `proposal_id`
  - `run_id`
  - `pdf_id`
  - `row_id`
  - `column_name`
  - `cell_id`
  - `source_mode`
  - `proposal_state`
  - `support_label`
  - `proposed_value`
  - `rationale`
  - `calculation`
  - `needs_more_evidence`
  - `primary_evidence_id`
  - `evidence_ids`

- [ ] **T007** Define the evidence JSON schema and contract for separate evidence records linked to proposals, including at least:
  - `evidence_id`
  - `proposal_id`
  - `pdf_id`
  - `source_type`
  - `page`
  - `quote_text`
  - `highlight`
  - `figure_ref`
  - `caption_text`
  - `crop_path`
  - `full_page_path`
  - `anchor_confidence`

- [ ] **T008** Define the review-decision JSON schema plus the run-summary and reviewer-summary JSON schemas.

- [ ] **T009** Define the single JSON config schema covering:
  - input table and schema paths
  - PDF directory path
  - parser settings
  - OCR fallback settings
  - matching settings
  - style-profile settings
  - retrieval settings
  - provider/model settings
  - figure-fallback settings
  - review settings
  - export settings

- [ ] **T010** Implement config default resolution into one effective runtime config before any run work starts.

- [ ] **T011** Create `config.example.json` as a minimal but complete example config file for the full MVP.

- [ ] **T012** Implement config/path validation and required metadata/schema validation:
  - validate that configured paths exist and are readable
  - validate that schema columns include at least `column_name` and `description`
  - validate that the source table contains `Title`, `Authors`, and `Publication Year`
  - fail early with actionable diagnostics when validation fails

- [ ] **T013** Implement config snapshotting into run artifacts:
  - validate config at run start
  - persist the resolved effective config as `config.snapshot.json`
  - ensure the run can later be explained from the snapshot

- [ ] **T014** Build a deterministic fixture corpus in `tests/fixtures/` containing at minimum:
  - one clean born-digital paper that should match and extract successfully
  - one scanned or text-inaccessible paper for OCR fallback
  - one unmatched paper
  - one ambiguous-match paper
  - one duplicate-row-conflict case
  - one figure-heavy paper
  - one workbook fixture with unsupported Excel features present for export warnings
  - one CSV fixture
  - one schema fixture

- [ ] **T015** Set up backend unit/integration/contract test tooling, including provider stubs/fakes and fixture helpers.

- [ ] **T016** Set up frontend test tooling and Playwright e2e scaffolding for the review workflow.

---

## Phase 1 — Run creation, input loading, normalization, and lifecycle

**Goal:** the system can start a run, validate and snapshot inputs, and compute which cells are eligible for extraction or verification.

- [ ] **T017** Implement spreadsheet loading for CSV and XLSX inputs.

- [ ] **T018** Implement schema loading from workbook or separate schema file.

- [ ] **T019** Implement table normalization and required metadata-column validation for `Title`, `Authors`, and `Publication Year`.

- [ ] **T020** Implement cell eligibility classification for at least:
  - empty / missing
  - already-filled
  - trivial placeholder treated as empty when configured
  - skipped / ineligible

- [ ] **T021** Implement Verify mode semantics so already-filled cells become eligible targets when Verify mode is enabled.

- [ ] **T022** Implement run lifecycle state transitions for at least:
  - `created`
  - `running`
  - `completed`
  - `completed_with_warnings`
  - `failed`
  - `interrupted`

- [ ] **T023** Implement run creation and inspection API endpoints for:
  - create run
  - list runs
  - get run summary
  - fetch config snapshot
  - fetch input summary

- [ ] **T024** Add tests covering valid input readiness, metadata-column rejection, missing-path rejection, placeholder handling, and Verify mode behavior.

---

## Phase 2 — Parsing baseline, PDF backend, OCR fallback, and normalized parsed-document artifacts

**Goal:** parse PDFs once, normalize them into one internal contract, and generate the low-level artifacts needed later for evidence review.

- [ ] **T025** Define the internal `ParsedDocument` schema/contract with fields for:
  - document identity
  - extracted metadata
  - pages
  - typed blocks/elements
  - source-preserving text
  - normalized text
  - reading order
  - figure/caption relationships when available
  - table regions when available
  - provenance links
  - optional geometry/bounding boxes

- [ ] **T026** Implement the parser adapter interface and register **Docling** as the main parser.

- [ ] **T027** Implement the low-level PDF abstraction using **`pypdfium2` / PDFium** for rendering, geometry, crop extraction, and page/image access.

- [ ] **T028** Integrate OCR fallback for scanned or text-inaccessible PDFs:
  - default OCR fallback tool = **OCRmyPDF**
  - use OCR fallback only when text extraction is empty or clearly insufficient
  - normalize OCR output into the same `ParsedDocument` contract as born-digital PDFs
  - store OCR-affected artifacts in the run bundle

- [ ] **T029** Implement parse-stage persistence so parser-native outputs and normalized parsed-document artifacts are both stored under stable run paths.

- [ ] **T030** Generate page-render artifacts and crop helpers needed later for text evidence, figure evidence, and PDF review.

- [ ] **T031** Add parser diagnostics per PDF, including parser path used, OCR used or not, and major extraction gaps.

- [ ] **T032** Add tests covering clean parse, OCR fallback, normalized parsed-document output, and stored page/crop artifacts.

---

## Phase 3 — PDF-to-row matching and blocked-match handling

**Goal:** each PDF ends in a trustworthy match state before extraction begins.

- [ ] **T033** Implement grounded paper-metadata extraction from parsed documents for title, authors, publication year, and identifiers when available.

- [ ] **T034** Implement deterministic matching scoring using publication metadata signals.

- [ ] **T035** Implement limited fallback adjudication only for plausible ambiguous cases.

- [ ] **T036** Implement final match outcome assignment for:
  - `matched`
  - `ambiguous`
  - `unmatched`
  - duplicate-row conflict

- [ ] **T037** Implement duplicate-row conflict detection that blocks all conflicting PDFs for extraction.

- [ ] **T038** Persist matching artifacts and reasoning summaries so unmatched, ambiguous, and conflict cases are inspectable later.

- [ ] **T039** Expose unmatched, ambiguous, and duplicate-row-conflict records through API endpoints for the UI.

- [ ] **T040** Add tests for deterministic match success, ambiguous-block behavior, unmatched behavior, and duplicate-row-conflict behavior.

---

## Phase 4 — Style profiles and MVP retrieval artifacts

**Goal:** generate safe per-column style guidance and bounded retrieval artifacts without semantic example leakage.

- [ ] **T041** Define the style-profile JSON schema with at least:
  - `field_type_guess`
  - `expected_length`
  - `tone`
  - `detail_level`
  - `value_shape`
  - `unit_style`
  - `format_notes`
  - `example_risk`

- [ ] **T042** Implement the per-column preprocessing LLM step that analyzes existing filled cells and produces one structured style profile per schema column.

- [ ] **T043** Persist style profiles under `style_profiles/` and ensure they guide only output form, not semantic content.

- [ ] **T044** Enforce the no-leakage baseline for style profiles:
  - do not inject raw filled cells as semantic exemplars by default
  - keep the preprocessing output limited to style/format guidance
  - keep any leakage-risk markers visible in artifacts and diagnostics

- [ ] **T045** Create MVP retrieval chunks for at least:
  - paragraphs
  - section blocks
  - captions
  - table regions

- [ ] **T046** Implement contextualized retrieval text while preserving separate source-preserving display text for review.

- [ ] **T047** Implement MVP retrieval assembly defaults:
  - `top_k = 6`
  - include captions and tables when relevant
  - include one neighbor window around selected text chunks
  - do **not** implement reranking, HyDE, or query expansion in the MVP baseline

- [ ] **T048** Persist retrieval artifacts and diagnostics so selected chunks, contextualized text, and source-preserving review text remain inspectable.

- [ ] **T049** Add tests covering style-profile generation, no raw-example leakage into extraction inputs, typed chunk generation, retrieval-text/display-text separation, and retrieval defaults.

---

## Phase 5 — Provider abstraction, extraction request building, proposal generation, evidence persistence, and failure handling

**Goal:** produce one best proposal per eligible target cell with inspectable evidence and stable structured contracts.

- [ ] **T050** Implement the provider abstraction and capability-probe model for structured-output support.

- [ ] **T051** Implement **LM Studio localhost API** integration as the initial MVP provider path.

- [ ] **T052** Implement provider error handling and structured-output failure policy for LM Studio, including:
  - timeout handling
  - model-unavailable handling
  - capability checks for required structured-output behavior
  - malformed JSON and malformed structured-output handling
  - explicit retry or fail-fast rules with no silent corruption
  - request/response logging policy with actionable diagnostics

- [ ] **T053** Implement the extraction request builder for LM Studio structured JSON:
  - assemble per-cell extraction requests from row context, column name, column description, style profile, retrieved passages, and relevant table/caption context
  - keep prompt/request construction separate from orchestration logic
  - support rationale and calculation fields in the response contract

- [ ] **T054** Build the structured JSON schema/request payload for the text model path.

- [ ] **T055** Build the structured JSON schema/request payload for the vision-capable model path.

- [ ] **T056** Implement proposal/evidence serialization using the shared artifact I/O layer so proposals and evidence are stored as separate linked records under stable bundle locations.

- [ ] **T057** Implement the per-target-cell extraction orchestrator that assembles:
  - row context
  - column definition
  - current cell value when relevant
  - style profile
  - retrieved evidence context
  - Verify mode state
  - text-model or vision-model request path as routed

- [ ] **T058** Implement proposal-state handling for at least:
  - `found`
  - `inferred`
  - `unclear`
  - `blocked`
  - `error`
  - `skipped`

- [ ] **T059** Implement text-evidence anchoring and validation for quote + page + highlight when possible.

- [ ] **T060** Implement the single narrow evidence-recovery pass when evidence is weak, missing, or unusable for display.

- [ ] **T061** Keep weak-but-reviewable proposals available when quote + page evidence exists even if precise highlighting fails.

- [ ] **T062** Implement scoped automatic figure fallback trigger logic:
  - trigger only when the field is likely figure/table-derived
  - and text/table retrieval failed or remained insufficient
  - no user-triggered fallback control is part of MVP

- [ ] **T063** Build the figure-fallback input package containing:
  - crop
  - caption
  - nearby text
  - full-page reference

- [ ] **T064** Persist figure-derived evidence records distinctly from text evidence while keeping figure-derived proposals as normal proposals with figure-marked evidence.

- [ ] **T065** Implement reviewer-facing support-label mapping from internal states, including figure-derived evidence labeling and weak-evidence labeling.

- [ ] **T066** Ensure Verify mode uses the same extraction path for already-filled cells and persists reviewable proposals for them.

- [ ] **T067** Add tests covering structured-output parsing, provider failure handling, proposal/evidence serialization, blocked outcomes, unclear outcomes, evidence recovery, quote-plus-page fallback, figure fallback triggers, and Verify mode extraction on filled cells.

---

## Phase 6 — Review-state backend, review-asset serving, warnings/status policy, filtering, and summaries

**Goal:** make proposals reviewable, filterable, auditable, asset-backed, and safe for partial review and export.

- [ ] **T068** Implement normalized warning and status surfaces:
  - define categories for ambiguous match, duplicate-row conflict, weak evidence, quote+page fallback without highlight, figure-derived evidence, no reviewed verified cells, and completed-with-warnings run outcome
  - persist these statuses in run and proposal artifacts
  - expose them consistently through API payloads

- [ ] **T069** Implement proposal-list APIs with filters for at least:
  - row
  - column
  - PDF
  - evidence status
  - figure-derived evidence
  - ambiguous/unmatched match status
  - review decision status

- [ ] **T070** Implement proposal-detail API payloads containing:
  - row context
  - column definition
  - current cell value
  - proposal state
  - support label
  - rationale
  - calculation
  - primary and secondary evidence
  - warning/status flags

- [ ] **T071** Implement review-asset serving endpoints for the review UI, including:
  - safe browser access to original PDFs for the PDF.js viewer
  - page-image serving
  - figure-crop serving
  - evidence metadata lookups needed by the viewer and detail pane

- [ ] **T072** Implement review-decision persistence for:
  - accept as-is
  - accept with edit
  - reject
  - no decision yet

- [ ] **T073** Preserve prior proposal state and review history for auditability when a review decision is recorded.

- [ ] **T074** Implement guarded bulk-accept semantics limited to the currently visible filtered subset of undecided proposals.

- [ ] **T075** Implement progress counters and decision-breakdown aggregation.

- [ ] **T076** Implement run-summary generation and persistence in `summaries/run_summary.json`, including at minimum:
  - PDFs processed
  - matched / unmatched / ambiguous PDFs
  - proposals generated
  - reviewed proposals
  - accepted as-is
  - accepted with edit
  - rejected
  - pending / undecided
  - changed cells exported
  - Verify mode on/off
  - provider/model names
  - local vs cloud status

- [ ] **T077** Implement reviewer-outcome summary generation as a pure function of proposals and review decisions, and persist it in `summaries/reviewer_summary.json`, including at minimum:
  - proposals generated
  - reviewed proposals
  - accepted as-is
  - accepted with edit
  - rejected
  - pending / undecided
  - changed cells exported
  - matched / unmatched / ambiguous PDFs
  - Verify mode on/off
  - provider/model names
  - local vs cloud status

- [ ] **T078** Support summary recomputation from artifact files so both run and reviewer summaries stay derivable and inspectable.

- [ ] **T079** Ensure export candidate selection uses only explicitly accepted proposals and excludes unreviewed proposals by construction.

- [ ] **T080** Add tests covering review decision recording, audit history, visible-subset bulk acceptance, warning/status semantics, review-asset serving, run-summary recomputation, reviewer-summary recomputation, and partial-review behavior.

---

## Phase 7 — Review UI shell, three-pane workspace, ordering rules, and evidence viewer

**Goal:** implement the dedicated queue-first local browser review application required by the MVP.

- [ ] **T081** Build the React frontend shell with Run and Review views.

- [ ] **T082** Implement the concise run summary view showing at least:
  - PDFs processed
  - matched / unmatched / ambiguous PDFs
  - proposals generated
  - reviewed proposals
  - accepted as-is
  - accepted with edit
  - rejected
  - changed cells exported
  - Verify mode on/off
  - provider/model names
  - local vs cloud status

- [ ] **T083** Implement the three-pane review workspace:
  - left pane = proposal queue/list
  - center pane = proposal detail
  - right pane = evidence viewer
  - top bar = counters, filters, and warnings

- [ ] **T084** Implement the proposal queue pane with the full MVP filter set, stable selection behavior, and explicit proposal ordering rules:
  - default pending / undecided proposals before reviewed proposals
  - within the same decision-status bucket, preserve stable spreadsheet row order, then column order, then `proposal_id`
  - do not auto-promote figure-derived or quote+page-fallback proposals unless the user applies filters
  - do not record review decisions implicitly from navigation or selection changes

- [ ] **T085** Implement the proposal detail pane showing row context, target column definition, current value in Verify mode, proposed value, support label, rationale, calculation, warning/status flags, and primary/secondary evidence.

- [ ] **T086** Implement the evidence viewer pane using a raw/custom PDF.js viewer for text evidence and attached reviewable figure evidence.

- [ ] **T087** Implement backend-to-viewer highlight coordinate conversion:
  - map canonical PDF/page coordinates from backend evidence records into PDF.js viewer overlay coordinates
  - render stable text highlight overlays
  - handle zoom and viewport changes correctly

- [ ] **T088** Implement graceful quote + page fallback display when highlight coordinates are missing or invalid.

- [ ] **T089** Implement the figure-evidence viewer with crop-first display, attached caption, figure-derived warning/status markers, and full-page access.

- [ ] **T090** Implement the review action area with:
  - accept
  - accept with edit
  - reject
  - next
  - previous
  - bulk accept visible subset

- [ ] **T091** Implement keyboard shortcuts for next/previous navigation, accept current proposal, reject current proposal, focus edit control, and focus/open evidence viewer.

- [ ] **T092** Implement unmatched, ambiguous, and duplicate-row-conflict inspection views in the UI.

- [ ] **T093** Surface warnings/statuses, run-summary fields, reviewer-summary fields, provider/model names, and local-vs-cloud status consistently across the review UI and run-summary UI.

- [ ] **T094** Add frontend tests for queue filtering, ordering rules, nonlinear review, quote+page fallback rendering, figure-evidence rendering, run-summary display, and bulk-accept confirmation flow.

- [ ] **T095** Add Playwright e2e tests for the core review loop from proposal selection through decision recording and summary updates.

---

## Phase 8 — Export, audit log, unsupported-feature warnings, diagnostics, and final downloads

**Goal:** safely export only explicitly accepted changes, stay honest about the workbook fidelity boundary, and make the finished run inspectable.

- [ ] **T096** Implement content-only XLSX export with changed-cell highlighting:
  - preserve cell contents only
  - apply only explicitly accepted changes
  - highlight changed cells
  - do **not** attempt to preserve formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, charts, shapes, or macros

- [ ] **T097** Implement best-effort detection and reporting of unsupported workbook features during export:
  - inspect the source workbook for unsupported advanced features when feasible
  - record warnings in diagnostics and logs
  - keep export behavior aligned with the content-only fidelity boundary
  - warn and ignore rather than trying to preserve unsupported features in MVP

- [ ] **T098** Implement audit-log generation with at least:
  - row identifier
  - column identifier
  - old value
  - new value
  - proposal source
  - reviewer decision
  - decision timestamp

- [ ] **T099** Implement diagnostics JSON for:
  - matching failures
  - blocked outcomes
  - unclear / skipped / error outcomes
  - weak evidence and evidence recovery
  - unsupported workbook feature warnings
  - completed-with-warnings runs

- [ ] **T100** Implement final download endpoints for:
  - updated workbook
  - audit log
  - `summaries/run_summary.json`
  - `summaries/reviewer_summary.json`
  - final downloadable run artifacts and relevant JSON outputs

- [ ] **T101** Add tests covering export integrity, content-only fidelity, changed-cell highlighting, accepted-only export behavior, unsupported-feature warnings, audit-log completeness, and completed-with-warnings semantics.

---

## Phase 9 — Orchestration, hardening, regression protection, and README updates

**Goal:** prove the full MVP workflow works end to end and stays inside the intended architecture boundary.

- [ ] **T102** Implement the app-owned staged runner that executes the canonical pipeline stages synchronously in FastAPI.

- [ ] **T103** Ensure interrupted or failed runs leave inspectable partial artifacts and that a new run creates a new run directory rather than resuming in place by default.

- [ ] **T104** Add hermetic end-to-end tests using stub providers over the fixture corpus for:
  - successful matched extraction
  - unmatched / ambiguous / duplicate-row blocked flows
  - weak-evidence quote+page review
  - Verify mode reviewed-cell flow
  - figure fallback flow
  - export with accepted-only changes

- [ ] **T105** Add one realistic non-hermetic smoke test path for local LM Studio execution behind an opt-in flag.

- [ ] **T106** Add a performance smoke test for representative small and medium batches so obvious regressions in parsing, retrieval, extraction, and review loading are caught.

- [ ] **T107** Update `README` with MVP run instructions:
  - how to prepare config
  - how to start the FastAPI backend and React UI
  - how to run a sample workflow
  - where artifacts and exports are written
  - how Verify mode behaves
  - what the export fidelity boundary is

---

## Explicit MVP exclusions for this task list

Do **not** add the following unless `spec.md` and `plan.md` are intentionally revised first:

- Tauri or Electron shell as a baseline requirement
- database-first persistence
- background jobs as baseline runtime behavior
- multi-user review or collaboration workflows
- chat-first or agent-shell UX
- reranking, HyDE, or query expansion as baseline retrieval
- GROBID as a required parser dependency
- in-place workbook patching
- workbook fidelity guarantees beyond content-only export plus changed-cell highlighting
- raw semantic example injection from filled cells as the default extraction strategy
- user-triggered figure fallback controls
- automated heterogeneous correctness scoring as the primary MVP evaluation metric

---

## Definition of done for this task list

This task list is complete enough when it can drive implementation toward a system that:

- runs the end-to-end paper-to-table workflow locally in a browser app
- uses React + FastAPI + Docling + `pypdfium2` + raw/custom PDF.js + LM Studio + filesystem artifact bundles
- keeps human review mandatory before spreadsheet mutation
- persists proposals, evidence, review decisions, run summaries, reviewer summaries, diagnostics, and exports as inspectable artifact files
- supports Verify mode end to end
- generates reviewer-outcome summaries for the MVP
- exports a new XLSX plus audit log within the explicit content-only fidelity boundary
- applies scoped automatic figure fallback without adding a user-triggered fallback workflow
- stays inside the MVP architecture boundary defined by `spec.md`, `research.md`, and `plan.md`
