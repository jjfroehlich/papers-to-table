# UI Review Workflow

- Status: Canonical focused spec
- Owner: Product Review Workflow
- Depends on: `spec.md`, `contracts.md`
- Consumed by: `app/frontend/`, `app/backend/src/backend/app/`, `docs/main-app/browser-review.md`, tests

## Purpose

This file owns the browser review workflow. The reviewer is deciding what the paper supports and what should be exported, not grading the model.

## Primary Surface

The browser UI is the primary human operator surface for:

- selecting or confirming inputs
- seeing preflight and run state
- starting runs
- reviewing proposals
- inspecting evidence and diagnostics
- exporting reviewed results

The JSON config remains the advanced-control surface. The UI may offer path pickers and narrow run overrides, but it must not become the primary advanced settings editor.

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

## Run-State Gating

Review is unavailable while a run is:

- `ready`
- `validating`
- `running`
- failed before meaningful proposal generation

A run may become reviewable with warnings only when meaningful proposal generation completed and the warning state is understandable to the reviewer.

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

## Decision Types

The reviewer can:

- accept as proposed
- accept with edit
- confirm no data in the paper
- reject
- bulk accept the currently visible filtered subset

Persisted decisions use these new decision-source values:

- `human_individual`
- `human_bulk_accept`
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

`skills/papers-to-table-agent-kit/` provides a static/local rich review UI for external-agent outputs. It follows the same review decision and accepted-only export semantics, but it is intentionally not full main-app parity.

The agent-kit review UI is acceptable for MVP when:

- proposals appear in a queue/table
- selecting a proposal opens the corresponding PDF page when possible
- quote text is highlighted when PDF.js can match it
- page-only or reasoning-only evidence is visibly labeled weak/attention
- reviewers can accept, accept with edit, reject, or confirm no data
- decisions can be downloaded or written through localhost server writeback
- accepted-only `exports/final_table.csv` is produced
- a valid package can be produced from quote/page evidence without bboxes, figure crops, page images, source table, or schema

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
