# Monorepo Spec Plan

## Purpose

This file is the supportive planning index for the unified monorepo spec system.

It does not own runtime behavior by itself. Runtime behavior and contracts are owned by the normative files linked below.

The archive layer under `archive/` preserves older, superseded, and rationale-heavy source material that should remain traceable even when not part of the current normative text.

## Current document map

- Main-app product behavior: `product/overview.md`, `product/main-app.md`, `product/review-workflow.md`
- Companion-tool behavior: `tools/eval.md`, `tools/optimizer.md`
- Shared contracts: `contracts/run-bundle.md`, `contracts/proposals-and-evidence.md`, `contracts/eval-summary.md`, `contracts/optimizer-candidate.md`
- Monorepo structure and integration: `architecture/monorepo-layout.md`, `architecture/integration.md`
- Process rules: `process/change-policy.md`, `process/testing-strategy.md`
- Historical and superseded spec material: `archive/README.md` plus the relevant files under `archive/main-app/`, `archive/eval/`, and `archive/optimizer/`
- Explicit section dispositions and restoration notes: `archive/migration-notes/legacy-section-mapping.md`, `archive/migration-notes/restoration-summary.md`
- Status tracking: `tasks.md`

## Planning intent

The spec system should continue to support these planning goals:

1. keep the main app clearly primary
2. keep eval and optimizer clearly subordinate companion tools
3. keep shared contracts defined exactly once
4. keep implementation status in one tracker only
5. make cross-tool behavior changes update the owning contract file rather than creating parallel truth
6. preserve older detailed material in archive files instead of deleting it when reorganizing specs

## Planning rules for future reorganizations

- Prefer moving shared rules into `contracts/` over copying them into product and tool docs.
- Prefer moving repo-wide boundaries into `architecture/` over duplicating them in tool docs.
- Prefer updating `tasks.md` over creating separate per-tool status files.
- If a new spec file is proposed, its owner and non-overlap with existing files should be explicit before it is added.
- If a current normative file is shortened materially, preserve the removed detail under `archive/` and update the mapping notes in the same pass.
- Assume large deletions are suspicious until each removed major section has an explicit disposition.

## Relationship to tasks

`tasks.md` remains the canonical implementation-status tracker.

This file exists to keep the spec system navigable and maintainable as the monorepo evolves.

## Current migration state

The spec system now follows a normative-plus-archive model:

- current behavior and active contracts stay in the normative files
- older detailed source material stays in `archive/`
- migration traceability is recorded in `archive/migration-notes/`

This keeps the unified spec tree readable without treating older product and technical depth as disposable.

## Preserved technical foundations

The deleted legacy `spec.md`, `plan.md`, and `research.md` files carried technical context that should remain available even though it no longer owns behavior directly.

### Main-app technical direction

- Keep the main app browser-first and queue-first. The review workspace is the product surface, not a thin wrapper around a background script.
- Keep the config file as the authoritative advanced-control surface. The UI may stage narrow overrides, but it should not become a second full configuration system.
- Keep parser output behind a stable parsed-document contract rather than scattering parser-specific assumptions across matching, retrieval, and evidence code.
- Keep filesystem artifacts as the canonical run state. Downstream tools should consume persisted files rather than hidden in-memory state.
- Keep one best proposal per eligible target cell while preserving enough provenance and evidence detail for review, eval, and optimizer consumers.
- Keep figure review text-guided and targeted when vision capability is available, rather than turning the main path into blanket page-level multimodal analysis.
- Keep style-profile generation bounded. Existing filled cells may inform column-level formatting or output-shape guidance, but they must not become hidden row-level answer leakage.

### Eval and optimizer technical direction

- Keep eval file-driven and decoupled from main-app runtime imports.
- Keep optimizer orchestration-only, with explicit separation between execution, scoring, and study control.
- Keep comparison rows and experiment records flat enough for inspection, plotting, and downstream reporting without reloading large verbose diagnostics.

## Current risks and mitigations

- Parser or OCR dependency drift can make runs look superficially wired while still failing on real PDFs.
	- Mitigation: keep readiness checks explicit and fail early when parser prerequisites or OCR-dependent paths are unavailable.
- Structured-output degradation can hide behind apparently successful runs if provider capability negotiation is not recorded truthfully.
	- Mitigation: preserve explicit degraded-mode and fallback fields in run artifacts and summaries.
- Matching ambiguity can quietly pollute extraction quality if unmatched or duplicate-row cases are normalized away.
	- Mitigation: keep matching ambiguity explicit in artifacts, summaries, and reviewer-facing diagnostics.
- Shared contracts can drift when one tool changes faster than the others.
	- Mitigation: update the owning `contracts/` file and verify impacted tools in the same pass.

## Open technical questions

These questions remain useful planning context, but they are not current product truth until they are resolved in the owning normative file.

- How far should the parsed-document contract be formalized for parser swaps without overcommitting to one parser implementation?
- Should style-profile generation stay purely column-level, or should a narrow per-schema adaptation surface be made explicit later?
- Should richer structured-field support metrics be added in eval beyond the current bounded anchor-validation and support-proxy behavior?
- Should optimizer holdout targeting remain strictly tied to promoted-incumbent lineage, or is there still a justified case for validating the best raw dev score seen?
- How much plot-contract hardening is worth specifying explicitly before it becomes needless report boilerplate?