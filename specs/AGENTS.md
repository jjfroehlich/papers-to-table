# AGENTS.md

## Scope

Applies to all files under `specs/`. Use this with the root `AGENTS.md`; this file is more specific for spec work.

## Canonical Spec Set

Active normative/spec-support files:

- `README.md`: spec-system index, read order, and add/remove/rename rules.
- `spec.md`: integrated product and system truth.
- `architecture.md`: repo layout, boundaries, and integration flow.
- `contracts.md`: human-readable shared contracts.
- `ui-review-workflow.md`: browser review, evidence, diagnostics, and export workflow.
- `eval-and-optimizer.md`: eval and optimizer behavior, benchmarks, suites, replicates, reports, and trust caveats.
- `decisions.md`: durable ADR-style decisions.
- `improvement-ideas.md`: prioritized untested or unresolved improvement ideas.
- `experiment-results.md`: tested evidence and decision records for improvement ideas.
- `plan.md`: current roadmap and direction only.
- `tasks.md`: living current backlog/status only.
- `contracts/schemas/*.json`: machine-readable artifact contracts.

Archive files are historical only. Older compatibility files under `archive/compatibility-refs-*`, old task ledgers, and archived rationale must not be treated as current authority.

## Required Workflow

1. Read `README.md`.
2. Read `spec.md`.
3. Read the focused owner for the change.
4. Read `decisions.md` when a durable product or architecture choice is involved.
5. Read `improvement-ideas.md` and `experiment-results.md` when the work involves extraction quality, runtime, eval, optimizer, benchmark interpretation, or tested ideas.
6. Read `plan.md` and `tasks.md` only when direction or status matters.

Substantial behavior, architecture, workflow, config, artifact, provider, UI, eval, optimizer, or CLI changes must update `spec.md` plus the focused owner in the same pass, or the final response must state why no spec update was needed.

## Drift Prevention

- Specs must be rebuild-grade: a capable coding agent should be able to rebuild a similar app from the active specs without archive files.
- Do not solve drift by copying the same truth into multiple files. Promote durable truth into the owning canonical file, replace stale references, and archive obsolete duplicates.
- Do not add a new active normative file unless the truth cannot fit cleanly into an existing owner.
- Any active spec add, remove, or rename must update `README.md`, this file, root `AGENTS.md`, relevant docs/tests, and drift checks in the same pass.
- `tasks.md` is not a historical ledger. Keep current work there and archive old ledgers only when useful.
- `plan.md` is current roadmap only. Do not preserve old completed phase plans there.
- `improvement-ideas.md` owns untested or still-open ideas. When an idea is benchmarked, rejected, superseded, or partly kept, move the evidence to `experiment-results.md` and update or remove the idea entry.
- `experiment-results.md` owns tested evidence and decisions. Run-table `Model` columns should contain only model ids.
- Improvement ledgers are active supporting files, but they do not own durable product behavior. Promote durable behavior changes into `spec.md` and the focused owner.
- Archive material may preserve history, but current behavior must be justified by current active specs and schemas.

## Conflict Rule

If active specs, code, docs, tests, config examples, screenshots, or run artifacts disagree, identify the owning active spec and either fix the implementation/docs/tests to match it or update the owning spec first if intended behavior changed.

When a machine-readable schema conflicts with prose, resolve both in the same pass. Schemas own validation shape; prose owns human-readable contract intent.

## Documentation Sync

- README and MkDocs pages may summarize workflows, but they must not become the only source of implementation truth.
- Update docs and screenshots when operator-visible behavior changes.
- Update `tools/docs/mkdocs.yml` when manual pages are added, removed, or renamed.
- Remove stale links instead of leaving old and new paths side by side.

## Completion Checklist

- Active specs remain rebuild-grade and agree with each other.
- Archive files are clearly historical and not required for current behavior.
- `spec.md` and the focused owner were updated for durable behavior changes, or no spec update was needed.
- `plan.md` contains only current direction.
- `tasks.md` contains only current backlog/status and recently verified work.
- Improvement ideas/results are in the active support ledgers when experiment planning or evidence changed.
- JSON schemas remain in `contracts/schemas/` and are updated when validation shape changes.
- Stale paths, provider names, benchmark names, and moved spec links were removed from active files.
- Relevant checks were run, including `python scripts/check_specs.py` for spec/doc-governance changes.
