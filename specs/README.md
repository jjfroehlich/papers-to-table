# Specification System

This directory is the canonical rebuild-grade specification set for papers-to-table.

## Active Files

- `spec.md`: integrated product and system truth across the app, tools, contracts, commands, diagnostics, and maintenance rules.
- `architecture.md`: repository layout, source and artifact boundaries, and main-app to eval to optimizer integration flow.
- `contracts.md`: human-readable run-bundle, proposal/evidence, review-decision, eval-summary, and optimizer-result contracts.
- `ui-review-workflow.md`: browser review workflow, queue behavior, run-state gating, evidence/PDF synchronization, and export boundary.
- `eval-and-optimizer.md`: eval and optimizer companion-tool behavior, benchmark policy, judge policy, study workflows, reports, and trust caveats.
- `decisions.md`: compact durable architectural and product decisions.
- `improvement-ideas.md`: prioritized untested or unresolved improvement ideas for extraction quality, runtime, eval, and optimizer work.
- `experiment-results.md`: tested evidence and decisions for implemented, benchmarked, rejected, superseded, or partly kept improvement ideas.
- `plan.md`: current technical direction and near-term roadmap only.
- `tasks.md`: living current backlog and recently verified status only.
- `AGENTS.md`: spec-editing rules for agents working in this directory.

Machine-readable artifact contracts live under `contracts/schemas/*.json`. They are current, canonical validation inputs and are not archive material.

`improvement-ideas.md` and `experiment-results.md` are active supporting files, not product-behavior specs. They guide experiments and preserve evidence for tuning decisions. Durable behavior that results from an experiment still must be promoted into `spec.md` and the focused owning spec.

## Archive Boundary

Files under `archive/` are historical only. They may preserve old wording, detailed compatibility references, old task ledgers, or superseded rationale, but current behavior must be understandable without reading archive files.

Do not cite archive files as current authority. If an archived statement is needed for current behavior, promote the durable truth into the active owning spec first.

## Required Read Order

For future agents:

1. `specs/README.md`
2. `specs/spec.md`
3. the focused spec that owns the work: `architecture.md`, `contracts.md`, `ui-review-workflow.md`, or `eval-and-optimizer.md`
4. `specs/decisions.md`
5. `specs/improvement-ideas.md` and `specs/experiment-results.md` when planning or interpreting extraction/eval/optimizer experiments
6. `specs/plan.md` and `specs/tasks.md` when direction or current status matters

## Adding, Removing, Or Renaming Specs

- Add a new active normative spec only when the truth cannot fit cleanly into an existing owner.
- Update this file in the same pass as any active spec add, remove, or rename.
- Update root `AGENTS.md`, `specs/AGENTS.md`, docs, tests, and drift checks when their references change.
- Archive or remove obsolete duplicates rather than leaving parallel active files.
- Do not solve drift by copying the same truth into several files. Put durable truth in the owning active spec, replace stale references, and archive historical copies.
