# Paper Table Agent — `tasks.md`

## Status

Implementation checklist for the full intended MVP.

## Purpose

This document turns `spec.md`, `research.md`, and `plan.md` into a concrete implementation task list for coding agents.

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
- raw/custom **PDF.js** viewer with synchronized quote-list and viewer navigation
- **LM Studio localhost API** as the initial provider path
- **separate text-model and vision-model configuration** in the provider config
- **filesystem artifact bundles + JSON files only**
- **no database in MVP**
- **no background job framework by default in MVP**
- **content-only XLSX export**
- **reviewer-outcome summaries** in MVP
- **per-column preprocessing LLM** for style profiles
- **no raw semantic example injection by default**
- **proactive figure review across all relevant extracted figures when a vision model is configured**
- figure evidence allowed for any field type; not restricted to figure-classified fields
- **no unrestricted full-page vision on every page by default**
- **no user-triggered figure fallback**
- **evidence ranking**: primary evidence selected by authority and relevance, not by model output order
- **evidence type taxonomy**: direct quote, inferred reasoning, calculation, approximate highlight fallback, quote-plus-page fallback, figure-based; each labeled and rendered distinctly
- **exact quote highlighting from page-text alignment** with honest labeled fallback to approximate highlight or quote-plus-page

If implementation pressure suggests changing any of these constraints, update `spec.md` and `plan.md` first, then update this file in the same work pass.

## Working assumptions

- Tasks are listed in required dependency order unless a task explicitly says it is safe to parallelize.
- Later tasks may assume earlier tasks are complete.
- Keep contracts stable before adding orchestration complexity.
- Keep persistence logic centralized in the artifact subsystem rather than scattering ad hoc JSON reads and writes across the codebase.
- Keep prompt/request construction separate from orchestration logic.
- Resolve config defaults into one effective runtime config before snapshotting.
- Keep unsupported or out-of-scope features explicitly blocked so coding agents do not silently broaden the MVP.
- A task is not truly done when a code path exists; it is done when the user-facing behavior, verification, and docs for that slice are strong enough to support the next batch.
- For UI-affecting tasks, browser verification or equivalent end-to-end coverage is part of done.
- Provider-path scaffolding is not a completed slice by itself. The canonical LM Studio path must either work on the canonical fixture set or fail early with a clear readiness error.
- Keep canonical provider naming, config shape, README/docs wording, tests, and UI labels in parity. Unknown provider identifiers must be rejected explicitly.
- Treat `README.md`, the checked-in config example, the runtime config schema, and operator-visible UI copy as one operator-facing contract. Keep provider, parser, model, Verify-mode, and run-state terminology aligned across those surfaces.
- Do not allow a clean shell to hide disabled, stubbed, degraded, or unreachable proposal generation.
- Treat the reviewer as reviewing the paper, not the model. Review-state semantics, no-data handling, and evidence interaction should reflect that throughout implementation.
- Evidence quality and reviewer trust are first-class implementation requirements. A proposal with an evidence record does not satisfy evidence requirements unless the evidence is ranked, typed, and labeled correctly. The first model-returned quote is not automatically primary.
- Evidence ranking must be authoritatively ordered. Implementation that treats supporting evidence items as unordered or treats all items as equivalent does not satisfy the evidence contract.

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

**Primary tasks:** `T001–T024a`, `T081`, `T082a`, `T102`, `T103`

**Why this batch exists:** future work goes shallow if the project starts from a backend-heavy skeleton with weak onboarding or vague run-state handling.

**Batch 1 is complete when:**

- a new local operator can install dependencies, start backend/frontend, open the browser UI, enter a config path, create a run, and understand `ready` / `validating` / `running` / terminal states
- config validation, config snapshotting, input summaries, run ids, and artifact layout are stable and inspectable
- provider token validation and run-start readiness checks catch broken setup, invalid provider config, missing dependencies, unreachable providers, and unavailable models before the operator waits through a misleading run
- readiness-failed and early-failed runs still expose resolved config/input context in artifacts and the UI
- the run/setup surface is picker-driven for normal use, resolves path differences clearly, and stays compact rather than path-heavy
- the UI explains what to do before review exists instead of dropping the user into an empty shell
- automated tests cover config validation, provider/readiness failures, lifecycle transitions, and basic run creation behavior

### Batch 2 — Parsing and row-matching baseline

**Purpose:** parse papers once into a stable contract, support OCR fallback, and produce trustworthy matched/unmatched/ambiguous/duplicate-row outcomes before extraction begins.

**Primary tasks:** `T025–T040`

**Why this batch exists:** mediocre implementations often rush into extraction before parser outputs, diagnostics, and blocked-match behavior are stable.

**Batch 2 is complete when:**

- PDFs are normalized into a stable parsed-document contract with stored parser diagnostics and page/crop artifacts
- OCR fallback is narrow, explicit, and stored in artifacts
- configured parser choice, actual parser used, and any explicit fallback path are inspectable rather than silently substituted
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
- structured-output compatibility is negotiated truthfully, malformed structured responses get bounded recovery before hard failure, long-text fields do not systematically fail from short-answer assumptions, and unsupported guessing resolves to `unclear`
- figure fallback stays scoped, clearly labeled, and review-first rather than becoming a generic second extraction path
- the canonical LM Studio path is proven on `tests/fixtures/tables/literature_fixture.xlsx` plus `tests/fixtures/papers/paper_1.pdf` by producing at least one non-empty proposal with reviewer-usable evidence, or the run fails early with an explicit readiness error rather than pretending extraction succeeded

### Batch 4 — Review backend, summaries, and export gating

**Purpose:** make proposals reviewable and filterable through stable APIs, preserve review decisions and auditability, and compute truthful run/reviewer summaries before the full browser workspace is polished.

**Primary tasks:** `T068–T080`

**Why this batch exists:** shallow implementations often build the visible review UI before the decision model, summary model, and warning semantics are trustworthy.

**Batch 4 is complete when:**

- proposal-list/detail/filter APIs support the full MVP review surface
- review decisions are explicit persisted records, not implicit UI state
- progress counters, warning/status categories, run summaries, and reviewer summaries are recomputable from artifacts
- run and reviewer summaries stay internally consistent, with provisional states labeled clearly and warning flags gated on real triggering conditions
- persisted review semantics distinguish confirmed no-data outcomes from rejected-or-model-wrong outcomes
- export candidate selection is safely limited to explicitly accepted proposals

### Batch 5 — Browser review workspace and operator usability

**Purpose:** deliver the actual queue-first review product surface with strong pre-review states, clear status/warning cues, safe review actions, and truthful artifact/download access.

**Primary tasks:** `T082`, `T083–T095`, `T100`

**Why this batch exists:** future agents can technically satisfy many UI requirements while still shipping a review workspace that feels fragmented, stale, or unsafe.

**Batch 5 is complete when:**

- the browser app presents a coherent run-summary plus queue/detail/evidence workspace
- grouped queue triage is actually usable, with paper and column grouping, compact cards, and high-scan state markers
- proposal ordering, filtering, selection, grouping mode changes, and run switching behave predictably without stale state leakage
- no-value cases have explicit reviewer paths, including manual entry and confirmed no-data resolution
- text highlights, quote-plus-page fallback, figure evidence, zoom/pan, evidence-to-input interaction, bulk acceptance, edited acceptance, keyboard navigation, and unresolved-match inspection are all actually usable
- rationale is concise and scannable in the decision pane rather than rendered as dense prose
- provider mode and readiness truth are visible in the UI, and disabled, degraded, stub, or unreachable proposal-generation states are not mistaken for normal live execution
- the run/setup UI is picker-driven rather than path-heavy while still showing config-derived resolved context
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
- hermetic end-to-end coverage protects the core workflow, with separate opt-in live LM Studio smoke coverage, opt-in cloud smoke coverage when implemented, and performance smoke tests
- `README.md` reflects the real primary happy path, artifact locations, config authority, UI-driven launch/status/review/export workflow, and export fidelity boundary
- the final user-facing docs set is audited against the implemented MVP so README and related docs do not mention speculative helpers, stale commands, obsolete architecture, or workflows that do not exist

The detailed task inventory below remains the source of truth for exact implementation work inside each batch.

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
  - review resolution reason
  - warning/status category
  - provider locality (`local` vs `cloud`)

- [ ] **T003** Define and implement stable identifier generation for runs, PDFs, rows, cells, proposals, evidence items, and review decisions, including at minimum:
  - deterministic `cell_id`
  - stable `pdf_id` assignment within a run
  - proposal and evidence ids that are unique and traceable, including cases where multiple PDFs target the same row/cell within one run
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
  - `primary_evidence_id` (the single most authoritative evidence item, selected by evidence ranking)
  - `supporting_evidence_ids` (ordered list of additional evidence item ids, ranked by authority and relevance, most authoritative first)

- [ ] **T007** Define the evidence JSON schema and contract for separate evidence records linked to proposals, including at least:
  - `evidence_id`
  - `proposal_id`
  - `pdf_id`
  - `source_type` (one of: `direct_quote`, `inferred_reasoning`, `calculation`, `approximate_highlight`, `quote_plus_page`, `figure_based`)
  - `page`
  - `quote_text` (verbatim text for direct quote, inferred reasoning, calculation, and quote-plus-page types)
  - `exact_highlight_regions` (bounding regions from page-text alignment when available)
  - `approximate_highlight_regions` (bounding regions from parser geometry when exact alignment failed; labeled as approximate)
  - `figure_ref`
  - `caption_text`
  - `crop_path`
  - `full_page_path`
  - `anchor_confidence`
  - `evidence_rank` (integer rank within the proposal, lower = more authoritative; primary evidence has rank 1)

- [ ] **T008** Define the review-decision JSON schema plus the run-summary and reviewer-summary JSON schemas.
  - review decisions must remain persistable as explicit records, not only as in-place proposal mutations
  - preserve a distinct confirmed-no-data outcome and structured resolution reasons for non-accepted or manually resolved states

- [ ] **T009** Define the single JSON config schema covering:
  - input table and schema paths
  - PDF directory path
  - parser settings
  - OCR fallback settings
  - matching settings
  - style-profile settings
  - retrieval settings
  - provider/model settings, including separate fields for text model identifier and vision model identifier
  - figure-review settings (scope, relevance selection strategy)
  - review settings
  - export settings

- [ ] **T009a** Define the canonical provider token policy and settings contract shared across runtime validation, config examples, tests, docs, and UI labels.
  - use `lm_studio` as the canonical LM Studio config token and `LM Studio` as the canonical operator-visible label
  - specify how optional cloud providers fit behind the same typed interface
  - document any allowed aliases in one place only and normalize them into canonical stored values
  - reject unknown, obsolete, or misspelled provider identifiers explicitly
  - provider settings must include separate model identifier fields for text extraction and for vision extraction; a single shared model field is not sufficient

- [ ] **T009b** Define the operator-facing terminology parity rules for provider, parser, model, Verify-mode, and run-state labels across the runtime config schema, checked-in config example, tests, docs, and UI copy.

- [ ] **T010** Implement config default resolution into one effective runtime config before any run work starts.

- [ ] **T011** Create `config.example.json` as a minimal but complete example config file for the full MVP.
  - keep `lm_studio` and `LM Studio` as the canonical live local config token and operator label
  - do not hardcode cloud credentials in committed examples

- [ ] **T011a** Add provider-contract example coverage for the checked-in configs and tests.
  - ensure checked-in example configs, fixture configs, and test helpers use the same canonical provider tokens and settings shape as runtime validation
  - prefer environment-variable or secret references for optional cloud-provider examples

- [ ] **T012** Implement config/path validation and required metadata/schema validation:
  - validate that configured paths exist and are readable
  - resolve relative, absolute, browser-selected, and platform-specific path spellings into one explicit resolved-run context before execution
  - validate that schema columns include at least `column_name` and `description`
  - validate that the source table contains `Title`, `Authors`, and `Publication Year`
  - fail early with actionable diagnostics when validation fails

- [ ] **T012a** Implement run-start preflight and readiness validation for the configured execution path.
  - validate provider token and provider-config shape
  - validate provider reachability for live providers
  - validate configured model availability or capability failure when it can be checked cheaply
  - validate parser and OCR dependency availability when those paths are configured
  - validate output-directory writability and other obvious broken local setup conditions
  - stop before normal processing when readiness fails, and persist actionable readiness diagnostics

- [ ] **T013** Implement config snapshotting into run artifacts:
  - validate config at run start
  - persist the resolved effective config as `config.snapshot.json`
  - ensure the run can later be explained from the snapshot

- [ ] **T013a** Persist a resolved input-summary artifact early enough that readiness-failed and early-failed runs still expose table, schema, PDF-directory, output-directory, and Verify-mode context to the UI and diagnostics.

- [ ] **T014** Audit, normalize, and document the canonical deterministic fixture corpus in `tests/fixtures/`.
  - reuse the existing checked-in workbook fixture with schema tab plus the existing four paper PDFs as the primary canonical fixture set when they cover the required scenarios
  - map those fixtures to success, OCR or text-access edge cases, unmatched or ambiguous cases, duplicate-row-conflict cases, and figure-heavy coverage where applicable
  - add text-based companion configs, manifests, expected outputs, or assertions when more precision is needed
  - avoid requiring new binary fixtures unless a real coverage gap cannot be addressed otherwise

- [ ] **T015** Set up backend unit/integration/contract test tooling, including provider stubs/fakes and fixture helpers.

- [ ] **T015a** Add contract-parity tests for provider naming and config semantics.
  - verify canonical provider tokens across runtime schemas, example configs, and test fixtures
  - verify unknown provider identifiers fail early with clear diagnostics

- [ ] **T016** Set up frontend test tooling and Playwright e2e scaffolding for the review workflow.
- [ ] **T016a** Harden the Playwright harness so fixture preparation is separate from server startup and browser/server processes start without shell-dependent heredocs or command chaining.
  - distinguish missing browser/runtime dependencies from application failures when practical
  - retain screenshots, traces, or similarly useful browser-failure artifacts when practical

---

## Phase 1 — Run creation, input loading, normalization, and lifecycle

**Goal:** the system can start a run, validate and snapshot inputs, and compute which cells are eligible for extraction or verification.

- [ ] **T017** Implement spreadsheet loading for CSV and XLSX inputs.
  - handle BOM-marked headers safely for CSV inputs
  - normalize Excel-native date and datetime cells into stable internal values instead of leaking raw serials

- [ ] **T018** Implement schema loading from workbook or separate schema file.
  - normalize BOM-marked or whitespace-padded headers for CSV-based schema sources before field validation

- [ ] **T019** Implement table normalization and required metadata-column validation for `Title`, `Authors`, and `Publication Year`.
  - perform header normalization before checking canonical field names

- [ ] **T020** Implement cell eligibility classification for at least:
  - empty / missing
  - already-filled
  - trivial placeholder treated as empty when configured
  - skipped / ineligible

- [ ] **T021** Implement Verify mode semantics so already-filled cells become eligible targets when Verify mode is enabled.

- [ ] **T022** Implement run lifecycle state transitions for at least:
  - `created`
  - `validating`
  - `running`
  - `completed`
  - `completed_with_warnings`
  - `failed`
  - `interrupted`
  - treat `created` and `interrupted` as internal or artifact-level states when useful, but map UI state to the normative operator-visible lifecycle defined in `spec.md`

- [ ] **T023** Implement run creation and inspection API endpoints for:
  - create run
  - list runs
  - get run summary
  - fetch config snapshot
  - fetch input summary

- [ ] **T023b** Support picker-driven input overrides in the run-creation flow while preserving config-file authority.
  - accept explicit run-input overrides for relevant file or folder paths
  - materialize browser-selected files or directories into app-owned staged inputs or another explicit backend-readable input handle before execution
  - return the resolved path context that the UI should display back to the operator
  - distinguish logical input source from backend-visible runtime locator in the returned run context
  - keep override handling narrow and input-focused rather than turning the API into a broad settings editor

- [ ] **T023a** Keep run creation UI-driven in practice by returning a created run immediately, then launching execution under app-owned backend control using a lightweight in-process background mechanism for MVP, with no external job framework required, while exposing validating/running/terminal state transitions, actionable failure messaging, and diagnostics/config access.

- [ ] **T024** Add tests covering valid input readiness, metadata-column rejection, missing-path rejection, placeholder handling, and Verify mode behavior.

- [ ] **T024a** Add tests covering readiness and startup truth.
  - invalid provider token rejection
  - provider-unreachable readiness failure
  - model-unavailable readiness failure where applicable
  - missing parser or OCR dependency readiness failure where applicable
  - broken output-path or similarly broken local setup failure

- [ ] **T024b** Add tests covering path-resolution and picker-driven setup truth.
  - relative versus absolute path resolution
  - browser-selected input override handling
  - backend staging or input-handle materialization for browser-selected inputs
  - resolved-path reporting in early-failure and success cases

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

- [ ] **T026a** Implement explicit parser-selection and fallback-policy handling.
  - record configured parser choice separately from actual parser used
  - if the configured parser cannot be used, fail readiness or parsing by default unless an explicit lower-quality fallback policy was enabled for debugging or constrained environments
  - surface any explicit fallback path in run artifacts, diagnostics, and operator-visible summaries

- [ ] **T027** Implement the low-level PDF abstraction using **`pypdfium2` / PDFium** for rendering, geometry, crop extraction, and page/image access.

- [ ] **T028** Integrate OCR fallback for scanned or text-inaccessible PDFs:
  - default OCR fallback tool = **OCRmyPDF**
  - use OCR fallback only when text extraction is empty or clearly insufficient
  - normalize OCR output into the same `ParsedDocument` contract as born-digital PDFs
  - store OCR-affected artifacts in the run bundle

- [ ] **T029** Implement parse-stage persistence so parser-native outputs and normalized parsed-document artifacts are both stored under stable run paths.

- [ ] **T030** Generate page-render artifacts and crop helpers needed later for text evidence, figure evidence, and PDF review.

- [ ] **T031** Add parser diagnostics per PDF, including configured parser choice, actual parser path used, OCR used or not, and major extraction gaps.

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
  - keep one typed interface that supports LM Studio as the default local-first path and optional cloud providers behind the same contract
  - expose canonical provider token, locality, readiness, and structured-output capability information through the abstraction
  - support separate model identifier fields for text extraction and vision extraction in the provider config
  - validate guided-JSON or equivalent structured-output compatibility instead of assuming one wire format
  - keep structured-output compatibility handling scoped so one provider-schema mismatch does not poison unrelated proposal attempts by default

- [ ] **T051** Implement **LM Studio localhost API** integration as the initial MVP provider path.
  - keep config parsing, runtime behavior, artifacts, and UI-visible summaries aligned with the canonical provider contract

- [ ] **T051a** Implement optional cloud-provider adapter slots behind the same provider interface.
  - support environment- or secret-based credential resolution
  - keep cloud providers optional and outside the committed local-first happy path
  - do not require opt-in live cloud tests for the default MVP path

- [ ] **T052** Implement provider error handling and structured-output failure policy for LM Studio, including:
  - timeout handling
  - model-unavailable handling
  - capability checks for required structured-output behavior
  - guided-JSON rejection handling with compatible fallback when the same proposal contract can still be preserved
  - malformed JSON and malformed structured-output handling
  - a bounded repair or retry path before recording a hard extraction error
  - a compact repair-oriented instruction or equivalent narrowly scoped recovery step for malformed JSON
  - containment of compatibility failures so the affected target or request path fails truthfully without unnecessarily poisoning the rest of the run
  - explicit fail-fast rules when recovery cannot preserve the proposal contract
  - request/response logging policy with actionable diagnostics

- [ ] **T052a** Make provider-mode truth explicit across runtime artifacts and operator surfaces.
  - classify proposal generation at minimum as live local, live cloud, unavailable, disabled, or explicit stub/demo/degraded mode
  - prevent silent fallback from a configured live path into an unlabeled stub or degraded path
  - persist the resulting mode and readiness status in run artifacts and summaries
  - record text model and vision model identifiers separately in run artifacts and summaries when both are used

- [ ] **T053** Implement the extraction request builder for LM Studio structured JSON:
  - assemble per-cell extraction requests from row context, column name, column description, style profile, retrieved passages, and relevant table/caption context
  - keep prompt/request construction separate from orchestration logic
  - support rationale and calculation fields in the response contract

- [ ] **T053a** Request concise markdown-bullet rationale from the extraction layer when rationale is returned.
  - prefer short scientific-review bullets over dense prose
  - keep the rationale output compact enough for the middle review pane by default

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

- [ ] **T057a** Add field-aware extraction handling for long-text targets so narrative outputs do not systematically fail because of short-answer-oriented response shaping or truncation assumptions.

- [ ] **T058** Implement proposal-state handling for at least:
  - `found`
  - `inferred`
  - `unclear`
  - `blocked`
  - `error`
  - `skipped`

- [ ] **T058a** Enforce the anti-guessing rule in extraction adjudication.
  - prefer `unclear` over guesses supported mainly by prior spreadsheet values, common practice, or weak implication
  - keep style profiles and prior table content as output-shaping context only, not as semantic evidence substitutes

- [ ] **T059** Implement text-evidence anchoring and highlight production using a page-text alignment strategy:
  - attempt exact quote matching against the rendered page text layer to produce character-level highlight regions
  - store resulting regions as `exact_highlight_regions` in the evidence record
  - if exact page-text alignment fails, attempt to derive approximate regions from parser geometry and store them as `approximate_highlight_regions`, labeled as approximate
  - if neither succeeds, fall back to quote-plus-page evidence, labeled as such
  - never present approximate or fallback highlights as exact highlights
  - store the `source_type` that reflects the achieved highlight fidelity

- [ ] **T060** Implement the single narrow evidence-recovery pass when evidence is weak, missing, or unusable for display.

- [ ] **T061** Keep weak-but-reviewable proposals available when quote + page evidence exists even if precise highlighting fails.
  - preserve the fallback as clearly rendered text evidence rather than letting it appear blank, missing, or mislabeled

- [ ] **T062** Implement proactive figure review when a vision model is configured:
  - when a vision model is configured, run figure review across all relevant extracted figures for the current paper as a normal supplemental evidence stage, not only when text extraction has failed
  - select relevant figures by structural heuristics, caption relevance, or an LLM-assisted relevance selection step, rather than processing every figure indiscriminately
  - figure evidence may support any field type, not only fields classified as figure-derived
  - figure evidence may strengthen text-derived proposals, supplement weak evidence, or rescue weak, unclear, or failed text-only proposals
  - figure review produces additional evidence items ranked by authority and relevance alongside existing text evidence
  - no user-triggered figure review control is part of MVP; figure review runs automatically based on configuration

- [ ] **T063** Build the figure-fallback input package containing:
  - crop
  - caption
  - nearby text
  - full-page reference

- [ ] **T064** Persist figure-derived evidence records distinctly from text evidence while keeping figure-derived proposals as normal proposals with figure-marked evidence.

- [ ] **T065** Implement reviewer-facing support-label mapping and evidence type labeling:
  - map internal proposal states to reviewer-facing labels such as `Direct evidence` and `Inferred from evidence`
  - label each evidence item's type visibly in the UI: direct quote, inferred reasoning, calculation, approximate highlight, quote-plus-page fallback, or figure-based
  - ensure the primary evidence item is visually distinguished as primary
  - ensure supporting evidence items are shown in ranked order
  - ensure direct quotes are visually separated from reasoning and calculations in the detail pane

- [ ] **T066** Ensure Verify mode uses the same extraction path for already-filled cells and persists reviewable proposals for them.

- [ ] **T067** Add tests covering structured-output parsing, provider failure handling, proposal/evidence serialization, blocked outcomes, unclear outcomes, evidence recovery, evidence ranking (primary selection by authority), evidence type labeling, exact-highlight vs. approximate-highlight vs. quote-plus-page fallback evidence paths, proactive figure review triggering, figure evidence support for any field type, figure rescue of weak text proposals, separate text and vision model config, and Verify mode extraction on filled cells.
  - include contract-parity and provider-mode truth assertions where applicable
  - cover compatibility mismatches that should not poison the rest of the run
  - cover malformed-JSON repair behavior and compact bullet-rationale output shape
  - cover evidence ranking behavior: proposals must have the highest-authority quote as primary
  - cover the honest fallback chain: exact → approximate → quote-plus-page, each with correct source_type

---

## Phase 6 — Review-state backend, review-asset serving, warnings/status policy, filtering, and summaries

**Goal:** make proposals reviewable, filterable, auditable, asset-backed, and safe for partial review and export.

- [ ] **T068** Implement normalized warning and status surfaces:
  - define categories for ambiguous match, duplicate-row conflict, weak evidence, quote+page fallback without highlight, figure-derived evidence, no reviewed verified cells, completed-with-warnings run outcome, readiness failure, provider unavailable, and explicit disabled or degraded provider mode
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
  - expose compact triage fields needed for grouped sidebar rendering by paper and by column

- [ ] **T070** Implement proposal-detail API payloads containing:
  - row context
  - column definition
  - current cell value
  - proposal state
  - support label
  - rationale
  - calculation
  - primary evidence (the single most authoritative evidence item)
  - ordered supporting evidence (additional evidence items ranked by authority and relevance)
  - evidence type for each evidence item
  - warning/status flags
  - no-value or manual-resolution affordances needed by the middle pane

- [ ] **T071** Implement review-asset serving endpoints for the review UI, including:
  - safe browser access to original PDFs for the PDF.js viewer
  - page-image serving
  - figure-crop serving
  - evidence metadata lookups needed by the viewer and detail pane

- [ ] **T072** Implement review-decision persistence for:
  - accept as-is
  - accept with edit
  - confirm no data
  - reject
  - no decision yet
  - persist explicit review-decision records that can later drive audit logs and summary recomputation
  - preserve structured resolution reasons for non-accepted or manually resolved outcomes

- [ ] **T073** Preserve prior proposal state and review history for auditability when a review decision is recorded.

- [ ] **T074** Implement guarded bulk-accept semantics limited to the currently visible filtered subset of undecided proposals.

- [ ] **T075** Implement progress counters and decision-breakdown aggregation.

- [ ] **T075a** Ensure review aggregates distinguish confirmed-no-data outcomes from rejected-or-model-wrong outcomes in both backend summaries and API payloads.

- [ ] **T076** Implement run-summary generation and persistence in `summaries/run_summary.json`, including at minimum:
  - PDFs processed
  - matched / unmatched / ambiguous PDFs
  - proposals generated
  - reviewed proposals
  - accepted as-is
  - accepted with edit
  - confirmed no-data outcomes when applicable
  - rejected
  - pending / undecided
  - changed cells exported
  - Verify mode on/off
  - provider/model names, with text model and vision model identified separately when both were used
  - local vs cloud status
  - provider mode and readiness outcome
  - internally consistent counts and warning flags derived from persisted data rather than speculative UI state

- [ ] **T077** Implement reviewer-outcome summary generation as a pure function of proposals and review decisions, and persist it in `summaries/reviewer_summary.json`, including at minimum:
  - proposals generated
  - reviewed proposals
  - accepted as-is
  - accepted with edit
  - confirmed no-data outcomes when applicable
  - rejected
  - pending / undecided
  - changed cells exported
  - matched / unmatched / ambiguous PDFs
  - Verify mode on/off
  - provider/model names, with text model and vision model identified separately when both were used
  - local vs cloud status
  - provider mode and readiness outcome where relevant to interpretation
  - explicit provisional labeling when too little reviewed data exists for meaningful interpretation

- [ ] **T078** Support summary recomputation from artifact files so both run and reviewer summaries stay derivable and inspectable.

- [ ] **T078a** Add summary-integrity checks that reject internally inconsistent counts, misleading zero-value rollups, and warning flags that fire before their triggering conditions are met.

- [ ] **T079** Ensure export candidate selection uses only explicitly accepted proposals and excludes unreviewed proposals by construction.

- [ ] **T080** Add tests covering review decision recording, audit history, visible-subset bulk acceptance, warning/status semantics, review-asset serving, run-summary recomputation, reviewer-summary recomputation, and partial-review behavior.
  - cover distinct confirmed-no-data persistence and summary reporting

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
  - confirmed no-data outcomes when applicable
  - rejected
  - changed cells exported
  - Verify mode on/off
  - provider/model names, with text model and vision model identified separately when both were used
  - local vs cloud status
  - provider mode and readiness outcome
  - direct links or equivalent access to workbook, audit-log, run-summary, and reviewer-summary downloads

- [ ] **T082a** Implement a run-launch and setup context surface in the UI that:
  - starts a run from a config-file path without exposing a broad advanced-settings editor
  - shows the config path and concise resolved input summary, including on readiness-failed or early-failed runs when that context is known
  - supports browser-compatible picker controls for relevant file and folder inputs while preserving config-file authority for advanced behavior
  - materializes picker-selected inputs into backend-readable staged files or directories, or another explicit server-side input handle, instead of relying on raw browser-native paths
  - shows picker-based overrides as explicit resolved run-input selections rather than hiding them
  - shows both logical input source and backend-visible runtime locator when picker overrides are used
  - keeps target-columns display collapsible, truncated, or otherwise compact by default
  - shows provider/readiness context clearly before the queue is reviewable
  - keeps empty/loading/warning/failure states explicit before the review queue is ready
  - makes the next operator action obvious when no run exists yet or when the selected run is not reviewable

- [ ] **T083** Implement the three-pane review workspace:
  - left pane = grouped review queue or sidebar
  - center pane = detail and decision workflow
  - right pane = evidence viewer
  - visible run/reviewer summary context in the main workspace
  - top bar or equivalent queue controls = grouping toggle, counters, filters, saved views or presets when implemented, and warnings

- [ ] **T083a** Implement grouped-queue client state and grouped rendering behavior.
  - support `Group by Paper` and `Group by Column`
  - show group-header summary context including total count, pending count, and any warning or manual-attention badge needed for triage
  - order groups with pending-actionable groups first, configured column order for column groups, and stable matched-row or PDF-name order for paper groups
  - preserve collapsible group state when helpful
  - keep grouping state, filters, and saved views or presets usable for both triage and deeper investigation

- [ ] **T084** Implement the proposal queue pane with the full MVP filter set, stable selection behavior, and explicit proposal ordering rules:
  - render compact grouped cards rather than a flat tall list
  - show only essential triage information on compact cards: target column, triage status, and support/confidence
  - add high-scan state markers such as left-border colors for pending, accepted, and manual-attention states
  - keep review decision state, support quality, and match outcome visually distinct rather than collapsing them into one status chip
  - default groups with pending actionable items before fully resolved or manual-attention-only groups
  - within grouped-by-column mode, preserve configured target-column order inside the same group-priority bucket
  - within grouped-by-paper mode, preserve stable matched-row order when available, otherwise stable PDF-name order inside the same group-priority bucket
  - default pending / undecided proposals before reviewed proposals
  - within undecided proposals, actionable proposals before blocked or unresolved items
  - within the same decision-status bucket, preserve stable spreadsheet row order, then column order, then `proposal_id`
  - do not auto-promote figure-derived or quote+page-fallback proposals unless the user applies filters
  - keep blocked, ambiguous, unmatched, and duplicate-row-conflict items visible without letting them dominate the main actionable queue by default
  - do not record review decisions implicitly from navigation or selection changes
  - allow filter continuity across run switches when practical, but do not preserve stale proposal/detail/evidence state across runs

- [ ] **T085** Implement the proposal detail pane showing row context, target column definition, current value in Verify mode, proposed value, support label, rationale, calculation, warning/status flags, and evidence list with primary and ordered supporting items.
  - status, evidence source, and warning state should be distinguishable at a glance
  - keep explicit row context near the top
  - present existing-versus-proposed comparison clearly in Verify mode
  - render concise rationale by default and fuller rationale through expansion
  - render markdown-bullet rationale cleanly when provided in bullet form
  - show direct quotes separately from inferred reasoning and calculations; each evidence type must be visually labeled
  - show the primary evidence item prominently and supporting items in ranked order
  - support explicit no-value reviewer actions including edited-value entry and confirmed-no-data resolution
  - surface structured resolution reasons for non-accepted or manually resolved outcomes

- [ ] **T086** Implement the evidence viewer pane using a raw/custom PDF.js viewer for text evidence and attached reviewable figure evidence.
  - include zoom and pan capabilities as baseline viewer behavior
  - include previous and next page navigation
  - include jump-to-page-by-number navigation
  - focus on the currently selected evidence item when it changes: scroll to and center or highlight the relevant region
  - refocus stably when evidence selection or zoom changes, without arbitrary jumping
  - support figure-to-full-page context: figure evidence viewable as focused crop and as full page from the same pane

- [ ] **T086a** Implement synchronized quote list and document viewer:
  - maintain an ordered list of evidence items for the current proposal (primary first, then supporting in ranked order)
  - when the reviewer selects an evidence item in the quote list, update the viewer to show that item's page and location
  - when evidence selection changes programmatically (e.g., proposal selection changes), update both the quote list selection and the viewer location
  - the viewer and quote list must never be out of sync when the reviewer navigates between evidence items

- [ ] **T087** Implement backend-to-viewer highlight coordinate conversion and evidence type rendering:
  - map canonical PDF/page coordinates from backend evidence records into PDF.js viewer overlay coordinates
  - render exact highlight overlays from `exact_highlight_regions` when available
  - render approximate highlight overlays from `approximate_highlight_regions` with a distinct visual label indicating they are approximate
  - render stable text highlight overlays
  - handle zoom and viewport changes correctly
  - do not emit fabricated placeholder highlight boxes when reliable anchor geometry is unavailable
  - display direct-quote evidence, inferred-reasoning evidence, and calculation evidence with distinct visual labels so the reviewer can tell which type they are inspecting
  - support click-to-populate flows from selected quote or highlight evidence into the active proposed-value or edited-value input
  - treat populate as replace-active-input by default rather than append unless an explicit append action is offered separately
  - limit automatic populate to textual evidence spans or figure-caption text, not raw image crops alone
  - use only the explicitly clicked or reviewer-selected span range rather than concatenating all visible evidence implicitly
  - stage overlong text for reviewer trim or confirmation rather than silently truncating or auto-saving it

- [ ] **T088** Implement honest fallback display for each evidence quality level:
  - for approximate highlights: show the approximate region with a visible label indicating it is approximate, not exact
  - for quote-plus-page fallback: display the quote text and page number with a visible label indicating this is fallback text evidence because highlighting was not available
  - explain missing exact highlight geometry explicitly rather than silently showing nothing
  - provide useful fallback actions such as opening the full PDF when scoped evidence is unavailable
  - never display approximate or fallback evidence as if it were exact highlighting

- [ ] **T089** Implement the figure-evidence viewer with crop-first display, attached caption, figure-derived warning/status markers, and full-page access.

- [ ] **T090** Implement the review action area with:
  - accept
  - accept with edit
  - confirm no data
  - reject
  - next
  - previous
  - bulk accept visible subset
  - disable accept actions for blocked items or items without a reviewable proposal value

- [ ] **T090a** Make bulk acceptance and edited acceptance behavior explicit and reviewer-safe:
  - confirm bulk acceptance against the currently visible filtered subset
  - present accept-with-edit as a distinct save-edited-value action rather than a vague duplicate of plain acceptance
  - keep confirmed-no-data resolution visibly distinct from rejection

- [ ] **T091** Implement keyboard shortcuts for next/previous navigation, accept current proposal, reject current proposal, focus edit control, and focus/open evidence viewer.
  - surface shortcuts in button tooltips or equivalent inline affordances on the relevant controls

- [ ] **T092** Implement unmatched, ambiguous, and duplicate-row-conflict inspection views in the UI.
  - identify the affected PDF, unresolved outcome, and rationale directly in the review workspace without requiring raw artifact inspection
  - keep this surface inspect-only for MVP rather than adding direct rematch or reassignment actions

- [ ] **T093** Surface warnings/statuses, run-summary fields, reviewer-summary fields, provider/model names, and local-vs-cloud status consistently across the review UI and run-summary UI.
  - show coarse running progress as current stage plus current item when available
  - show provider mode and readiness truth without hiding disabled, unavailable, or degraded proposal generation
  - show both text model and vision model identifiers separately when both were used for a run
  - show configured parser choice, actual parser used, and any explicit fallback state when relevant
  - if zero verified cells have been reviewed, keep per-column lines visible only as evidence-coverage context with explicit wording that reviewer outcomes are not yet meaningful
  - do not show limited-review or similar warnings before their real triggering conditions are met
  - keep confirmed-no-data outcomes distinct from rejected-or-model-wrong outcomes in visible summaries and badges

- [ ] **T094** Add frontend tests for grouped queue behavior, group-header summaries, group ordering rules, queue filtering, item ordering rules, nonlinear review, evidence type labeling (direct quote vs. inferred vs. calculation vs. approximate vs. fallback), exact-highlight vs. approximate-highlight vs. quote-plus-page fallback rendering, synchronized quote-list and viewer behavior, viewer navigation (previous/next page, jump to page), figure-evidence rendering with full-page access, run-summary display including text and vision model identifiers, no-data workflow rendering, picker-driven setup flow, markdown-bullet rationale rendering, click-to-populate replace behavior, overlong-text staging behavior, tooltip shortcut surfacing, and bulk-accept confirmation flow.

- [ ] **T095** Add Playwright e2e tests for the core review loop from proposal selection through grouped triage, group ordering, evidence interaction, no-data resolution, decision recording, picker-input staging, and summary updates.

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

- [ ] **T102** Implement the app-owned staged runner that executes the canonical pipeline stages under backend control while the API remains responsive enough for UI-driven launch, polling, diagnostics, and review-state loading.

- [ ] **T103** Ensure interrupted or failed runs leave inspectable partial artifacts and that a new run creates a new run directory rather than resuming in place by default.

- [ ] **T104** Add hermetic end-to-end tests using stub providers over the fixture corpus for:
  - successful matched extraction
  - unmatched / ambiguous / duplicate-row blocked flows
  - weak-evidence quote+page review
  - exact highlight vs. approximate highlight vs. quote-plus-page fallback evidence paths
  - Verify mode reviewed-cell flow
  - proactive figure review flow with figure evidence supporting a proposal
  - figure rescue of a weak text-only proposal
  - export with accepted-only changes
  - use the canonical checked-in fixture set as the main proof target and prefer text-based expected outputs over new binary fixtures

- [ ] **T105** Add one realistic non-hermetic smoke test path for local LM Studio execution behind an opt-in flag.
  - use `tests/fixtures/tables/literature_fixture.xlsx` plus `tests/fixtures/papers/paper_1.pdf` as the canonical live-smoke fixture target
  - require at least one non-empty proposal with reviewer-usable evidence when the environment is correctly configured
  - when readiness fails, capture and report the explicit readiness error rather than treating the run as a normal success

- [ ] **T105a** Add optional live cloud-provider smoke coverage only behind separate opt-in flags when cloud adapters are implemented.
  - use environment- or secret-based credentials only
  - keep cloud smoke coverage separate from the default local-first acceptance path

- [ ] **T106** Add a performance smoke test for representative small and medium batches so obvious regressions in parsing, retrieval, extraction, and review loading are caught.

- [ ] **T107** Update `README` with MVP run instructions:
  - how to prepare config
  - how to start the FastAPI backend and React UI
  - how to run a sample workflow
  - how picker-driven setup and path overrides work while config-file authority is preserved
  - where artifacts and exports are written
  - how Verify mode behaves
  - what the export fidelity boundary is
  - what provider tokens and provider modes mean in practice
  - how readiness and startup failures are surfaced
  - include at least one known-working LM Studio model example while making clear that stronger or newer compatible models may also be used
  - make every documented command and workflow match the implementation that currently ships
- [ ] **T107a** Preserve user-facing onboarding in `README`, including clone/install steps, config-file purpose, LM Studio expectations, backend/frontend run commands, testing commands, artifact locations, and the export fidelity boundary.
  - do not remove useful onboarding content unless it is obsolete and replaced with something clearer in the same work pass
  - keep the checked-in config example, runtime config schema, and README terminology aligned for provider, parser, model, Verify mode, and run states
  - do not keep obsolete onboarding text, superseded commands, or alternate startup paths that are not real supported workflows

- [ ] **T107b** Keep README aligned with the real primary happy path:
  - start backend and frontend
  - launch a run from the browser using a config path plus picker-driven input selection when supported
  - observe run lifecycle state in the UI
  - review/export from the same surface
  - describe the canonical LM Studio live path truthfully and avoid implying live proposal generation when the implementation is stubbed, disabled, or degraded
  - document the real config workflow, run lifecycle, review flow, export behavior, and limitations of the implemented MVP
  - do not document speculative helpers or workflows that do not exist

---

## Phase 10 — Evidence quality, proactive figure review, and model transparency

**Goal:** ensure the system satisfies the evidence-first, reviewer-centered quality bar defined in the improved product direction.

- [ ] **T108** Stale-spec cleanup: audit the codebase and tests for any remaining references to "scoped figure fallback only," narrow fallback triggers, or single-model provider config that conflict with the improved product direction. Update or remove them in the same pass.

- [ ] **T109** Implement evidence ranking and authority-aware evidence selection:
  - rank evidence items by source section authority and field relevance rather than by model output order
  - select the highest-ranked evidence item as the primary evidence item for the proposal
  - store the remaining items as ordered supporting evidence
  - the ranking logic may use structural heuristics, section type classifications, or an LLM-assisted selection step
  - acceptance criteria: a reviewer reviewing a procedural field proposal sees the most authoritative section as primary, not an arbitrary paragraph

- [ ] **T110** Implement end-to-end evidence type labeling and validation:
  - verify that each evidence record stores a valid `source_type` from the defined taxonomy
  - verify that exact highlights, approximate highlights, and quote-plus-page fallback evidence are stored and surfaced correctly
  - verify that the UI displays each evidence type with its correct label and distinct visual treatment
  - acceptance criteria: a reviewer can tell at a glance whether any evidence item is a direct quote, approximate highlight, quote-plus-page fallback, inferred reasoning, calculation, or figure-based without reading additional explanation

- [ ] **T111** End-to-end validation for proactive figure review behavior:
  - verify that when a vision model is configured, figure review runs for relevant extracted figures even when text extraction succeeded
  - verify that figure evidence can be stored alongside text evidence for the same proposal
  - verify that figure evidence appears in the ranked evidence list for any field type
  - verify that figure rescue of a weak or unclear text-only proposal produces a visible reviewable proposal with figure-based evidence
  - acceptance criteria: a run where text extraction produced weak evidence and relevant figures were available must produce at least one proposal with figure evidence when a vision model is configured

- [ ] **T112** Implement and validate separate text-model and vision-model configuration:
  - verify that the config schema accepts separate model identifier fields for text and vision
  - verify that run artifacts record both model identifiers separately
  - verify that the run summary shows both model identifiers when both were used
  - verify that the reviewer-visible run context exposes both model identifiers
  - acceptance criteria: a reviewer can see which text model and which vision model were used for any run where both were configured

- [ ] **T113** Validate synchronized quote list and viewer behavior:
  - verify that selecting a different evidence item in the quote list updates the viewer to that item's page and location
  - verify that the viewer refocuses stably when evidence selection changes
  - verify that zoom changes do not cause the viewer to lose focus on the selected evidence item
  - acceptance criteria: after selecting any evidence item from the quote list, the viewer shows that item's page and location within one interaction, without requiring additional navigation by the reviewer

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
- user-triggered figure review controls
- unrestricted full-page vision on every page of every paper for every field
- automated heterogeneous correctness scoring as the primary MVP evaluation metric

---

## Definition of done for this task list

This task list is complete enough when it can drive implementation toward a system that:

- runs the end-to-end paper-to-table workflow locally in a browser app
- makes the startup and pre-review workflow understandable without requiring the operator to infer the happy path from source code or test fixtures
- uses React + FastAPI + Docling + `pypdfium2` + raw/custom PDF.js + LM Studio + filesystem artifact bundles
- enforces canonical provider/config/runtime/docs/tests parity and fails early on unknown or broken provider setups
- keeps human review mandatory before spreadsheet mutation
- persists proposals, evidence, review decisions, run summaries, reviewer summaries, diagnostics, and exports as inspectable artifact files
- supports Verify mode end to end
- generates reviewer-outcome summaries for the MVP
- exports a new XLSX plus audit log within the explicit content-only fidelity boundary
- produces evidence with correct type labels (direct quote, inferred reasoning, calculation, approximate highlight, quote-plus-page fallback, figure-based) and ranks evidence by authority so the most authoritative item is primary
- produces exact quote highlights from page-text alignment when possible and degrades honestly with labeled fallback when it fails; fallback evidence is never presented as exact
- keeps the quote list and document viewer synchronized around the selected evidence item, with stable refocus on selection or zoom changes, previous/next/jump-to-page navigation, and figure-to-full-page context
- runs proactive figure review across all relevant extracted figures when a vision model is configured, with figure evidence allowed for any field type, including figure rescue of weak text-only proposals
- records text model and vision model identifiers separately in run artifacts, run summaries, and reviewer-visible context
- keeps loading, empty, warning, failure, and not-yet-reviewable states explicit and actionable in the operator workflow
- proves the canonical LM Studio path can generate at least one non-empty reviewable proposal with evidence on the canonical checked-in fixture set, or fails early with a clear readiness error
- ships with a truthful user-facing `README.md` and related operator docs that match the implemented commands, architecture, workflow, exports, and limitations
- stays inside the MVP architecture boundary defined by `spec.md`, `research.md`, and `plan.md`
