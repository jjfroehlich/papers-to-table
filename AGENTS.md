# AGENTS

## Purpose

This file defines durable rules for coding agents editing `extract-structured-info-from-papers-eval`.

## Canonical Document Roles

Keep these roles strict:

- `specs/spec.md` records stable product behavior and acceptance criteria only.
- `specs/plan.md` records stable technical architecture and implementation direction only.
- `specs/research.md` records rationale, tradeoffs, open questions, and deferred items only.
- `specs/tasks.md` is the canonical implementation checklist and status tracker.
- `README.md` is the operator-facing workflow document.
- `AGENTS.md` records durable editing and verification rules.

## Spec Editing Rules

When editing spec files:

- preserve the existing canonical section structure unless the task explicitly requires a structural rewrite
- prefer editing the correct existing section over appending a new ad hoc section
- remove stale statements instead of leaving old and new truth side by side
- do not add temporary pass-specific notes, status banners, or sequencing language to `spec.md`, `plan.md`, or `research.md`
- if a note is temporary or historical, place it in `specs/tasks.md` or a clearly labeled appendix instead of the main body of stable docs
- if a document has accumulated scattered edits, reorganize it in the same pass rather than appending more drift

## Task Tracking Rules

Status belongs in `specs/tasks.md` only.

When editing `specs/tasks.md`:

- keep one canonical checked or unchecked task list
- keep each task listed exactly once
- preserve the durable section structure based on product areas
- do not reintroduce batch or phase frameworks unless explicitly asked
- keep completed tasks visible
- use an appendix for historical implementation-order notes if they are still useful
- do not mark a task complete unless code, tests, and docs support that claim

## README Rules

When editing `README.md`:

- keep it operator-facing rather than design-history-facing
- use real commands, real artifact names, real metric names, and real limitations
- describe judge behavior truthfully, including when LM Studio is and is not required
- do not document speculative features as if they already ship

## Verification Rules

Before finalizing a spec or README pass:

- re-audit relevant code paths and tests
- reclassify overstated task status instead of preserving it for continuity
- verify that commands, artifact names, and metrics mentioned in docs match the repo
- include any remaining gaps explicitly rather than leaving implied support

## Implementation Rules

When a docs pass reveals a small correctness issue that blocks truthful verification, fix it in the same pass when practical.

Prefer minimal changes that restore consistency at the root cause.
