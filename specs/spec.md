# Repository Spec Index

- Status: Normative umbrella index

The active repository spec is split across the owned files under `specs/`.

Current top-level truths that must stay aligned across the main app, eval, optimizer, configs, docs, and reports:

- the main app emits evidence-backed proposals, matching diagnostics, metadata diagnostics, and reviewer-facing degraded-mode truth through stable run-bundle artifacts
- eval scores those run bundles against gold, preserves dual-judge details when configured, and publishes evidence-anchor plus metadata-family audit summaries
- optimizer uses explicit benchmark manifests, distinguishes real benchmark versus fixture or smoke configs, and reports both the raw benchmark winner and the recommended default when they differ

Owning files:

- product behavior: `product/main-app.md`, `product/review-workflow.md`
- eval behavior: `tools/eval.md`
- optimizer behavior: `tools/optimizer.md`
- shared contracts: `contracts/run-bundle.md`, `contracts/eval-summary.md`, `contracts/optimizer-candidate.md`
- supporting technical direction: `plan.md`
