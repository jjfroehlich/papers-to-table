# Spec Archive

## Purpose

This directory preserves historical, superseded, exploratory, and implementation-detail-heavy spec material that is still useful for understanding the product and tools.

The files here are not the current normative source of truth unless a file explicitly says otherwise.

Within this archive, `verbatim/` is the strict preservation layer. Mapping or status text belongs outside those verbatim copies.

## Archive structure

- `verbatim/`: untouched legacy major spec files preserved directly from their original paths
- `main-app/`: archived root spec, technical plan, and research material from the main app
- `eval/`: archived eval spec stack
- `optimizer/`: archived optimizer spec stack
- `mapping/`: preservation audit, old-path to archive-path mapping, and restoration summary for the verbatim archive
- `migration-notes/`: explicit section mapping, restoration notes, and migration guardrails

## Archive status labels

Archived files should carry a short header that labels them as one or more of:

- historical
- superseded
- still informative
- partially migrated into newer normative files

These labels help future contributors keep useful detail without mistaking old text for the current canonical behavior.

## How to use the archive

- Read current behavior from the normative files under `../product/`, `../tools/`, `../contracts/`, `../architecture/`, and `../process/`.
- Use `verbatim/` when you need strict preservation of the original major files.
- Use `mapping/` when you need proof of preservation or old-path to current-owner traceability.
- Use the other archived directories when you want the migration-era annotated copies and status headers.
- Check `mapping/preservation-audit.md` and `mapping/legacy-file-mapping.md` before removing or compressing any archived material further.

## Editing rule

Do not silently delete major historical material from this archive.

If archived material is reorganized, preserve traceability by updating the migration notes and keeping the old section disposition explicit.