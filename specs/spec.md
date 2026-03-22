# Paper Table Agent - spec.md

## Status

Finalized baseline

## Summary

Paper Table Agent helps a researcher turn a folder of scientific PDFs plus a structured spreadsheet into reviewed spreadsheet updates.

The system matches PDFs to spreadsheet rows, proposes values for missing cells using grounded evidence from the papers, and provides a review interface where a human can accept, edit, reject, or bulk-accept the currently visible filtered subset before any spreadsheet is updated.

The system primarily extracts from text and tables, and may use scoped figure-aware fallback extraction when the field appears likely figure- or table-derived, text or table retrieval remains insufficient, or text-first extraction remains insufficient after evidence recovery.

The product is designed for high-trust extraction workflows where proposed values must remain inspectable, auditable, reversible, and clearly distinguishable by support level.

---

## End-to-end workflow

The intended MVP workflow is:

1. Start a run from the UI by selecting or typing the path to a run configuration file, then let the app validate and snapshot the resolved config before work begins.
2. Normalize table columns and determine which cells are missing versus already filled.
3. Parse PDFs and extract paper-level metadata needed for row matching.
4. Match each PDF to at most one row, while surfacing unmatched, ambiguous, and duplicate-row conflicts.
5. Generate one best proposal per eligible target cell, with evidence and support labeling.
6. Let a human reviewer inspect, filter, accept, edit, reject, or bulk-accept the currently visible filtered subset.
7. Export a new XLSX workbook containing only explicitly accepted changes plus an audit log and run summaries.
8. Preserve diagnostics and artifacts so the run can be inspected later.

This workflow is intentionally linear from the operator’s perspective even if the implementation uses multiple internal stages.

### Operator-visible run states

The UI must make run lifecycle state explicit. The operator-visible states are:

- `ready`: the UI has enough information to start a run from a config file, but work has not started yet
- `validating`: the app is checking config paths, required inputs, and basic run readiness
- `running`: the staged pipeline is actively parsing, matching, retrieving, extracting, or writing outputs
- `completed`: the run finished cleanly and is ready for review/export
- `completed with warnings`: the run finished and is reviewable, but unresolved matching issues, export caveats, or other important warnings remain visible
- `failed`: the run could not complete and the operator must be able to see an actionable reason

These states are reviewer-facing UX requirements, not merely backend implementation details.

---

## Problem statement

To compare technical parameters and findings across research projects and scientific papers, researchers need to read publications, find relevant information, extract it, and organize it in spreadsheets. This is slow, repetitive, and error-prone.

General chat-style document tools can answer questions about PDFs, but they do not reliably support row-aware extraction against a spreadsheet schema, evidence-backed human review, or audited spreadsheet export.

Paper Table Agent addresses this by turning PDF-to-table curation into a structured review workflow rather than a chat interaction.

---

## Goals

- Reduce manual effort for extracting structured information from scientific papers into tables.
- Keep a human reviewer in control of every spreadsheet update.
- Preserve evidence and provenance for every proposed value.
- Support repeatable, auditable runs across many PDFs.
- Work well for scientific papers with mixed prose, captions, tables, and figures.
- Support figure-aware fallback extraction for cases where important information is primarily contained in charts, diagrams, image panels, or other figure content.
- Support verification against already-filled cells when enabled, so the user can compare proposals against existing entries and assess app performance through reviewer outcomes.

## Non-goals

- Fully autonomous spreadsheet editing without human review.
- General-purpose chat over documents.
- Replacing expert judgment for ambiguous scientific interpretation.
- Multi-user collaboration workflows.
- Full multimodal parsing or reasoning on every page by default.
- In-UI advanced parameter tuning; advanced run behavior is controlled through the run configuration.

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
- Evidence is attached to proposals, not hidden inside model reasoning.
- Plausible values may still be surfaced even when evidence is weak, but they must be flagged accordingly.
- A proposal being present does not imply that it is correct.
- Attached evidence does not automatically imply that a proposal is correct.
- Locked cells are protected by default, except when a human explicitly accepts an update in verify mode.
- All runs are auditable.
- The product is optimized for trustworthy extraction workflows, not maximal automation at any cost.
- The product should preserve a clear distinction between directly supported values and inferred or derived values.

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
- documentation reflects the actual happy path and the actual limits of the product

---

## User stories

1. As a researcher, I want to load my spreadsheet, schema, and PDF folder so the system can identify missing values worth extracting.
2. As a researcher, I want the system to match each PDF to the most likely spreadsheet row so that extraction happens in the correct row context.
3. As a researcher, I want the system to propose values for missing cells and show supporting evidence from the paper so that I can judge whether the proposal is trustworthy.
4. As a reviewer, I want to inspect the PDF page with a highlight of the most relevant quoted evidence, or at minimum the quote plus page when highlighting fails, and see a concise rationale or calculation when the value is derived, so that I can accept, edit, or reject it confidently.
5. As a curator, I want non-empty spreadsheet cells to remain protected unless I explicitly choose otherwise so that previously curated data is not overwritten accidentally.
6. As a curator, I want an updated export file and audit log after review so that I can update my master table safely and trace what changed.
7. As a developer or advanced user, I want diagnostic outputs about matching, extraction, evidence quality, and reviewer-outcome reporting so that I can troubleshoot poor runs.
8. As a reviewer, I want verify mode to compare proposals against already-filled cells so that I can review disagreements, make decisions on them, and assess how well the app is performing through reviewer outcomes.

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
- Storing one or more evidence items per proposed value.
- Human review of proposals with PDF evidence display when available, including weaker review states when text highlighting fails but quote plus page evidence is available.
- Figure-aware fallback extraction for unresolved or weakly supported cases, across all figure types and all target field types.
- Figure-based evidence display in review when available.
- Verify mode: generating proposals for already-filled cells, showing them in review, and including reviewer decisions on them in run summaries.
- MVP filtering by row, column, PDF, evidence status, figure-based evidence, and ambiguous or unmatched match status.
- Accept, accept-with-edit, reject, and guarded bulk acceptance of the currently visible filtered proposal subset.
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

---

## Inputs

The system accepts:

- A table file in CSV or XLSX format.
- A schema, either embedded in the workbook or provided separately.
- A folder of PDFs.
- A run configuration file.

### Input expectations

- The schema contains at least a `column_name` and a `description` for each target column.
- The table must contain standardized metadata columns named `Title`, `Authors`, and `Publication Year` for row matching.
- The schema defines the intended meaning of each target field.
- PDFs are scientific papers or similarly structured technical documents.
- PDFs may contain important information in prose, captions, tables, and figures.
- Born-digital scientific PDFs are the main target.
- OCR support may be used as a fallback for scanned or text-inaccessible PDFs.
- Supplementary PDFs should ideally be merged with the main paper by the user before running the app.

### Input guidance from existing cells

- The system may derive a non-binding style or format profile from existing filled cells for all field types through a preprocessing LLM, but such guidance must be used only to influence output shape, detail level, and formatting. Raw existing cells are not passed as semantic exemplars by default, and proposal content must remain grounded in the current PDF.

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

### Output expectations

- No spreadsheet cell is updated automatically without an explicit human decision.
- All exported changes are traceable back to reviewed proposals.
- Proposal identifiers must remain unique within a run, including cases where multiple PDFs target the same row/cell context.
- The exported table must remain in XLSX format, even when the input table is CSV.
- The exported XLSX table guarantees content-only fidelity plus highlighting of changed cells. Workbook formatting, layout, formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, and similar workbook behavior are out of guarantee for MVP.
- Cells changed through accepted proposals must be visually highlighted in the exported XLSX table.
- Diagnostic outputs remain available after the run finishes.
- Verify-mode reviewer-outcome summaries remain available even when there are no verified cells, with a clear status or explanation instead of silent empty metrics.
- Verify-mode reviewer-outcome summaries must not silently report an all-zero result when no targets were actually reviewed.
- Unreviewed proposals must not appear as accepted changes in the exported table.
- A concise run summary must report provider/model names used, whether processing stayed local or used cloud providers, and key run metrics.

---

## Proposal and review terminology

The product uses the following reviewer-facing concepts consistently across the UI, exports, and diagnostics:

- **Match outcome**: whether a PDF is `matched`, `ambiguous`, `unmatched`, or blocked by a duplicate-row conflict.
- **Proposal**: the one best attempted value for a specific row/column cell in a specific run.
- **Support level**: how strongly the system believes the evidence supports the proposal, such as direct evidence, inferred from evidence, weak evidence, or figure-based evidence.
- **Evidence item**: the reviewer-visible text quote, page anchor, highlight, figure crop, caption, or related source reference used to justify the proposal.
- **Review decision**: accept as-is, accept with edit, reject, or no decision yet.
- **Diagnostics-only outcome**: a recorded extraction result that should appear in diagnostics even when there is no reviewable proposal.

This terminology is normative for the MVP even if internal implementation names differ.

---

## Functional requirements

### FR-1 Import, configuration, and normalization

The system must allow the user to provide a table, schema, PDF folder, and run configuration.

The primary happy path is that the operator starts a run from the UI by providing a config-file path. The UI may also support equivalent local-first shortcuts, but it must not require the user to pre-run the workflow through ad hoc Python snippets just to create a run.

The system must normalize column identifiers and detect which cells are missing, already filled, or otherwise eligible for extraction or verification behavior.

The system must validate that the table includes standardized metadata columns named `Title`, `Authors`, and `Publication Year` before row matching begins.

Advanced run behavior must be controlled through the run configuration rather than through extensive tuning controls in the UI.

The UI must show the config path plus a concise resolved-input summary, including at least the table path, schema path when present, PDF directory, output directory, target-column count or list, and Verify-mode status.

When the operator switches from one run to another, the UI may preserve the current queue filter, but it must treat proposal selection, proposal detail, and evidence-viewer state as run-scoped. It must clear or reload those views for the newly selected run rather than briefly showing or requesting stale proposal or evidence data from the previous run.

Validation failures must be surfaced with actionable operator-facing messages rather than generic request failures.

Before any run exists, or when the selected run is not yet reviewable, the UI must make the next valid operator action obvious rather than presenting an unexplained empty review workspace.

### FR-2 Paper metadata extraction

The system must extract paper-level metadata needed for row matching, such as title, authors, publication year, and identifiers when available.

Metadata extraction for matching must be grounded in the paper and must not invent missing metadata.

The system should support OCR as a fallback when PDF text is not directly accessible.

### FR-3 PDF-to-row matching

The system must attempt to match each PDF to the most likely table row.

The system must support:

- a deterministic matching pass
- a fallback adjudication step for ambiguous but plausible cases
- a final state of matched, ambiguous, or unmatched

If matching remains ambiguous, extraction for that PDF must be blocked entirely.

If multiple PDFs plausibly compete for the same row, the system must flag the conflict, block extraction for all PDFs involved in that duplicate-row conflict, and require manual cleanup before either PDF can proceed.

Unmatched and ambiguous PDFs must remain visible in the UI for manual inspection.

### FR-4 Schema-driven extraction

The system must attempt extraction only for schema-defined columns.

The system must support values whose intended outputs may be free text, numeric, categorical, boolean, or ranges.

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

### FR-5 Proposal behavior and derived reasoning

The extraction system is a proposal system, not a quote-only copier.

The system may infer or derive a plausible value when direct wording is incomplete, including cases where:
- a value can be calculated from quoted evidence
- a concise argument can be made from one or more quoted evidence items
- a figure provides the strongest evidence

When a proposal depends on calculation or reasoning, the system must show a concise reviewer-facing rationale or calculation summary. Hidden chain-of-thought is not required or expected.

Reviewer-visible proposal states must distinguish at least between:
- `found`: directly supported enough by evidence
- `inferred`: derived or weakly supported
- `unclear`: no sufficiently useful value proposed
- `blocked`: not attempted because of a blocking condition such as ambiguous matching

Reviewer-visible proposal states should use clear human-readable language that communicates the support level of the proposal. Internal names such as `found` and `inferred` may be mapped to labels such as `Direct evidence` and `Inferred from evidence`.

### FR-6 Evidence attachment

Each non-empty proposed value must include at least one evidence item when feasible.

For text-derived proposals, the minimum reviewer-visible evidence target is a highlighted source quote on the PDF page.

If text highlighting cannot be recovered reliably, the proposal must remain reviewable with the source quote plus page reference, and it must be marked as weaker text evidence.

The UI must not fabricate placeholder or guessed highlight geometry merely to avoid fallback display. If reliable page geometry is unavailable, the reviewer must see an explicit quote-plus-page fallback instead.

For figure-derived proposals, the minimum reviewer-visible evidence target is a figure crop plus caption, with the full page also accessible in the UI.

An evidence item must contain enough source information for a reviewer to inspect the origin of the proposal.

Attached evidence is decision support for the reviewer, not proof of correctness by itself.

Multiple evidence items may support a single proposal, but the review UI should show one primary evidence item by default and allow additional items to be expanded.

### FR-7 Evidence validation and recovery

The system must validate whether evidence is suitably anchored for display and review.

If evidence is missing, weak, or unusable for display, the system must make at least one evidence recovery attempt before finalizing the proposal state.

If strong evidence still cannot be recovered, the proposal may remain available for review, but it must be marked as needing more evidence.

Failure to recover a highlight for a text-derived proposal must not by itself move the proposal to diagnostics-only if quote plus page evidence is available.

### FR-8 Scoped figure-aware fallback

The system must support scoped figure-aware fallback extraction when the field appears likely figure- or table-derived, when text or table retrieval or extraction remains insufficient, or when text-first extraction remains insufficient after evidence recovery.

Figure-aware fallback may use scoped visual context such as:
- figure crops
- full page images
- captions
- nearby narrative text

Figure-aware extraction is in scope for all figure types and all target field types, including complex image-heavy scientific figures, but reliability varies by figure type and all figure-derived proposals remain subject to human review.

Figure-derived proposals must remain clearly marked as figure-based evidence in review.

Figure-derived proposals remain subject to heightened reviewer scrutiny and may rely more heavily on visual context and concise rationale than direct text-derived proposals.

### FR-9 Review workflow

The system must provide a review interface where a human can inspect proposals and supporting evidence.

The same local browser app must also support starting runs and monitoring run state; review is not a separate operator surface disconnected from run startup.

The review interface must support a queue-first workflow with:
- a proposal list or queue
- a focused detail pane for the selected proposal
- an evidence viewer pane
- visible run-summary and reviewer-summary context in the main review workspace

Review must be nonlinear: selecting a proposal for inspection must not itself record a decision.

The UI should support one visible master queue with filtering, reusable saved views or equivalent presets, and progress indicators.

The review workspace must also handle pre-review states well, including:
- no runs yet
- run selected but still validating or running
- completed run with no actionable proposals
- completed run with warnings
- failed run with diagnostics or at least an actionable failure message

In those pre-review states, the UI must explain whether the operator should start a run, wait for processing, inspect warnings, or inspect diagnostics, instead of only showing the absence of proposals.

When a run is in `running`, the user-facing status surface should show coarse progress at the level of current pipeline stage plus current item when available. MVP does not require a full job monitor, resumable task graph, or fine-grained per-substep telemetry.

Inspection of unmatched, ambiguous, and duplicate-row-conflict PDFs must remain available from the same review workspace, and it must identify at least the PDF name, match outcome, and rationale for the unresolved state.

In MVP, unresolved-match inspection is inspect-only. The operator does not need direct rematch, reassignment, or conflict-resolution actions from that same surface.

The default queue ordering should prioritize actionable review items ahead of blocked or otherwise unresolved records.

Blocked, unresolved, unmatched, ambiguous, or duplicate-row-conflict records must remain visible for inspection, but they should not dominate the main actionable review flow by default.

The reviewer must be able to:
- accept a proposal
- accept a proposal with edits
- reject a proposal
- bulk-accept the currently visible filtered proposal subset, subject to confirmation
- move through proposals efficiently without recording a decision
- inspect unmatched and ambiguous PDFs
- see progress counters including reviewed versus total proposals and decision breakdowns

Export may proceed with only a subset of proposals reviewed.

Unreviewed proposals that have not been explicitly accepted must be discarded from export.

The review interface must show enough row context, column context, proposal state, evidence context, and rationale context for a meaningful decision.

Accept-with-edit must behave as an explicit edit-save action rather than a vague duplicate of normal acceptance.

Proposal status, evidence source, and warning state must be visually distinguishable at a glance.

Accept actions must not be available for blocked items or items without a reviewable proposal value.

Figure-derived evidence should be displayed crop-first, with caption directly attached and the full page accessible on demand.

The review interface must support filtering by row, column, PDF, evidence status, figure-based evidence, and ambiguous or unmatched match status.

Any stored proposal must be reviewable in the interface, including proposals whose text evidence is shown as quote plus page without a reliable highlight.

The review workspace must expose direct access to the main run artifacts needed by a reviewer after decisions are made, including the exported workbook, audit log, run summary, and reviewer summary.

### FR-10 Spreadsheet protection and verify mode

The system must not overwrite already-filled cells by default.

The system must support a single named mode, **Verify mode**, in which the system also generates proposals for already-filled cells.

Verify mode must be configurable through the run configuration and enabled by default.

In Verify mode:
- proposals for already-filled cells must be visible in the review interface
- the reviewer must be able to compare the proposed value against the existing entry
- accepted updates to already-filled cells must be exportable
- reviewer decisions on verified cells must contribute to reviewer-outcome statistics and per-column review summaries for the run

The system may treat single-space or similarly trivial placeholders as empty when configured to do so.

### FR-11 Export

The system must export:
- an updated XLSX table containing the original retained values plus only explicitly accepted changes
- an audit log of changes
- reviewer-outcome summaries and run diagnostics

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
- why a run finished with few or no usable proposals

The system must provide a normal user-facing run summary with at least:
- current or terminal run state
- actionable status or failure message
- number of PDFs processed
- number of PDFs matched, unmatched, and ambiguous
- number of proposals generated
- number of proposals reviewed
- accepted as-is count and rate
- accepted with edit count and rate
- rejected count and rate
- proposal coverage
- number of accepted changes
- provider/model names used for the run
- whether processing stayed local or used cloud providers
- reviewer-outcome summary when Verify mode is enabled

Detailed logs and deeper diagnostics may exist as advanced outputs for development and troubleshooting.

The normal user-facing run summary should remain useful even before the run reaches a terminal state, for example by showing validation or processing state together with the resolved input/config context.

When a run is not yet reviewable, the summary surface should still help the operator understand what has happened so far, what is blocked, and whether review will become available automatically or requires intervention.

Download surfaces must also remain truthful: config snapshots and diagnostics may be available early, but exports and summaries must not be presented as ready when the underlying files have not been written yet.

If no verified cells have been reviewed yet, reviewer-outcome reporting should remain visible but explicitly provisional. The UI should keep per-column evidence-coverage lines visible with wording that makes clear they are coverage context rather than reviewer-outcome scores until at least one verified cell has actually been reviewed.

In MVP, reviewer-outcome summaries are the primary reporting mechanism, and automated correctness scoring across heterogeneous field types is deferred.

Reviewer-outcome summaries must include, at minimum:
- reviewed verified-cell count
- accepted as-is count and rate
- accepted with edit count and rate
- rejected count and rate
- proposal coverage
- per-column reviewer outcome breakdown
- evidence coverage
- anchorable or highlightable evidence rates when applicable

Verify mode may still compare proposals against already-filled cells, but future automated Verify-mode scoring is deferred and may be added later.

If there are too few reviewed proposals or verified proposals for meaningful interpretation, the system must warn explicitly.

If reviewer-outcome reporting may be biased or if any future automated evaluation would be leakage-prone, the system should warn explicitly.

Run summaries and reviewer summaries must remain derivable from persisted artifact data so they can be recomputed and inspected later.

### FR-13 Structured-document support

The system must work with PDFs whose useful evidence may appear in prose, captions, table-like content, or scoped figure-aware fallback evidence.

When document structure can be detected, the system should preserve enough of that structure to improve proposal quality and evidence review without changing the user-facing workflow.

### FR-14 Run completion semantics

If a run matches one or more PDFs but yields no usable proposals, the run outcome must remain visible as a completed run with warnings rather than appearing silently successful.

Failures that prevent safe execution must be surfaced clearly in run diagnostics.

---

## Review and trust requirements

### TR-1 Explainable proposal state

A reviewer must be able to tell, for each proposal:
- what value was proposed
- what support level it has, such as direct evidence, inferred from evidence, weak evidence, or figure-based evidence
- what evidence supports it
- whether the value depends on calculation or reasoning
- whether additional scrutiny is recommended

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

Bit-for-bit deterministic replay is not required for the MVP.

### NFR-3 Inspectability

Intermediate and final outputs should remain inspectable by an advanced user for debugging and reviewer-outcome analysis.

### NFR-4 Robustness to partial failure

Failure in one stage or for one PDF should not necessarily invalidate the entire run. The system should preserve partial results whenever safe.

### NFR-5 Performance

The system should be usable on realistic researcher-sized batches of PDFs without requiring manual intervention between every document.

A realistic MVP workload is roughly 1 to 150 PDFs, with smaller batches common during testing.

### NFR-6 Privacy and provider transparency

The product should make it clear when external model or parsing providers are used.

At minimum, run outputs or the UI should make visible:
- whether processing stayed local or used external providers
- which providers/models were used for the run

This transparency should appear in a concise run summary rather than only in deep diagnostic logs.

### NFR-7 Extensibility

The product should allow future replacement or addition of parser, retrieval, and model backends without changing the user-facing workflow.

### NFR-8 Usability

The review interface should be visually clear, efficient for repeated review work, and suitable for modern desktop use.

---

## Key behavioral rules

- Already-filled cells are protected by default.
- Evidence quality influences reviewer scrutiny, not only whether a proposal exists.
- Proposals may be supported by multiple evidence items.
- Reviewer-visible evidence must remain anchored to the source even if internal retrieval uses transformed text.
- Diagnostic-only outcomes must remain clearly distinct from reviewable proposals.
- Any stored proposal remains reviewable, even when text highlighting fails and only quote plus page evidence is available.
- One target cell receives at most one best proposal per run.
- Proposal identifiers remain unique within a run even when multiple PDFs surface the same row/column target.
- Ambiguous PDF-to-row matches block extraction rather than silently proceeding.
- Duplicate PDF matches to the same row block all conflicting PDFs until manual cleanup.
- Verify mode is the only product-level mode for reviewing already-filled cells and generating reviewer-outcome summaries for those comparisons.
- Verify mode is configurable and enabled by default.

---

## Acceptance criteria

### AC-1 Import readiness

Given a valid table, schema, PDF folder, and run configuration with standardized `Title`, `Authors`, and `Publication Year` columns,
when the user starts a run,
then the system records the run inputs and identifies missing versus already-filled target cells.

### AC-2 Matched extraction path

Given a PDF that can be matched to a row,
when extraction is run,
then the system attempts each eligible target column and stores one best outcome for each attempted target cell.

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
then the reviewer can inspect the proposed value, proposal state, relevant row and column context, primary evidence, and concise rationale or calculation when applicable, including quote-plus-page evidence when a text highlight could not be recovered, while also seeing visually distinct status/evidence/warning cues and the surrounding run-summary context.

### AC-6 Decision control

Given a proposal under review,
when the reviewer accepts, edits, rejects, or bulk-accepts the currently visible filtered subset after confirmation,
then the system stores that decision as an explicit persisted review record, preserves the prior proposal state for auditability, and does not offer accept actions for blocked or non-reviewable items.

### AC-7 Locked-cell safety

Given an already-filled input cell,
when the run completes and exports are generated outside Verify mode,
then that cell is not overwritten unless explicit review behavior has authorized the change.

### AC-8 Verify mode behavior

Given Verify mode is enabled, and Verify mode is on by default unless disabled in configuration,
when the system processes already-filled cells,
then it generates reviewable proposals for those cells, allows explicit accept/edit/reject decisions, and uses those reviewer decisions in reviewer-outcome statistics and per-column review summaries.

### AC-9 Export integrity

Given accepted proposals,
when the user exports results,
then the system produces an updated XLSX table and an audit log containing only approved changes, while leaving the original input table unchanged, and any available audit timestamp comes from the persisted review-decision record for that change.

### AC-10 Export fidelity

Given an exported XLSX table,
when the export is opened,
then the table preserves accepted and unchanged cell content correctly, guarantees content-only fidelity plus highlighting of changed cells, and does not promise preservation of workbook formatting or other workbook behavior.

### AC-11 Diagnostic transparency

Given a run with matched PDFs but no usable accepted values,
when the run finishes,
then the system provides diagnostics explaining why no values were produced or accepted and marks the run as completed with warnings rather than silently successful.

### AC-12 Weak-evidence handling

Given a plausible proposal with weak, missing, or initially unusable evidence,
when proposal processing completes,
then the system makes one recovery attempt, keeps the proposal reviewable if appropriate, and marks it accordingly, including quote-plus-page review when text highlighting could not be recovered.

### AC-13 Figure fallback

Given a target field that remains unresolved after text or table extraction,
when the system identifies relevant figure evidence,
then it may produce a figure-based proposal with clearly labeled visual evidence, including a crop and caption, for review.

### AC-14 Evaluation integrity

Given Verify mode is enabled but too few verified proposals were reviewed to support meaningful interpretation,
when reviewer-outcome summaries are generated,
then the system emits a warning or explicit limited-review status rather than a misleading normal reviewer-outcome summary.

### AC-15 Partial-review export behavior

Given some proposals remain unreviewed,
when the user exports results,
then only explicitly accepted proposals appear in the exported workbook and audit log, and unreviewed proposals remain excluded.

### AC-16 Provider transparency

Given a run used one or more model or parsing providers,
when the run summary is shown or exported,
then the summary identifies the provider or model names used and whether processing stayed local or used external services.

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
- Figure-aware fallback extraction for all figure types and all target field types in scoped, review-oriented form.
- Filtering by row, column, PDF, evidence status, figure-based evidence, and ambiguous or unmatched match status.
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

Paper Table Agent is a local-first paper-to-table review system. It matches papers to spreadsheet rows, proposes values for missing or verified cells with anchored evidence, and lets a human reviewer accept, edit, reject, or bulk-accept the currently visible filtered subset before exporting an audited XLSX table update.
