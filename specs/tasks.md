# Extract Structured Info from Papers — tasks.md

## Purpose

This is the canonical implementation checklist and status tracker for the MVP.

Use this file for checked/unchecked task state. Keep product behavior in `spec.md`, architecture in `plan.md`, rationale in `research.md`, operator workflow in `README.md`, and editing rules in `AGENTS.md`.

## Canonical Editing Rules

- Keep one checked/unchecked checklist only.
- Each task id appears exactly once in the canonical list.
- Preserve the section structure below when editing.
- Put temporary or historical notes in the appendix, not in the main checklist.
- Do not add new batch or phase frameworks unless explicitly asked.

## Current Repo-Truth Notes

Reality-checked on 2026-04-06 against current backend/frontend source, targeted tests, historical run artifacts, and live browser behavior.

- Implemented: resolved `config.snapshot.json` persistence and resolved input context.
- Implemented: lexical retrieval baseline with persisted per-cell retrieval artifacts.
- Implemented: prompt bundle loading plus persisted prompt identity/provenance.
- Implemented: stable non-UI automation entrypoint with machine-readable start/status/wait outputs.
- Implemented: provider/runtime diagnostics, artifact completeness summary, retrieval-failure diagnostics, and figure-review ROI diagnostics.
- Implemented in the latest pass: readiness-versus-capability truth split for provider status across backend artifacts, automation payloads, and UI summaries.
- Implemented in the latest pass: retrieval heuristic policy is now explicit in retrieval artifacts and summarized at the run level.
- Implemented in the latest pass: compact structured `run_stats.json` diagnostics with explicit stage/PDF/cell timings, repeated-work counters, provider/evidence rollups, and consistency coverage.
- Historical run bundles under `runs/` are useful examples but are not the canonical artifact-shape source of truth.

## Canonical Checklist

### Foundation / contracts / config

- [x] **T001** Create the base `backend/`, `frontend/`, and `tests/` project skeleton and root architecture note.
- [x] **T002** Define shared domain enums and JSON/Pydantic/TypeScript schemas for run state, matching, proposals, evidence, review, warnings, and provider locality.
- [x] **T003** Define stable identifiers for runs, PDFs, rows, cells, proposals, evidence, and review decisions.
- [x] **T004** Implement the stable run artifact bundle layout.
- [x] **T005** Implement shared artifact I/O helpers for JSON, JSONL, stable paths, lookups, and summary recomputation.
- [x] **T006** Define the canonical proposal schema.
- [x] **T007** Define the canonical evidence schema.
- [x] **T008** Define review-decision, run-summary, and reviewer-summary schemas.
- [x] **T009** Define the single JSON config schema for inputs, parsing, matching, retrieval, style profiles, providers, review, and export.
- [x] **T009a** Define the canonical provider-token policy shared across runtime validation, examples, docs, tests, and UI labels.
- [x] **T009b** Define operator-facing terminology parity rules for provider, parser, model, Verify mode, Eval mode, and run states.
- [x] **T009c** Extend the config contract with explicit Eval-mode semantics.
- [x] **T010** Resolve config defaults into one effective runtime config before work starts.
- [x] **T011** Create `config.example.json` as a minimal but complete example config.
- [x] **T011a** Add provider-contract example coverage for checked-in configs and tests.
- [x] **T012** Implement config/path validation and required metadata/schema validation.
- [x] **T012a** Implement run-start preflight and readiness validation for the configured execution path.
- [x] **T013** Snapshot the resolved config into run artifacts.
- [x] **T013a** Persist a resolved input-summary artifact early enough for readiness-failed and early-failed runs.
- [x] **T013b** Persist stable run-identity metadata needed by downstream eval tooling.
- [x] **T013c** Add explicit run-bundle schema-version fields for run, proposal, and evidence artifacts.
- [x] **T014** Audit, normalize, and document the canonical deterministic fixture corpus under `tests/fixtures/`.
- [x] **T015** Set up backend unit/integration/contract test tooling with provider stubs/fakes and fixture helpers.
- [x] **T015a** Add contract-parity tests for provider naming and config semantics.
- [x] **T016** Set up frontend test tooling and Playwright e2e scaffolding.
- [x] **T016a** Harden the Playwright harness so fixture preparation and server startup are shell-robust.
- [x] **T108** Clean up config and naming truth for retrieval-related settings.
- [x] **T108a** Canonicalize retrieval config naming so it describes the implemented lexical baseline truthfully.
- [x] **T108b** Normalize legacy retrieval aliases while persisting canonical values.
- [x] **T108c** Add config naming tests for canonicalization and unknown-value failure behavior.
- [x] **T110** Externalize important prompts while preserving deterministic prompt identity/provenance.
- [x] **T110a** Move extraction and style-profile system prompts into dedicated prompt files.
- [x] **T110b** Implement prompt loading/composition helpers with deterministic failure semantics.
- [x] **T110c** Extend prompt identity/provenance in artifacts.
- [x] **T110d** Add prompt externalization tests.

### Run lifecycle and inputs

- [x] **T017** Implement spreadsheet loading for CSV and XLSX inputs.
- [x] **T018** Implement schema loading from workbook or separate schema file.
- [x] **T019** Implement table normalization and required metadata-column validation.
- [x] **T020** Implement cell-eligibility classification.
- [x] **T020a** Keep already-filled cells outside Verify mode diagnostics-only or out of scope.
- [x] **T021** Implement Verify-mode semantics so already-filled cells become eligible when Verify mode is enabled.
- [x] **T021a** Implement Eval-mode setup semantics from the completed gold table.
- [x] **T022** Implement run lifecycle state transitions.
- [x] **T023** Implement run creation and inspection API endpoints.
- [x] **T023a** Keep run creation UI-driven while execution runs under app-owned backend control.
- [x] **T023b** Support picker-driven input overrides while preserving config-file authority.
- [x] **T023b1** Materialize browser-selected files/directories into staged backend-readable input handles.
- [x] **T023c** Implement active-run auto-refresh and cancellation support end to end.
- [x] **T024** Add tests for valid-input readiness, metadata rejection, missing-path rejection, placeholder handling, and Verify mode behavior.
- [x] **T024a** Add tests covering readiness and startup truth.
- [x] **T024b** Add tests covering path-resolution and picker-driven setup truth.
- [x] **T024c** Add tests for provider hard-fail truth and warning semantics.
- [x] **T024d** Add backend tests for Eval-mode validation and staging.
- [x] **T102** Implement the app-owned staged runner that executes the canonical pipeline while keeping the API responsive.
- [x] **T103** Ensure interrupted or failed runs keep inspectable partial artifacts and that reruns create new run directories.
- [x] **T117a** Add a stable non-UI automation entrypoint for tooling while preserving browser-first operator workflow.
- [x] **T117b** Support optional wait-until-terminal behavior and deterministic machine-readable terminal output.
- [x] **T117c** Add hermetic tests for automation start/wait/status and failure reporting.

### Parsing and normalized document contract

- [x] **T025** Define the internal `ParsedDocument` contract.
- [x] **T026** Implement the parser adapter interface and register Docling as the main parser.
- [x] **T026a** Implement explicit parser-selection and fallback-policy handling.
- [x] **T027** Implement the low-level PDF abstraction using `pypdfium2` / PDFium.
- [x] **T028** Integrate OCR fallback for scanned or text-inaccessible PDFs.
- [x] **T029** Persist parser-native outputs and normalized parsed-document artifacts under stable run paths.
- [x] **T030** Generate page-render artifacts and crop helpers for text evidence, figure evidence, and PDF review.
- [x] **T031** Add per-PDF parser diagnostics, including parser path, OCR use, and major extraction gaps.
- [x] **T032** Add tests covering clean parse, OCR fallback, normalized parsed-document output, and stored page/crop artifacts.

### Matching

- [x] **T033** Implement grounded paper-metadata extraction from parsed documents.
- [x] **T034** Implement deterministic matching scoring using publication metadata signals.
- [x] **T034a** Rebalance deterministic matching so exact and near-exact signals dominate title similarity.
- [x] **T035** Implement limited fallback adjudication only for plausible ambiguous cases.
- [x] **T036** Implement final match outcome assignment.
- [x] **T037** Implement duplicate-row conflict detection that blocks conflicting PDFs from extraction.
- [x] **T038** Persist matching artifacts and reasoning summaries.
- [x] **T038a** Persist duplicate-row conflicts as first-class diagnostic records.
- [x] **T039** Expose unmatched, ambiguous, and duplicate-row-conflict records through API endpoints.
- [x] **T040** Add tests for deterministic match success, ambiguous blocking, unmatched behavior, and duplicate-row conflicts.
- [x] **T040a** Add tests for the tightened matching heuristic contract.

### Retrieval

- [x] **T041** Define the style-profile schema.
- [x] **T041a** Extend the schema contract with optional field typing.
- [x] **T042** Implement per-column preprocessing that produces structured style profiles.
- [x] **T042a** Make style-profile preprocessing helper-only and empty-table-safe.
- [x] **T043** Persist style profiles under `style_profiles/` and restrict them to output-form guidance.
- [x] **T044** Enforce the no-leakage baseline for style profiles.
- [x] **T044a** Tighten extraction request construction against schema leakage.
- [x] **T045** Create MVP retrieval chunks for the supported parsed-document content types.
- [x] **T046** Implement contextualized retrieval text while preserving separate source-preserving display text.
- [x] **T047** Implement MVP retrieval assembly defaults.
- [x] **T047a** Remove dead `retrieval.chunk_size` config from schema, examples, docs, and tests.
- [x] **T047b** Implement deterministic recall rescue for `unclear` first-pass results.
- [x] **T047c** Add optional config-controlled whole-document mode.
- [x] **T048** Persist retrieval artifacts and diagnostics so selected chunks and review text remain inspectable.
- [x] **T048a** Cache retrieval chunks and term statistics per parsed PDF so repeated cell extraction does not rebuild the same retrieval index.
- [x] **T049** Add tests covering style profiles, no raw-example leakage, typed chunks, retrieval-text/display-text separation, and retrieval defaults.
- [x] **T049a** Add tests for schema-first extraction and optional field typing.
- [x] **T049b** Add tests for bounded recall rescue and optional whole-document mode.
- [x] **T049c** Add tests covering retrieval-index reuse and repeated-work counter truth.
- [x] **T111** Make schema-aware retrieval heuristics transparent and inspectable at the run level.
- [x] **T111a** Define a small explicit retrieval-heuristic policy contract.
- [x] **T111b** Persist heuristic policy details in retrieval artifacts.
- [x] **T111c** Surface heuristic-policy usage summaries in run outputs.
- [x] **T111d** Add heuristic-policy tests.
- [x] **T112** Add an opt-in experimental hybrid retrieval benchmark path while keeping lexical retrieval as default.
- [x] **T112a** Add a retrieval-mode toggle in config with lexical default baseline.
- [x] **T112b** Implement the hybrid retrieval path behind explicit opt-in mode.
- [x] **T112c** Persist and expose retrieval mode in run artifacts and summaries.
- [x] **T112d** Add hybrid-mode tests.

### Extraction and provider behavior

- [x] **T050** Implement the provider abstraction and capability-probe model for structured-output support.
- [x] **T050b** Enforce provider-unavailable hard-fail semantics at run start.
- [x] **T051** Implement LM Studio localhost API integration as the initial provider path.
- [x] **T051b** Add app-owned LM Studio model-management with separate working-budget versus load-context config, compatible loaded-model reuse, API-driven load before extraction, and persisted load diagnostics.
- [x] **T051a** Implement optional cloud-provider adapter slots behind the same provider interface.
- [x] **T052** Implement provider error handling and structured-output failure policy for LM Studio.
- [x] **T052a** Make provider-mode truth explicit across runtime artifacts and operator surfaces.
- [x] **T052b** Tighten structured-output recovery to one bounded ladder.
- [x] **T052c** Normalize warning and status propagation end to end.
- [x] **T052d** Distinguish readiness and capability failure classes end to end.
- [x] **T053** Implement the extraction request builder for LM Studio structured JSON.
- [x] **T053a** Request concise markdown-bullet rationale when rationale is returned.
- [x] **T054** Build the structured JSON schema/request payload for the text-model path.
- [x] **T055** Build the structured JSON schema/request payload for the vision-model path.
- [x] **T056** Implement proposal/evidence serialization using the shared artifact layer.
- [x] **T056a** Migrate canonical proposal persistence to `proposals.jsonl` plus proposal index.
- [x] **T056b** Extend proposal and evidence metadata for downstream eval compatibility.
- [x] **T056c** Preserve eval-consumable evidence and page-text-compatible artifacts from the main run bundle without requiring downstream imports from main-app code.
- [x] **T056d** Remove repeated full-log rereads from proposal persistence while keeping proposal lookup artifacts truthful.
- [x] **T057** Implement the per-target-cell extraction orchestrator.
- [x] **T057a** Add field-aware extraction handling for long-text targets.
- [x] **T057b** Add schema-aware field-type handling to extraction and proposal contracts.
- [x] **T057c** Enforce Eval-mode anti-leakage in extraction orchestration.
- [x] **T058** Implement canonical proposal-state handling.
- [x] **T058a** Enforce the anti-guessing rule in extraction adjudication.

### Evidence and figure review

- [x] **T058b** Fix direct-evidence support semantics.
- [x] **T059** Implement text-evidence anchoring and highlight production with honest fallback.
- [x] **T059a** Support multiple quote evidence items for one proposal when genuinely needed.
- [x] **T060** Implement the single narrow evidence-recovery pass.
- [x] **T061** Keep weak-but-reviewable proposals available when quote-plus-page evidence exists.
- [x] **T062** Implement proactive figure review when a vision model is configured.
- [x] **T062a** Split figure evidence into reviewer-visible subtypes.
- [x] **T062b** Tighten figure-evidence ranking semantics.
- [x] **T062c** Implement figure-reference-aware candidate shortlisting.
- [x] **T062d** Implement caption-plus-reference ranking for targeted figure calls.
- [x] **T062e** Implement evidence-aware vision triggering for all fields.
- [x] **T063** Build the figure-fallback input package.
- [x] **T063a** Pass figure-referencing textual context into vision requests.
- [x] **T064** Persist figure-derived evidence records distinctly from text evidence.
- [x] **T065** Implement reviewer-facing support-label mapping and evidence-type labeling.
- [x] **T066** Ensure Verify mode uses the same extraction path for already-filled cells.
- [x] **T067** Add tests covering structured-output parsing, provider failure handling, proposal/evidence serialization, blocked and unclear outcomes, evidence ranking, evidence typing, fallback chains, figure review, text/vision config, and Verify mode extraction.
- [x] **T067a** Add tests for the tightened extraction-truth contract.
- [x] **T067b** Add backend tests for Eval-mode leakage protection and artifact emission.
- [x] **T067c** Add backend tests for text-guided figure shortlisting.
- [x] **T067d** Add backend tests for figure-derived approximate numeric proposals.
- [x] **T067e** Add tests for structured-output negotiation and capability-truth classification.
- [x] **T067f** Add contract tests proving eval-mode run bundles remain directly loadable by the separate eval tool.

### Verification and CI

- [x] **T118** Add minimal CI coverage for backend, frontend, and artifact-contract regression checks.

### Review UI

- [x] **T068** Implement normalized warning and status surfaces for review.
- [x] **T068a** Surface degraded parsing, duplicate conflicts, and evidence-fallback truth consistently.
- [x] **T069** Implement proposal-list APIs with the MVP filter set.
- [x] **T070** Implement proposal-detail API payloads.
- [x] **T071** Implement review-asset serving endpoints.
- [x] **T072** Implement review-decision persistence.
- [x] **T073** Preserve prior proposal state and review history for auditability.
- [x] **T074** Implement guarded bulk-accept semantics limited to the visible filtered subset.
- [x] **T075** Implement progress counters and decision-breakdown aggregation.
- [x] **T075a** Distinguish confirmed-no-data outcomes from rejected/model-wrong outcomes.
- [x] **T075b** Make actionable-only counts the default review-progress source.
- [x] **T076** Implement run-summary generation and persistence.
- [x] **T076b** Extend run-summary and reviewer-summary contracts for Eval-mode truth.
- [x] **T077** Implement reviewer-outcome summary generation as a pure function of proposals and decisions.
- [x] **T078** Support summary recomputation from artifact files.
- [x] **T078a** Add summary-integrity checks for inconsistent counts and premature warning flags.
- [x] **T079** Ensure export candidate selection uses only explicitly accepted proposals.
- [x] **T080** Add tests covering review decision recording, audit history, bulk acceptance, warning/status semantics, review assets, and summary recomputation.
- [x] **T080a** Add tests for warning/status truth across artifacts, APIs, and summaries.
- [x] **T081** Build the React frontend shell with Run and Review views.
- [x] **T082** Implement the concise run summary view.
- [x] **T082a** Implement a run-launch and setup context surface in the UI.
- [x] **T082b** Add a `Browse...` control next to the config-path text field.
- [x] **T083** Implement the three-pane review workspace.
- [x] **T083a** Implement grouped-queue client state and grouped rendering behavior.
- [x] **T084** Implement the proposal queue pane with the full MVP filter set, stable selection behavior, and explicit ordering rules.
- [x] **T084a** Make actionable-only progress explicit in the review workspace.
- [x] **T085** Implement the proposal detail pane.
- [x] **T086** Implement the evidence viewer pane for annotated evidence inspection plus browser-realistic reading support.
- [x] **T086a** Synchronize the quote list and document viewer.
- [x] **T086b** Preserve ordinary PDF-viewer fallback affordances from the review pane.
- [x] **T086c** Strengthen evidence navigation and highlight behavior.
- [x] **T087** Implement backend-to-viewer highlight coordinate conversion and evidence-type rendering.
- [x] **T088** Implement honest fallback display for each evidence quality level.
- [x] **T089** Implement the figure-evidence viewer with crop-first display and full-page access.
- [x] **T090** Implement the review action area.
- [x] **T090a** Make bulk acceptance and edited acceptance behavior explicit and reviewer-safe.
- [x] **T090b** Auto-advance after explicit review decisions.
- [x] **T091** Implement keyboard shortcuts for review workflow actions.
- [x] **T091a** Extend keyboard support for fast sequential review.
- [x] **T092** Implement unmatched, ambiguous, and duplicate-row-conflict inspection views.
- [x] **T093** Surface warnings, summaries, provider/model names, and locality truth consistently across the UI.
- [x] **T093a** Tighten review-surface truth for parsing fallback and actionable counts.
- [x] **T093b** Surface Eval-mode context and artifact truth across the UI.
- [x] **T094** Add frontend tests for MVP-core reviewer workflow behavior.
- [x] **T094a** Add frontend tests for the reviewer-throughput contract.
- [x] **T094b** Add frontend tests for Eval-mode run-summary and setup truth.
- [x] **T094c** Add extended frontend regression coverage beyond MVP-core.
- [x] **T095** Add bounded Playwright e2e coverage for the hermetic core review loop.
- [x] **T095a** Add Playwright coverage for fast sequential review and explicit export flow.
- [x] **T095b** Add expanded Playwright coverage beyond MVP-core.

### Export and artifacts

- [x] **T096** Implement content-only XLSX export with changed-cell highlighting.
- [x] **T096a** Keep export explicitly manual in the product workflow.
- [x] **T097** Detect and report unsupported workbook features during export.
- [x] **T098** Implement audit-log generation.
- [x] **T099** Implement diagnostics JSON for matching failures, blocked outcomes, weak evidence, unsupported workbook features, and warning-state runs.
- [x] **T100** Implement final download endpoints for workbook, audit log, summaries, and downloadable run artifacts.
- [x] **T101** Add tests covering export integrity, content-only fidelity, highlighting, accepted-only export behavior, unsupported-feature warnings, audit-log completeness, and completed-with-warnings semantics.
- [x] **T101a** Add tests for manual-export truth.
- [x] **T113** Add an artifact completeness/parity summary for main-app runs.

### Diagnostics / eval / observability

- [x] **T109** Strengthen measurement-first run instrumentation.
- [x] **T109a** Add run-level stage timing capture.
- [x] **T109b** Add per-PDF timing and counts.
- [x] **T109c** Add per-cell timing capture.
- [x] **T109d** Add retrieval repeated-work and chunk counters.
- [x] **T109e** Add provider and evidence counters into run stats.
- [x] **T109f** Persist a compact structured run-stats artifact and expose it as a first-class run output.
- [x] **T109g** Add run-stats tests for structure and consistency.
- [x] **T114** Persist compact provider/runtime failure diagnostics.
- [x] **T115** Add proposal-level retrieval-failure diagnostics.
- [x] **T116** Persist figure-review ROI diagnostics at per-cell and per-run level.

### Docs / verification / screenshots

- [x] **T104** Add hermetic end-to-end tests using stub providers over the canonical fixture corpus.
- [x] **T105** Add an opt-in realistic local LM Studio smoke-test path.
- [x] **T105a** Keep optional cloud-provider smoke coverage gated behind separate opt-in flags until a concrete cloud provider adapter is implemented.
- [x] **T106** Add a performance smoke test for representative small and medium batches.
- [x] **T107** Update `README.md` with real MVP run instructions, workflow, artifacts, and limitations.
- [x] **T107a** Preserve user-facing onboarding in `README.md` while removing obsolete commands and flows.
- [x] **T107b** Keep `README.md` aligned with the real primary happy path.
- [x] **T107c** Update `README.md` and related operator docs for the tightened workflow contract.
- [x] **T107d** Add a reproducible screenshot-capture workflow for docs.
- [x] **T107e** Update `README.md` and related operator docs for Eval mode.

## Appendix: Historical Notes (Non-Canonical)

- The previous batch/phase framing has been removed from the canonical checklist.
- Historical implementation audits and pass-specific notes should live in supporting docs such as `docs/spec-implementation-audit.md`.
- If future work needs temporary sequencing guidance, keep it outside the canonical checklist or in a clearly labeled appendix.
