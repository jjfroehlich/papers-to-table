# Run Bundle Contract

## Purpose

This file defines the shared run-bundle contract emitted by the main app and consumed by eval and optimizer.

This contract is owned here exactly once.

## Scope

The run bundle is the canonical cross-tool filesystem contract for one main-app run.

It must be consumable from files alone.
Downstream tools must not need to import main-app runtime code to interpret it.

## Required files

Each run bundle must contain at least:

- `run.json`
- `proposals/proposals.jsonl`

When present, the following files are part of the stable shared surface:

- `config.snapshot.json`
- `inputs/input_summary.json`
- `summaries/run_summary.json`
- `summaries/reviewer_summary.json`
- `proposal_index.json`
- canonical evidence artifacts
- persisted page-text-compatible or parsed-document artifacts needed for anchor validation

## Stable artifact categories

The run bundle should keep artifact categories explicit rather than flattening everything into one directory.

Stable categories include:

- inputs
- style profiles
- parsed artifacts
- matching artifacts
- retrieval artifacts
- proposals
- evidence
- review decisions
- summaries
- diagnostics
- exports

Directory names may evolve with versioning, but downstream tools should continue to find the same conceptual categories in stable published locations.

## Proposal persistence

- `proposals/proposals.jsonl` is the canonical append-friendly proposal record stream.
- Secondary proposal index or lookup files may exist for fast UI and tooling access, but they do not replace the canonical proposal stream.
- Published proposal records must preserve stable cross-tool identifiers and enough provenance for review, eval, and optimizer consumers.

## Stable identifiers

Proposal records must publish these stable join fields:

- `row_id`
- `column_name`
- `cell_id`

`row_index` may exist as debug or fallback context, but it is not the canonical cross-tool join contract.

## Schema-version rules

The run bundle must publish explicit schema-version fields for:

- the run bundle
- proposal records
- evidence records

Downstream tools must validate supported versions explicitly rather than guessing.

## Eval-mode provenance

When a run is marked as Eval mode, the bundle must preserve reproducibility metadata for the gold table and the masked working table.

The evaluator must be able to load this provenance from persisted run artifacts, including the stable nested main-app aliases already used in practice.

## Compact provenance passthrough

Stable summary artifacts must expose compact provenance needed by downstream tooling without reparsing verbose diagnostics.

That compact truth includes, when applicable:

- structured-output mode and degraded fallback truth
- parse-repair usage
- extraction-contract validity and warnings
- retrieval mode and retrieval top-k
- recall-rescue and whole-document retrieval usage
- extraction lane and failure attribution
- parser-cache and related reuse truth

Stable eval-facing provenance should also preserve, when applicable:

- run mode and eval-mode masking context
- gold and masked snapshot references and hashes
- source model identity for text and vision paths
- extraction lane and failure attribution needed by downstream scoring and reporting

Those summary fields are the shared contract consumed by eval and optimizer reporting.

## Ownership boundary

This file owns the run-bundle surface.

Main-app product docs and tool docs may reference this contract, but they must not restate its detailed file and field rules independently.