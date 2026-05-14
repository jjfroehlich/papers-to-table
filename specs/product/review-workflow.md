# Review Workflow

> Compatibility reference: canonical product/system truth now lives in [`../spec.md`](../spec.md), roadmap direction in [`../plan.md`](../plan.md), and status/backlog in [`../tasks.md`](../tasks.md). Do not treat this file as normative when it conflicts with the canonical files.

- Status: Compatibility reference
- Owner: Product
- Depends on: product/main-app.md, contracts/proposals-and-evidence.md
- Consumed by: docs/main-app/browser-review.md, app/frontend/src/

## Purpose

This file preserves reviewer workflow compatibility notes for the main app.

The reviewer is reviewing what the paper supports, not grading the model. The review workspace must therefore keep paper evidence, review actions, and explicit curation outcomes primary.

## Queue-first design rule

The review workspace is intentionally queue-first.

It should optimize for sustained curation of many candidate cells, not for freeform exploration alone. Browsing the paper matters, but the primary job is deciding whether a proposed spreadsheet update is supported.

## Review surface requirements

The main review workspace is a browser-based, reviewer-centered curation workstation.

It must provide:

- a queue of reviewable items
- proposal detail for the selected item
- synchronized evidence and PDF inspection
- explicit review actions
- actionable progress and warning context
- a dedicated diagnostics surface for unresolved matching issues and run warnings

The workspace must default to actionable review items rather than loading every diagnostic-only pipeline outcome into the main queue.
The default workspace layout must be a viewport-contained three-panel review surface:

- proposal queue on the left
- proposal detail and decisions in the center
- evidence and PDF inspection on the right

The top review bar must stay compact and workflow-oriented. It should show current run context, review progress, warning count, diagnostics access, export, and any small mode labels that are still necessary. Large summary cards or dashboard-style status blocks must remain secondary rather than occupying the default review viewport.

## Queue behavior

- The queue must support grouped triage.
- Reviewer-facing counts must distinguish actionable items from broader attempted or diagnostic totals.
- Diagnostic-only outcomes such as unmatched rows, ambiguous matches, blocked extraction, and skipped cells must remain visible through diagnostics and summaries, but they must not dominate the main proposal queue.
- Unresolved diagnostics should not compete with the primary evidence panel for attention during normal review.
- Bulk review actions apply only to the currently visible filtered subset, never to hidden queue items.
- Grouping and ordering should support fast scanning rather than flattening every proposal into one undifferentiated list.
- Queue rows should stay compact and calm: field name, proposed value or explicit no-value text, support marker, and warning indicator only when needed.

## Review decisions

The reviewer must be able to:

- accept as proposed
- accept with edits
- confirm no data in the paper
- reject
- bulk-accept the currently visible filtered subset

These decision types are first-class curation outcomes and must remain distinct in artifacts and summaries.

Persisted review artifacts must also distinguish how a decision was recorded:

- `human_individual` for ordinary reviewer actions
- `human_bulk_accept` for bulk acceptance of the visible filtered subset
- `automation_accept_all` for explicit headless `--accept-all` runs

Legacy `human_reviewer` values remain readable for backward compatibility, but newly written review artifacts must use the explicit current decision-source values.

No-value states must remain actionable. The review workspace should support explicit manual entry and explicit `confirm no data` behavior rather than dead-ending in an empty detail pane.

## Evidence handling

- Direct quotes must be shown separately from reasoning or calculation text.
- Evidence items must be ordered, with the most authoritative field-relevant evidence primary.
- Exact highlighting should be used whenever possible.
- When exact highlighting is unavailable, fallback evidence must be labeled honestly rather than presented as exact.
- Figure-derived evidence must remain distinguishable from text-derived evidence.
- When figure evidence is used, the reviewer should be able to understand whether it came from a targeted crop, a page-level region, or broader figure-context inspection.
- The evidence list and the document viewer should stay synchronized around the selected evidence item.

Shared evidence-type and support-label rules are canonical in `../spec.md`; this file preserves older compatibility detail.

## Review ergonomics

The review workspace must support:

- stable selection behavior
- adjustable pane widths
- internal scrolling for the queue, proposal detail pane, and evidence viewer without requiring the whole page to become one oversized canvas
- always-visible or sticky review actions within the proposal-detail area
- evidence navigation synchronized with the document viewer
- a persistent evidence toolbar while the document area scrolls
- ordinary PDF reading affordances such as zoom, pan, and text copy when the source PDF allows it
- fast sequential review, including keyboard shortcuts where implemented
- auto-advance after an explicit decision when that behavior is implemented

Diagnostics must be collapsed by default and opened intentionally in a secondary drawer, panel, or equivalent surface that preserves the current review selection.

## Review state transitions

- A run is not reviewable while it is still validating, running, or has failed before meaningful proposal generation.
- A run may become reviewable with warnings when meaningful proposal generation completed and the warning states are still understandable to the reviewer.
- Review summaries, queue counts, and artifact summaries must agree about whether the run is actionable, partial, or blocked.

## Review gating and summaries

- Review must remain unavailable while a run is still validating, running, or failed.
- The UI must still expose useful setup, progress, warning, and diagnostics context during that time.
- Run summaries and reviewer summaries must remain consistent with persisted proposal and review artifacts.

When a run completes with no actionable proposals, the review surface should still explain why, rather than looking like an empty successful queue.

## Auditability requirements

- Review decisions must remain first-class persisted artifacts.
- The app should preserve enough history for a reviewer or evaluator to understand what was proposed, what evidence was shown, what decision was made, and what was eventually exported.
- Review actions must be reversible at the workflow level until explicit export commits the reviewed result into a new workbook artifact.

## Export boundary

Review decisions do not update the source workbook in place.

Only explicit export creates a new workbook containing accepted changes and audit artifacts.

Unreviewed proposals must not be treated as accepted changes during export.

## Ownership boundary

This file is a compatibility reference for reviewer workflow behavior. Canonical behavior lives in `../spec.md`.

It does not own shared artifact contracts, score semantics, or optimizer behavior.
