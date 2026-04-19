# Extract Structured Info from Papers — tasks.md

## Purpose

This is the canonical implementation checklist and status tracker for the monorepo.

Use this file for checked/unchecked task state only. Keep behavior and contracts in the owning files under `product/`, `tools/`, `contracts/`, `architecture/`, and `process/`. Keep supportive planning in `plan.md`, operator workflow in `README.md`, and editing rules in `AGENTS.md`.

## Canonical Editing Rules

- Keep one checked/unchecked checklist only.
- Each task id appears exactly once in the canonical list.
- Preserve the section structure below when editing.
- Put temporary or historical notes in the appendix, not in the main checklist.
- Do not add new batch or phase frameworks unless explicitly asked.

## Spec-System Alignment

- Main-app product behavior is owned by `product/overview.md`, `product/main-app.md`, and `product/review-workflow.md`.
- Eval behavior is owned by `tools/eval.md`.
- Optimizer behavior is owned by `tools/optimizer.md`.
- Shared cross-tool contracts are owned by `contracts/`.
- Monorepo structure and integration are owned by `architecture/`.
- Change and verification policy are owned by `process/`.
- Implementation status lives here only.

## Current Repo-Truth Notes

Reality-checked on 2026-04-06 against current backend/frontend source, targeted tests, historical run artifacts, and live browser behavior.

Treat this section as a point-in-time implementation note. If it becomes stale after a behavior change, refresh it in the same pass or remove outdated lines rather than letting it become a second drifting spec surface.

- Implemented: resolved `config.snapshot.json` persistence and resolved input context.
- Implemented: lexical retrieval baseline with persisted per-cell retrieval artifacts.
- Implemented: prompt bundle loading plus persisted prompt identity/provenance.
- Implemented: stable non-UI automation entrypoint with machine-readable start/status/wait outputs.
- Implemented: provider/runtime diagnostics, artifact completeness summary, retrieval-failure diagnostics, and figure-review ROI diagnostics.
- Implemented in the latest pass: readiness-versus-capability truth split for provider status across backend artifacts, automation payloads, and UI summaries.
- Implemented in the latest pass: retrieval heuristic policy is now explicit in retrieval artifacts and summarized at the run level.
- Implemented in the latest pass: compact structured `run_stats.json` diagnostics with explicit stage/PDF/cell timings, repeated-work counters, provider/evidence rollups, and consistency coverage.
- Implemented in the latest pass: compact eval-facing extraction and retrieval provenance is now emitted in stable summary artifacts and automation payloads.
- Implemented in the latest pass: parser-first metadata and front-matter extraction is separated from the general extraction lane with explicit proposal provenance and failure attribution.
- Implemented in the latest pass: style-profile behavior is explicit per run mode and persisted as benchmark-safety provenance.
- Implemented in the latest pass: parser-cache reuse is wired into the staged runner and summarized in stable run artifacts.
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
- [x] **T033a** Split parser-first metadata and front-matter extraction from the general content-extraction lane and persist metadata-specific ambiguity diagnostics.
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
- [x] **T044b** Make style-profile behavior explicit per run mode and persist benchmark-safety provenance in stable summaries.
- [x] **T029a** Reuse persisted parsed-document bundles through a bounded parser cache keyed by PDF content, parser settings, parser runtime fingerprint, and parse-artifact contract version.
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

### Companion tool - eval

- [x] **E001** Create the base package layout for the evaluator CLI and supporting modules.
- [x] **E002** Implement CLI argument parsing for `evaluate` with `--run`, `--runs-root`, repeated `--run`, `--gold`, optional `--gold-sheet`, optional `--schema`, and `--out`.
- [x] **E003** Implement output-directory creation and run-level output path helpers.
- [x] **E004** Define evaluator-owned typed contracts for loaded run metadata, proposal records, evidence records, gold cells, scored cells, and run summaries.
- [x] **E005** Implement main-app run bundle discovery for one run, a runs root, and an explicit run list.
- [x] **E006** Implement contract validation for required main-app artifact files and the published stable eval join fields.
- [x] **E007** Implement proposal loading from `proposals/proposals.jsonl`.
- [x] **E008** Implement loading of run metadata from `run.json`, `config.snapshot.json`, `inputs/input_summary.json`, and `summaries/run_summary.json` when present.
- [x] **E009** Implement a loader or adapter path for evidence data when proposals do not already carry enough evidence detail.
- [x] **E009a** Load canonical main-app per-evidence JSON artifacts when sidecar evidence files are absent.
- [x] **E009b** Reconstruct page-text-compatible source text from persisted parsed-document artifacts when page-text sidecars are absent.
- [x] **E010** Implement explicit contract errors for missing required scoring fields, especially missing stable join identifiers such as `row_id`, `column_name`, and `cell_id`.
- [x] **E011** Implement gold CSV loading.
- [x] **E012** Implement gold XLSX loading with single-sheet selection per invocation and a documented default first-sheet behavior when no sheet is specified.
- [x] **E013** Implement consistent gold-present versus gold-empty detection.
- [x] **E014** Implement field-type resolution precedence across proposal metadata, schema metadata, and evaluator fallbacks, including field or column scoring-policy overrides for text fields.
- [x] **E015** Implement boolean normalization.
- [x] **E016** Implement categorical normalization with alias mapping and `allowed_values` support.
- [x] **E017** Implement numeric normalization for exact, range, and approximate forms, plus numeric tolerance resolution with per-column override and global defaults.
- [x] **E018** Implement deterministic boolean comparison.
- [x] **E019** Implement deterministic categorical comparison.
- [x] **E020** Implement deterministic numeric comparison with binary headline correctness under the resolved tolerance policy plus diagnostic error fields.
- [x] **E021** Implement per-cell scoring orchestration for structured fields on gold-present cells only, consuming stable main-app identifiers rather than derived row-index joins.
- [x] **E022** Write per-cell outputs for one run in JSONL and CSV.
- [x] **E023** Implement per-run aggregation for structured metrics and diagnostic counts.
- [x] **E024** Write per-run `run_summary.json` and `run_summary.csv`.
- [x] **E025** Implement batch evaluation over a runs root and repeated explicit run paths.
- [x] **E026** Normalize run metadata into one flat comparison row schema.
- [x] **E027** Include core run metadata columns such as run id, mode, text model id, vision model id, parser identity or version, prompt version or hash, schema hash or version, and config hash.
- [x] **E028** Implement the minimal evidence anchor contract check using page plus quote text, and quote locatability when persisted page text or equivalent text evidence is available.
- [x] **E028a** Add bounded normalized-text fallback so parsed-document text can validate anchors without overstating confidence.
- [x] **E029** Implement `anchor_valid_rate`, counting only fully validated anchors and distinguishing evidence-present-but-unvalidated as a separate diagnostic state.
- [x] **E030** Implement `correct_and_anchored_rate`.
- [x] **E031** Implement optional structured-field support proxy evaluation behind a narrow internal interface.
- [x] **E032** Implement diagnostic counting for gold-empty proposals, including `filled_on_gold_empty_count`.
- [x] **E033** Implement batch comparison row generation with one row per run.
- [x] **E034** Write the canonical batch comparison CSV.
- [x] **E035** Write batch comparison XLSX from the same normalized rows.
- [x] **E036** Write batch comparison Parquet from the same normalized rows.
- [x] **E037** Implement `compare` command support for rebuilding comparison artifacts from per-run summaries.
- [x] **E038** Define the judge request and response schema for text-field scoring under a judge-by-default policy for text fields.
- [x] **E039** Implement judge prompt construction with bounded field context only.
- [x] **E040** Implement a judge adapter with fixed model configuration, temperature 0, and bounded fallback from `json_schema` to `json_object` to prompt-only JSON mode.
- [x] **E041** Implement text-field normalization helpers needed before judge invocation and deterministic override support for highly standardized text columns.
- [x] **E042** Implement `text_accuracy` under the configured text scoring policy, with judge-backed scoring by default and deterministic override where configured.
- [x] **E043** Persist judge metadata per scored text cell, including judge model id, prompt version or hash, and temperature.
- [x] **E044** Write judge records to a separate inspectable artifact such as `judge_records.jsonl`.
- [x] **E045** Ensure judge use is limited to text fields by default, while allowing explicit field or column deterministic override for standardized text fields.
- [x] **E046** Add CLI flags or config inputs for fixed judge model selection without widening the tool into a broad config framework.
- [x] **E047** Add contract validation for eval-mode provenance fields such as gold and masked table hashes and snapshot paths when runs are marked as eval runs.
- [x] **E048** Fail fast when the published stable join contract is missing or inconsistent, and document the contract gap clearly.
- [x] **E048a** Fail fast on unsupported main-app artifact schema versions while preserving bounded backward compatibility for known versions.
- [x] **E049** Implement unit tests for boolean, categorical, and numeric normalization.
- [x] **E050** Implement unit tests for deterministic comparators.
- [x] **E051** Implement unit tests for gold-present and gold-empty detection.
- [x] **E052** Implement unit tests for evidence anchor validation, including locatable versus present-but-unvalidated quote cases.
- [x] **E052a** Add tests for canonical main-app evidence-directory loading and parsed-document page-text fallback.
- [x] **E053** Implement contract tests for required main-app artifact fields, worksheet selection behavior, and failure messages.
- [x] **E054** Implement end-to-end tests for scoring one run.
- [x] **E055** Implement end-to-end tests for scoring multiple runs and writing batch comparison outputs.
- [x] **E055a** Add contract tests proving a main-app-style eval-mode run bundle remains loadable and anchor-validatable.
- [x] **E056** Implement mocked judge tests for text scoring under judge-by-default behavior and deterministic text override behavior.
- [x] **E057** Write the initial `README.md` or operator documentation once actual commands, output paths, and examples exist.
- [x] **E058** Document the published input artifact contract expected from the main app in operator-facing docs, including stable join identifiers and single-sheet XLSX behavior.
- [x] **E059** Review the spec set together for consistency after material changes.
- [x] **E060** Keep an explicit visible note in docs about the required stable join-key contract between the main app and the eval repo, with `row_index` treated only as fallback or debug context.
- [x] **E061** Make LM Studio the default local-first judge provider through its OpenAI-compatible API, with `qwen/qwen3.5-35b-a3b` as the default configured judge model for MVP.
- [x] **E062** Persist full judge provenance for judge-backed cells and judge records, including provider, configured judge model, resolved runtime judge model, prompt version or hash, verdict, and input hash.
- [x] **E063** Tighten `README.md` and operator docs so they clearly explain what the eval repo does, expected main-app inputs, one-run and many-run evaluation workflows, headline metrics, diagnostic metrics, and current limitations.
- [x] **E064** Add explicit operator guidance and examples for the LM Studio judge path, including configuration, the default judge model `qwen/qwen3.5-35b-a3b`, and how persisted judge metadata should be interpreted.
- [x] **E065** Add optional machine-readable JSON stdout completion mode for `evaluate` and `compare`, while keeping file artifacts canonical.
- [x] **E066** Add tests and docs for JSON stdout mode, including payload schema tagging and key produced artifact paths.
- [x] **E067** Document judge fallback behavior and the additional judge-failure and judge-response-mode diagnostic metrics exposed in run summaries.
- [x] **E068** Add minimal CI coverage for loader, scorer, and contract-regression tests.
- [x] **E069** Add optional dual-judge support, explicit `scored` or `unscored_reason` summary truth, and scored-column filtering for metadata-safe optimizer consumption.
- [x] **E070** Make headline correctness content-focused while keeping metadata correctness as an explicit secondary metric.
- [x] **E071** Propagate extraction-lane and failure-attribution provenance from main-app proposals into scored cells and run summaries.
- [x] **E072** Add evidence-grounded and failure-attribution aggregate metrics for downstream optimizer diagnostics.

### Companion tool - optimizer

- [x] **O001** Create base package layout for optimizer CLI and modules.
- [x] **O002** Implement CLI parsing for `optimize`, `evaluate-candidate`, `validate-best`, and `summarize`.
- [x] **O002a** Implement fast `preflight` CLI coverage for config, path, and contract validation without running a study.
- [x] **O003** Implement optimizer config loading and validation.
- [x] **O004** Define typed contracts for settings, benchmarks, search space, candidate bundles, candidate results, round summaries, and best-candidate records.
- [x] **O005** Implement benchmark manifest loading for `smoke`, `dev`, and `holdout` style splits.
- [x] **O006** Implement split validation so `dev` and `holdout` cannot be the same benchmark id.
- [x] **O007** Implement explicit search-space validation for bounded optimizer-owned fields.
- [x] **O008** Define baseline candidate contract and validation rules.
- [x] **O009** Implement candidate hashing, lineage fields, and immutable bundle materialization.
- [x] **O010** Implement candidate-owned resolved overlay generation for optimizer-controlled fields.
- [x] **O011** Implement main-app launcher integration via stable automation command and run-artifact discovery.
- [x] **O012** Implement eval-app launcher integration via stable CLI command and eval-summary discovery.
- [x] **O013** Implement candidate-level result records with lineage, metric groups, runtime, and decision fields for both study modes.
- [x] **O014** Implement experiment-level artifact writes (`experiment.json`, candidate manifests, `results.csv`, `results.jsonl`, summary files, and current compare-study diagnostics artifacts).
- [x] **O015** Add tests for config loading, search-space handling, benchmark split checks, and candidate hashing.
- [x] **O016** Add mocked subprocess contract tests for main-app and eval-app launch flows.
- [x] **O017** Implement deterministic-first candidate generation for bounded per-round batches.
- [x] **O017a** Strengthen deterministic candidate generation so bounded batches cover multi-knob search combinations more truthfully than one-axis-only mutation.
- [x] **O018** Implement duplicate suppression across round proposals and prior seen candidates.
- [x] **O019** Implement mode-aware study control flow with compare single-pass and optimize multi-round behavior.
- [x] **O020** Implement primary-metric comparison rule for promotion decisions.
- [x] **O021** Implement guardrail evaluation for evidence, runtime, and null-failure constraints.
- [x] **O022** Implement explicit deterministic pre-promotion checks as a dedicated acceptance gate stage.
- [x] **O023** Implement structured promotion or rejection decision reasons in candidate records.
- [x] **O024** Implement best-candidate tracking and `best_candidate.json` updates.
- [x] **O025** Implement compare summaries with ranked fixed-candidate outcomes, winner materialization, and candidate-level explanation artifacts for scored and unscored candidates.
- [x] **O025a** Harden compare-mode empty-results and missing-winner handling so no-winner outcomes produce explicit summaries rather than file errors.
- [x] **O026** Complete mode-specific plotting contract coverage, including bounded parameter sweep views where relevant.
- [x] **O027** Add focused unit tests for acceptance logic, guardrail failures, and tie-breaking paths.
- [x] **O028** Add smoke-level end-to-end tests for compare and optimize flows on tiny mocked benchmarks.
- [x] **O029** Ensure optimize holdout validation uses final promoted incumbent semantics only and not generic best-score ranking.
- [x] **O030** Implement separate holdout validation artifacts and summary records.
- [x] **O031** Implement `summarize` to regenerate mode-appropriate plots from persisted artifacts.
- [x] **O032** Add richer experiment summaries for lineage and promotion-history rollups.
- [x] **O033** Add explicit contract checks for required metric names and required eval-summary fields.
- [x] **O034** Add explicit contract checks for required main-app run metadata relevant to provenance.
- [x] **O035** Add end-to-end tests for holdout validation and summarize regeneration.
- [x] **O036** Maintain README operator documentation aligned with current behavior.
- [x] **O037** Keep spec stack consistency across the unified root spec system.
- [x] **O038** Define optional proposer request or response schema constrained to existing search surface.
- [x] **O039** Implement LM Studio-backed proposer adapter for bounded deltas.
- [x] **O040** Persist proposer prompts or responses and applied candidate deltas for audit.
- [x] **O041** Route proposer outputs through the same candidate validation, hashing, and acceptance flow.
- [x] **O042** Add tests for invalid proposer outputs, duplicate handling, and proposer audit persistence.
- [x] **O043** Document proposer feature as optional and disabled by default.
- [x] **O044** Implement fixed-candidate-set loading or validation for compare mode with shared candidate contract.
- [x] **O045** Implement optional bounded confirmation-rerun policy hook for top candidates, disabled by default.
- [x] **O046** Add minimal CI coverage for preflight, launch-contract, and study-regression tests.
- [x] **O047** Add explicit scored or unscored result truth, report generation, richer plots, and tie-break config validation for optimizer-facing experiment reporting.
- [x] **O048** Persist progressive compare and optimize summaries so interrupted studies still expose truthful current state.
- [x] **O049** Separate raw best, eligible winner, and provisional winner semantics in optimizer summaries and reports.
- [x] **O050** Refresh overnight manifest and report artifacts incrementally after each completed stage.

## Appendix: Historical Notes (Non-Canonical)

- The previous batch/phase framing has been removed from the canonical checklist.
- Historical implementation audits and pass-specific notes should live in supporting docs such as `docs/spec-implementation-audit.md`.
- If future work needs temporary sequencing guidance, keep it outside the canonical checklist or in a clearly labeled appendix.
