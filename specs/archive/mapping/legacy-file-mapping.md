# Legacy File Mapping

## Purpose

This file maps each major pre-reorganization spec file to its verbatim archive location and the current normative files that now own active behavior.

The verbatim archive is the preservation layer.
The normative tree remains the current source of truth.

## Main app legacy files

| Original path | Verbatim archive path | Current normative references |
| --- | --- | --- |
| `specs/spec.md` | `specs/archive/verbatim/main-app/spec.md` | `specs/product/overview.md`; `specs/product/main-app.md`; `specs/product/review-workflow.md`; `specs/contracts/run-bundle.md`; `specs/contracts/proposals-and-evidence.md` |
| `specs/plan.md` | `specs/archive/verbatim/main-app/plan.md` | `specs/plan.md`; `specs/architecture/monorepo-layout.md`; `specs/architecture/integration.md`; `specs/process/change-policy.md`; `specs/process/testing-strategy.md` |
| `specs/research.md` | `specs/archive/verbatim/main-app/research.md` | `specs/plan.md`; `specs/product/main-app.md` |
| `specs/tasks.md` | `specs/archive/verbatim/main-app/tasks.md` | `specs/tasks.md` |

## Eval legacy files

| Original path | Verbatim archive path | Current normative references |
| --- | --- | --- |
| `tools/eval/specs/spec.md` | `specs/archive/verbatim/eval/spec.md` | `specs/tools/eval.md`; `specs/contracts/run-bundle.md`; `specs/contracts/proposals-and-evidence.md`; `specs/contracts/eval-summary.md` |
| `tools/eval/specs/plan.md` | `specs/archive/verbatim/eval/plan.md` | `specs/tools/eval.md`; `specs/plan.md` |
| `tools/eval/specs/research.md` | `specs/archive/verbatim/eval/research.md` | `specs/tools/eval.md`; `specs/plan.md` |
| `tools/eval/specs/tasks.md` | `specs/archive/verbatim/eval/tasks.md` | `specs/tasks.md`; `specs/tools/eval.md` |

## Optimizer legacy files

| Original path | Verbatim archive path | Current normative references |
| --- | --- | --- |
| `tools/optimizer/specs/spec.md` | `specs/archive/verbatim/optimizer/spec.md` | `specs/tools/optimizer.md`; `specs/contracts/optimizer-candidate.md`; `specs/contracts/eval-summary.md`; `specs/architecture/integration.md` |
| `tools/optimizer/specs/plan.md` | `specs/archive/verbatim/optimizer/plan.md` | `specs/tools/optimizer.md`; `specs/architecture/integration.md`; `specs/contracts/optimizer-candidate.md`; `specs/plan.md` |
| `tools/optimizer/specs/research.md` | `specs/archive/verbatim/optimizer/research.md` | `specs/tools/optimizer.md`; `specs/plan.md` |
| `tools/optimizer/specs/tasks.md` | `specs/archive/verbatim/optimizer/tasks.md` | `specs/tasks.md`; `specs/tools/optimizer.md` |

## Notes

- The verbatim archive files were materialized directly from git history for the original path with no prepended archive header.
- The older `specs/archive/main-app/`, `specs/archive/eval/`, and `specs/archive/optimizer/` files remain as annotated migration-era archive copies, but they are not the proof layer for verbatim preservation.
- Current normative files may summarize or split behavior for readability. That is acceptable only because the full historical text is preserved intact under `specs/archive/verbatim/`.