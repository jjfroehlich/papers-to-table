# Restoration Summary

## Purpose

This file summarizes what was previously at risk in the spec migration and how the current preservation pass safeguards it.

## What had been at risk

- The initial reorganization produced a large negative specs diff, especially through deletion of `specs/spec.md` and `specs/research.md` from the live tree.
- The first archive pass stored legacy files with prepended archive-status headers, which made those copies useful but not strictly verbatim.
- The root legacy `specs/tasks.md` was not preserved in archive form.
- The proof of preservation depended too heavily on narrative mapping rather than direct preserved locations.

## What this pass changed

- Added a separate verbatim archive at `specs/archive/verbatim/`.
- Preserved all major legacy main-app, eval, and optimizer spec files under that verbatim layer using their original filenames.
- Kept explanatory context and audit logic outside the preserved files, under `specs/archive/mapping/`.
- Added file-by-file preservation accounting with original path, archived path, line counts, and normative references.

## Resulting model

- Current normative specs: current source of truth
- Verbatim archive: intact historical source material
- Mapping docs: traceability and audit proof

## Practical consequence

The current normative spec system can remain organized, split by ownership, and easier to maintain.

That organization no longer depends on trusting summary equivalence alone, because the original deep material is now available at stable archive paths with explicit audit accounting.