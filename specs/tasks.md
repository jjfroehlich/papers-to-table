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
`tasks.md` defines the exhaustive implementation inventory and the canonical execution batches for future coding-agent work.

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
- A task is not truly done when a code path exists; it is done when the user-facing behavior, verification, and docs for that slice are strong enough to support the next batch.
- For UI-affecting tasks, browser verification or equivalent end-to-end coverage is part of done.

## Assumed repo shape

Use or map tasks onto a local-first repo shape such as:

- `backend/` — FastAPI app, staged runner, parsing/matching/retrieval/extraction/export logic
- `frontend/` — React review UI
- `tests/` — unit, integration, contract, and e2e tests
- `tests/fixtures/` — deterministic spreadsheet/PDF fixture corpus
- `docs/` — optional internal notes if needed

If the repo already uses different names, preserve the existing structure and map the tasks accordingly.

## How to use this file

This file is intentionally exhaustive. Do **not** shrink it into a sprint checklist and do **not** treat a broad one-pass implementation as the default just because every task is listed here.

Future coding-agent implementation should normally proceed by the canonical batches below.

### Batch execution rules

- Implement one batch at a time unless the user explicitly asks for a different scope.
- Finish the current batch deeply enough that a normal operator can use that slice without guesswork.
- Do not satisfy a user-facing batch with backend support alone; verify the actual browser or operator-visible behavior for that slice.
- When a batch changes workflow truth, update `README.md`, `spec.md`, `plan.md`, and this file in the same pass.
- End each operator-facing batch by generating or updating the user-facing `README.md` and any other operator docs needed for that slice so they truthfully match the implemented behavior before the next batch begins.
- Do not mark tasks complete merely because code exists already. Re-check current behavior against the spec and batch completion standard.

## Canonical implementation batches

### Batch 1 — Foundation and operator-start baseline

**Purpose:** establish contracts, artifact persistence, config resolution, deterministic test harnesses, and a real browser-first run-start path with explicit pre-review and lifecycle guidance.

**Primary tasks:** `T001–T024`, `T081`, `T082a`, `T102`, `T103`

**Why this batch exists:** future work goes shallow if the project starts from a backend-heavy skeleton with weak onboarding or vague run-state handling.

**Batch 1 is complete when:**

- a new local operator can install dependencies, start backend/frontend, open the browser UI, enter a config path, create a run, and understand `ready` / `validating` / `running` / terminal states
- config validation, config snapshotting, input summaries, run ids, and artifact layout are stable and inspectable
- the UI explains what to do before review exists instead of dropping the user into an empty shell
- automated tests cover config validation, lifecycle transitions, and basic run creation behavior

### Batch 2 — Parsing and row-matching baseline

**Purpose:** parse papers once into a stable contract, support OCR fallback, and produce trustworthy matched/unmatched/ambiguous/duplicate-row outcomes before extraction begins.

**Primary tasks:** `T025–T040`

**Why this batch exists:** mediocre implementations often rush into extraction before parser outputs, diagnostics, and blocked-match behavior are stable.

**Batch 2 is complete when:**

- PDFs are normalized into a stable parsed-document contract with stored parser diagnostics and page/crop artifacts
- OCR fallback is narrow, explicit, and stored in artifacts
- each PDF ends in a clear match outcome before extraction
- ambiguous, unmatched, and duplicate-row-conflict cases are blocked and inspectable rather than silently leaking into extraction

### Batch 3 — Retrieval, style profiles, extraction, and evidence

**Purpose:** produce one best proposal per eligible target cell with grounded evidence, stable structured contracts, scoped recovery, and scoped figure fallback.

**Primary tasks:** `T041–T067`

**Why this batch exists:** proposal quality depends on retrieval discipline, style guidance, structured outputs, and strict evidence handling rather than on raw model access alone.

**Batch 3 is complete when:**

- retrieval artifacts, style profiles, prompts, proposal records, and evidence records are all inspectable in run artifacts
- one best proposal per target cell is generated with explicit `found` / `inferred` / `unclear` / `blocked` / `error` / `skipped` handling
- quote-plus-page fallback remains reviewable when highlight anchoring fails
- figure fallback stays scoped, clearly labeled, and review-first rather than becoming a generic second extraction path

### Batch 4 — Review backend, summaries, and export gating

**Purpose:** make proposals reviewable and filterable through stable APIs, preserve review decisions and auditability, and compute truthful run/reviewer summaries before the full browser workspace is polished.

**Primary tasks:** `T068–T080`

**Why this batch exists:** shallow implementations often build the visible review UI before the decision model, summary model, and warning semantics are trustworthy.

**Batch 4 is complete when:**

- proposal-list/detail/filter APIs support the full MVP review surface
- review decisions are explicit persisted records, not implicit UI state
- progress counters, warning/status categories, run summaries, and reviewer summaries are recomputable from artifacts
- export candidate selection is safely limited to explicitly accepted proposals

### Batch 5 — Browser review workspace and operator usability

**Purpose:** deliver the actual queue-first review product surface with strong pre-review states, clear status/warning cues, safe review actions, and truthful artifact/download access.

**Primary tasks:** `T082`, `T083–T095`, `T100`

**Why this batch exists:** future agents can technically satisfy many UI requirements while still shipping a review workspace that feels fragmented, stale, or unsafe.

**Batch 5 is complete when:**

- the browser app presents a coherent run-summary plus queue/detail/evidence workspace
- proposal ordering, filtering, selection, and run switching behave predictably without stale state leakage
- text highlights, quote-plus-page fallback, figure evidence, bulk acceptance, edited acceptance, keyboard navigation, and unresolved-match inspection are all actually usable
- download surfaces are truthful about what is ready versus not yet written
- end of Batch 5: generate or update `README.md` so it truthfully matches the implemented app’s startup path, config workflow, run lifecycle, review workflow, current download/export behavior, and known MVP limitations at that stage
- frontend tests and Playwright coverage verify real user-facing behavior, not just component presence

### Batch 6 — Export, hardening, regression protection, and docs truth

**Purpose:** finish the product with safe accepted-only export, unsupported-feature warnings, hermetic regression coverage, opt-in live smoke coverage, performance checks, and fully truthful onboarding docs.

**Primary tasks:** `T096–T101`, `T104–T107b`

**Why this batch exists:** the app is not finished when review works if export integrity, warnings, diagnostics, and onboarding still mislead users.

**Batch 6 is complete when:**

- accepted-only export, changed-cell highlighting, audit logs, and completed-with-warnings behavior are verified end to end
- unsupported workbook feature warnings and diagnostics remain explicit rather than implied
- hermetic end-to-end coverage protects the core workflow, with separate opt-in live-provider smoke coverage and performance smoke tests
- `README.md` reflects the real primary happy path, artifact locations, config authority, UI-driven launch/status/review/export workflow, and export fidelity boundary
- the final user-facing docs set is audited against the implemented MVP so README and related docs do not mention speculative helpers, stale commands, obsolete architecture, or workflows that do not exist

The detailed task inventory below remains the source of truth for exact implementation work inside each batch.

---

## Phase 0 — Foundation, contracts, config, identifiers, and deterministic test harness

**Goal:** establish stable schemas, stable identifiers, filesystem persistence, config behavior, and test scaffolding for the full MVP.

- [x] **T001** Create the base project skeleton for `backend/`, `frontend/`, and `tests/`, plus a short root-level development note that describes the local-first architecture and canonical pipeline stages.

- [x] **T002** Define the shared domain enums and common JSON/Pydantic/TypeScript schemas for at least:
  - run status
  - match outcome
  - proposal state
  - support label
  - evidence source type
  - review decision
  - warning/status category
  - provider locality (`local` vs `cloud`)

- [x] **T003** Define and implement stable identifier generation for runs, PDFs, rows, cells, proposals, evidence items, and review decisions, including at minimum:
  - deterministic `cell_id`
  - stable `pdf_id` assignment within a run
  - proposal and evidence ids that are unique and traceable, including cases where multiple PDFs target the same row/cell within one run
  - stable review-decision ids linked back to proposal and cell context

- [x] **T004** Implement the stable run artifact bundle layout with at least:
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

- [x] **T005** Implement the artifact I/O helper layer:
  - shared helpers for writing and reading JSON snapshot files
  - shared helpers for appending and reading JSONL files
  - stable artifact-path generation inside a run bundle
  - lookup helpers for proposals, evidence, and review decisions by id
  - run-summary and reviewer-summary recomputation from artifact files
  - write behavior that is atomic enough for local single-user reliability

- [x] **T006** Define the proposal JSON schema and contract for one proposal object per target cell per run, including at least:
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

- [x] **T007** Define the evidence JSON schema and contract for separate evidence records linked to proposals, including at least:
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

- [x] **T008** Define the review-decision JSON schema plus the run-summary and reviewer-summary JSON schemas.
  - review decisions must remain persistable as explicit records, not only as in-place proposal mutations

- [x] **T009** Define the single JSON config schema covering:
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

- [x] **T010** Implement config default resolution into one effective runtime config before any run work starts.

- [x] **T011** Create `config.example.json` as a minimal but complete example config file for the full MVP.

- [x] **T012** Implement config/path validation and required metadata/schema validation:
  - validate that configured paths exist and are readable
  - validate that schema columns include at least `column_name` and `description`
  - validate that the source table contains `Title`, `Authors`, and `Publication Year`
  - fail early with actionable diagnostics when validation fails

- [x] **T013** Implement config snapshotting into run artifacts:
  - validate config at run start
  - persist the resolved effective config as `config.snapshot.json`
  - ensure the run can later be explained from the snapshot

- [x] **T014** Build a deterministic fixture corpus in `tests/fixtures/` containing at minimum:
  - one clean born-digital paper that should match and extract successfully
  - one scanned or text-inaccessible paper for OCR fallback
  - one unmatched paper
  - one ambiguous-match paper
  - one duplicate-row-conflict case
  - one figure-heavy paper
  - one workbook fixture with unsupported Excel features present for export warnings
  - one CSV fixture
  - one schema fixture

- [x] **T015** Set up backend unit/integration/contract test tooling, including provider stubs/fakes and fixture helpers.

- [x] **T016** Set up frontend test tooling and Playwright e2e scaffolding for the review workflow.
- [x] **T016a** Harden the Playwright harness so fixture preparation is separate from server startup and browser/server processes start without shell-dependent heredocs or command chaining.
  - distinguish missing browser/runtime dependencies from application failures when practical
  - retain screenshots, traces, or similarly useful browser-failure artifacts when practical

---

## Phase 1 — Run creation, input loading, normalization, and lifecycle

**Goal:** the system can start a run, validate and snapshot inputs, and compute which cells are eligible for extraction or verification.

- [x] **T017** Implement spreadsheet loading for CSV and XLSX inputs.

- [x] **T018** Implement schema loading from workbook or separate schema file.

- [x] **T019** Implement table normalization and required metadata-column validation for `Title`, `Authors`, and `Publication Year`.

- [x] **T020** Implement cell eligibility classification for at least:
  - empty / missing
  - already-filled
  - trivial placeholder treated as empty when configured
  - skipped / ineligible

- [x] **T021** Implement Verify mode semantics so already-filled cells become eligible targets when Verify mode is enabled.

- [x] **T022** Implement run lifecycle state transitions for at least:
  - `created`
  - `validating`
  - `running`
  - `completed`
  - `completed_with_warnings`
  - `failed`
  - `interrupted`
  - treat `created` and `interrupted` as internal or artifact-level states when useful, but map UI state to the normative operator-visible lifecycle defined in `spec.md`

- [x] **T023** Implement run creation and inspection API endpoints for:
  - create run
  - list runs
  - get run summary
  - fetch config snapshot
  - fetch input summary

- [x] **T023a** Keep run creation UI-driven in practice by returning a created run immediately, then executing the staged runner under app-owned backend control with a lightweight in-process background mechanism while exposing validating/running/terminal state transitions, actionable failure messaging, and diagnostics/config access.

- [x] **T024** Add tests covering valid input readiness, metadata-column rejection, missing-path rejection, placeholder handling, and Verify mode behavior.

---

## Phase 2 — Parsing baseline, PDF backend, OCR fallback, and normalized parsed-document artifacts

**Goal:** parse PDFs once, normalize them into one internal contract, and generate the low-level artifacts needed later for evidence review.

- [x] **T025** Define the internal `ParsedDocument` schema/contract with fields for:
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

- [x] **T026** Implement the parser adapter interface and register **Docling** as the main parser.

- [x] **T027** Implement the low-level PDF abstraction using **`pypdfium2` / PDFium** for rendering, geometry, crop extraction, and page/image access.

- [x] **T028** Integrate OCR fallback for scanned or text-inaccessible PDFs:
  - default OCR fallback tool = **OCRmyPDF**
  - use OCR fallback only when text extraction is empty or clearly insufficient
  - normalize OCR output into the same `ParsedDocument` contract as born-digital PDFs
  - store OCR-affected artifacts in the run bundle

- [x] **T029** Implement parse-stage persistence so parser-native outputs and normalized parsed-document artifacts are both stored under stable run paths.

- [x] **T030** Generate page-render artifacts and crop helpers needed later for text evidence, figure evidence, and PDF review.

- [x] **T031** Add parser diagnostics per PDF, including parser path used, OCR used or not, and major extraction gaps.

- [x] **T032** Add tests covering clean parse, OCR fallback, normalized parsed-document output, and stored page/crop artifacts.

---

## Phase 3 — PDF-to-row matching and blocked-match handling

**Goal:** each PDF ends in a trustworthy match state before extraction begins.

- [x] **T033** Implement grounded paper-metadata extraction from parsed documents for title, authors, publication year, and identifiers when available.

- [x] **T034** Implement deterministic matching scoring using publication metadata signals.

- [x] **T035** Implement limited fallback adjudication only for plausible ambiguous cases.

- [x] **T036** Implement final match outcome assignment for:
  - `matched`
  - `ambiguous`
  - `unmatched`
  - duplicate-row conflict

- [x] **T037** Implement duplicate-row conflict detection that blocks all conflicting PDFs for extraction.

- [x] **T038** Persist matching artifacts and reasoning summaries so unmatched, ambiguous, and conflict cases are inspectable later.

- [x] **T039** Expose unmatched, ambiguous, and duplicate-row-conflict records through API endpoints for the UI.

- [x] **T040** Add tests for deterministic match success, ambiguous-block behavior, unmatched behavior, and duplicate-row-conflict behavior.

---

## Phase 4 — Style profiles and MVP retrieval artifacts

**Goal:** generate safe per-column style guidance and bounded retrieval artifacts without semantic example leakage.

- [x] **T041** Define the style-profile JSON schema with at least:
  - `field_type_guess`
  - `expected_length`
  - `tone`
  - `detail_level`
  - `value_shape`
  - `unit_style`
  - `format_notes`
  - `example_risk`

- [x] **T042** Implement the per-column preprocessing LLM step that analyzes existing filled cells and produces one structured style profile per schema column.

- [x] **T043** Persist style profiles under `style_profiles/` and ensure they guide only output form, not semantic content.

- [x] **T044** Enforce the no-leakage baseline for style profiles:
  - do not inject raw filled cells as semantic exemplars by default
  - keep the preprocessing output limited to style/format guidance
  - keep any leakage-risk markers visible in artifacts and diagnostics

- [x] **T045** Create MVP retrieval chunks for at least:
  - paragraphs
  - section blocks
  - captions
  - table regions

- [x] **T046** Implement contextualized retrieval text while preserving separate source-preserving display text for review.

- [x] **T047** Implement MVP retrieval assembly defaults:
  - `top_k = 6`
  - include captions and tables when relevant
  - include one neighbor window around selected text chunks
  - do **not** implement reranking, HyDE, or query expansion in the MVP baseline

- [x] **T048** Persist retrieval artifacts and diagnostics so selected chunks, contextualized text, and source-preserving review text remain inspectable.

- [x] **T049** Add tests covering style-profile generation, no raw-example leakage into extraction inputs, typed chunk generation, retrieval-text/display-text separation, and retrieval defaults.

---

## Phase 5 — Provider abstraction, extraction request building, proposal generation, evidence persistence, and failure handling

**Goal:** produce one best proposal per eligible target cell with inspectable evidence and stable structured contracts.

- [x] **T050** Implement the provider abstraction and capability-probe model for structured-output support.

- [x] **T051** Implement **LM Studio localhost API** integration as the initial MVP provider path.

- [x] **T052** Implement provider error handling and structured-output failure policy for LM Studio, including:
  - timeout handling
  - model-unavailable handling
  - capability checks for required structured-output behavior
  - malformed JSON and malformed structured-output handling
  - explicit retry or fail-fast rules with no silent corruption
  - request/response logging policy with actionable diagnostics

- [x] **T053** Implement the extraction request builder for LM Studio structured JSON:
  - assemble per-cell extraction requests from row context, column name, column description, style profile, retrieved passages, and relevant table/caption context
  - keep prompt/request construction separate from orchestration logic
  - support rationale and calculation fields in the response contract

- [x] **T054** Build the structured JSON schema/request payload for the text model path.

- [x] **T055** Build the structured JSON schema/request payload for the vision-capable model path.

- [x] **T056** Implement proposal/evidence serialization using the shared artifact I/O layer so proposals and evidence are stored as separate linked records under stable bundle locations.

- [x] **T057** Implement the per-target-cell extraction orchestrator that assembles:
  - row context
  - column definition
  - current cell value when relevant
  - style profile
  - retrieved evidence context
  - Verify mode state
  - text-model or vision-model request path as routed

- [x] **T058** Implement proposal-state handling for at least:
  - `found`
  - `inferred`
  - `unclear`
  - `blocked`
  - `error`
  - `skipped`

- [x] **T059** Implement text-evidence anchoring and validation for quote + page + highlight when possible.

- [x] **T060** Implement the single narrow evidence-recovery pass when evidence is weak, missing, or unusable for display.

- [x] **T061** Keep weak-but-reviewable proposals available when quote + page evidence exists even if precise highlighting fails.

- [x] **T062** Implement scoped automatic figure fallback trigger logic:
  - trigger only when the field is likely figure/table-derived
  - and text/table retrieval failed or remained insufficient
  - no user-triggered fallback control is part of MVP

- [x] **T063** Build the figure-fallback input package containing:
  - crop
  - caption
  - nearby text
  - full-page reference

- [x] **T064** Persist figure-derived evidence records distinctly from text evidence while keeping figure-derived proposals as normal proposals with figure-marked evidence.

- [x] **T065** Implement reviewer-facing support-label mapping from internal states, including figure-derived evidence labeling and weak-evidence labeling.

- [x] **T066** Ensure Verify mode uses the same extraction path for already-filled cells and persists reviewable proposals for them.

- [x] **T067** Add tests covering structured-output parsing, provider failure handling, proposal/evidence serialization, blocked outcomes, unclear outcomes, evidence recovery, quote-plus-page fallback, figure fallback triggers, and Verify mode extraction on filled cells.

---

## Phase 6 — Review-state backend, review-asset serving, warnings/status policy, filtering, and summaries

**Goal:** make proposals reviewable, filterable, auditable, asset-backed, and safe for partial review and export.

- [x] **T068** Implement normalized warning and status surfaces:
  - define categories for ambiguous match, duplicate-row conflict, weak evidence, quote+page fallback without highlight, figure-derived evidence, no reviewed verified cells, and completed-with-warnings run outcome
  - persist these statuses in run and proposal artifacts
  - expose them consistently through API payloads

- [x] **T069** Implement proposal-list APIs with filters for at least:
  - row
  - column
  - PDF
  - evidence status
  - figure-derived evidence
  - ambiguous/unmatched match status
  - review decision status

- [x] **T070** Implement proposal-detail API payloads containing:
  - row context
  - column definition
  - current cell value
  - proposal state
  - support label
  - rationale
  - calculation
  - primary and secondary evidence
  - warning/status flags

- [x] **T071** Implement review-asset serving endpoints for the review UI, including:
  - safe browser access to original PDFs for the PDF.js viewer
  - page-image serving
  - figure-crop serving
  - evidence metadata lookups needed by the viewer and detail pane

- [x] **T072** Implement review-decision persistence for:
  - accept as-is
  - accept with edit
  - reject
  - no decision yet
  - persist explicit review-decision records that can later drive audit logs and summary recomputation

- [x] **T073** Preserve prior proposal state and review history for auditability when a review decision is recorded.

- [x] **T074** Implement guarded bulk-accept semantics limited to the currently visible filtered subset of undecided proposals.

- [x] **T075** Implement progress counters and decision-breakdown aggregation.

- [x] **T076** Implement run-summary generation and persistence in `summaries/run_summary.json`, including at minimum:
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

- [x] **T077** Implement reviewer-outcome summary generation as a pure function of proposals and review decisions, and persist it in `summaries/reviewer_summary.json`, including at minimum:
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

- [x] **T078** Support summary recomputation from artifact files so both run and reviewer summaries stay derivable and inspectable.

- [x] **T079** Ensure export candidate selection uses only explicitly accepted proposals and excludes unreviewed proposals by construction.

- [x] **T080** Add tests covering review decision recording, audit history, visible-subset bulk acceptance, warning/status semantics, review-asset serving, run-summary recomputation, reviewer-summary recomputation, and partial-review behavior.

---

## Phase 7 — Review UI shell, three-pane workspace, ordering rules, and evidence viewer

**Goal:** implement the dedicated queue-first local browser review application required by the MVP.

- [x] **T081** Build the React frontend shell with Run and Review views.

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
  - direct links or equivalent access to workbook, audit-log, run-summary, and reviewer-summary downloads

- [x] **T082a** Implement a run-launch and setup context surface in the UI that:
  - starts a run from a config-file path without exposing a broad advanced-settings editor
  - shows the config path and concise resolved input summary
  - keeps empty/loading/warning/failure states explicit before the review queue is ready
  - makes the next operator action obvious when no run exists yet or when the selected run is not reviewable

- [ ] **T083** Implement the three-pane review workspace:
  - left pane = proposal queue/list
  - center pane = proposal detail
  - right pane = evidence viewer
  - visible run/reviewer summary context in the main workspace
  - top bar or equivalent queue controls = counters, filters, and warnings

- [ ] **T084** Implement the proposal queue pane with the full MVP filter set, stable selection behavior, and explicit proposal ordering rules:
  - default pending / undecided proposals before reviewed proposals
  - within undecided proposals, actionable proposals before blocked or unresolved items
  - within the same decision-status bucket, preserve stable spreadsheet row order, then column order, then `proposal_id`
  - do not auto-promote figure-derived or quote+page-fallback proposals unless the user applies filters
  - keep blocked, ambiguous, unmatched, and duplicate-row-conflict items visible without letting them dominate the main actionable queue by default
  - do not record review decisions implicitly from navigation or selection changes
  - allow filter continuity across run switches when practical, but do not preserve stale proposal/detail/evidence state across runs

- [ ] **T085** Implement the proposal detail pane showing row context, target column definition, current value in Verify mode, proposed value, support label, rationale, calculation, warning/status flags, and primary/secondary evidence.
  - status, evidence source, and warning state should be distinguishable at a glance

- [ ] **T086** Implement the evidence viewer pane using a raw/custom PDF.js viewer for text evidence and attached reviewable figure evidence.

- [ ] **T087** Implement backend-to-viewer highlight coordinate conversion:
  - map canonical PDF/page coordinates from backend evidence records into PDF.js viewer overlay coordinates
  - render stable text highlight overlays
  - handle zoom and viewport changes correctly
  - do not emit fabricated placeholder highlight boxes when reliable anchor geometry is unavailable

- [ ] **T088** Implement graceful quote + page fallback display when highlight coordinates are missing or invalid.

- [ ] **T089** Implement the figure-evidence viewer with crop-first display, attached caption, figure-derived warning/status markers, and full-page access.

- [ ] **T090** Implement the review action area with:
  - accept
  - accept with edit
  - reject
  - next
  - previous
  - bulk accept visible subset
  - disable accept actions for blocked items or items without a reviewable proposal value

- [ ] **T090a** Make bulk acceptance and edited acceptance behavior explicit and reviewer-safe:
  - confirm bulk acceptance against the currently visible filtered subset
  - present accept-with-edit as a distinct save-edited-value action rather than a vague duplicate of plain acceptance

- [ ] **T091** Implement keyboard shortcuts for next/previous navigation, accept current proposal, reject current proposal, focus edit control, and focus/open evidence viewer.

- [ ] **T092** Implement unmatched, ambiguous, and duplicate-row-conflict inspection views in the UI.
  - identify the affected PDF, unresolved outcome, and rationale directly in the review workspace without requiring raw artifact inspection
  - keep this surface inspect-only for MVP rather than adding direct rematch or reassignment actions

- [ ] **T093** Surface warnings/statuses, run-summary fields, reviewer-summary fields, provider/model names, and local-vs-cloud status consistently across the review UI and run-summary UI.
  - show coarse running progress as current stage plus current item when available
  - if zero verified cells have been reviewed, keep per-column lines visible only as evidence-coverage context with explicit wording that reviewer outcomes are not yet meaningful

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
  - derive decision timestamps from persisted review-decision records when available instead of placeholder strings

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
  - keep the UI truthful about which downloads are actually ready versus not yet written

- [ ] **T101** Add tests covering export integrity, content-only fidelity, changed-cell highlighting, accepted-only export behavior, unsupported-feature warnings, audit-log completeness, and completed-with-warnings semantics.

---

## Phase 9 — Orchestration, hardening, regression protection, and README updates

**Goal:** prove the full MVP workflow works end to end and stays inside the intended architecture boundary.

- [x] **T102** Implement the app-owned staged runner that executes the canonical pipeline stages under backend control while the API remains responsive enough for UI-driven launch, polling, diagnostics, and review-state loading.

- [x] **T103** Ensure interrupted or failed runs leave inspectable partial artifacts and that a new run creates a new run directory rather than resuming in place by default.

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
  - make every documented command and workflow match the implementation that currently ships
- [ ] **T107a** Preserve user-facing onboarding in `README`, including clone/install steps, config-file purpose, LM Studio expectations, backend/frontend run commands, testing commands, artifact locations, and the export fidelity boundary.
  - do not remove useful onboarding content unless it is obsolete and replaced with something clearer in the same work pass
  - do not keep obsolete onboarding text, superseded commands, or alternate startup paths that are not real supported workflows

- [ ] **T107b** Keep README aligned with the real primary happy path:
  - start backend and frontend
  - launch a run from the browser using a config path
  - observe run lifecycle state in the UI
  - review/export from the same surface
  - document the real config workflow, run lifecycle, review flow, export behavior, and limitations of the implemented MVP
  - do not document speculative helpers or workflows that do not exist

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
- makes the startup and pre-review workflow understandable without requiring the operator to infer the happy path from source code or test fixtures
- uses React + FastAPI + Docling + `pypdfium2` + raw/custom PDF.js + LM Studio + filesystem artifact bundles
- keeps human review mandatory before spreadsheet mutation
- persists proposals, evidence, review decisions, run summaries, reviewer summaries, diagnostics, and exports as inspectable artifact files
- supports Verify mode end to end
- generates reviewer-outcome summaries for the MVP
- exports a new XLSX plus audit log within the explicit content-only fidelity boundary
- applies scoped automatic figure fallback without adding a user-triggered fallback workflow
- keeps loading, empty, warning, failure, and not-yet-reviewable states explicit and actionable in the operator workflow
- ships with a truthful user-facing `README.md` and related operator docs that match the implemented commands, architecture, workflow, exports, and limitations
- stays inside the MVP architecture boundary defined by `spec.md`, `research.md`, and `plan.md`
