# Preservation Audit

## Purpose

This document provides explicit file-by-file accounting for the major legacy spec files preserved during the spec reorganization.

## Audit method

- Original content source: `git show HEAD:<original-path>`
- Archived content source: files under `specs/archive/verbatim/`
- Preservation rule: archived file must contain the original file content verbatim with no prepended archive header and no line-count drift

## File-by-file accounting

| Original path | Verbatim archive path | Preserved verbatim | Original lines | Archived lines | Current normative spec references it | Any content intentionally not preserved |
| --- | --- | --- | ---: | ---: | --- | --- |
| `specs/spec.md` | `specs/archive/verbatim/main-app/spec.md` | yes | 1523 | 1523 | yes | none |
| `specs/plan.md` | `specs/archive/verbatim/main-app/plan.md` | yes | 1861 | 1861 | yes | none |
| `specs/research.md` | `specs/archive/verbatim/main-app/research.md` | yes | 1731 | 1731 | yes | none |
| `specs/tasks.md` | `specs/archive/verbatim/main-app/tasks.md` | yes | 317 | 317 | yes | none |
| `tools/eval/specs/spec.md` | `specs/archive/verbatim/eval/spec.md` | yes | 213 | 213 | yes | none |
| `tools/eval/specs/plan.md` | `specs/archive/verbatim/eval/plan.md` | yes | 177 | 177 | yes | none |
| `tools/eval/specs/research.md` | `specs/archive/verbatim/eval/research.md` | yes | 104 | 104 | yes | none |
| `tools/eval/specs/tasks.md` | `specs/archive/verbatim/eval/tasks.md` | yes | 130 | 130 | yes | none |
| `tools/optimizer/specs/spec.md` | `specs/archive/verbatim/optimizer/spec.md` | yes | 169 | 169 | yes | none |
| `tools/optimizer/specs/plan.md` | `specs/archive/verbatim/optimizer/plan.md` | yes | 163 | 163 | yes | none |
| `tools/optimizer/specs/research.md` | `specs/archive/verbatim/optimizer/research.md` | yes | 76 | 76 | yes | none |
| `tools/optimizer/specs/tasks.md` | `specs/archive/verbatim/optimizer/tasks.md` | yes | 106 | 106 | yes | none |

## Reorganization reassessment

### Previously at-risk areas

- The first archive pass preserved old files only in annotated copies under `specs/archive/main-app/`, `specs/archive/eval/`, and `specs/archive/optimizer/`, each with prepended header text.
- The former root `specs/tasks.md` had not been archived at all.
- The live specs-only diff still showed very large deletions in `specs/spec.md` and `specs/research.md`, which made preservation difficult to prove from the working tree alone.

### Current preservation status

- Every major legacy main-app, eval, and optimizer spec file now exists under `specs/archive/verbatim/` as a same-content archive copy.
- The verbatim layer is separate from mapping notes, status headers, and normative references.
- The annotated archive copies remain available for migration-era context, but they are no longer being relied on as proof of preservation.

### Summary-only or dropped findings

- Current normative files still summarize and redistribute large portions of the old material for readability and ownership.
- That is no longer a preservation failure because the original deep material is preserved intact under `specs/archive/verbatim/`.
- No major legacy file in the audited set is currently dropped without a concrete preserved location.

## Exact non-preservation exceptions

- None in the audited major-file set.

## Related mapping

See `legacy-file-mapping.md` for old-path to archive-path to normative-owner traceability.