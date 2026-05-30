# Decisions

This file records compact durable decisions. It is not a historical ledger; archive detailed old rationale under `archive/` when needed.

## D001 Local-first default identity

Decision: papers-to-table remains local-first by default.

Rationale: The product handles scientific PDFs, local spreadsheets, and local review artifacts where reproducibility, privacy, and offline use matter.

Implications: Optional cloud providers may exist later, but provider locality and readiness truth must remain explicit in UI, configs, specs, tests, and artifacts.

## D002 Browser-first human review

Decision: The browser UI is the primary human operator surface.

Rationale: The core product promise is reviewed spreadsheet updates with evidence inspection, not autonomous terminal extraction.

Implications: Headless mode is additive for agents and batch runs. It must not erase review gating, evidence inspection, or explicit export semantics.

## D003 JSON config as advanced-control surface

Decision: The JSON config file is the authoritative advanced-control surface.

Rationale: Provider, parser, retrieval, prompt, diagnostics, and figure-review settings must be reproducible and diffable.

Implications: The UI may provide path pickers and narrow overrides, but broad configuration remains file-owned.

## D004 Run bundles as cross-tool contract

Decision: Run bundles are the stable integration contract between main app, eval, optimizer, review, and audit tooling.

Rationale: Persisted artifacts keep tool boundaries clear and make runs inspectable without hidden in-process coupling.

Implications: Eval reads files rather than importing main-app runtime code; optimizer launches tools and consumes artifacts rather than reimplementing extraction or scoring.

## D005 Source workbook is never mutated in place

Decision: Export writes a new workbook and audit artifacts.

Rationale: Review decisions should be auditable and reversible until explicit export, and source data must remain intact.

Implications: Only accepted decisions are exported. Rejected, unreviewed, diagnostic, and confirmed-no-data outcomes are not written as accepted values.

## D006 Eval and optimizer are companions

Decision: Eval and optimizer support the main app; they are not separate end-user products.

Rationale: Keeping extraction, scoring, and orchestration separate prevents benchmark workflows from redefining the product.

Implications: Eval owns scoring. Optimizer owns study orchestration and reports. Main app owns extraction, review, and export.

## D007 LM Studio token and label

Decision: The canonical local live provider config token is `lm_studio`; the operator-visible label is `LM Studio`.

Rationale: Provider naming drift caused readiness and docs ambiguity.

Implications: Unknown or obsolete provider identifiers fail early. UI, runtime, config examples, tests, docs, and specs must use the same naming.

## D008 Current skill directory name

Decision: Agent skills live under `skills/`.

Rationale: The actual repo directories are `skills/papers-to-table-agent-kit/` and `skills/papers-to-table-local-app/`.

Implications: New docs and specs must use `skills/` and must not introduce an alternate active skill-root path.

## D009 Current benchmark dataset organization

Decision: Active benchmark datasets live directly under `benchmark_datasets/`; external/gold comparison results live under `benchmark_datasets/data/`.

Rationale: The app, eval, optimizer, tests, and docs need one visible repository-root corpus.

Implications: Current active datasets are `massively_parallel_reporter_assays`, `genome_editing_tools`, and `spatial_transcriptomics`. Optimizer ids are `bench_massively_parallel_reporter_assays`, `bench_genome_editing`, and `bench_spatial_transcriptomics`; `bench_smoke` is fixture-only.

## D010 Historical specs are non-normative

Decision: Older detailed compatibility references and legacy ledgers live under `specs/archive/` and are historical only.

Rationale: Long semi-current compatibility files made it unclear which source owned current truth.

Implications: Active current behavior must be understandable from the root canonical spec set. Archived files may preserve context, but cannot justify current behavior unless the relevant truth is promoted back into an active spec.
