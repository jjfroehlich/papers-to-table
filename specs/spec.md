# Extract Structured Info from Papers - spec.md

## Summary

Extract Structured Info from Papers helps a researcher turn a folder of scientific PDFs plus a structured spreadsheet into reviewed spreadsheet updates.

The system matches PDFs to spreadsheet rows, proposes values for schema-defined target cells using grounded evidence from the papers, and provides a review interface where a human can accept, edit, confirm no data, reject, or bulk-accept the currently visible filtered subset before any spreadsheet is updated.

The system supports three operator-visible run modes: normal extraction for empty targets, Verify mode for reviewer comparison on already-filled cells, and Eval mode for leakage-aware benchmark runs. In Eval mode the app loads the completed human-filled table as the gold input, creates an app-owned masked working copy of the target cells before extraction, and preserves eval-ready artifacts for a separate scoring tool.

Eval-ready artifacts must remain directly consumable by the separate evaluator and optimizer from files alone. The main app therefore owns a versioned run-bundle contract and must persist enough proposal, evidence, and source-text-compatible artifact truth for downstream anchor validation to remain meaningful.

In addition to full-fidelity diagnostics, the main app must also publish a compact downstream contract in stable summary artifacts so the separate evaluator and optimizer can consume structured-output degradation, parse-repair, retrieval-policy, and extraction-contract truth without importing main-app runtime code or reparsing verbose traces.

The system extracts primarily from text and tables. Extraction is schema-first: column name, description, and optional field typing define what should be extracted, while existing filled cells are optional format helpers only. The schema stays lightweight and must not require explicit per-column vision policy fields. When vision capability is available, the system uses text-guided figure shortlisting and panel targeting as a normal supplemental evidence stage, allowing figure evidence to strengthen any proposal, corroborate text evidence, or rescue weak text-only results without broad untargeted vision calls.

The product is designed for high-trust extraction workflows where proposed values must remain inspectable, auditable, reversible, and clearly distinguishable by support level, parsing quality, and provider-mode truth.

The reviewer is reviewing what the paper supports, not grading the model, so the review workspace must keep paper evidence, reviewer judgment, and explicit curation outcomes primary.

The review workspace must show actionable review items by default rather than every recorded pipeline outcome. Diagnostic-only outcomes such as unmatched rows, blocked extraction caused by missing or ambiguous paper matching, skipped cells outside Verify mode, or other non-reviewable pipeline results must remain visible through diagnostics and summaries, but they must not dominate the main proposal queue or inflate reviewer-facing counts.

## Document role

This file defines product behavior, operator expectations, and acceptance criteria.

Keep architecture and implementation direction in `plan.md`.
Keep rationale and tradeoffs in `research.md`.
Keep execution order and verified completion status in `tasks.md`.

---

## End-to-end workflow

The intended MVP workflow is:

1. Start a run from the UI by typing the path to a run configuration file or using a `Browse...` affordance for local selection, then let the app validate and snapshot the resolved config, run explicit readiness checks, and surface the active proposal-generation mode before work begins.
2. Normalize table columns, determine whether the run is in normal, Verify, or Eval mode, classify which cells are eligible, and create a masked working copy of target cells before extraction when Eval mode is enabled.
3. Parse PDFs and extract paper-level metadata needed for row matching.
4. Match each PDF to at most one row, while surfacing unmatched, ambiguous, and duplicate-row conflicts.
5. Generate one best proposal per eligible target cell using schema-first extraction, with evidence and support labeling that do not depend on prefilled cell values and that operate on the masked working copy rather than the original completed table in Eval mode.
6. Let a human reviewer inspect, filter, accept, edit, confirm no data, reject, or bulk-accept the currently visible filtered subset, while navigating evidence and proposals quickly.
7. Manually trigger export from the review UI to generate a new XLSX workbook containing only explicitly accepted changes plus an audit log and run summaries.
8. Preserve diagnostics and artifacts so the run can be inspected later or scored later by a separate eval tool when Eval mode was used.
9. Allow the operator to abort an active run from the UI and see that interruption reflected promptly in run state.

This workflow is intentionally linear from the operator’s perspective even if the implementation uses multiple internal stages.

### Operator-visible run states

The UI must make run lifecycle state explicit. The operator-visible states are:

- `ready`: the UI has enough information to start a run from a config file, but work has not started yet
- `validating`: the app is checking config paths, required inputs, and basic run readiness
- `running`: the staged pipeline is actively parsing, matching, retrieving, extracting, or writing outputs
- `completed`: the run finished cleanly and is ready for review/export
- `completed with warnings`: the run finished and is reviewable, but unresolved matching issues, export caveats, or other important warnings remain visible
- `failed`: the run could not complete and the operator must be able to see an actionable reason

`completed with warnings` is reserved for partial-success runs where meaningful processing actually happened. Provider unavailability or provider-unreachable state discovered at run start must fail the run during readiness rather than producing a cosmetically completed run.

Active runs must refresh automatically in the UI often enough that an operator can follow progress without relying on manual refresh as the primary mechanism. Manual refresh may remain available, but it is a fallback rather than the normative status path.

If the UI cannot refresh live state, it must tell the operator explicitly that the displayed state may be stale.

These states are reviewer-facing UX requirements, not merely backend implementation details.

Internal lifecycle states may include additional values such as `created` or `interrupted`, but the UI must map them onto these normative operator-visible states rather than exposing an inconsistent second state model.

### Config authority and operator surface

The JSON config file is the authoritative control surface for advanced run behavior, reproducibility, and resolved runtime parameters.

The browser UI is the normal operator-facing workflow surface for:

- entering or selecting the config path
- confirming the resolved input/output context for the run
- starting a run
- understanding lifecycle state and warnings
- reviewing proposals and unresolved matching issues
- exporting and downloading outputs
- aborting an active run

The UI may expose the config path, resolved paths, active run mode (`normal`, `verify`, or `eval`), and provider/model context, but broad parameter editing in the UI is not an MVP requirement and must not become the default control surface.

The config may expose narrow diagnostics controls for provider logging verbosity and preview length, but those controls remain config-owned rather than becoming a broad UI settings surface. Default behavior should stay low-noise, with detailed provider traces opt-in.

In addition to the browser UI, the product should expose one stable non-UI automation entrypoint for tooling. That automation path should support config-path-driven run start, narrow path overrides already supported by the runtime contract, optional wait-until-terminal behavior, and machine-readable outputs derived from run artifacts. This automation path is additive and must not replace the browser UI as the normal human workflow.

The automation payload contract should remain explicit and stable for tooling use. At minimum it should include a payload schema tag (for example `schema_version`), string status, explicit terminal-state boolean, run id, run mode, and key run artifact paths.

The checked-in config example, runtime config schema, README, and operator-visible UI terminology are part of one operator-facing contract. Names and meanings for provider, parser, model, Verify mode, Eval mode, and run-state settings must stay aligned across those surfaces. Operator docs should include at least one known-working LM Studio model example, clearly labeled as an example rather than as the only acceptable model choice.

Config naming must describe actual implemented behavior rather than aspirational behavior. Canonical config names must be explicit and truthful for reproducibility, operator comprehension, and benchmark comparability.

Every run must persist a resolved effective config artifact in run outputs. Compatibility aliases may be accepted pragmatically, but persisted artifacts and docs must use canonical names.

The run bundle is also a cross-repo contract. Persisted run metadata, proposal records, and evidence records must include explicit schema-version fields so downstream tooling can reject unsupported shapes or apply bounded compatibility fallbacks deliberately rather than guessing.

### Provider contract, readiness, and mode truth

The product must preserve one canonical provider contract for proposal generation.

That contract must stay consistent across:

- runtime validation and config parsing
- checked-in config examples
- README and operator docs
- automated tests and fixtures
- operator-visible UI labels and summaries

Unknown, misspelled, deprecated, or otherwise unsupported provider identifiers must fail early with a clear validation or readiness error rather than being accepted implicitly.

The default local-first provider path is LM Studio via its localhost API.

The canonical config token for that provider is `lm_studio`.

The canonical operator-visible label is `LM Studio`.

If compatibility aliases are supported, they must normalize to the same canonical stored value, remain documented in the checked-in config and operator docs, and never create disagreement between validation, artifacts, and UI labels.

Optional cloud providers may be supported behind the same typed provider interface, but they must not change the product's local-first identity, and committed config examples must use environment or secret references rather than hardcoded cloud credentials.

The operator must be able to tell whether proposal generation for a run is:

- live via LM Studio
- live via a supported cloud provider
- unavailable or unreachable
- disabled by configuration
- running in an explicit stub, demo, or degraded fallback mode

Provider readiness and provider capability truth are distinct and must be reported distinctly. At minimum, operator-visible status, run summaries, and persisted artifacts must distinguish:

- provider unreachable or unavailable
- model unavailable, load failed, or not compatible with requested load context
- provider reachable but `json_schema` unsupported
- provider reachable but no compatible structured-output mode available

These states must not be collapsed into one generic "provider unavailable" label.

For LM Studio runs, the app must manage model readiness itself: it should inspect the configured model, reuse a compatible loaded instance when possible, and otherwise load the configured model with the required load-time context before extraction begins. Structured output is enabled per extraction request through the LM Studio OpenAI-compatible request contract rather than through a separate operator toggle.

When separate text and vision model paths are configured, structured-output capability truth must remain separable for those paths. A text model reaching one structured-output mode must not imply that the configured vision path supports the same mode.

Run artifacts should also separate user-facing summaries from deeper implementation diagnostics. Reviewer-facing and operator-facing summary artifacts should live in a stable summary area, while verbose provider/runtime diagnostics, probes, traces, and run statistics should live in a dedicated diagnostics area.

The app must not present a stub, demo, disabled, or degraded provider path as if it were the normal live proposal-generation happy path.

If the configured live provider is unavailable at run start, the run must fail during readiness with an operator-facing reason. That condition is not a valid `completed with warnings` outcome.

---

## Problem statement

To compare technical parameters and findings across research projects and scientific papers, researchers need to read publications, find relevant information, extract it, and organize it in spreadsheets. This is slow, repetitive, and error-prone.

General chat-style document tools can answer questions about PDFs, but they do not reliably support row-aware extraction against a spreadsheet schema, evidence-backed human review, or audited spreadsheet export.

Extract Structured Info from Papers addresses this by turning PDF-to-table curation into a structured review workflow rather than a chat interaction.

---

## Goals

- Reduce manual effort for extracting structured information from scientific papers into tables.
- Keep a human reviewer in control of every spreadsheet update.
- Treat evidence quality and reviewer trust as first-class product requirements, not implementation details.
- Preserve evidence and provenance for every proposed value.
- Support repeatable, auditable runs across many PDFs.
- Work well for scientific papers with mixed prose, captions, tables, and figures.
- Support text-guided targeted figure review when vision capability is available, using retrieved text, figure captions, and figure or panel references to shortlist likely relevant figures and panels, with figure evidence allowed to supplement, strengthen, corroborate, or rescue any proposal regardless of field type.
- Persist figure crop and full-page artifacts when figures are extracted so that review and vision analysis operate on the same concrete evidence.
- Support verification against already-filled cells when enabled, so the user can compare proposals against existing entries and assess app performance through reviewer outcomes.
- Produce leakage-aware eval-ready runs whose artifacts can be consumed later by a separate evaluation tool without turning the main app into a benchmark framework.
- Preserve a stable, versioned run-bundle contract so the eval and optimizer repos can consume main-app outputs without silent drift.
- Keep eval-ready evidence artifacts compatible with downstream anchor validation, including persisted evidence records and page-text-compatible source artifacts.

## Non-goals

- Fully autonomous spreadsheet editing without human review.
- General-purpose chat over documents.
- Replacing expert judgment for ambiguous scientific interpretation.
- Multi-user collaboration workflows.
- Full multimodal reasoning on every page by default; figure review remains text-guided and targeted, not blanket per-page vision.
- In-UI advanced parameter tuning; advanced run behavior is controlled through the run configuration.
- Computing full benchmark metrics inside the main app, bundling a large evaluation framework into the main product, or requiring a dedicated eval UI for Eval mode.
- Requiring downstream scoring tools to import main-app runtime code just to interpret run artifacts.

---

## Actors

### Primary actor

A researcher or curator who maintains a structured spreadsheet of information extracted from scientific papers.

### Secondary actor

A lab member or assistant who reviews proposed spreadsheet updates with supporting evidence.

### Supporting actor

A developer or advanced user who inspects diagnostics to understand matching, extraction, evidence, or reviewer-outcome reporting failures.

---

## Product principles

- Human review is required before spreadsheet updates.
- Evidence quality and reviewer trust are first-class product requirements, not polish.
- Evidence is attached to proposals, not hidden inside model reasoning.
- Each proposal should support one best answer, but may include multiple evidence items when useful. The most authoritative evidence item becomes the primary evidence; additional items are ordered supporting evidence.
- Evidence must be ranked and ordered: source authority and field relevance determine which evidence is primary, not the order in which the model returned quotes.
- The product must distinguish clearly between evidence types: direct quote evidence, inferred reasoning, calculation-based justification, approximate highlight fallback, quote-plus-page fallback, and figure-derived evidence split into caption-grounded and visual-interpretation subtypes.
- Direct quotes must be shown separately from reasoning and calculations in the review UI.
- Exact quote highlighting should be produced from rendered page text or an equivalent page-text alignment strategy whenever possible; if it fails, the product must degrade honestly and visibly to approximate region highlighting or quote-plus-page evidence, and fallback evidence must be labeled as fallback, not presented as exact.
- Plausible values may still be surfaced even when evidence is weak, but they must be flagged accordingly.
- A proposal being present does not imply that it is correct.
- Attached evidence does not automatically imply that a proposal is correct.
- Locked cells are protected by default, except when a human explicitly accepts an update in verify mode.
- The product supports three distinct run modes: normal extraction, Verify mode for in-app comparison on already-filled cells, and Eval mode for leakage-aware benchmark runs scored later by a separate tool.
- Eval mode must never expose target-cell gold values to the extraction path; it uses an app-owned masked working copy and preserves auditable gold-table and masked-table provenance in artifacts.
- Eval-ready summary artifacts must also publish compact extraction and retrieval provenance fields such as structured-output mode, prompt-only degraded fallback truth, parse-repair usage, extraction-contract validity and warnings, retrieval mode, retrieval top-k, recall-rescue configuration and usage, and whole-document retrieval usage.
- Eval mode artifacts must preserve enough versioned proposal, evidence, and source-text provenance for a separate evaluator to validate anchors and score runs from files alone.
- All runs are auditable.
- The product is optimized for trustworthy extraction workflows, not maximal automation at any cost.
- The product should preserve a clear distinction between directly supported values and inferred or derived values.
- The reviewer is reviewing the paper, not the model, so evidence and paper context must remain visually primary over model-generated prose.
- Confirmed absence of data in the paper is a valid review outcome and must remain distinct from model error or unsupported extraction.
- Empty gold cells in Eval mode are not proof that the paper omits a value; any scoring policy for gold-absent cells belongs to the downstream eval tool rather than the main app.

## Product quality bar

The MVP is done only when the product works as a coherent local operator workflow, not merely when each feature exists in isolation.

That means:

- a new user can install dependencies, start the app, point the UI at a config file, and reach a reviewable run without reconstructing the workflow from source code
- the first-run experience makes the next operator action obvious even before any run exists, instead of dropping the user into an empty but unexplained review shell
- the UI exposes the config path and a useful resolved-run summary without becoming a broad advanced-settings editor
- run startup, validation, processing, completion, warning, and failure states are visible and understandable
- loading, empty, warning, and failure states are explicit and actionable rather than silent or generic
- review surfaces stay clearly gated until the run is actually reviewable, while still exposing useful setup, progress, and diagnostics context
- review ergonomics support confident human decisions instead of forcing the operator to infer workflow intent from raw implementation details
- “minimal” or “task-focused” means legible, guided, and trustworthy rather than barebones, cryptic, or developer-centric
- the browser UI feels like one coherent run-launch, status, review, and export workflow rather than a thin shell over artifact files
- the review workspace behaves like a reviewer-centered scientific curation workstation rather than a generic model-output browser
- the left sidebar supports dense grouped triage without collapsing decision state, support quality, and match outcome into one vague status chip
- no-value cases remain actionable through explicit no-data confirmation or manual entry rather than dead-ending in an empty detail pane
- evidence handling is interactive enough that the reviewer can inspect, zoom, pan, drag the page naturally, select and copy text when the source PDF allows it, and use paper evidence directly while editing a value
- the review workspace performs acceptably on realistic runs because it defaults to actionable review items rather than loading thousands of diagnostic-only artifacts into the main queue
- reviewer-facing counts distinguish reviewable proposals from broader attempted-cell or diagnostic totals, so the operator is not misled by large numbers that do not reflect actual review work
- the review workspace supports adjustable pane widths so the operator can rebalance queue, detail, and PDF space during curation
- paper-group labels in the queue use useful citation context when available, not only internal file identifiers
- the run/setup surface is action-oriented and picker-driven rather than dominated by raw path entry and long uncollapsed lists
- the proposal-generation path is truthful: provider mode, readiness state, parse-failure or low-text states, and any degraded or unavailable status are visible before the operator mistakes a clean shell for a working extraction system
- text-based PDFs remain parseable across supported upstream parser versions; parser-integration drift must not silently collapse a paper into an empty parsed document
- when figure review is enabled, extracted figures persist real crop artifacts and page links for both reviewer inspection and vision-model calls, and shortlisted vision requests include textual context from retrieved passages, captions, and figure-reference snippets; caption-only figure metadata is not sufficient
- the documented LM Studio happy path is either genuinely capable of producing reviewable proposals with evidence on the canonical checked-in fixture path or it fails early with an actionable readiness error
- documentation reflects the actual happy path and the actual limits of the product
- the user-facing `README.md` is treated as a product surface, not as post-hoc cleanup
- the `README.md` and other operator-facing docs must describe the real startup path, config workflow, run lifecycle, review workflow, export behavior, artifact locations, and known MVP limitations that the implementation actually supports
- documentation must match actual commands, actual architecture, and actual UI flow at the time of shipping
- documentation must not describe speculative helpers, obsolete commands, aspirational workflows, or convenience scripts that are not part of the implemented MVP

---

## User stories

1. As a researcher, I want to load my spreadsheet, schema, and PDF folder so the system can identify missing values worth extracting.
2. As a researcher, I want the system to match each PDF to the most likely spreadsheet row so that extraction happens in the correct row context.
3. As a researcher, I want the system to propose values for missing cells and show supporting evidence from the paper so that I can judge whether the proposal is trustworthy.
4. As a reviewer, I want to inspect the PDF page with a highlight of the most relevant quoted evidence, see direct quotes separately from reasoning and calculations, navigate through multiple supporting evidence items in ranked order, and have the viewer stay synchronized with whichever evidence item I select, so that I can make a well-informed decision about what the paper actually supports.
5. As a reviewer, I want figure evidence shown alongside text evidence when available, with crop, caption, and full-page access, so that I can assess evidence from charts or diagrams as readily as from text passages.
6. As a curator, I want non-empty spreadsheet cells to remain protected unless I explicitly choose otherwise so that previously curated data is not overwritten accidentally.
7. As a curator, I want an updated export file and audit log after review so that I can update my master table safely and trace what changed.
8. As a developer or advanced user, I want diagnostic outputs about matching, extraction, evidence quality, and reviewer-outcome reporting so that I can troubleshoot poor runs.
9. As a reviewer, I want verify mode to compare proposals against already-filled cells so that I can review disagreements, make decisions on them, and assess how well the app is performing through reviewer outcomes.
10. As a reviewer, I want to switch between grouping proposals by paper and by column so that I can triage quickly and then investigate deeply without losing context.
11. As a reviewer, I want to confirm that a paper truly does not report a value, separately from rejecting a wrong model guess, so that the recorded outcome reflects the paper rather than the model.
12. As a reviewer, I want to zoom, pan, drag the page naturally, navigate pages, select and copy text from the paper when possible, and click evidence into my edited-value workflow so that I am curating from the paper rather than copying information manually across panes.
13. As a reviewer, I want the queue, detail pane, and PDF pane widths to be adjustable so that I can prioritize the content needed for the current decision.
14. As an operator, I want active runs to refresh automatically and support cancellation so that I do not need to infer whether work is still happening.
15. As a benchmark operator, I want eval mode to hide completed target-cell values from extraction while preserving gold and masked table references in artifacts, so that a separate eval tool can score the run later without leakage.

---

## Scope

### In scope

- Importing a table and schema.
- Importing a folder of PDFs.
- Detecting missing versus already-filled cells.
- Extracting paper metadata needed for row matching.
- Matching PDFs to spreadsheet rows using publication metadata.
- Blocking extraction when a PDF-to-row match remains ambiguous.
- Blocking extraction when two or more PDFs match the same row until the conflict is cleaned up manually.
- Proposing values for schema-defined target cells.
- Producing at most one best proposal per target cell per run.
- Restricting the default review queue to reviewable proposals only, while keeping blocked, unmatched, duplicate-conflict, skipped, and other diagnostic-only outcomes visible through diagnostics and summaries.
- Storing one or more evidence items per proposed value.
- Human review of proposals with PDF evidence display when available, including weaker review states when text highlighting fails but quote plus page evidence is available.
- Text-guided targeted figure review when vision capability is available, using retrieved text, captions, and figure-reference context to shortlist figures or panels, with figure evidence allowed to supplement, strengthen, corroborate, or rescue any proposal regardless of field type.
- Figure-derived evidence display in review when available, including caption-grounded and visual-interpretation figure evidence.
- Verify mode: generating proposals for already-filled cells, showing them in review, and including reviewer decisions on them in run summaries.
- Eval mode: loading a completed human-filled table as gold input, masking target cells in an app-owned working copy before extraction, and persisting minimal eval-ready artifacts for a separate scoring tool.
- MVP filtering by row, column, PDF, evidence status, figure-derived evidence, and ambiguous or unmatched match status.
- Accept, accept-with-edit, confirm-no-data, reject, and guarded bulk acceptance of the currently visible filtered proposal subset.
- Navigation through proposals without recording a decision.
- Exporting an updated XLSX table and an audit log.
- Preserving cell content in the exported table and visually marking updated cells with distinct background coloring.
- Writing run diagnostics and reviewer-outcome summaries.
- Keeping unmatched or ambiguous PDFs visible for manual inspection.

### Out of scope

- Real-time collaborative review by multiple users.
- Automatic correction of already-filled cells without explicit review.
- End-to-end citation graph building across papers.
- Fine-grained ontology management.
- General-purpose conversational assistant features.
- Fully automatic database synchronization to external systems.
- Full multimodal reasoning on every page of every paper by default.
- Headless or multi-user deployment as an MVP requirement.
- Computing full automated benchmark metrics or retrieval-centric correctness scores inside the main app.

### Deferred for this MVP

- paper-local retrieval state or cache architecture
- broad chunk-quality overhaul
- broad provider or runtime speedup work beyond instrumentation-ready design
- dense retrieval as default behavior
- HyDE default behavior
- broad main-app versus eval-app artifact-contract cleanup beyond maintaining minimal eval-ready metadata

---

## Inputs

The system accepts:

- A table file in CSV or XLSX format.
- A schema, either embedded in the workbook or provided separately.
- A folder of PDFs.
- A run configuration file.

### Input expectations

- The schema contains at least a `column_name` and a `description` for each target column.
- The schema may also include an optional `field_type` with one of `text`, `number`, `categorical`, or `boolean`.
- The schema may include optional `allowed_values` only when `field_type` is `categorical`.
- The schema does not require `normalization_notes` for MVP.
- The schema must not require explicit per-column vision-policy fields such as text-only or vision-required. Vision triggering is inferred from field intent, retrieved evidence strength, and figure-reference context.
- The table must contain standardized metadata columns named `Title`, `Authors`, and `Publication Year` for row matching.
- CSV or schema files may arrive with UTF-8 BOM markers or surrounding whitespace in headers; normalization must not misread canonical field names because of those artifacts.
- Workbook date and datetime cells may arrive as native Excel cell types or text representations; normalization must preserve their intended meaning for matching, extraction, review, and export rather than treating them as opaque serial values.
- The schema defines the intended meaning of each target field.
- Schema descriptions should explain the field meaning, expected answer shape, and important inclusions or exclusions clearly enough that extraction can remain schema-first rather than value-example-driven.
- PDFs are scientific papers or similarly structured technical documents.
- PDFs may contain important information in prose, captions, tables, and figures.
- Born-digital scientific PDFs are the main target.
- OCR support may be used as a fallback for scanned or text-inaccessible PDFs.
- Supplementary PDFs should ideally be merged with the main paper by the user before running the app.
- The run configuration may select normal extraction, Verify mode, or Eval mode; Verify mode and Eval mode must not both be enabled for the same run.
- In Eval mode, the user still provides a completed human-filled table as the gold input, but the app must create an app-owned masked working copy of target cells before extraction begins and retain identifiers for both the original gold table and the masked working table in artifacts.
- In Eval mode, the original gold table should be persisted with source path or reference, content hash, and a copied snapshot path inside the run bundle when feasible.
- In Eval mode, the masked working table should be persisted with its app-owned run-bundle path, a masked-table content hash, and the copied masked snapshot artifact used by the run.
- Empty cells in the gold or human-filled table must remain unevaluated-by-default context, not proof that the paper definitely omits the field.

### Input guidance from existing cells

- The system may derive a non-binding style or format profile from existing filled cells for all field types through a preprocessing LLM, but such guidance must be used only to influence output shape, detail level, and formatting.
- Raw existing cells must not be passed into extraction prompts as semantic exemplars.
- Extraction must remain functional when a table or a column is empty. Existing filled cells are optional helpers only and not a precondition for extraction.
- Proposal content must remain grounded in the current PDF plus the schema definition for the target field.
- In Eval mode, style-profile preprocessing and extraction must operate on the masked working copy or another leakage-safe representation so target-cell gold values are not exposed downstream.

---

## Outputs

For each run, the system must produce:

- Persistent run records.
- Proposal records for attempted extractions.
- Evidence records for each proposal when available.
- Review decisions.
- An exportable updated XLSX table.
- An audit log of accepted changes.
- Run diagnostics and reviewer-outcome summaries.
- Eval-ready run metadata and artifact references when Eval mode is enabled.

The run may also produce diagnostics-only records for blocked, skipped, unmatched, ambiguous, duplicate-conflict, or otherwise non-reviewable outcomes, but those records are distinct from reviewable proposals and must not be treated as normal queue items by default.

### Output expectations

- No spreadsheet cell is updated automatically without an explicit human decision.
- All exported changes are traceable back to reviewed proposals.
- Proposal identifiers must remain unique within a run, including cases where multiple PDFs target the same row/cell context.
- Reviewable proposal counts, attempted-extraction counts, unresolved-match counts, and diagnostics-only outcome counts must remain distinct in artifacts and in the UI.
- The exported table must remain in XLSX format, even when the input table is CSV.
- The exported XLSX table guarantees content-only fidelity plus highlighting of changed cells. Workbook formatting, layout, formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, and similar workbook behavior are out of guarantee for MVP.
- Cells changed through accepted proposals must be visually highlighted in the exported XLSX table.
- Diagnostic outputs remain available after the run finishes.
- Verify-mode reviewer-outcome summaries remain available even when there are no verified cells, with a clear status or explanation instead of silent empty metrics.
- Verify-mode reviewer-outcome summaries must not silently report an all-zero result when no targets were actually reviewed.
- Unreviewed proposals must not appear as accepted changes in the exported table.
- Confirmed no-data outcomes must remain distinct from rejected-or-model-wrong outcomes in persisted review state, diagnostics, and user-facing summaries.
- A concise run summary must report run mode (`normal`, `verify`, or `eval`), provider/model names used, whether processing stayed local or used cloud providers, and key run metrics.
- The run summary and UI must distinguish between live provider execution, explicit disabled mode, explicit stub or demo mode, and provider-unavailable or provider-unreachable outcomes.
- Runs that are aborted by the operator must persist an explicit interrupted outcome with enough context for the UI and diagnostics to distinguish interruption from failure.
- Artifact persistence must sanitize runtime-derived filenames or use opaque identifiers so run behavior is robust across supported operating systems.
- When Eval mode is used, the run summary, config snapshot, and diagnostics must identify the original gold table, the masked working table, the parser identity, the schema identity, the config snapshot or hash, and the model context used for the run.
- Every run must persist prompt identity as part of reproducibility metadata. `prompt_version` is preferred when explicit versioning exists, but a deterministic `prompt_hash` is the required fallback for every run.
- When Eval mode is used, those artifacts must also identify gold-table and masked-working-table provenance through path or reference, content hash, and run-bundle snapshot location when applicable.
- The masked working copy does not carry a workbook-formatting guarantee. It must stay structurally and semantically usable for extraction and downstream evaluation, but formatting preservation is at most a best-effort implementation detail.
- Eval-mode artifacts must preserve stable proposal metadata sufficient for a separate eval tool to score the run later, while keeping the main app's artifact contract minimal and auditable.
- The main app must not require a dedicated eval UI or compute full benchmark metrics as part of Eval mode; it emits eval-ready run artifacts and leaves final metric computation to a separate tool.

---

## Proposal and review terminology

The product uses the following reviewer-facing concepts consistently across the UI, exports, and diagnostics:

- **Match outcome**: whether a PDF is `matched`, `ambiguous`, `unmatched`, or blocked by a duplicate-row conflict.
- **Proposal**: the one best attempted value for a specific row/column cell in a specific run.
- **Reviewable proposal**: a proposal that should appear in the main review queue because a reviewer can make a decision on it.
- **Field type**: an optional schema-level constraint used to shape extraction and review semantics. MVP supports `text`, `number`, `categorical`, and `boolean`.
- **Numeric value form**: the internal representation for a numeric answer. MVP must allow at least `exact`, `range`, and `approximate`.
- **Support level**: how strongly the system believes the evidence supports the proposal, such as direct evidence, inferred from evidence, weak evidence, or figure-derived evidence.
- **Evidence item**: the reviewer-visible text quote, page anchor, highlight, figure crop, caption, or related source reference used to justify the proposal.
- **Evidence type**: the semantic kind of evidence, which the UI must render and label distinctly. The defined types are:
  - `direct_quote`: a verbatim passage from the paper that directly states the value and has an exact or approximate page anchor when possible
  - `inferred_reasoning`: a reasoning chain or argument constructed from one or more quoted passages
  - `calculation`: a calculation or derivation performed on quoted numeric evidence
  - `approximate_highlight`: a highlight region derived from approximate parser geometry rather than precise page-text alignment, labeled as approximate
  - `quote_plus_page`: a quote plus page number when precise highlighting fails; labeled as fallback text evidence rather than as an exact highlight
  - `caption_grounded_figure_evidence`: evidence grounded primarily in a figure caption plus figure context, with figure crop, caption, and full-page context
  - `visual_interpretation_figure_evidence`: evidence grounded primarily in visual interpretation of a figure, chart, diagram, or image, with crop and full-page context
- **Primary evidence**: the single most authoritative evidence item for a proposal, selected by evidence ranking based on source authority and field relevance.
- **Supporting evidence**: additional ordered evidence items that corroborate or supplement the primary evidence, shown in ranked order.
- **Evidence ranking**: the process of ordering evidence items by source authority and field relevance so the most authoritative evidence becomes primary and supporting items are ordered accordingly.
- **Review decision**: accept as-is, accept with edit, confirm no data, reject, or no decision yet.
- **Resolution reason**: a structured reviewer reason attached to a non-accepted or manually resolved outcome, such as `not reported in paper`, `insufficient evidence`, `model wrong`, or `needs manual entry`.
- **Triage projection**: the compact sidebar view of broader proposal and run state used for fast scanning. It may compress state for density, but it must not erase the underlying distinctions between review decision state, evidence/support quality, and match outcome.
- **Diagnostics-only outcome**: a recorded extraction result that should appear in diagnostics even when there is no reviewable proposal.

Blocked or skipped cells outside Verify mode, unresolved match failures, duplicate-row conflicts, provider-initialization failures before extraction, and similar non-reviewable states are diagnostics-only outcomes unless the spec explicitly says they belong in review.

This terminology is normative for the MVP even if internal implementation names differ.

---

## Functional requirements

### FR-1 Import, configuration, and normalization

The system must allow the user to provide a table, schema, PDF folder, and run configuration.

The primary happy path is that the operator starts a run from the UI by providing a config-file path. The UI may also support equivalent local-first shortcuts, but it must not require the user to pre-run the workflow through ad hoc Python snippets just to create a run.

The system must normalize column identifiers and detect which cells are missing, already filled, or otherwise eligible for extraction or verification behavior.

The system must support three product modes: normal extraction, Verify mode, and Eval mode. `verify_mode = true` and `eval_mode = true` is invalid and must fail during validation or readiness before extraction begins.

Normalization must robustly handle common real-world input quirks such as BOM-marked CSV headers, surrounding header whitespace, and Excel-native date or datetime cells.

The runtime must also resolve common path-input differences consistently, including relative versus absolute paths, browser-selected inputs, and platform-specific path spellings, and surface one clear resolved path context to the operator before work begins.

The system must validate that the table includes standardized metadata columns named `Title`, `Authors`, and `Publication Year` before row matching begins.

Before the run leaves the validation/readiness phase, the system must also validate:

- provider identifier and provider-config shape
- provider reachability when a live provider is configured
- configured model availability or equivalent capability failure when it can be checked up front
- structured-output compatibility readiness, including whether `json_schema` is supported and whether bounded `json_object` fallback is available when `json_schema` is unsupported
- parser or OCR dependency availability when those paths are configured
- output-path writability and other obvious broken-install or broken-setup conditions

When both Verify mode and Eval mode are disabled, already-filled cells must remain out of scope for proposal generation and review. The system must not generate reviewer-facing placeholder proposals, fake blocked rationales, or verify-style comparison panes for those cells.

When Eval mode is enabled, the runtime must load the completed human-filled table as the gold source, create an app-owned masked working copy of target cells before any extraction-stage consumer reads target-cell values, and preserve both gold-table and masked-working-table provenance in run artifacts.

The product must preserve one clear primary local happy path: install dependencies, start backend and frontend, open the browser UI, provide a config path, launch the run, monitor state, review proposals, and export accepted changes. Developer shortcuts may exist for debugging, but they must not replace this documented operator path.

Advanced run behavior must be controlled through the run configuration rather than through extensive tuning controls in the UI.

The UI may let the operator override relevant input file or folder paths from within the app using picker controls, provided the config file remains the authoritative source for advanced behavior and reproducibility and the resolved run context remains explicit.

For MVP browser mode, the normal setup flow should prefer browser-compatible picker behavior for file and directory selection. Native OS dialogs may be used only in a future desktop package and are not an MVP assumption.

Because a pure browser client cannot be assumed to expose stable native filesystem paths, picker-selected inputs must be materialized into backend-readable staged files or directories, or into another explicit app-owned server-side input handle, before validation and execution begin.

The resolved run context must distinguish the logical source of each input, such as config-declared path, typed backend path, or picker-staged override, from the backend-visible locator actually used at runtime.

Manual raw absolute-path entry may remain available as a fallback, but it must not be the primary setup interaction for the normal operator workflow.

The config-path control must remain a text field so operators can paste or inspect the exact path, but the UI must also expose a `Browse...` action that supports normal local-first use.

The UI must show the config path plus a concise resolved-input summary, including at least the table path, schema path when present, PDF directory, output directory, target-column count or list, and active run mode.

When Eval mode is enabled, that setup summary must also identify the gold table source and the masked working-table handle or path that the run will use.

The target-column list should be collapsible, truncated, or otherwise compact by default so the run/setup surface stays focused on what worked, what needs attention, and what the operator should do next.

That resolved context must be preserved in run artifacts and remain visible in the UI even when the run fails during readiness or another early stage, including explicit mode truth and Eval-mode gold or masked table references when applicable.

The UI must also show a concise provider/readiness summary before the run starts or while validation is in progress, including the canonical provider name, configured model names when relevant, and whether the app currently sees the provider path as live, unavailable, disabled, or explicitly degraded.

That summary must preserve readiness and capability truth by distinguishing unreachable provider state from model-unavailable state and from structured-output compatibility mismatches.

The run setup and later run summary must also identify the configured parser choice and, when parsing begins, the actual parser path used. If the configured parser cannot be used, the default behavior must be an explicit failure or blocked readiness result unless the operator has explicitly enabled a documented fallback path that is surfaced in the UI and run artifacts.

When the operator switches from one run to another, the UI may preserve the current queue filter, but it must treat proposal selection, proposal detail, and evidence-viewer state as run-scoped. It must clear or reload those views for the newly selected run rather than briefly showing or requesting stale proposal or evidence data from the previous run.

Validation failures must be surfaced with actionable operator-facing messages rather than generic request failures.

Provider readiness failures must be surfaced before the operator waits through a nominal run that cannot actually produce proposals.

Before any run exists, or when the selected run is not yet reviewable, the UI must make the next valid operator action obvious rather than presenting an unexplained empty review workspace.

The UI must allow an operator to request run cancellation while a run is validating or running, and it must surface whether that cancellation has been accepted, completed, or failed.

Active run detail and run list views must refresh automatically on a reasonable cadence while work is in progress, and must clear stale stage text promptly when a run reaches a terminal state.

The review workspace must treat queue grouping labels as reviewer-facing context rather than internal ids. When row metadata is available, paper-group labels should prefer a concise citation-style label such as first author plus year and a short title fragment over a bare PDF filename.

The review workspace must allow the operator to resize the queue, detail, and evidence panes by direct manipulation.

The right pane's primary in-app document mode must remain optimized for evidence quotes and highlight overlays. When reviewers need normal reading behavior beyond that annotated mode, the workspace must provide an explicit action to open the PDF in the operating system's default local PDF viewer.

### FR-2 Paper metadata extraction

The system must extract paper-level metadata needed for row matching, such as title, authors, publication year, and identifiers when available.

Metadata extraction for matching must be grounded in the paper and must not invent missing metadata.

The system should support OCR as a fallback when PDF text is not directly accessible.

Any parsing fallback, OCR use, low-text condition, or other degraded parsing outcome must be surfaced in persisted diagnostics, run summaries, and reviewer-visible status surfaces rather than remaining an implementation-only detail.

### FR-3 PDF-to-row matching

The system must attempt to match each PDF to the most likely table row.

The system must support:

- a deterministic matching pass
- a fallback adjudication step for ambiguous but plausible cases
- a final state of matched, ambiguous, or unmatched

Deterministic matching must rely primarily on interpretable publication signals such as DOI or other stable identifiers, first-author agreement, author overlap, publication year, and title similarity. Title similarity remains useful but must not dominate the score when stronger exact or near-exact signals are available.

Abstract similarity may be used as an optional secondary deterministic signal when available, but it must not replace the stronger identifier and author/year signals.

If matching remains ambiguous, extraction for that PDF must be blocked entirely.

If multiple PDFs plausibly compete for the same row, the system must flag the conflict, block extraction for all PDFs involved in that duplicate-row conflict, and require manual cleanup before either PDF can proceed.

Unmatched and ambiguous PDFs must remain visible in the UI for manual inspection.

Duplicate-row conflicts must be represented distinctly from ordinary ambiguity in artifacts, summaries, and UI-facing diagnostics.

### FR-4 Schema-driven extraction

The system must attempt extraction only for schema-defined columns.

The default extraction contract is schema-first. Column name, description, and optional field type must drive extraction even when the source table is empty.

The system must support values whose intended outputs may be free text, numeric, categorical, or boolean.

When `field_type` is provided in the schema, extraction must honor it. When `field_type` is omitted, extraction should still proceed from the column name and description rather than failing schema validation.

When `field_type` is `categorical`, optional `allowed_values` may constrain output normalization and reviewer presentation.

When `field_type` is `number`, the internal contract must support at least `exact`, `range`, and `approximate` numeric forms rather than forcing every answer into one scalar shape.

For each target cell, the system must produce at most one best proposal per run.

Each attempted target cell must result in one of:

- a proposed value
- an unclear outcome
- a blocked outcome
- an error outcome
- a skipped outcome with reason

Targets with no proposed value do not need to appear as normal actionable proposals, but blocked or otherwise unresolved records should remain inspectable in review surfaces and they must appear in diagnostics.

The system may use schema descriptions and non-binding format or style guidance to shape the expected output format, but proposal content must be grounded in the current PDF evidence.

For some field types, the system may use non-binding format or style guidance derived from existing column entries to improve output shape and consistency, provided the proposal content itself remains grounded only in the current PDF.

Historical spreadsheet values must not be described or implied as semantic exemplars for extraction.

The provider layer must probe or otherwise establish structured-output compatibility for the configured provider-model path before relying on a specific guided-JSON mechanism, and it must use a provider-accepted structured format for that path.

The bounded structured-output fallback ladder is:

1. `json_schema`
2. if `json_schema` is unsupported for the configured provider-model path, fall back to `json_object` and mark provider mode as explicit degraded structured-output mode
3. if the active request shape triggers provider regex or grammar incompatibility, downgrade within the same bounded ladder and record explicit backend-incompatibility truth in run artifacts
4. if both structured modes are unavailable for the configured provider-model path, continue only in explicit degraded prompt-only JSON mode with app-side validation and record explicit capability-mismatch truth in run artifacts
5. degraded text extraction modes must keep value and evidence coupled with a smaller compact response contract rather than reopening broad unstructured extraction
6. one retry with stronger instruction when the returned structure is invalid
7. bounded degraded-mode structural normalization for list-shaped scalars and missing nullable fields, then minimal JSON repair when the failure is purely syntactic, including wrapper stripping and balanced-object extraction from mixed output
8. otherwise mark extraction failed for that target

The system must not add a longer implicit fallback ladder by default.

Prompt-only compatibility fallback is acceptable only as an explicit degraded live mode with app-side validation, degraded-mode warnings, and the same bounded proposal contract checks used for other structured-output fallbacks. The system must not silently accept broad unvalidated prompt output as a valid proposal path.

Long-text target fields must remain first-class extraction targets; the system must not systematically collapse them into empty, truncated, or schema-invalid outcomes merely because they exceed short-answer assumptions.

The first extraction pass should use focused retrieval by default. When that pass returns `unclear`, the system must use a bounded deterministic recall-rescue path: expanded retrieval, then section-level or full-text context when configured and justified.

Lexical retrieval remains the baseline default path for MVP behavior and benchmark comparisons.

Hybrid retrieval may be supported only as an experimental opt-in config mode for benchmark comparison. It must not become default behavior implicitly.

The active retrieval mode (baseline lexical versus experimental hybrid) must be persisted in run artifacts and visible in run summaries so comparisons remain clean.

The system may derive small schema-aware retrieval heuristics from column name and description, optionally assisted during style profiling, but final retrieval policy must remain coarse, explicit, and inspectable in persisted artifacts.

Inputs for those heuristics remain column name and column description plus schema metadata already in scope. Additional user-facing schema burden is out of scope.

The config may offer an optional whole-document mode for important fields when parsed text fits comfortably within the active model context, but that mode must remain optional and non-default.

The system must not treat a syntactically completed extraction stage as functional proposal success if the active provider path was unreachable, stubbed, disabled, silently degraded, or otherwise unable to generate meaningful proposals.

Extraction-critical prompt wording should be managed through a small manifest-based prompt-bundle layout rather than scattered inline literals. Dynamic runtime assembly, schema construction, retrieval insertion, and provider fallback control flow remain code-owned. Run artifacts must persist prompt-bundle identity and file provenance so prompt variation is inspectable and reproducible.

### FR-5 Proposal behavior and derived reasoning

The extraction system is a proposal system, not a quote-only copier.

The system may infer or derive a plausible value when direct wording is incomplete, including cases where:
- a value can be calculated from quoted evidence
- a concise argument can be made from one or more quoted evidence items
- a figure provides the strongest evidence

When a proposal depends on calculation or reasoning, the system must show a concise reviewer-facing rationale or calculation summary. Hidden chain-of-thought is not required or expected.

The system should prefer `unclear` over guessing when the strongest support is common practice, prior spreadsheet content, or weak implication rather than current-paper evidence.

Reviewer-visible proposal states must distinguish at least between:
- `found`: directly supported enough by evidence
- `inferred`: derived or weakly supported
- `unclear`: no sufficiently useful value proposed
- `blocked`: not attempted because of a blocking condition such as ambiguous matching

Reviewer-visible proposal states should use clear human-readable language that communicates the support level of the proposal. Internal names such as `found` and `inferred` may be mapped to labels such as `Direct evidence` and `Inferred from evidence`.

`Direct evidence` must require an anchored direct quote. A proposal supported only by a loosely related quote plus reasoning must be labeled as inferred or weak evidence instead.

### FR-6 Evidence attachment

Each non-empty proposed value must include at least one evidence item when feasible.

Each proposal must expose one primary evidence item. Additional supporting evidence items may be attached and must be ordered by authority and relevance, most authoritative first.

The system must not assume that the first model-returned quote is automatically the best evidence. Evidence must be ranked and ordered so the most authoritative item becomes primary. Evidence selection should consider source authority and field relevance, for example preferring more authoritative procedural sections for procedural fields.

More than one direct quote may be attached when genuinely needed to support a single proposal.

The review UI must show direct quotes separately from reasoning and calculations. A direct quote evidence item and an inferred reasoning or calculation item serve different reviewer functions and must be visually distinguishable.

`direct_quote` evidence must require a reviewer-visible anchored quote. A quote that is only loosely related to the answer must not be promoted to direct evidence merely because a quote exists.

For text-derived proposals, the minimum reviewer-visible evidence target is a highlighted source quote on the PDF page. Exact quote highlighting should be produced from rendered page text or an equivalent page-text alignment strategy whenever possible.

If exact quote matching fails, the product must degrade honestly and visibly. Approximate region highlighting is acceptable as a labeled fallback, but it must be marked as approximate, not presented as exact. If no reliable geometry is available at all, the proposal must remain reviewable with the source quote plus page reference, clearly labeled as quote-plus-page fallback text evidence.

The quote list and the document viewer must stay synchronized around the currently selected evidence item. When the reviewer selects a different evidence item in the quote list, the viewer must scroll to and highlight that item. When the selected evidence changes or zoom changes, the viewer must refocus stably rather than jumping arbitrarily.

Evidence must render according to its semantics. Text evidence without coordinates remains text evidence. Approximate highlight is distinct from exact highlight. Figure evidence is distinct from text evidence. The absence of exact highlight boxes must not make valid evidence appear missing.

The UI must not fabricate placeholder or guessed highlight geometry merely to avoid fallback display. If reliable page geometry is unavailable, the reviewer must see an explicit quote-plus-page fallback instead.

For figure-derived proposals, the minimum reviewer-visible evidence target is a figure crop plus caption, with the full page also accessible in the UI. The viewer must support navigation from the figure crop to the full page context.

`caption_grounded_figure_evidence` should normally rank above generic inferred reasoning when both are otherwise comparably relevant. `visual_interpretation_figure_evidence` remains valid but should carry higher reviewer scrutiny.

An evidence item must contain enough source information for a reviewer to inspect the origin of the proposal.

Attached evidence is decision support for the reviewer, not proof of correctness by itself.

Multiple evidence items may support a single proposal. The review UI must show the primary evidence item by default and allow additional supporting items to be navigated in order.

### FR-7 Evidence validation and recovery

The system must validate whether evidence is suitably anchored for display and review.

If evidence is missing, weak, or unusable for display, the system must make at least one evidence recovery attempt before finalizing the proposal state.

If strong evidence still cannot be recovered, the proposal may remain available for review, but it must be marked as needing more evidence.

Failure to recover a highlight for a text-derived proposal must not by itself move the proposal to diagnostics-only if quote plus page evidence is available.

### FR-8 Text-guided targeted figure review

When vision capability is available, the system must use text-guided candidate shortlisting before figure inspection. Shortlisting must consider:
- retrieved text for the current field
- figure captions
- sentences or paragraphs that reference figures or panels (for example, Fig. 2a, Figure 3B, or Fig. 4a-c)
- nearby local section or results context when useful

Vision should behave like scientific reading: read relevant text, follow figure or panel references, read captions, then inspect the shortlisted figure or panel with that context.

Vision is available for all fields as fallback, rescue, and corroboration. The system must not require a schema-side per-field vision policy to enable this.

The default trigger for the vision path is weak or uncertain text evidence. Vision should usually be invoked when text evidence is unclear, weak, contradictory, or needs confirmation. Vision may also be used when text does not state the answer directly but a figure can provide a useful approximate answer.

If the configured vision path only supports explicit prompt-only degraded JSON mode and the run configuration opts to skip figure review in that state, the system should suppress figure-review calls rather than spend vision budget on a weak contract. That suppression must be recorded explicitly in figure-review diagnostics rather than appearing as if no figure-review decision was made.

Text-guided targeted figure review makes figure evidence available to:
- strengthen and corroborate text-derived proposals
- supplement weak or ambiguous text evidence
- rescue weak, unclear, or failed text-only proposals when appropriate

Figure evidence must be allowed to support any field type when it materially strengthens the answer. The system must not restrict figure review to fields explicitly classified as figure-derived.

Figure-aware extraction may use scoped visual context such as:
- figure crops
- full page images
- captions
- nearby narrative text

Figure-derived proposals must remain clearly marked as figure-derived evidence in review, and the review surface must expose whether the support is caption-grounded or visual interpretation.

Figure-derived proposals remain subject to heightened reviewer scrutiny and may rely more heavily on visual context and concise rationale than direct text-derived proposals.

For graph-derived numeric answers, the system may return approximate or range-style proposals when exact values are not available in text, as long as those proposals are labeled honestly as figure-derived approximation rather than exact quoted values.

Figure evidence must preserve the distinction between caption-grounded support and pure visual interpretation.

The system must still avoid unrestricted full multimodal reasoning on every page by default. The scope remains targeted: inspect text-guided shortlisted figures or panels as supplemental evidence, not every page of every paper for every field.

### FR-9 Review workflow

The system must provide a review interface where a human can inspect proposals and supporting evidence.

The same local browser app must also support starting runs and monitoring run state; review is not a separate operator surface disconnected from run startup.

The review workspace is a scientific curation workstation. Its primary purpose is to help the reviewer decide what the paper supports, not to showcase model output.

The normative MVP pane structure is:
- left = grouped review queue or sidebar
- middle = details and decision workflow
- right = evidence viewer or PDF viewer

The review interface must support a queue-first workflow with:
- a proposal list or queue
- a focused detail pane for the selected proposal
- an evidence viewer pane
- visible run-summary and reviewer-summary context in the main review workspace

Launching runs, understanding status, reviewing proposals, and exporting outputs must feel like one connected workflow in the same browser app rather than separate utilities that the operator has to stitch together mentally.

Review must be nonlinear: selecting a proposal for inspection must not itself record a decision.

The UI should support one visible master queue with filtering, reusable saved views or equivalent presets, and progress indicators.

The main progress headline and default counts in the review workspace must use reviewable proposals or otherwise actionable proposals. Broader attempted totals and diagnostics-only totals may still be shown secondarily.

The left sidebar must support two grouping modes:
- `Group by Paper`
- `Group by Column`

The grouping mode must be switchable from a control at the top of the sidebar.

Each group header must show enough summary context for triage, including at minimum the group label, total item count, pending count, and any match-warning or manual-attention badge needed for triage.

The default group ordering should prioritize groups with pending actionable items ahead of groups that are fully resolved or only manual-attention.

Within the same priority bucket:
- `Group by Column` follows configured target-column order
- `Group by Paper` follows stable matched-row order when available, otherwise stable PDF-name order

Grouped sections may be collapsible when that improves density, but grouped triage must remain immediately scannable.

The sidebar must use compact grouped cards rather than tall repetitive cards.

Compact cards should show only the essential triage information:
- target column
- triage-oriented status
- confidence or support level

Compact cards must also include a high-scan visual progress indicator such as a colored left border or equivalent marker. At minimum, the compact triage projection must distinguish:
- yellow = pending or undecided
- green = accepted
- red = needs manual entry or unresolved manual action

The broader product status taxonomy still applies, but the sidebar may project it into a denser triage view only if review decision state, evidence/support quality, and match outcome remain separately visible through group headers, badges, compact sublabels, or detail state.

Queue density and fast scanning are first-class requirements. Grouping, density, filtering, and saved views or presets must support both rapid triage and deeper investigation.

The review workspace must also handle pre-review states well, including:
- no runs yet
- run selected but still validating or running
- completed run with no actionable proposals
- completed run with warnings
- failed run with diagnostics or at least an actionable failure message

In those pre-review states, the UI must explain whether the operator should start a run, wait for processing, inspect warnings, or inspect diagnostics, instead of only showing the absence of proposals.

When a run is in `running`, the user-facing status surface should show coarse progress at the level of current pipeline stage plus current item when available. MVP does not require a full job monitor or resumable task graph. Minimal structured stage and repeated-work timing stats are required for diagnosis, but broad telemetry-platform behavior is out of scope.

Inspection of unmatched, ambiguous, and duplicate-row-conflict PDFs must remain available from the same review workspace, and it must identify at least the PDF name, match outcome, and rationale for the unresolved state.

In MVP, unresolved-match inspection is inspect-only. The operator does not need direct rematch, reassignment, or conflict-resolution actions from that same surface.

The default queue ordering should prioritize actionable review items ahead of blocked or otherwise unresolved records.

Blocked, unresolved, unmatched, ambiguous, or duplicate-row-conflict records must remain visible for inspection, but they should not dominate the main actionable review flow by default.

The reviewer must be able to:
- accept a proposal
- accept a proposal with edits
- confirm no data in paper
- reject a proposal
- bulk-accept the currently visible filtered proposal subset, subject to confirmation
- move through proposals efficiently without recording a decision
- cycle through evidence items efficiently without losing proposal context
- inspect unmatched and ambiguous PDFs
- see progress counters including reviewed versus total proposals and decision breakdowns

Export may proceed with only a subset of proposals reviewed.

Unreviewed proposals that have not been explicitly accepted must be discarded from export.

The review interface must show enough row context, column context, proposal state, evidence context, and rationale context for a meaningful decision.

The middle pane is the primary details and decision surface.

Explicit row context must appear near the top of the middle pane.

In Verify mode, the middle pane must present a clear comparison between the existing value and the proposed value.

Rationale should default to a short, scannable summary, with fuller rationale available through expansion when needed.

If the model finds no value, the middle pane must not dead-end. The no-value state must still support reviewer action with at least:
- an `Enter edited value` input or equivalent
- a `Confirm No Data` action or equivalent

`Confirm No Data` is a valid resolved outcome meaning the reviewer believes the paper does not report the value. It must remain distinct from rejecting a wrong or untrustworthy model output.

The persisted review semantics must preserve that distinction through a dedicated confirmed-no-data review outcome that does not collapse `not reported in paper` into `model wrong`.

At minimum, non-accepted or manually resolved review outcomes must preserve structured resolution reasons that distinguish:
- not reported in paper
- insufficient evidence
- model wrong
- needs manual entry

Accept-with-edit must behave as an explicit edit-save action rather than a vague duplicate of normal acceptance.

After the reviewer records `accept`, `accept with edit`, `confirm no data`, or `reject`, the workspace should auto-advance to the next reviewable proposal by default.

If rationale is rendered in bullet form, the UI must render it cleanly as concise markdown bullets rather than as a dense paragraph blob.

Proposal status, evidence source, and warning state must be visually distinguishable at a glance.

Accept actions must not be available for blocked items or items without a reviewable proposal value.

Figure-derived evidence should be displayed crop-first, with caption directly attached and the full page accessible on demand.

The right evidence pane must support zoom and pan for document evidence.

The in-app viewer's primary job is to show evidence quotes, page focus, and highlight overlays reliably. It is acceptable for the in-app viewer to prioritize annotation fidelity over full native-reader behavior, provided the UI offers an explicit one-click path to open the same PDF in the operating system's default local PDF viewer for ordinary reading and search.

If strong highlighting and evidence navigation can coexist cleanly with native pan, drag, selection, and search in the same in-app mode, that is preferred. If not, highlight quality and evidence navigation take priority and the explicit local-viewer fallback remains required.

The viewer must support real review work. Required navigation capabilities are:
- previous and next page
- jump to a specific page by number
- zoom in and out
- focus on evidence: when an evidence item is selected, the viewer must scroll to and center or highlight the relevant region
- stable refocus: when the selected evidence item changes or when zoom changes, the viewer must refocus stably without arbitrary jumping
- figure-to-full-page context: figure evidence must be viewable both as a focused crop and as full page context accessible from the same pane
- open in local viewer: the operator must be able to open the current PDF in the default OS PDF application for standard reading, text selection, copy/paste, and search outside the in-app annotated pane

In-viewer text search is optional. If the annotated pane does not provide full text-search or native text-selection behavior, the UI must provide an obvious fallback by opening the PDF in the operating system's default local PDF viewer.

The quote list and the document viewer must stay synchronized around the currently selected evidence item. Selecting a different evidence item in the list must update the viewer to show that item's location. The viewer must not remain stuck on an unrelated page or position when evidence selection changes.

Clicking the selected quote or highlighted evidence should be able to populate either the proposed-value input or the edited-value input, depending on the active editing state.

Populate-from-evidence is a reviewer-assist action only: it must stage text into the active input and must not auto-save, auto-accept, or silently record a decision.

The default populate behavior must replace the active input with normalized text from the explicitly clicked evidence span. Append behavior may exist only as a separate explicit action.

Automatic populate must apply only to textual evidence, including quote-plus-page text and figure-caption text, not to raw image crops with no textual payload.

If the reviewer has not explicitly selected multiple spans, the populate action must use only the clicked span rather than concatenating all visible evidence.

If populated text is obviously longer than the target field shape or violates known field-format guidance, the UI must stage it without silent truncation and require reviewer trimming or confirmation before save.

When no scoped evidence is available, the evidence pane must still provide a useful fallback action such as opening the full PDF.

When highlight geometry is unavailable, the UI must explain that limitation explicitly rather than faking highlight boxes.

The review interface must support filtering by row, column, PDF, evidence status, figure-derived evidence, and ambiguous or unmatched match status.

Any stored proposal must be reviewable in the interface, including proposals whose text evidence is shown as quote plus page without a reliable highlight.

The review workspace must expose direct access to the main run artifacts needed by a reviewer after decisions are made, including the exported workbook, audit log, run summary, and reviewer summary.

Keyboard shortcuts must be surfaced in context through button tooltips or equivalent inline affordances. The operator must not need to rely on a footer legend alone to discover core review shortcuts.

Keyboard support must include fast sequential review behavior, including next or previous proposal navigation, focus edit input, and next or previous evidence navigation.

### FR-10 Spreadsheet protection, Verify mode, and Eval mode

The system must not overwrite already-filled cells by default.

The system must support three operator-facing run modes:

- **Normal mode**: generate proposals only for empty or missing target cells.
- **Verify mode**: apply the normal extraction flow to already-filled cells so a reviewer can compare proposals against existing entries inside the app.
- **Eval mode**: use the completed human-filled table as the gold source, but create an app-owned masked working copy of the target cells before extraction so proposal generation cannot see the gold target values.

Verify mode must be configurable through the run configuration and enabled by default.

`verify_mode = true` and `eval_mode = true` is invalid and must fail early. These modes have different purposes: Verify mode is for in-app reviewer comparison workflows, while Eval mode is for leakage-aware benchmark runs whose outputs are scored later by a separate eval tool.

In Verify mode:
- proposals for already-filled cells must be visible in the review interface
- the reviewer must be able to compare the proposed value against the existing entry
- accepted updates to already-filled cells must be exportable
- reviewer decisions on verified cells must contribute to reviewer-outcome statistics and per-column review summaries for the run

In Eval mode:
- extraction, style-profile shaping, and any current-cell context used for target cells must operate on the masked working copy rather than the original completed table
- the original completed table remains the gold source and must remain unchanged
- run artifacts must preserve explicit mode truth, per-run prompt identity, and eval-table provenance: original gold-table source path or reference plus hash and snapshot when feasible, and masked working-table path plus hash and snapshot
- empty gold-table cells must not be interpreted by the main app as proof that the paper does not report the field
- the masked working copy must preserve structure and content relevance needed for extraction and downstream evaluation, but workbook-formatting preservation in that internal artifact is not guaranteed
- the main app must emit eval-ready artifacts but must not compute the final eval metrics or require a dedicated eval UI

The system may treat single-space or similarly trivial placeholders as empty when configured to do so.

### FR-11 Export

The system must export:
- an updated XLSX table containing the original retained values plus only explicitly accepted changes
- an audit log of changes
- reviewer-outcome summaries and run diagnostics

Export must be a manual reviewer action from the review UI. It must not occur implicitly at run completion or as a side effect of recording review decisions.

The original input table must remain unchanged.

Changed cells must be visually highlighted in the exported table.

The export guarantee is content-only fidelity plus highlighting of changed cells. Workbook formatting, formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, and similar workbook behavior are out of guarantee for MVP.

The audit log must include, at minimum:
- row identifier
- column identifier
- old value
- new value
- proposal source
- reviewer decision
- decision timestamp

When a persisted review-decision record exists, the audit-log timestamp must come from that stored decision record rather than from a placeholder string.

### FR-12 Diagnostics and reviewer-outcome summaries

The system must preserve diagnostics that help explain:
- why a PDF was matched, left unmatched, or marked ambiguous
- why a value was proposed, left unclear, blocked, skipped, or not proposed
- whether evidence was strong, weak, missing, or recovered
- whether parsing used a fallback or degraded path
- why a run finished with few or no usable proposals

The system must provide a normal user-facing run summary with at least:
- current or terminal run state
- actionable status or failure message
- readiness or preflight outcome when the run did not proceed normally
- run mode (`normal`, `verify`, or `eval`)
- number of PDFs processed
- number of PDFs matched, unmatched, and ambiguous
- number of proposals generated
- number of proposals reviewed
- accepted as-is count and rate
- accepted with edit count and rate
- confirmed no-data count and rate when applicable
- rejected count and rate
- proposal coverage
- number of accepted changes
- configured provider for the run
- configured text model for the run
- configured vision model for the run when configured
- provider mode for proposal generation, such as live local, live cloud, unavailable, disabled, or explicit degraded/demo mode
- negotiated structured-output mode for extraction (`json_schema`, `json_object`, or `none`)
- whether structured-output fallback was used
- retrieval mode for the run (baseline lexical or experimental hybrid)
- readiness or structured-capability failure reason when applicable
- configured parser choice plus the actual parser identity or version used when available
- schema hash or schema version plus config snapshot reference or config hash
- prompt identity for the run, including prompt-bundle identity (`prompt_bundle_id`, optional `prompt_bundle_version`, `prompt_bundle_path`), prompt-bundle hashes (`prompt_manifest_hash`, `prompt_bundle_hash`), prompt file provenance map, and effective prompt-contract identity (`prompt_hash`; `prompt_version` when available)
- original gold-table and masked working-table provenance when Eval mode is enabled
- whether processing stayed local or used cloud providers
- reviewer-outcome summary when Verify mode is enabled

In addition to summaries, the run must persist a compact structured run-stats artifact (or an equivalent small set of structured artifacts) for bottleneck and repeated-work diagnosis.

The run-stats scope should stay intentionally narrow, manually inspectable, and benchmark-friendly.

Target observability dimensions are:

- per-run timing: `run_total_ms`, `stage_validating_ms`, `stage_matching_ms`, `stage_parsing_ms`, `stage_style_profiles_ms`, `stage_extraction_ms`
- per-PDF timing and shape: `parse_pdf_ms`, `retrieval_prep_ms`, `pdf_cell_count`
- per-cell timing: `retrieval_query_ms`, `text_model_ms`, `evidence_anchoring_ms`, conditional `figure_review_ms` when triggered, and `cell_total_ms`
- run or PDF counters: `pdf_count`, `eligible_cell_count`, `cells_per_pdf`, `chunk_count_total`, and `chunk_count_by_type` for paragraph, section, caption, table_region, abstract, and list_item
- retrieval counters: `retrieval_calls`, `retrieval_calls_per_pdf`, `chunk_build_count_per_pdf`, `idf_build_count_per_pdf`, `neighbor_chunks_added_count`
- provider counters: `text_model_call_count`, `vision_model_call_count`, and existing `provider_request_counts` when present
- evidence counters: `evidence_item_count`, `direct_quote_count`, `approximate_highlight_count`, `quote_plus_page_count`, `needs_more_evidence_count`, `recall_rescue_used_count`, `whole_document_used_count`, `figure_review_triggered_count`, `figure_derived_evidence_count`

Implementation may roll out a practical subset first, but artifacts and naming should clearly target these dimensions so later expansion does not require redesign.

Detailed logs and deeper diagnostics may exist as advanced outputs for development and troubleshooting.

The normal user-facing run summary should remain useful even before the run reaches a terminal state, for example by showing validation or processing state together with the resolved input/config context.

Run summaries and review summaries must also surface duplicate-row conflicts, degraded parsing conditions, and evidence-fallback states when those conditions materially affect reviewer trust or throughput.

When a run is not yet reviewable, the summary surface should still help the operator understand what has happened so far, what is blocked, and whether review will become available automatically or requires intervention.

Runs that fail during readiness or soon after launch must still retain the resolved config/input context and any completed preflight results so operators can diagnose the failure without opening source code.

Download surfaces must also remain truthful: config snapshots and diagnostics may be available early, but exports and summaries must not be presented as ready when the underlying files have not been written yet.

If no verified cells have been reviewed yet, reviewer-outcome reporting should remain visible but explicitly provisional. The UI should keep per-column evidence-coverage lines visible with wording that makes clear they are coverage context rather than reviewer-outcome scores until at least one verified cell has actually been reviewed.

If a run completes but yields no reviewable proposals, the normal summary must make clear whether the reason was blocked matching, degraded parsing, explicit disabled or degraded mode, extraction failure, or another diagnostic class rather than collapsing all such cases into a generic `completed` result.

In MVP, reviewer-outcome summaries are the primary reporting mechanism inside the app, and full benchmark scoring across heterogeneous field types is delegated to a separate eval tool or repo.

Reviewer-outcome summaries must include, at minimum:
- reviewed verified-cell count
- accepted as-is count and rate
- accepted with edit count and rate
- confirmed no-data count and rate when applicable
- rejected count and rate
- proposal coverage
- per-column reviewer outcome breakdown
- evidence coverage
- anchorable or highlightable evidence rates when applicable

Verify mode may still compare proposals against already-filled cells, but future automated Verify-mode scoring is deferred and may be added later. Eval mode should emit the minimal persisted data needed for later external scoring instead of implementing that scoring inside the main app.

If there are too few reviewed proposals or verified proposals for meaningful interpretation, the system must warn explicitly.

If reviewer-outcome reporting may be biased or if any future automated evaluation would be leakage-prone, the system should warn explicitly.

Summary metrics and warning flags must be internally consistent across UI and artifact files. Counts must reflect persisted underlying facts, and provisional or not-yet-evaluable states must be labeled clearly instead of being reported as final warnings or scores.

Run summaries and reviewer summaries must remain derivable from persisted artifact data so they can be recomputed and inspected later.

In Eval mode, the persisted artifact contract must remain minimal but sufficient for downstream scoring. Across `run.json`, `config.snapshot.json`, proposal or evidence artifacts, and summaries, the run must preserve at minimum: run id; mode; stable row id, column id, and cell id; pdf id; raw proposal value; proposal state; support label; field type when known; evidence items with at least page, quote text, and evidence type; text model id; vision model id if used; parser identity or version; prompt identity, using `prompt_version` when available and deterministic `prompt_hash` otherwise; schema hash or schema version; config hash or config snapshot reference; original gold-table source path or reference plus gold-table content hash and run-bundle snapshot path when feasible; and masked working-table run-bundle path plus masked-table hash and masked snapshot artifact.

If retrieval or evidence-coverage diagnostics are emitted for Eval mode later, they must remain supporting diagnostics rather than becoming the main correctness score inside this app.

### FR-13 Structured-document support

The system must work with PDFs whose useful evidence may appear in prose, captions, table-like content, or scoped figure-aware fallback evidence.

When document structure can be detected, the system should preserve enough of that structure to improve proposal quality and evidence review without changing the user-facing workflow.

### FR-14 Run completion semantics

If a run matches one or more PDFs and meaningful processing occurred but the result is still only partially useful, the run outcome may be `completed with warnings` rather than silently successful.

If provider unavailability or provider-unreachable state prevents useful extraction before processing starts, the run must fail rather than being recast as `completed with warnings`.

Failures that prevent safe execution must be surfaced clearly in run diagnostics.

---

## Review and trust requirements

### TR-1 Explainable proposal state

A reviewer must be able to tell, for each proposal:
- what value was proposed
- what support level it has, such as direct evidence, inferred from evidence, weak evidence, or figure-derived evidence
- what evidence supports it, including which item is primary and which are supporting
- what evidence type each item is: direct quote, inferred reasoning, calculation, approximate highlight, quote-plus-page fallback, `caption_grounded_figure_evidence`, or `visual_interpretation_figure_evidence`
- whether the value depends on calculation or reasoning, shown separately from direct quotes
- whether additional scrutiny is recommended

The primary reviewer question is what the paper supports, including whether the paper does not report the target value, not whether the model happened to produce an answer.

Direct quotes must be shown separately from reasoning and calculations. A reviewer must be able to distinguish which parts of the evidence are verbatim from the paper and which are model-constructed inferences.

Figure-derived evidence must be visibly distinguishable from text or table evidence.

When figure evidence is used, reviewers must be able to inspect both the figure crop and the full page.

Reviewer judgment remains essential even when a proposal is present and evidence is attached.

### TR-2 No hidden spreadsheet mutation

Spreadsheet changes must happen only through explicit reviewed export behavior.

### TR-3 Reversible audit trail

Every exported change must be traceable back to its reviewed proposal and decision outcome.

### TR-4 Safe handling of uncertainty

The system must not silently convert uncertainty into certainty. Ambiguous matches, unclear extractions, weak evidence, and failed highlights must remain visible as such.

---

## Non-functional requirements

### NFR-1 Local-first operation

The product should support local-first operation for document handling and review workflows.

Single-user desktop or local operation is sufficient for the MVP.

### NFR-2 Reproducibility

A completed run should preserve enough inputs, configuration, outputs, and decisions that the run can later be inspected, explained, and compared against other runs.

For Eval mode, this includes preserving stable mode truth plus the gold-table and masked-working-table references needed to audit that masking occurred.

Bit-for-bit deterministic replay is not required for the MVP.

### NFR-3 Inspectability

Intermediate and final outputs should remain inspectable by an advanced user for debugging and reviewer-outcome analysis.

### NFR-4 Robustness to partial failure

Failure in one stage or for one PDF should not necessarily invalidate the entire run. The system should preserve partial results whenever safe.

### NFR-5 Performance

The system should be usable on realistic researcher-sized batches of PDFs without requiring manual intervention between every document.

A realistic MVP workload is roughly 1 to 150 PDFs, with smaller batches common during testing.

### NFR-6 Privacy, provider transparency, and contract parity

The product should make it clear when external model or parsing providers are used.

At minimum, run outputs or the UI should make visible:
- whether processing stayed local or used external providers
- which providers/models were used for the run

Provider naming and config semantics should remain canonical across runtime validation, config examples, docs, tests, and operator-visible UI surfaces.

Cloud credentials must be supplied through environment variables, secret references, or equivalent local secret handling rather than committed example credentials.

This transparency should appear in a concise run summary rather than only in deep diagnostic logs.

### NFR-7 Extensibility

The product should allow future replacement or addition of parser, retrieval, and model backends without changing the user-facing workflow.

### NFR-8 Usability

The review interface should be visually clear, efficient for repeated review work, and suitable for modern desktop use.

Usability for MVP specifically requires dense grouped triage, clear no-data handling, evidence interaction that supports direct curation work, and setup flows that are picker-driven rather than path-heavy.

### NFR-9 Workflow and documentation truthfulness

The README, in-app labels, status text, and normal startup commands must describe the same real local workflow.

The checked-in config example and runtime config schema are part of that same operator-facing contract and must use the same terminology and semantics for provider, parser, model, Verify-mode, Eval-mode, and run-state settings as the README and UI.

Operator-facing docs should include at least one known-working LM Studio model example while remaining explicit that better or newer models may also satisfy the contract.

Developer-only shortcuts, helper scripts, or partial implementation paths must not be presented as the primary operator path unless they truly are the intended MVP workflow.

---

## Key behavioral rules

- Already-filled cells are protected by default.
- Evidence quality influences reviewer scrutiny, not only whether a proposal exists.
- Each proposal exposes one primary evidence item, selected by evidence ranking. Additional supporting evidence items are ordered by authority and relevance.
- Evidence must be ranked: the most authoritative evidence becomes primary. The first model-returned quote is not automatically primary.
- The product distinguishes evidence types: direct quote, inferred reasoning, calculation, approximate highlight fallback, quote-plus-page fallback, `caption_grounded_figure_evidence`, and `visual_interpretation_figure_evidence`. These types must be labeled and rendered distinctly.
- Direct quotes must be shown separately from reasoning and calculations in the review UI.
- Exact quote highlighting is produced from page-text alignment when possible; if it fails, fallback must be labeled as fallback.
- The quote list and the document viewer must stay synchronized around the currently selected evidence item.
- Proposals may be supported by multiple evidence items.
- Reviewer-visible evidence must remain anchored to the source even if internal retrieval uses transformed text.
- Diagnostic-only outcomes must remain clearly distinct from reviewable proposals.
- Any stored proposal remains reviewable, even when text highlighting fails and only quote plus page evidence is available.
- Schema-first extraction remains valid even when a table or a target column has no prefilled example values.
- One target cell receives at most one best proposal per run.
- Proposal identifiers remain unique within a run even when multiple PDFs surface the same row/column target.
- Ambiguous PDF-to-row matches block extraction rather than silently proceeding.
- Duplicate PDF matches to the same row block all conflicting PDFs until manual cleanup.
- Run mode is always one of `normal`, `verify`, or `eval`; Verify mode and Eval mode cannot both be enabled.
- Verify mode is configurable and enabled by default for in-app comparison on already-filled cells.
- Eval mode uses an app-owned masked working copy for leakage-aware benchmark runs and never treats gold-empty cells as proof of paper absence.
- Confirmed no-data outcomes remain distinct from rejected-or-model-wrong outcomes in review state and summaries.

---

## Acceptance criteria

### AC-1 Import readiness

Given a valid table, schema, PDF folder, and run configuration with standardized `Title`, `Authors`, and `Publication Year` columns,
when the user starts a run,
then the system records a resolved config snapshot and resolved input context, including explicit run mode, normalizes common real-world input quirks such as BOM-marked headers and Excel datetime cells, and identifies missing versus already-filled target cells.

### AC-1a Preflight and readiness truth

Given a run configuration references a provider, model, parser, OCR path, output path, or other required runtime dependency,
when the user starts a run,
then the system performs explicit readiness checks before normal processing, surfaces actionable errors for invalid or unavailable dependencies, preserves the resolved config/input context for inspection even on early failure, and does not pretend the run is functionally healthy when the live proposal path is not ready.

### AC-1b Parser truthfulness

Given a run configuration selects a parser,
when readiness or parsing begins,
then the operator can tell which parser was configured, which parser was actually used, and whether any fallback path was explicitly enabled, and the app does not silently substitute another parser by default.

### AC-1c Setup ergonomics and resolved path truth

Given the operator is preparing a run from the browser UI,
when they select or override relevant inputs,
then the setup flow prefers browser-compatible picker controls over raw path typing, keeps the config-path field editable as text, provides a `Browse...` action for normal local use, resolves relative and platform-specific path inputs into one clear run context, materializes picker-selected inputs into backend-readable staged files or directories or another explicit server-side input handle before execution, preserves config-file authority for advanced behavior, keeps the target-columns display compact by default through truncation, collapse, or equivalent compact presentation, and shows both the logical input source and the backend-visible runtime locator in the resolved run context.

### AC-2 Matched extraction path

Given a PDF that can be matched to a row,
when extraction is run,
then the system attempts each eligible target column, including long-text fields, uses column name, description, and optional field type as the primary extraction contract, remains functional even when no prefilled spreadsheet examples exist for that column, prefers a truthful `unclear` outcome over unsupported guessing, and stores one best outcome for each attempted target cell.

### AC-2a Structured-output compatibility and recovery

Given a live provider rejects the preferred guided-JSON or structured-output mode, or returns malformed structured JSON,
when extraction is run,
then the system tries `json_schema`, may fall back to `json_object` when `json_schema` is unsupported for that provider-model path, labels that fallback as explicit degraded mode, retries once with stronger instruction if the response is invalid, attempts minimal syntactic JSON repair when appropriate, preserves the proposal contract if recovery succeeds, records a clear hard error only if that bounded recovery fails, and does not switch to broad prompt-only unstructured fallback by default.

### AC-2b Recall rescue and field typing

Given a target field has an optional schema `field_type` and the first retrieval-based extraction pass returns `unclear`,
when extraction continues,
then the system may use expanded retrieval and a bounded section-level or optional full-text rescue pass, while preserving the field-type contract and leaving whole-document mode opt-in rather than default.

### AC-3 Ambiguous matching blocking

Given a PDF that cannot be matched confidently to a single row, or two PDFs that match the same row,
when matching completes,
then the system records the outcome as ambiguous, unmatched, or duplicate-row conflict as applicable, blocks extraction for the affected PDF or PDFs, and keeps them visible for manual inspection and cleanup.

### AC-4 Proposal evidence requirement

Given a non-empty proposed value,
when the proposal is stored,
then the proposal includes at least one evidence item when feasible or is flagged as needing more evidence.

### AC-5 Reviewability

Given a stored proposal,
when a reviewer opens it in the review interface,
then the reviewer can inspect the proposed value, proposal state, relevant row and column context, primary evidence, and concise rationale or calculation when applicable, including clear quote-plus-page text evidence when a text highlight could not be recovered, while also seeing visually distinct status/evidence/warning cues and the surrounding run-summary context.

### AC-5a Grouped queue triage

Given a run with multiple reviewable proposals,
when the reviewer uses the left sidebar,
then the queue supports `Group by Paper` and `Group by Column`, presents compact grouped cards rather than tall repetitive cards, keeps grouping headers or badges dense and scannable, shows group-header summary context including total count, pending count, and any warning or manual-attention badge needed for triage, orders groups predictably with pending-actionable groups first, configured column order for column groups, and stable matched-row or PDF-name order for paper groups, and preserves separate signals for review decision state, support quality, and match outcome rather than collapsing them into one vague status chip.

### AC-5b Compact triage indicators

Given proposals appear in the sidebar triage view,
when the reviewer scans the queue,
then each compact card shows at least target column, triage-oriented status, and support level, and uses a high-scan progress marker such as a colored left border that makes pending, accepted, and manual-attention states easy to distinguish.

### AC-5c Explicit no-value handling

Given the model did not produce a usable value or the reviewer determines the paper does not report the target field,
when the reviewer uses the middle pane,
then the UI still provides an `Enter edited value` path and a `Confirm No Data` path or equivalent, and the no-data resolution is persisted distinctly from rejecting a wrong model output.

### AC-5d Evidence interaction, viewer navigation, and fallback behavior

Given a proposal has selected text or figure evidence,
when the reviewer uses the right evidence pane,
then the viewer supports zoom and pan; supports previous and next page navigation; supports jump to page by number; provides a normal reading mode with pointer-drag page movement and text selection/copy when the PDF source and chosen viewer mode allow it; supports next and previous evidence navigation; focuses on the currently selected evidence item and refocuses stably when evidence selection or zoom changes; supports figure-to-full-page context navigation; keeps the quote list and the document viewer synchronized so selecting a different evidence item in the list moves the viewer to that item's location; preserves quote-plus-page fallback when highlight geometry is missing; explains missing highlight geometry instead of faking boxes; distinguishes approximate highlight fallback from exact highlight; allows full-PDF fallback when scoped evidence is unavailable; and supports clicking selected quote or highlight evidence into the active proposed-value or edited-value workflow as a non-saving staging action that replaces the active input by default, applies only to textual evidence or figure-caption text, uses only the explicitly clicked or selected span, and never silently truncates overlong text.

### AC-5f Actionable counts and auto-advance

Given the reviewer is working through a run,
when the queue and review actions are displayed,
then the main progress headline uses actionable or reviewable proposals by default, broader attempted totals remain secondary, and after `accept`, `accept with edit`, `confirm no data`, or `reject`, the workspace auto-advances to the next reviewable proposal when one exists.

### AC-5e Rationale rendering

Given a proposal includes rationale formatted as concise markdown bullets,
when the reviewer opens the middle pane,
then the default rationale view remains scannable and the bullet structure renders cleanly as markdown bullets rather than as a dense paragraph blob, with fuller rationale available only through expansion when needed.

### AC-6 Decision control

Given a proposal under review,
when the reviewer accepts, edits, confirms no data, rejects, or bulk-accepts the currently visible filtered subset after confirmation,
then the system stores that decision as an explicit persisted review record, preserves the prior proposal state for auditability, records structured resolution reasons for non-accepted or manually resolved outcomes, and does not offer accept actions for blocked or non-reviewable items.

### AC-6a Shortcut affordances

Given the review workspace exposes keyboard shortcuts for core actions,
when the reviewer hovers or focuses the relevant controls,
then the shortcut is surfaced in a tooltip or equivalent inline affordance on the control itself rather than only in a separate legend.

### AC-7 Locked-cell safety

Given an already-filled input cell,
when the run completes and exports are generated outside Verify mode,
then that cell is not overwritten unless explicit review behavior has authorized the change.

### AC-8 Verify mode behavior

Given Verify mode is enabled, and Verify mode is on by default unless disabled in configuration,
when the system processes already-filled cells,
then it generates reviewable proposals for those cells, allows explicit accept/edit/confirm-no-data/reject decisions, and uses those reviewer decisions in reviewer-outcome statistics and per-column review summaries.

### AC-8a Eval mode behavior

Given Eval mode is enabled and Verify mode is disabled,
when the system processes a completed human-filled table,
then it creates and uses a masked working copy of the target cells for extraction, preserves explicit mode truth plus gold-table and masked-table provenance in artifacts and summaries, and does not expose target-cell gold values to the extraction path.

### AC-8b Invalid Verify-plus-Eval configuration

Given `verify_mode = true` and `eval_mode = true` in the same run configuration,
when the user starts a run,
then readiness fails early with an actionable validation error, no extraction begins, and the invalid combination is preserved truthfully in diagnostics or resolved config context.

### AC-9 Export integrity

Given accepted proposals,
when the user exports results,
then the system produces an updated XLSX table and an audit log containing only approved changes, while leaving the original input table unchanged, any available audit timestamp comes from the persisted review-decision record for that change, and export happens only after an explicit manual export action from the review UI.

### AC-10 Export fidelity

Given an exported XLSX table,
when the export is opened,
then the table preserves accepted and unchanged cell content correctly, guarantees content-only fidelity plus highlighting of changed cells, and does not promise preservation of workbook formatting or other workbook behavior.

### AC-11 Diagnostic transparency

Given a run fails early or finishes with matched PDFs but no usable accepted values,
when the run reaches its terminal state,
then the system provides diagnostics and resolved context explaining what happened, why no values were produced or accepted, whether parsing was degraded or used fallback, and whether the result is a readiness failure, a completed run with warnings, or another terminal outcome rather than a silent success.

### AC-16a Provider hard-fail truth

Given the configured live provider is unavailable or unreachable before proposal generation can begin,
when the operator starts a run,
then the run fails during readiness with an actionable provider error and does not surface as `completed with warnings`.

### AC-16b Provider readiness versus capability truth

Given provider checks run during readiness or early extraction,
when the system reports status in the UI, run summary, and persisted artifacts,
then it distinguishes at minimum provider unreachable or unavailable, model unavailable or not loaded, `json_schema` unsupported with `json_object` fallback used, and prompt-only JSON fallback used when `json_schema/json_object` are unavailable, and does not collapse those outcomes into one generic "provider unavailable" label.

For LM Studio runs, persisted artifacts must also record whether the app reused an already-loaded model or requested a load, the requested load context, and the load configuration actually applied when LM Studio returns it.

When a live provider rejects guided output because of backend regex or grammar incompatibility for the active request shape, the run artifacts must preserve that reason explicitly rather than flattening it into a generic malformed-JSON or provider-unreachable label.

### AC-12 Weak-evidence handling

Given a plausible proposal with weak, missing, or initially unusable evidence,
when proposal processing completes,
then the system makes one recovery attempt, keeps the proposal reviewable if appropriate, and marks it accordingly, including quote-plus-page review when text highlighting could not be recovered.

### AC-13 Figure-derived support and rescue

Given a target field that remains unresolved after text or table extraction,
when the system identifies relevant figure evidence,
then it may produce a figure-derived proposal with clearly labeled caption-grounded or visual-interpretation evidence, including a crop and caption, for review.

### AC-14 Evaluation integrity

Given Verify mode is enabled but too few verified proposals were reviewed to support meaningful interpretation,
when reviewer-outcome summaries are generated,
then the system emits a warning or explicit limited-review status rather than a misleading normal reviewer-outcome summary, keeps provisional metrics clearly labeled as provisional, and does not show internally inconsistent counts or premature warning flags.

### AC-14a Eval-ready artifact contract

Given Eval mode completes or reaches an inspectable terminal state after extraction work began,
when the operator or a downstream tool inspects the run artifacts,
then the bundle contains the stable proposal, evidence, mode, model, parser, schema, config, prompt-identity, gold-table, and masked-working-table metadata needed for later scoring, including explicit artifact schema versions, table hashes and snapshot references, eval-consumable evidence records, and page-text-compatible source artifacts or deterministic fallbacks, labels the run as Eval mode in summaries and diagnostics, and does not claim that the main app already computed the final benchmark metrics.

### AC-15 Partial-review export behavior

Given some proposals remain unreviewed,
when the user exports results,
then only explicitly accepted proposals appear in the exported workbook and audit log, and unreviewed proposals remain excluded.

### AC-16 Provider transparency

Given a run used one or more model or parsing providers,
when the run summary is shown or exported,
then the summary identifies the provider or model names used, separately identifying the text model and the vision model when both were used, whether processing stayed local or used external services, and whether proposal generation ran live, was unavailable, was disabled, or used an explicit degraded or demo path.

### AC-17 Onboarding and workflow truth

Given a new local operator following the documented primary happy path,
when they install dependencies, start the backend and frontend, open the browser UI, enter a config path, and launch a run,
then the app, README, checked-in config example, runtime config schema, and UI terminology agree on the same workflow, the operator can understand pre-review and in-progress states without consulting source code, the docs include at least one known-working LM Studio model example without treating it as the only valid model, the docs explain what Eval mode is, why it masks target cells, why it cannot be combined with Verify mode, and that downstream scoring belongs to a separate eval tool, and the same app surface remains the normal place to review proposals and export outputs.

### AC-18 Canonical provider contract parity

Given the checked-in config examples, runtime config validation, tests, and operator-visible provider labels,
when a supported provider is referenced,
then the same canonical provider token and settings shape are accepted consistently across those surfaces, including `lm_studio` as the canonical LM Studio config token and `LM Studio` as the operator-visible label, documented compatibility aliases normalize to the same stored form when supported, and unsupported identifiers fail early with a clear error.

### AC-19 Canonical live proposal path

Given the canonical live-smoke fixture target consisting of `tests/fixtures/tables/literature_fixture.xlsx` plus `tests/fixtures/papers/paper_1.pdf`, and a reachable LM Studio configuration,
when the operator runs the normal browser-first workflow,
then the system either produces at least one non-empty reviewable proposal with reviewer-usable evidence or fails early with an explicit readiness error that clearly explains why live proposal generation could not proceed.

---

## MVP boundary

The following behaviors are required for the MVP represented by this spec:

- Spreadsheet import and schema-driven extraction.
- Fuzzy PDF-to-row matching using publication metadata.
- Blocking extraction for ambiguous matches and duplicate PDF matches to the same row.
- A queue-first proposal review workflow with filters, progress indicators, and a focused detail view, followed by XLSX export.
- Evidence attachment and clear weak-evidence signaling.
- Locked-cell protection.
- Verify mode for already-filled cells, including review and reviewer-outcome summaries.
- Diagnostics sufficient to explain no-value or poor-quality runs.
- Evidence quality is a first-class requirement: evidence ranking, evidence type taxonomy, primary and supporting evidence semantics, exact quote highlighting with honest fallback, and synchronized multi-evidence review UX.
- Schema-first extraction is a first-class requirement: extraction works without prefilled cells, optional field typing shapes output when present, and historical spreadsheet values are not semantic exemplars.
- Text-guided targeted figure review when vision capability is available, with figure evidence allowed to supplement, strengthen, corroborate, or rescue any proposal, and with shortlisted requests grounded in retrieved text, captions, and figure-reference context.
- Separate text-model and vision-model configuration with both exposed in reviewer-visible run context and summaries.
- Filtering by row, column, PDF, evidence status, figure-derived evidence, and ambiguous or unmatched match status.
- OCR support as a fallback.

The following behaviors are important but may ship as progressive quality improvements so long as they do not weaken the core review workflow:

- improved figure reasoning quality
- future automated Verify-mode scoring research for free-text or reasoning-heavy fields
- more sophisticated diagnostics in the UI

---

## Success metrics

The following are candidate success metrics:

- accepted as-is rate
- accepted with edit rate
- confirmed no-data rate
- rejected rate
- proposal coverage
- per-column reviewer outcome breakdown
- proportion of missing target cells that receive reviewable proposals
- evidence coverage rate
- evidence display success rate
- match accuracy on a labeled sample
- median review time or time saved per curated paper or per completed row

Metrics should be interpreted together rather than in isolation. For example, a high proposal count with low reviewer acceptance or weak evidence coverage is not a successful run.

---

## Assumptions

- Users already maintain a spreadsheet with meaningful row structure.
- Users can provide a schema that defines what each target column means.
- Most PDFs contain enough text structure to support extraction and evidence display.
- Review quality improves when evidence is visible directly alongside the proposal.
- Each row represents one publication and therefore one primary PDF input for MVP purposes.

---

## Future extensions

These are intentionally out of scope for the current spec but anticipated:

- Collaborative multi-user review.
- Active learning from reviewer decisions.
- Schema-specific validation and normalization assistants.
- Cross-paper aggregation into one row.
- Richer programmatic APIs and integrations.
- Continuous watch-folder ingestion.
- More advanced multimodal figure reasoning and panel alignment.
- Additional export targets beyond XLSX.

---

## Relationship to plan.md

This spec defines what the product must do and what quality bars it must meet.

Technical architecture, parser strategy, retrieval strategy, model behavior, persistence, operational defaults, artifact paths, rollout sequencing, and implementation tradeoffs are intentionally captured in `specs/plan.md` so the spec can remain product-focused.

---

## Appendix: concise product statement

Extract Structured Info from Papers is a local-first, evidence-first paper-to-table review system. It matches papers to spreadsheet rows and proposes values for missing or verified cells, attaching ranked, typed, and anchored evidence to each proposal. The reviewer can inspect direct quotes separately from reasoning and calculations, navigate multiple supporting evidence items in order, and accept, edit, confirm no data, or reject each proposal before exporting an audited XLSX table update. Evidence quality and reviewer trust are first-class product requirements.
