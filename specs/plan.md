# Technical Direction

## Purpose

This file summarizes the current technical direction behind the normative spec files.

It does not own runtime behavior by itself. Product behavior belongs in `product/`, shared contracts belong in `contracts/`, and process rules belong in `process/`.

## Role in the spec system

Use this file for durable technical direction that helps explain why the current spec set looks the way it does.

Do not use this file as:

- a second product spec
- a migration ledger
- a historical archive
- a duplicate task tracker

Historical legacy detail is preserved under `archive/verbatim/`.

## Current technical direction

### Main-app direction

- Keep the main app browser-first and queue-first. The review workspace is the product surface, not a thin shell over background scripts.
- Keep the JSON config file as the authoritative advanced-control surface. The UI may stage narrow input overrides, but it should not become a second full config system.
- Keep filesystem artifacts as the canonical run state. Downstream tools should consume persisted files rather than hidden in-memory runtime state.
- Keep one best proposal per eligible target cell while preserving enough provenance and evidence detail for review, eval, and optimizer consumers.
- Keep review truthful: provider readiness, degraded extraction, blocked matching, and evidence fallback must stay explicit in artifacts and reviewer-facing summaries.

### Pipeline direction

- Keep a deterministic staged runner as the baseline execution model.
- Keep parser output behind a stable parsed-document contract rather than scattering parser-specific assumptions through matching, retrieval, and evidence code.
- Keep retrieval row-aware and column-aware by default, with bounded recall-rescue and optional whole-document behavior only when explicitly configured.
- Keep extraction structured-output-first with bounded compatibility fallback rather than long implicit fallback ladders.
- Keep figure review text-guided and targeted when vision capability is available, rather than turning the main path into blanket page-level multimodal analysis.

### Review direction

- Keep the review workspace centered on actionable proposals rather than raw pipeline volume.
- Keep evidence ranking, evidence labeling, and honest fallback as first-class requirements.
- Keep explicit reviewer outcomes, including `confirm no data`, as persisted facts rather than UI-local interpretations.
- Keep export manual and explicit. The source workbook must not be mutated in place.

### Companion-tool direction

- Keep eval file-driven and decoupled from main-app runtime imports.
- Keep optimizer orchestration-only, with explicit separation between execution, scoring, and study control.
- Keep shared contracts defined once in `contracts/` so tool changes update one owner instead of creating parallel truth.
- Keep real benchmark studies explicit and separate from fixture or smoke studies.
- Keep dual-judge, evidence-grounding, metadata-diagnostics, and degraded-mode truth visible in top-level reports rather than only raw artifacts.

## Current risks and mitigations

- Parser or OCR dependency drift can make runs look superficially wired while still failing on real PDFs.
  Mitigation: fail readiness early and persist parser-path truth explicitly.
- Structured-output degradation can hide behind apparently successful runs if provider capability negotiation is not recorded truthfully.
  Mitigation: preserve explicit negotiated mode and degraded fallback truth in stable summaries.
- Matching ambiguity can quietly pollute extraction quality if unmatched or duplicate-row cases are normalized away.
  Mitigation: keep unmatched, ambiguous, and duplicate-row outcomes explicit in artifacts, summaries, and review diagnostics.
- Spec drift can reappear if the same behavior is described in several places.
  Mitigation: keep one owner per truth and treat `archive/verbatim/` as history only.

## Open technical questions

These remain planning questions, not current product truth:

- How far should the parsed-document contract be formalized for future parser swaps without overcommitting to one parser implementation?
- Should style-profile behavior remain purely column-level, or should a narrow per-schema adaptation surface be made explicit later?
- Should eval add richer structured-field support metrics beyond the current bounded anchor-validation and support-proxy behavior?
- Should optimizer holdout targeting remain strictly tied to promoted-incumbent lineage, or is there still a justified case for validating the best raw dev score seen?
