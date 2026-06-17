# Current Plan

This file is the current technical direction and near-term roadmap. It is not a historical implementation plan.

## Technical Direction

- Keep the main app local-first, browser-first, and config-first.
- Keep run bundles as the cross-tool contract between main app, eval, optimizer, review, and export.
- Keep eval file-driven and separate from extraction.
- Keep optimizer orchestration-only and explicit about suites, replicates, raw winners, recommended defaults, and trust caveats.
- Keep LM Studio provider behavior conservative: serialized access by default, explicit readiness failure, and visible degraded-mode truth.
- Keep active specs small, rebuild-grade, and owned by the root canonical files in this directory.
- Keep improvement ideas and experiment results in active support ledgers without letting them replace durable behavior specs.

## Near-Term Roadmap

- Add focused validation for docs-referenced commands and spec drift checks.
- Use `improvement-ideas.md` for untested or unresolved improvement hypotheses and `experiment-results.md` for benchmarked, rejected, superseded, or partly kept ideas.
- Treat A2b typed retrieval scoring, A4 evidence-aware reranking, and F excluded-column join diagnostics as current main behavior, not experiment flags.
- Before another prompt/recovery/vision value-acceptance dev-check, inspect evidence-anchor and artifact diffs from the C2/D3/E2 guardrail failures.
- Use ignored `.tmp/` or external sibling worktrees for future experiment loops; do not recreate a visible top-level `w/` worktree container.
- Keep the portable agent kit centered on `review_input.json` authoring, rich static/local review, and accepted-only export without turning it into a second app.
- Refresh screenshots when the next visible UI workflow change lands.
- Continue reducing personal-path assumptions in benchmark presets and historical external-result material.
- Keep benchmark reporting clear about low replicate counts, degraded scoring, judge instability, and raw-winner versus recommended-default distinctions.

## Deferred / Not Now

- Do not make eval or optimizer separate end-user products.
- Do not replace the browser review workflow with unattended export as the default path.
- Do not add broad cloud-provider behavior without preserving local-first defaults and explicit provider locality.
- Do not add new active spec files unless an existing canonical owner cannot hold the durable truth.
- Do not restore long compatibility-reference files to active folders.
- Do not treat improvement ledgers as a replacement for updating `spec.md` and the focused owner when behavior changes.

## Spec-System Direction

The active spec set is intentionally small:

- integrated truth in `spec.md`
- focused truth in `architecture.md`, `contracts.md`, `ui-review-workflow.md`, and `eval-and-optimizer.md`
- durable decisions in `decisions.md`
- active experiment planning/evidence in `improvement-ideas.md` and `experiment-results.md`
- current direction here
- living status in `tasks.md`
- machine-readable validation in `contracts/schemas/*.json`

Historical task ledgers, superseded rationale, and compatibility references belong under `archive/` and must remain non-normative.
