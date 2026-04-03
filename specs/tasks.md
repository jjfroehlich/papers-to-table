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
- evidence viewer with synchronized quote list and viewer navigation, preserving standard PDF-reading affordances in at least one explicit mode
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
- **no user-triggered figure-review rerun control**
- **evidence ranking**: primary evidence selected by authority and relevance, not by model output order
- **evidence type taxonomy**: direct quote, inferred reasoning, calculation, approximate highlight fallback, quote-plus-page fallback, caption-grounded figure evidence, and visual-interpretation figure evidence; each labeled and rendered distinctly
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
- Keep reviewable proposals, diagnostics-only outcomes, and reviewer-facing counts as separate concepts. The main queue must not become a raw dump of every blocked, skipped, ambiguous, or failed cell artifact.

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

### Batch 1 — Extraction truth, matching, and persistence refinement

**Purpose:** tighten the extraction contract so the system is schema-first, empty-table-safe, deterministically matchable, provider-truthful, and evidence-strict before more UI polish lands.

**Primary tasks:** `T020a`, `T024c`, `T034a`, `T038a`, `T040a`, `T041a`, `T042a`, `T044a`, `T047a`, `T047b`, `T047c`, `T049a`, `T049b`, `T050b`, `T052b`, `T052c`, `T056a`, `T057b`, `T058b`, `T059a`, `T062a`, `T062b`, `T067a`

**Why this batch exists:** the next implementation pass should first fix extraction leakage risk, matching integrity, warning truth, and artifact shape. Otherwise later review UX polish will sit on top of weak or misleading backend semantics.

**Batch 1 is complete when:**

- deterministic matching clearly favors DOI, author, and year signals over title-heavy scoring and explains duplicate-row conflicts distinctly from ordinary ambiguity
- schema-first extraction works without prefilled cells, optional field typing is honored, and style profiles remain helper-only rather than semantic exemplars
- retrieval rescue is bounded and explicit, whole-document mode is optional rather than default, and dead `retrieval.chunk_size` config is gone
- provider-unavailable state hard-fails at run start, warning propagation is truthful, and the structured-output ladder is bounded and testable
- proposal persistence uses `proposals.jsonl` plus an index or equivalent lookup structure
- direct evidence requires anchored direct support, multiple quotes are supported when genuinely needed, and figure evidence subtypes are ranked and labeled correctly

### Batch 2 — Reviewer workflow, viewer navigation, and export control

**Purpose:** make the run and review workspace faster and more trustworthy by tightening setup and status truth, centering actionable counts, improving fast sequential review, and keeping export explicit.

**Primary tasks:** `T023c`, `T024b`, `T068a`, `T075b`, `T080a`, `T082b`, `T084a`, `T086c`, `T090b`, `T091a`, `T093a`, `T094a`, `T095a`, `T096a`, `T101a`

**Why this batch exists:** the current baseline already has a substantial review shell. The next useful step is to tighten reviewer throughput and truthfulness rather than rebuild the whole workspace again.

**Batch 2 is complete when:**

- active runs refresh automatically, cancellation is explicit, and stale-refresh failures are surfaced instead of silently leaving the operator with stale state
- the review workspace headline and progress controls default to actionable or reviewable proposals instead of broader attempted totals
- the config path remains editable as text while also supporting a `Browse...` control for normal use
- evidence navigation supports fast sequential review, including next or previous evidence and stronger highlight synchronization
- explicit decisions auto-advance to the next reviewable proposal when one exists
- parsing fallback, duplicate conflicts, evidence fallback, and provider-mode truth are surfaced consistently in review-facing summaries and diagnostics
- export is an explicit manual reviewer action and never an implicit side effect

### Batch 3 — Regression protection, screenshots, and trustworthiness docs

**Purpose:** close the loop with coverage and operator docs so the tightened workflow remains demonstrable, repeatable, and truthful.

**Primary tasks:** `T107c`, `T107d`

**Why this batch exists:** these changes are product-trust changes. They should ship with screenshots, lightweight trust guidance, and reproducible documentation rather than being left as implicit code behavior.

**Batch 3 is complete when:**

- operator docs explain schema descriptions, manual export, evidence semantics, and provider or parsing truth without drift
- the README includes current screenshots for run setup, highlighted evidence review, and export or diagnostics views
- screenshot capture is reproducible through Playwright or an equivalent checked-in workflow
- the README includes a compact trustworthiness checklist aligned with local-first usage, evidence labeling, fallback visibility, review-before-export, and audit artifact access

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
  - review resolution reason
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
  - `primary_evidence_id` (the single most authoritative evidence item, selected by evidence ranking)
  - `ordered_supporting_evidence_ids` (ordered list of additional evidence item ids, ranked by authority and relevance, most authoritative first)

- [ ] **T007** Define the evidence JSON schema and contract for separate evidence records linked to proposals, including at least:
  - `evidence_id`
  - `proposal_id`
  - `pdf_id`
  - `source_type` (one of: `direct_quote`, `inferred_reasoning`, `calculation`, `approximate_highlight`, `quote_plus_page`, `caption_grounded_figure_evidence`, `visual_interpretation_figure_evidence`)
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

- [x] **T008** Define the review-decision JSON schema plus the run-summary and reviewer-summary JSON schemas.
  - review decisions must remain persistable as explicit records, not only as in-place proposal mutations
  - preserve a distinct confirmed-no-data outcome and structured resolution reasons for non-accepted or manually resolved states

- [x] **T009** Define the single JSON config schema covering:
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

- [x] **T009a** Define the canonical provider token policy and settings contract shared across runtime validation, config examples, tests, docs, and UI labels.
  - use `lm_studio` as the canonical LM Studio config token and `LM Studio` as the canonical operator-visible label
  - specify how optional cloud providers fit behind the same typed interface
  - document any allowed aliases in one place only and normalize them into canonical stored values
  - reject unknown, obsolete, or misspelled provider identifiers explicitly
  - provider settings must include separate model identifier fields for text extraction and for vision extraction; a single shared model field is not sufficient

- [x] **T009b** Define the operator-facing terminology parity rules for provider, parser, model, Verify-mode, and run-state labels across the runtime config schema, checked-in config example, tests, docs, and UI copy.

- [x] **T010** Implement config default resolution into one effective runtime config before any run work starts.

- [x] **T011** Create `config.example.json` as a minimal but complete example config file for the full MVP.
  - keep `lm_studio` and `LM Studio` as the canonical live local config token and operator label
  - do not hardcode cloud credentials in committed examples

- [x] **T011a** Add provider-contract example coverage for the checked-in configs and tests.
  - ensure checked-in example configs, fixture configs, and test helpers use the same canonical provider tokens and settings shape as runtime validation
  - prefer environment-variable or secret references for optional cloud-provider examples

- [x] **T012** Implement config/path validation and required metadata/schema validation:
  - validate that configured paths exist and are readable
  - resolve relative, absolute, browser-selected, and platform-specific path spellings into one explicit resolved-run context before execution
  - validate that schema columns include at least `column_name` and `description`
  - validate that the source table contains `Title`, `Authors`, and `Publication Year`
  - fail early with actionable diagnostics when validation fails

- [x] **T012a** Implement run-start preflight and readiness validation for the configured execution path.
  - validate provider token and provider-config shape
  - validate provider reachability for live providers
  - validate configured model availability or capability failure when it can be checked cheaply
  - validate parser and OCR dependency availability when those paths are configured
  - validate output-directory writability and other obvious broken local setup conditions
  - stop before normal processing when readiness fails, and persist actionable readiness diagnostics

- [x] **T013** Implement config snapshotting into run artifacts:
  - validate config at run start
  - persist the resolved effective config as `config.snapshot.json`
  - ensure the run can later be explained from the snapshot

- [x] **T013a** Persist a resolved input-summary artifact early enough that readiness-failed and early-failed runs still expose table, schema, PDF-directory, output-directory, and Verify-mode context to the UI and diagnostics.

- [x] **T014** Audit, normalize, and document the canonical deterministic fixture corpus in `tests/fixtures/`.
  - reuse the existing checked-in workbook fixture with schema tab plus the existing four paper PDFs as the primary canonical fixture set when they cover the required scenarios
  - map those fixtures to success, OCR or text-access edge cases, unmatched or ambiguous cases, duplicate-row-conflict cases, and figure-heavy coverage where applicable
  - add text-based companion configs, manifests, expected outputs, or assertions when more precision is needed
  - avoid requiring new binary fixtures unless a real coverage gap cannot be addressed otherwise

- [x] **T015** Set up backend unit/integration/contract test tooling, including provider stubs/fakes and fixture helpers.

- [x] **T015a** Add contract-parity tests for provider naming and config semantics.
  - verify canonical provider tokens across runtime schemas, example configs, and test fixtures
  - verify unknown provider identifiers fail early with clear diagnostics

- [x] **T016** Set up frontend test tooling and Playwright e2e scaffolding for the review workflow.
- [x] **T016a** Harden the Playwright harness so fixture preparation is separate from server startup and browser/server processes start without shell-dependent heredocs or command chaining.
  - distinguish missing browser/runtime dependencies from application failures when practical
  - retain screenshots, traces, or similarly useful browser-failure artifacts when practical

---

## Phase 1 — Run creation, input loading, normalization, and lifecycle

**Goal:** the system can start a run, validate and snapshot inputs, and compute which cells are eligible for extraction or verification.

- [x] **T017** Implement spreadsheet loading for CSV and XLSX inputs.
  - handle BOM-marked headers safely for CSV inputs
  - normalize Excel-native date and datetime cells into stable internal values instead of leaking raw serials

- [x] **T018** Implement schema loading from workbook or separate schema file.
  - normalize BOM-marked or whitespace-padded headers for CSV-based schema sources before field validation

- [x] **T019** Implement table normalization and required metadata-column validation for `Title`, `Authors`, and `Publication Year`.
  - perform header normalization before checking canonical field names

- [x] **T020** Implement cell eligibility classification for at least:
  - empty / missing
  - already-filled
  - trivial placeholder treated as empty when configured
  - skipped / ineligible

- [x] **T020a** Enforce that already-filled cells outside Verify mode remain diagnostics-only or entirely out of scope, rather than producing reviewer-facing placeholder proposals or synthetic blocked rationales.

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

- [x] **T023c** Implement active-run auto-refresh and cancellation support end to end.
  - expose a backend run-cancel endpoint or equivalent control path
  - persist interrupted state distinctly from failed state
  - make UI polling or streaming keep active status current without requiring manual refresh as the primary mechanism
  - surface stale-refresh failures explicitly in the UI

- [x] **T023b** Support picker-driven input overrides in the run-creation flow while preserving config-file authority.
  - accept explicit run-input overrides for relevant file or folder paths
  - materialize browser-selected files or directories into app-owned staged inputs or another explicit backend-readable input handle before execution
  - return the resolved path context that the UI should display back to the operator
  - distinguish logical input source from backend-visible runtime locator in the returned run context
  - keep override handling narrow and input-focused rather than turning the API into a broad settings editor

- [x] **T023a** Keep run creation UI-driven in practice by returning a created run immediately, then launching execution under app-owned backend control using a lightweight in-process background mechanism for MVP, with no external job framework required, while exposing validating/running/terminal state transitions, actionable failure messaging, and diagnostics/config access.

- [ ] **T024** Add tests covering valid input readiness, metadata-column rejection, missing-path rejection, placeholder handling, and Verify mode behavior.

- [ ] **T024a** Add tests covering readiness and startup truth.
  - invalid provider token rejection
  - provider-unreachable readiness failure
  - model-unavailable readiness failure where applicable
  - missing parser or OCR dependency readiness failure where applicable
  - broken output-path or similarly broken local setup failure

- [x] **T024b** Add tests covering path-resolution and picker-driven setup truth.
  - relative versus absolute path resolution
  - browser-selected input override handling
  - backend staging or input-handle materialization for browser-selected inputs
  - resolved-path reporting in early-failure and success cases

- [x] **T024c** Add tests for provider hard-fail truth and warning semantics.
  - provider-unavailable at run start must produce readiness failure rather than `completed_with_warnings`
  - `completed_with_warnings` must remain reserved for partial-success runs where meaningful processing actually happened
  - run summaries and reviewer summaries must preserve that distinction

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

- [x] **T026a** Implement explicit parser-selection and fallback-policy handling.
  - record configured parser choice separately from actual parser used
  - if the configured parser cannot be used, fail readiness or parsing by default unless an explicit lower-quality fallback policy was enabled for debugging or constrained environments
  - surface any explicit fallback path in run artifacts, diagnostics, and operator-visible summaries

- [x] **T027** Implement the low-level PDF abstraction using **`pypdfium2` / PDFium** for rendering, geometry, crop extraction, and page/image access.

- [x] **T028** Integrate OCR fallback for scanned or text-inaccessible PDFs:
  - default OCR fallback tool = **OCRmyPDF**
  - use OCR fallback only when text extraction is empty or clearly insufficient
  - normalize OCR output into the same `ParsedDocument` contract as born-digital PDFs
  - store OCR-affected artifacts in the run bundle

- [x] **T029** Implement parse-stage persistence so parser-native outputs and normalized parsed-document artifacts are both stored under stable run paths.

- [x] **T030** Generate page-render artifacts and crop helpers needed later for text evidence, figure evidence, and PDF review.

- [x] **T031** Add parser diagnostics per PDF, including configured parser choice, actual parser path used, OCR used or not, and major extraction gaps.

- [x] **T032** Add tests covering clean parse, OCR fallback, normalized parsed-document output, and stored page/crop artifacts.

---

## Phase 3 — PDF-to-row matching and blocked-match handling

**Goal:** each PDF ends in a trustworthy match state before extraction begins.

- [x] **T033** Implement grounded paper-metadata extraction from parsed documents for title, authors, publication year, and identifiers when available.

- [x] **T034** Implement deterministic matching scoring using publication metadata signals.

- [x] **T034a** Rebalance deterministic matching so exact and near-exact signals dominate title similarity.
  - prioritize DOI and other stable identifiers when present
  - strengthen first-author match, broader author overlap, and year consistency signals
  - lower title dominance so title similarity cannot outweigh stronger identifier or author/year evidence by itself
  - allow optional abstract similarity only as a secondary deterministic signal when available

- [x] **T035** Implement limited fallback adjudication only for plausible ambiguous cases.

- [x] **T036** Implement final match outcome assignment for:
  - `matched`
  - `ambiguous`
  - `unmatched`
  - duplicate-row conflict

- [x] **T037** Implement duplicate-row conflict detection that blocks all conflicting PDFs for extraction.

- [x] **T038** Persist matching artifacts and reasoning summaries so unmatched, ambiguous, and conflict cases are inspectable later.

- [x] **T038a** Persist duplicate-row conflicts as first-class diagnostic records.
  - record the conflicting PDF set, target row, and per-signal rationale
  - keep duplicate-row conflicts distinct from ordinary ambiguity in artifacts, summaries, and UI-facing payloads

- [x] **T039** Expose unmatched, ambiguous, and duplicate-row-conflict records through API endpoints for the UI.

- [x] **T040** Add tests for deterministic match success, ambiguous-block behavior, unmatched behavior, and duplicate-row-conflict behavior.

- [x] **T040a** Add tests for the tightened matching heuristic contract.
  - DOI or identifier matches must outrank title-only similarity
  - first-author and author-overlap signals must change ranking materially
  - year mismatches and duplicate-row conflicts must remain explainable in persisted diagnostics

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

- [x] **T041a** Extend the schema contract with optional field typing.
  - add optional `field_type` values: `text`, `number`, `categorical`, `boolean`
  - add optional `allowed_values` for `categorical` only
  - do not require `normalization_notes`
  - document numeric answer forms `exact`, `range`, and `approximate` in the extraction contract

- [ ] **T042** Implement the per-column preprocessing LLM step that analyzes existing filled cells and produces one structured style profile per schema column.

- [x] **T042a** Make style-profile preprocessing helper-only and empty-table-safe.
  - allow extraction to proceed when a table or target column has no filled examples
  - treat missing style profiles as expected input conditions rather than extraction failures
  - preserve schema-first behavior when style-profile preprocessing yields no useful profile

- [x] **T043** Persist style profiles under `style_profiles/` and ensure they guide only output form, not semantic content.

- [x] **T044** Enforce the no-leakage baseline for style profiles:
  - do not inject raw filled cells as semantic exemplars by default
  - keep the preprocessing output limited to style/format guidance
  - keep any leakage-risk markers visible in artifacts and diagnostics

- [x] **T044a** Tighten extraction request construction against schema leakage.
  - pass column name, description, optional field type, and style-profile summary only
  - do not pass raw historical cell values into extraction prompts as semantic examples
  - keep extraction behavior schema-first even when Verify mode is enabled

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

- [x] **T047a** Remove dead `retrieval.chunk_size` config from schema, examples, docs, and tests if the runtime does not use it.

- [x] **T047b** Implement deterministic recall rescue for `unclear` first-pass results.
  - start with focused retrieval-based extraction
  - on `unclear`, expand retrieval context or promote to section-level context
  - keep the rescue path explicit in artifacts and diagnostics rather than hidden in prompt construction

- [x] **T047c** Add optional config-controlled whole-document mode.
  - keep it off by default
  - enable it only when parsed text fits comfortably in the active model context and the field is important enough to justify the broader pass
  - record when whole-document mode was used in run artifacts and summaries

- [x] **T048** Persist retrieval artifacts and diagnostics so selected chunks, contextualized text, and source-preserving review text remain inspectable.

- [ ] **T049** Add tests covering style-profile generation, no raw-example leakage into extraction inputs, typed chunk generation, retrieval-text/display-text separation, and retrieval defaults.

- [x] **T049a** Add tests for schema-first extraction and optional field typing.
  - empty-table or empty-column cases must still extract without error
  - `categorical` fields must honor `allowed_values` when provided
  - numeric fields must accept `exact`, `range`, and `approximate` forms in the internal contract

- [x] **T049b** Add tests for bounded recall rescue and optional whole-document mode.
  - first-pass `unclear` outcomes should trigger the configured rescue path
  - whole-document mode must remain opt-in and visible in artifacts when used

---

## Phase 5 — Provider abstraction, extraction request building, proposal generation, evidence persistence, and failure handling

**Goal:** produce one best proposal per eligible target cell with inspectable evidence and stable structured contracts.

- [x] **T050** Implement the provider abstraction and capability-probe model for structured-output support.
  - keep one typed interface that supports LM Studio as the default local-first path and optional cloud providers behind the same contract
  - expose canonical provider token, locality, readiness, and structured-output capability information through the abstraction
  - support separate model identifier fields for text extraction and vision extraction in the provider config
  - validate guided-JSON or equivalent structured-output compatibility instead of assuming one wire format
  - keep structured-output compatibility handling scoped so one provider-schema mismatch does not poison unrelated proposal attempts by default

- [x] **T050b** Enforce provider-unavailable hard-fail semantics at run start.
  - fail readiness when a configured live provider is unavailable or unreachable before proposal generation begins
  - reserve `completed_with_warnings` for partial-success runs only
  - keep provider-mode truth explicit in artifacts, summaries, and UI-facing payloads

- [x] **T051** Implement **LM Studio localhost API** integration as the initial MVP provider path.
  - keep config parsing, runtime behavior, artifacts, and UI-visible summaries aligned with the canonical provider contract

- [x] **T051a** Implement optional cloud-provider adapter slots behind the same provider interface.
  - support environment- or secret-based credential resolution
  - keep cloud providers optional and outside the committed local-first happy path
  - do not require opt-in live cloud tests for the default MVP path

- [x] **T052** Implement provider error handling and structured-output failure policy for LM Studio, including:
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

- [x] **T052b** Tighten structured-output recovery to one bounded ladder.
  - `json_schema` first
  - one stronger-instruction retry if the response is invalid
  - minimal JSON repair only for purely syntactic failures
  - otherwise mark extraction failed for the affected target

- [x] **T052c** Normalize warning and status propagation end to end.
  - keep evidence-fallback mapping keys consistent from extraction artifacts through review APIs and UI summaries
  - ensure provider-mode truth and fallback-status truth are derived from persisted facts rather than UI-local heuristics

- [x] **T052a** Make provider-mode truth explicit across runtime artifacts and operator surfaces.
  - classify proposal generation at minimum as live local, live cloud, unavailable, disabled, or explicit stub/demo/degraded mode
  - prevent silent fallback from a configured live path into an unlabeled stub or degraded path
  - persist the resulting mode and readiness status in run artifacts and summaries
  - record text model and vision model identifiers separately in run artifacts and summaries when both are used

- [x] **T053** Implement the extraction request builder for LM Studio structured JSON:
  - assemble per-cell extraction requests from row context, column name, column description, style profile, retrieved passages, and relevant table/caption context
  - keep prompt/request construction separate from orchestration logic
  - support rationale and calculation fields in the response contract

- [x] **T053a** Request concise markdown-bullet rationale from the extraction layer when rationale is returned.
  - prefer short scientific-review bullets over dense prose
  - keep the rationale output compact enough for the middle review pane by default

- [x] **T054** Build the structured JSON schema/request payload for the text model path.

- [x] **T055** Build the structured JSON schema/request payload for the vision-capable model path.

- [x] **T056** Implement proposal/evidence serialization using the shared artifact I/O layer so proposals and evidence are stored as separate linked records under stable bundle locations.

- [x] **T056a** Migrate canonical proposal persistence to `proposals.jsonl` plus proposal index.
  - keep filesystem-first JSON persistence
  - use an index or equivalent lookup structure for id-based loading and filtered list assembly
  - remove any remaining many-small-proposal-file direction from artifacts and docs

- [x] **T057** Implement the per-target-cell extraction orchestrator that assembles:
  - row context
  - column definition
  - current cell value when relevant
  - style profile
  - retrieved evidence context
  - Verify mode state
  - text-model or vision-model request path as routed

- [x] **T057b** Add schema-aware field-type handling to extraction and proposal contracts.
  - pass optional schema `field_type` and `allowed_values` into extraction requests when present
  - keep numeric outputs internally typed as `exact`, `range`, or `approximate`
  - ensure the absence of field typing does not block extraction

- [x] **T057a** Add field-aware extraction handling for long-text targets so narrative outputs do not systematically fail because of short-answer-oriented response shaping or truncation assumptions.

- [x] **T058** Implement proposal-state handling for at least:
  - `found`
  - `inferred`
  - `unclear`
  - `blocked`
  - `error`
  - `skipped`

- [x] **T058a** Enforce the anti-guessing rule in extraction adjudication.
  - prefer `unclear` over guesses supported mainly by prior spreadsheet values, common practice, or weak implication
  - keep style profiles and prior table content as output-shaping context only, not as semantic evidence substitutes

- [x] **T058b** Fix direct-evidence support semantics.
  - require anchored direct quote support before labeling a proposal as direct evidence
  - downgrade quote-plus-reasoning cases to inferred or weak evidence when the quote does not directly state the answer

- [x] **T059** Implement text-evidence anchoring and highlight production using a page-text alignment strategy:
  - attempt exact quote matching against the rendered page text layer to produce character-level highlight regions
  - store resulting regions as `exact_highlight_regions` in the evidence record
  - if exact page-text alignment fails, attempt to derive approximate regions from parser geometry and store them as `approximate_highlight_regions`, labeled as approximate
  - if neither succeeds, fall back to quote-plus-page evidence, labeled as such
  - never present approximate or fallback highlights as exact highlights
  - store the `source_type` that reflects the achieved highlight fidelity

- [x] **T059a** Support multiple quote evidence items for one proposal when genuinely needed.
  - preserve ranked ordering across multiple quotes, calculations, and supporting evidence items
  - avoid collapsing multi-part support into one synthetic quote blob when separate quotes are clearer for review

- [x] **T060** Implement the single narrow evidence-recovery pass when evidence is weak, missing, or unusable for display.

- [x] **T061** Keep weak-but-reviewable proposals available when quote + page evidence exists even if precise highlighting fails.
  - preserve the fallback as clearly rendered text evidence rather than letting it appear blank, missing, or mislabeled

- [x] **T062** Implement proactive figure review when a vision model is configured:
  - when a vision model is configured, run figure review across all relevant extracted figures for the current paper as a normal supplemental evidence stage, not only when text extraction has failed
  - select relevant figures by structural heuristics, caption relevance, or an LLM-assisted relevance selection step, rather than processing every figure indiscriminately
  - figure evidence may support any field type, not only fields classified as figure-derived
  - figure evidence may strengthen text-derived proposals, supplement weak evidence, or rescue weak, unclear, or failed text-only proposals
  - figure review produces additional evidence items ranked by authority and relevance alongside existing text evidence
  - no user-triggered figure review control is part of MVP; figure review runs automatically based on configuration

- [x] **T062a** Split figure evidence into reviewer-visible subtypes.
  - persist `caption_grounded_figure_evidence` separately from `visual_interpretation_figure_evidence`
  - expose both subtypes through artifacts, API payloads, and UI labels

- [x] **T062b** Tighten figure-evidence ranking semantics.
  - rank caption-grounded figure evidence above generic inferred reasoning when otherwise comparably relevant
  - keep pure visual-interpretation evidence visibly distinct and subject to higher reviewer scrutiny

- [x] **T063** Build the figure-fallback input package containing:
  - crop
  - caption
  - nearby text
  - full-page reference

- [x] **T064** Persist figure-derived evidence records distinctly from text evidence while keeping figure-derived proposals as normal proposals with figure-marked evidence.

- [ ] **T065** Implement reviewer-facing support-label mapping and evidence type labeling:
  - map internal proposal states to reviewer-facing labels such as `Direct evidence` and `Inferred from evidence`
  - label each evidence item's type visibly in the UI: direct quote, inferred reasoning, calculation, approximate highlight, quote-plus-page fallback, `caption_grounded_figure_evidence`, or `visual_interpretation_figure_evidence`
  - ensure the primary evidence item is visually distinguished as primary
  - ensure supporting evidence items are shown in ranked order
  - ensure direct quotes are visually separated from reasoning and calculations in the detail pane

- [x] **T066** Ensure Verify mode uses the same extraction path for already-filled cells and persists reviewable proposals for them.

- [ ] **T067** Add tests covering structured-output parsing, provider failure handling, proposal/evidence serialization, blocked outcomes, unclear outcomes, evidence recovery, evidence ranking (primary selection by authority), evidence type labeling, exact-highlight vs. approximate-highlight vs. quote-plus-page fallback evidence paths, proactive figure review triggering, figure evidence support for any field type, figure rescue of weak text proposals, separate text and vision model config, and Verify mode extraction on filled cells.
  - include contract-parity and provider-mode truth assertions where applicable
  - cover compatibility mismatches that should not poison the rest of the run
  - cover malformed-JSON repair behavior and compact bullet-rationale output shape
  - cover evidence ranking behavior: proposals must have the highest-authority quote as primary
  - cover the honest fallback chain: exact → approximate → quote-plus-page, each with correct source_type

- [x] **T067a** Add tests for the tightened extraction-truth contract.
  - cover provider hard-fail semantics at run start
  - cover the bounded structured-output ladder exactly as specified
  - cover direct-evidence thresholding, multi-quote support, and figure-evidence subtype ranking
  - cover `proposals.jsonl` plus index persistence behavior

---

## Phase 6 — Review-state backend, review-asset serving, warnings/status policy, filtering, and summaries

**Goal:** make proposals reviewable, filterable, auditable, asset-backed, and safe for partial review and export.

- [x] **T068** Implement normalized warning and status surfaces:
  - define categories for ambiguous match, duplicate-row conflict, weak evidence, quote+page fallback without highlight, figure-derived evidence, no reviewed verified cells, completed-with-warnings run outcome, readiness failure, provider unavailable, and explicit disabled or degraded provider mode
  - persist these statuses in run and proposal artifacts
  - expose them consistently through API payloads

- [x] **T068a** Surface degraded parsing, duplicate-row conflicts, and evidence-fallback truth consistently.
  - carry parse-fallback and low-text warnings from parsing artifacts into run summaries and review payloads
  - keep duplicate-row conflicts distinct from ambiguous matches in status categories and API responses
  - ensure evidence-fallback states remain reviewer-visible without inflating the main actionable queue

- [x] **T069** Implement proposal-list APIs with filters for at least:
  - row
  - column
  - PDF
  - evidence status
  - figure-derived evidence
  - ambiguous/unmatched match status
  - review decision status
  - expose compact triage fields needed for grouped sidebar rendering by paper and by column

- [x] **T070** Implement proposal-detail API payloads containing:
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

- [x] **T071** Implement review-asset serving endpoints for the review UI, including:
  - safe browser access to original PDFs for the PDF.js viewer
  - page-image serving
  - figure-crop serving
  - evidence metadata lookups needed by the viewer and detail pane

- [x] **T072** Implement review-decision persistence for:
  - accept as-is
  - accept with edit
  - confirm no data
  - reject
  - no decision yet
  - persist explicit review-decision records that can later drive audit logs and summary recomputation
  - preserve structured resolution reasons for non-accepted or manually resolved outcomes

- [x] **T073** Preserve prior proposal state and review history for auditability when a review decision is recorded.

- [x] **T074** Implement guarded bulk-accept semantics limited to the currently visible filtered subset of undecided proposals.

- [x] **T075** Implement progress counters and decision-breakdown aggregation.

- [x] **T075a** Ensure review aggregates distinguish confirmed-no-data outcomes from rejected-or-model-wrong outcomes in both backend summaries and API payloads.

- [x] **T075b** Make actionable-only counts the default review-progress source.
  - compute primary progress from reviewable or actionable proposals
  - expose broader attempted totals, blocked counts, and diagnostic totals only as secondary context

- [x] **T076** Implement run-summary generation and persistence in `summaries/run_summary.json`, including at minimum:
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

- [x] **T077** Implement reviewer-outcome summary generation as a pure function of proposals and review decisions, and persist it in `summaries/reviewer_summary.json`, including at minimum:
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

- [x] **T078** Support summary recomputation from artifact files so both run and reviewer summaries stay derivable and inspectable.

- [x] **T078a** Add summary-integrity checks that reject internally inconsistent counts, misleading zero-value rollups, and warning flags that fire before their triggering conditions are met.

- [x] **T079** Ensure export candidate selection uses only explicitly accepted proposals and excludes unreviewed proposals by construction.

- [x] **T080** Add tests covering review decision recording, audit history, visible-subset bulk acceptance, warning/status semantics, review-asset serving, run-summary recomputation, reviewer-summary recomputation, and partial-review behavior.
  - cover distinct confirmed-no-data persistence and summary reporting

- [x] **T080a** Add tests for warning/status truth across artifacts, APIs, and summaries.
  - parse fallback, provider-mode truth, duplicate-row conflicts, and evidence-fallback warnings must stay consistent across surfaces
  - actionable-only counts must remain distinct from broader attempted totals in summary payloads

---

## Phase 7 — Review UI shell, three-pane workspace, ordering rules, and evidence viewer

**Goal:** implement the dedicated queue-first local browser review application required by the MVP.

- [x] **T081** Build the React frontend shell with Run and Review views.

- [x] **T082** Implement the concise run summary view showing at least:
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

- [x] **T082a** Implement a run-launch and setup context surface in the UI that:
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

- [x] **T082b** Add a `Browse...` control next to the config-path text field.
  - keep the text field as the canonical visible path control
  - allow normal local-first file selection without hiding or replacing the path value

- [x] **T083** Implement the three-pane review workspace:
  - left pane = grouped review queue or sidebar
  - center pane = detail and decision workflow
  - right pane = evidence viewer
  - visible run/reviewer summary context in the main workspace
  - top bar or equivalent queue controls = grouping toggle, counters, filters, saved views or presets when implemented, and warnings

- [x] **T083a** Implement grouped-queue client state and grouped rendering behavior.
  - support `Group by Paper` and `Group by Column`
  - show group-header summary context including total count, pending count, and any warning or manual-attention badge needed for triage
  - order groups with pending-actionable groups first, configured column order for column groups, and stable matched-row or PDF-name order for paper groups
  - preserve collapsible group state when helpful
  - keep grouping state, filters, and saved views or presets usable for both triage and deeper investigation

- [x] **T084** Implement the proposal queue pane with the full MVP filter set, stable selection behavior, and explicit proposal ordering rules:
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

- [x] **T084a** Make actionable-only progress explicit in the review workspace.
  - use reviewable or actionable proposal counts in the main headline and primary counters
  - keep broader totals available secondarily without dominating queue triage

- [x] **T085** Implement the proposal detail pane showing row context, target column definition, current value in Verify mode, proposed value, support label, rationale, calculation, warning/status flags, and evidence list with primary and ordered supporting items.
  - status, evidence source, and warning state should be distinguishable at a glance
  - keep explicit row context near the top
  - present existing-versus-proposed comparison clearly in Verify mode
  - render concise rationale by default and fuller rationale through expansion
  - render markdown-bullet rationale cleanly when provided in bullet form
  - show direct quotes separately from inferred reasoning and calculations; each evidence type must be visually labeled
  - show the primary evidence item prominently and supporting items in ranked order
  - support explicit no-value reviewer actions including edited-value entry and confirmed-no-data resolution
  - surface structured resolution reasons for non-accepted or manually resolved outcomes

- [ ] **T086** Implement the evidence viewer pane so it supports both annotated evidence inspection and normal PDF reading behavior for text evidence and attached reviewable figure evidence.
  - include zoom and pan capabilities as baseline viewer behavior
  - include previous and next page navigation
  - include jump-to-page-by-number navigation
  - provide a standard interactive reading mode, or equivalent viewer behavior, with pointer-drag page movement and text selection/copy when the source PDF and viewer foundation permit it
  - focus on the currently selected evidence item when it changes: scroll to and center or highlight the relevant region
  - refocus stably when evidence selection or zoom changes, without arbitrary jumping
  - support figure-to-full-page context: figure evidence viewable as focused crop and as full page from the same pane

- [x] **T086b** Preserve ordinary PDF-viewer fallback affordances from the review pane.
  - expose an obvious action to open the current PDF in a fuller browser-native viewer when scoped evidence or in-pane controls are insufficient
  - treat in-viewer text search as recommended when supported cleanly by the chosen viewer mode or browser PDF surface, but do not require a brittle custom search layer for MVP
  - do not force reviewers to remain in an overlay-only mode when they need to read or copy from the paper naturally

- [x] **T086c** Strengthen evidence navigation and highlight behavior in the viewer.
  - add explicit next and previous evidence controls in the evidence pane
  - keep highlight focus synchronized as the reviewer cycles evidence items
  - prioritize highlight and navigation quality over forcing every native-reader affordance into the same in-app mode

- [x] **T086a** Implement synchronized quote list and document viewer:
  - maintain an ordered list of evidence items for the current proposal (primary first, then supporting in ranked order)
  - when the reviewer selects an evidence item in the quote list, update the viewer to show that item's page and location
  - when evidence selection changes programmatically (e.g., proposal selection changes), update both the quote list selection and the viewer location
  - the viewer and quote list must never be out of sync when the reviewer navigates between evidence items

- [x] **T087** Implement backend-to-viewer highlight coordinate conversion and evidence type rendering:
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

- [x] **T088** Implement honest fallback display for each evidence quality level:
  - for approximate highlights: show the approximate region with a visible label indicating it is approximate, not exact
  - for quote-plus-page fallback: display the quote text and page number with a visible label indicating this is fallback text evidence because highlighting was not available
  - explain missing exact highlight geometry explicitly rather than silently showing nothing
  - provide useful fallback actions such as opening the full PDF when scoped evidence is unavailable
  - never display approximate or fallback evidence as if it were exact highlighting

- [ ] **T089** Implement the figure-evidence viewer with crop-first display, attached caption, figure-derived warning/status markers, and full-page access.

- [x] **T090** Implement the review action area with:
  - accept
  - accept with edit
  - confirm no data
  - reject
  - next
  - previous
  - bulk accept visible subset
  - disable accept actions for blocked items or items without a reviewable proposal value

- [x] **T090a** Make bulk acceptance and edited acceptance behavior explicit and reviewer-safe:
  - confirm bulk acceptance against the currently visible filtered subset
  - present accept-with-edit as a distinct save-edited-value action rather than a vague duplicate of plain acceptance
  - keep confirmed-no-data resolution visibly distinct from rejection

- [x] **T090b** Auto-advance after explicit review decisions.
  - after `accept`, `accept_with_edit`, `confirm_no_data`, or `reject`, move to the next reviewable proposal when one exists
  - do not auto-advance on mere selection changes or partial edits

- [x] **T091** Implement keyboard shortcuts for next/previous navigation, accept current proposal, reject current proposal, focus edit control, and focus/open evidence viewer.
  - surface shortcuts in button tooltips or equivalent inline affordances on the relevant controls

- [x] **T091a** Extend keyboard support for fast sequential review.
  - add next and previous evidence shortcuts
  - preserve focus-edit behavior for quick accept-with-edit flows
  - keep shortcut handling safe when text inputs are focused

- [x] **T092** Implement unmatched, ambiguous, and duplicate-row-conflict inspection views in the UI.
  - identify the affected PDF, unresolved outcome, and rationale directly in the review workspace without requiring raw artifact inspection
  - keep this surface inspect-only for MVP rather than adding direct rematch or reassignment actions

- [x] **T093** Surface warnings/statuses, run-summary fields, reviewer-summary fields, provider/model names, and local-vs-cloud status consistently across the review UI and run-summary UI.
  - show coarse running progress as current stage plus current item when available
  - show provider mode and readiness truth without hiding disabled, unavailable, or degraded proposal generation
  - show both text model and vision model identifiers separately when both were used for a run
  - show configured parser choice, actual parser used, and any explicit fallback state when relevant
  - if zero verified cells have been reviewed, keep per-column lines visible only as evidence-coverage context with explicit wording that reviewer outcomes are not yet meaningful
  - do not show limited-review or similar warnings before their real triggering conditions are met
  - keep confirmed-no-data outcomes distinct from rejected-or-model-wrong outcomes in visible summaries and badges

- [x] **T093a** Tighten review-surface truth for parsing fallback and actionable counts.
  - surface degraded parsing, OCR fallback, duplicate-row conflicts, and evidence fallback in reviewer-visible summaries and diagnostics
  - keep actionable-only progress as the primary headline while preserving secondary totals for context

- [ ] **T094** Add frontend tests for grouped queue behavior, group-header summaries, group ordering rules, queue filtering, item ordering rules, nonlinear review, evidence type labeling (direct quote vs. inferred vs. calculation vs. approximate vs. fallback), exact-highlight vs. approximate-highlight vs. quote-plus-page fallback rendering, synchronized quote-list and viewer behavior, viewer navigation (previous/next page, jump to page), figure-evidence rendering with full-page access, run-summary display including text and vision model identifiers, no-data workflow rendering, picker-driven setup flow, markdown-bullet rationale rendering, click-to-populate replace behavior, overlong-text staging behavior, tooltip shortcut surfacing, and bulk-accept confirmation flow.

- [x] **T094a** Add frontend tests for the next reviewer-throughput contract.
  - actionable-only headline counts
  - config-path `Browse...` control
  - next or previous evidence navigation
  - auto-advance after explicit decisions
  - degraded parsing and provider-mode warning display in review-facing summaries

- [ ] **T095** Add Playwright e2e tests for the core review loop from proposal selection through grouped triage, group ordering, evidence interaction, no-data resolution, decision recording, picker-input staging, and summary updates.

- [x] **T095a** Add Playwright coverage for fast sequential review and explicit export flow.
  - evidence cycling and auto-advance after explicit decisions
  - manual export trigger from the review UI
  - highlighted-evidence review flow suitable for README screenshot capture

---

## Phase 8 — Export, audit log, unsupported-feature warnings, diagnostics, and final downloads

**Goal:** safely export only explicitly accepted changes, stay honest about the workbook fidelity boundary, and make the finished run inspectable.

- [x] **T096** Implement content-only XLSX export with changed-cell highlighting:
  - preserve cell contents only
  - apply only explicitly accepted changes
  - highlight changed cells
  - do **not** attempt to preserve formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, charts, shapes, or macros

- [x] **T096a** Keep export explicitly manual in the product workflow.
  - require the reviewer to trigger export from the review UI
  - ensure run completion and decision recording never auto-export implicitly

- [x] **T097** Implement best-effort detection and reporting of unsupported workbook features during export:
  - inspect the source workbook for unsupported advanced features when feasible
  - record warnings in diagnostics and logs
  - keep export behavior aligned with the content-only fidelity boundary
  - warn and ignore rather than trying to preserve unsupported features in MVP

- [x] **T098** Implement audit-log generation with at least:
  - row identifier
  - column identifier
  - old value
  - new value
  - proposal source
  - reviewer decision
  - decision timestamp
  - derive decision timestamps from persisted review-decision records when available instead of placeholder strings

- [x] **T099** Implement diagnostics JSON for:
  - matching failures
  - blocked outcomes
  - unclear / skipped / error outcomes
  - weak evidence and evidence recovery
  - unsupported workbook feature warnings
  - completed-with-warnings runs

- [x] **T100** Implement final download endpoints for:
  - updated workbook
  - audit log
  - `summaries/run_summary.json`
  - `summaries/reviewer_summary.json`
  - final downloadable run artifacts and relevant JSON outputs
  - keep the UI truthful about which downloads are actually ready versus not yet written

- [x] **T101** Add tests covering export integrity, content-only fidelity, changed-cell highlighting, accepted-only export behavior, unsupported-feature warnings, audit-log completeness, and completed-with-warnings semantics.

- [x] **T101a** Add tests for manual-export truth.
  - exports must not appear automatically after run completion alone
  - changed-cell highlighting must remain visible in the explicit export output
  - diagnostics should reflect manual-export timing truthfully

---

## Phase 9 — Orchestration, hardening, regression protection, and README updates

**Goal:** prove the full MVP workflow works end to end and stays inside the intended architecture boundary.

- [x] **T102** Implement the app-owned staged runner that executes the canonical pipeline stages under backend control while the API remains responsive enough for UI-driven launch, polling, diagnostics, and review-state loading.

- [x] **T103** Ensure interrupted or failed runs leave inspectable partial artifacts and that a new run creates a new run directory rather than resuming in place by default.

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

- [x] **T105** Add one realistic non-hermetic smoke test path for local LM Studio execution behind an opt-in flag.
  - use `tests/fixtures/tables/literature_fixture.xlsx` plus `tests/fixtures/papers/paper_1.pdf` as the canonical live-smoke fixture target
  - require at least one non-empty proposal with reviewer-usable evidence when the environment is correctly configured
  - when readiness fails, capture and report the explicit readiness error rather than treating the run as a normal success

- [x] **T105a** Add optional live cloud-provider smoke coverage only behind separate opt-in flags when cloud adapters are implemented.
  - use environment- or secret-based credentials only
  - keep cloud smoke coverage separate from the default local-first acceptance path
  - *Note: Cloud adapters are not implemented in this MVP; this task is complete as a no-op pending T051a cloud adapter work.*

- [x] **T106** Add a performance smoke test for representative small and medium batches so obvious regressions in parsing, retrieval, extraction, and review loading are caught.

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

- [ ] **T107c** Update `README.md` and related operator docs for the tightened workflow contract.
  - add guidance for writing strong schema descriptions
  - include at least one concrete schema snippet showing `column_name`, `description`, optional `field_type`, and categorical `allowed_values`
  - present schema-first empty-table operation as the normal/default mental model, not just a supported edge case
  - include numeric answer-form examples for `exact`, `range`, and `approximate`, such as `5`, `5-7`, `~5`, or estimated-from-graph cases
  - describe manual export explicitly instead of implying automatic export
  - include screenshot expectations for run setup, highlighted-evidence review workspace, and export or diagnostics views
  - add a lightweight trustworthiness checklist covering provider path, evidence labeling, fallback visibility, review-before-export, and audit artifacts

- [ ] **T107d** Add a reproducible screenshot-capture workflow for docs.
  - prefer Playwright-based capture tied to real UI states
  - keep the workflow lightweight and local-first
  - store or document the commands needed to refresh README screenshots consistently

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
- uses `proposals.jsonl` plus a proposal index or equivalent lookup structure as the canonical proposal persistence direction
- supports Verify mode end to end
- generates reviewer-outcome summaries for the MVP
- exports a new XLSX plus audit log within the explicit content-only fidelity boundary
- produces evidence with correct type labels (direct quote, inferred reasoning, calculation, approximate highlight, quote-plus-page fallback, `caption_grounded_figure_evidence`, `visual_interpretation_figure_evidence`) and ranks evidence by authority so the most authoritative item is primary
- produces exact quote highlights from page-text alignment when possible and degrades honestly with labeled fallback when it fails; fallback evidence is never presented as exact
- keeps the quote list and document viewer synchronized around the selected evidence item, with stable refocus on selection or zoom changes, previous/next/jump-to-page navigation, and figure-to-full-page context
- runs proactive figure review across all relevant extracted figures when a vision model is configured, with figure evidence allowed for any field type, including figure rescue of weak text-only proposals
- records text model and vision model identifiers separately in run artifacts, run summaries, and reviewer-visible context
- keeps loading, empty, warning, failure, and not-yet-reviewable states explicit and actionable in the operator workflow
- proves the canonical LM Studio path can generate at least one non-empty reviewable proposal with evidence on the canonical checked-in fixture set, or fails early with a clear readiness error
- keeps manual export explicit, actionable-only review counts primary, and parsing/provider fallback truth visible to reviewers
- ships with a truthful user-facing `README.md` and related operator docs that match the implemented commands, architecture, workflow, exports, and limitations
- stays inside the MVP architecture boundary defined by `spec.md`, `research.md`, and `plan.md`
