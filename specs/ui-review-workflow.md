# UI Review Workflow

- Status: Canonical focused spec
- Owner: Product Review Workflow
- Depends on: `spec.md`, `contracts.md`
- Consumed by: `app/frontend/`, `app/backend/src/backend/app/`, `docs/main-app/browser-review.md`, tests

## Purpose

This file owns the browser review workflow. The reviewer is deciding which source-linked extracted information should be exported, not grading the model or adjudicating whether a publication's scientific claims are supported or true.

## Primary Surface

The browser UI is the primary human operator surface for:

- selecting or confirming inputs
- seeing preflight and run state
- starting runs
- reviewing proposals
- inspecting evidence and diagnostics
- exporting reviewed results

The JSON config remains the advanced-control surface. The UI may offer path pickers and narrow run overrides, but it must not become the primary advanced settings editor.

## Run Discovery Directory

The Runs panel owns the directory used to discover existing run bundles. It defaults to `app/runs/` through the backend-relative `./runs`, accepts a validated backend-readable path, and offers a local native folder chooser with manual entry as fallback. Windows and other supported graphical systems use Tk; macOS uses the native Finder chooser through `osascript` without shell interpolation. Only an existing directory permitted by the configured output-root policy may become active. Missing GUI support, headless execution, or picker-launch failure must produce an inline explanation that directs the operator to enter the path manually.

The last successfully activated directory is persisted in browser storage. A launch-specific `review --runs-dir PATH` value takes precedence for that app launch. Cancellation and invalid, inaccessible, file, or disallowed paths leave the current directory active and produce an inline explanation.

Changing the active directory clears the current run selection, reloads the directory-scoped run list, and reconnects the directory-scoped live event stream. Only one discovery root is active at a time. All subsequent review and export operations use the selected run's recorded `output_dir`, not an inferred global path.

The Create Run `Output directory` remains independent. Changing the Runs discovery directory must not alter the destination entered for a new run.

## Queue-First Review Design

The review workspace is queue-first. It should optimize sustained curation of many target cells, not freeform paper browsing alone.

The default queue focuses on actionable review-surface proposals:

- `review` bucket proposals
- `attention` bucket proposals
- unresolved no-value target-cell outcomes that carry useful rationale, reason codes, retrieval/candidate context, or manual-edit value

Diagnostic-only outcomes remain visible in summaries and diagnostics but do not dominate the default proposal queue.

## Three-Panel Workspace

The default completed-run review viewport is a contained three-panel workspace:

- left: proposal queue
- center: proposal detail and decision controls
- right: evidence and PDF inspection

The top review bar stays compact and workflow-oriented. It may show current run context, review progress, diagnostics access, export, and small mode labels. Large summary cards and dashboard-style panels belong in secondary surfaces, not the default review viewport.

Queue, detail, and evidence panes must scroll independently. Review actions remain visible or sticky within the proposal-detail area when long content is inspected.

The center pane presents the selected column name first in a centered, visually distinct pale-grey **Field** context card, then the proposed **Value**, rationale or calculation context when present, and the **Evidence** list. The Field card must read as non-interactive and remain distinct from the lighter Value surface. Separate collapsed **Details** and **Diagnostics** disclosures follow Evidence. Their headers follow the same compact uppercase label style as the Rationale and Evidence sections, with an immediately adjacent triangle that clearly indicates collapsed or expanded state. Details contains **Field and description** and **Paper**. Diagnostics retains muted review, proposal, evidence, and reason-code flags, then presents exception-oriented detail: competing or unclear candidates with reviewer-readable sources, Selection only for ambiguity or failure, Retrieval only for exceptional outcomes or nonstandard evidence routes, and Metadata only for conflicts or failure. Redundant evidence-item counts, routine single-candidate selection, normal zero counts, raw diagnostic tokens, provider timings, raw model responses, query strings, figure-planning internals, and other development telemetry are excluded from the primary review surface. Neither disclosure contains nested disclosures or card-within-card fragmentation, both retain their open or closed state while the reviewer navigates between proposals, and matching proposed values and rationale are not repeated because Value and Rationale already provide them in the primary review flow. The decision controls are horizontally centered at the bottom of the pane.

Keyboard navigation follows the workspace's spatial model: `A` or left arrow moves to the previous proposal, `D` or right arrow to the next proposal, `W` or up arrow accepts, and `S` or down arrow rejects. Ctrl/Command plus left or right arrow switches evidence, while `E` focuses the edit control. Shift is reserved as the range/rectangle selection modifier. The help surface must show these mappings, and shortcuts must be suppressed while focus is in an input, textarea, select, or editable element.

## Run-State Gating

Review is unavailable while a run is:

- `ready`
- `validating`
- `running`
- failed before meaningful proposal generation

A run may become reviewable with warnings only when meaningful proposal generation completed and the warning state is understandable to the reviewer.

For `completed` and `completed_with_warnings` runs, the selected-run detail shows **Start human review** as a direct entry to the same workspace as the Review tab. The action is absent for non-reviewable statuses and never creates a second run or review bundle.

The UI must expose useful setup, progress, warning, provider-readiness, and diagnostics context while review is gated. A completed run with no actionable proposals must explain why rather than presenting an empty successful queue.

## Counts And Filters

Reviewer-facing counts must distinguish:

- actionable reviewable proposals
- attention items
- accepted/edited/rejected/confirmed-no-data decisions
- pending proposals in the current filter
- broader attempted or diagnostic totals

The visible All filter means all non-diagnostic review-surface records. Diagnostic records remain available through summaries and diagnostics views.

The Attention filter is visual and pragmatic: proposals with non-green proposal/evidence status, weak evidence, unresolved state, fallback anchoring, or other review-useful caveats should be easy to find.

Bulk actions apply only to the currently visible filtered subset, never to hidden queue items.

Explicit multi-selection is available in queue and table modes. Plain click selects one proposal; Ctrl/Command-click toggles individual proposals; Shift-click selects a contiguous queue range or the proposal-containing table rectangle from the last anchor. In table mode, holding the primary mouse button and dragging across cells selects every proposal-backed cell inside the rectangle, including when its boundary crosses unchanged cells. Empty, unchanged, and diagnostic-only cells are never action targets. The selection bar requires confirmation for Accept, Reject, or Confirm no data. It targets pending proposals by default; replacing existing decisions requires a separate explicit checkbox.

## Decision Types

The reviewer can:

- accept as proposed
- accept with edit
- confirm no data in the paper
- reject
- bulk accept the currently visible filtered subset
- apply accept, reject, or confirm-no-data to an explicit multi-selection

Persisted decisions use these new decision-source values:

- `human_individual`
- `human_bulk_accept`
- `human_bulk_selection`
- `automation_accept_all`

Legacy `human_reviewer` remains readable for old artifacts, but new manual decisions must use the explicit individual or bulk values.

No-value states must remain actionable. The detail pane must support explicit manual entry and explicit `confirm no data` behavior rather than dead-ending when no value was proposed.

## Evidence And PDF Synchronization

Evidence inspection must keep evidence and document context synchronized:

- direct quotes are shown separately from reasoning or calculation text
- evidence is ordered with the most authoritative field-relevant item primary
- exact highlighting is used when available
- approximate or fallback anchors are labeled honestly
- quote-plus-page evidence remains useful when highlight geometry is unavailable
- figure-derived evidence is visibly distinct from text-derived evidence
- figure evidence indicates whether it came from a crop, full-page fallback, or planner-preferred full page when that metadata exists
- selecting evidence moves or highlights the corresponding PDF/page context when possible

The evidence toolbar should remain available while the document area scrolls. Ordinary PDF reading affordances such as zoom, pan, and text copy should be preserved when the source PDF allows them.

## Diagnostics Surface

Diagnostics are secondary by default and opened intentionally through a drawer, panel, or equivalent surface that preserves the current review selection.

Diagnostics include:

- readiness warnings
- run-warning count, categories, and messages
- unmatched PDFs
- ambiguous matches
- duplicate-row conflicts
- parser and OCR fallback
- provider readiness/degraded mode
- extraction and evidence failures
- figure-review suppression/failure/no-hit diagnostics

Diagnostics should not permanently take review space away from evidence inspection during ordinary curation.

## Export Boundary

Review decisions do not update the source workbook.

Only explicit export writes a new workbook and audit artifacts. Only accepted and accepted-with-edit decisions become exported cell updates. Unreviewed proposals, rejected proposals, confirmed-no-data outcomes, and diagnostic records must not be written as accepted values.

Export should clearly report where the workbook and audit artifacts were written and preserve enough audit detail to reconstruct what was proposed, what evidence was shown, what decision was made, and what was exported.

## Portable Agent-Kit Review UI

`skills/papers-to-table-agent-kit/` provides an optional static/local review UI for external-agent outputs. The default kit handoff is an agent-extracted root filled CSV plus `RUN_DIR/extraction/` provenance. The UI is built under `RUN_DIR/human_review/` only after the user opts in. It is not full main-app lifecycle parity, but shared review interactions stay aligned: Ctrl/Command and Shift multi-selection, guarded pending-only bulk decisions with explicit replacement, Field-before-Value hierarchy, Evidence followed by persistent Details and exception-oriented Diagnostics disclosures, centered decision controls, muted diagnostic tags, and the spatial keyboard map defined above. Portable-only static decision download and localhost writeback/export remain separate contracts.

When the portable kit is explicitly authored in `fill_and_verify` mode, populated-cell proposals show the recorded existing value beside the proposed correction. The unreviewed filled CSV retains the existing value; acceptance is required before the reviewed CSV changes.

The agent-kit review UI is acceptable for MVP when:

- proposals appear in a queue/table
- selecting a proposal opens the corresponding PDF page when possible
- quote text is highlighted when the bundled PDF.js viewer can match it, including partial matches for long or slightly imperfect quotes
- a loaded PDF document remains paired with its `pdf_id`, and a paper switch cancels/defer-checks page rendering before the prior PDF.js document is destroyed
- page-only or reasoning-only evidence is visibly labeled weak/attention
- reviewers can accept, accept with edit, reject, or confirm no data
- reviewers can explicitly multi-select proposal cells and apply guarded Accept, Reject, or Confirm no data actions with `human_bulk_selection` provenance
- decisions can be downloaded or written through localhost server writeback, and the UI visibly distinguishes browser-only saves from confirmed server writeback or writeback errors
- an accepted-only root `<stem>_reviewed.csv` is produced beside the filled CSV
- a valid package can be produced from quote/page evidence without bboxes, figure crops, page images, source table, or schema

Review handoff uses `launch_review_servers.py`, which starts detached localhost servers, probes each URL, and returns exact links ending in `/human_review/index.html`. The user-visible handoff must include the exact URL. Static HTML may show proposal/evidence text, but served mode is required for reliable referenced-PDF rendering and quote highlighting.

The agent-kit UI must not grow implicit full backend expectations such as provider diagnostics, run lifecycle state, eval mode, mandatory page image generation, mandatory figure extraction, or mandatory bbox anchoring.

## Acceptance Criteria

The review UI is acceptable when:

1. A normal operator can tell whether a run is ready, running, failed, reviewable, or exportable.
2. The default completed-run screen prioritizes the proposal review loop.
3. Queue counts and run summaries agree with persisted proposal and decision artifacts.
4. Diagnostic-only outcomes are available but do not crowd the main review queue.
5. Each decision type is explicit in UI behavior and persisted artifacts.
6. Evidence and PDF context remain synchronized enough for real review.
7. Empty or no-actionable-proposal states explain the cause and next action.
8. Export is accepted-only and never mutates the source workbook.
9. The operator can switch to an external runs directory, reload its bundles, and retain that directory for later app launches without moving or copying artifacts.
10. Run discovery never changes the Create Run output destination, and live updates do not leak runs from another output root into the active list.
