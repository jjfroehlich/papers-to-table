# Archived Optimizer Research

Archive status: historical, superseded as normative current source, still informative, partially migrated into [../../plan.md](../../plan.md) and selected current optimizer normative files.

Original source path: `tools/optimizer/specs/research.md`

This file preserves the pre-unification optimizer research notes in archival form. The legacy content below is preserved verbatim from git history except for this archive header.

---

# Extract Structured Info from Papers Optimizer - research.md

## Why this product shape

The optimizer answers a bounded question:

- which explicit prompt/model/config candidate performs best on a fixed benchmark under explicit guardrails?

That favors an orchestration harness over autonomous code-editing systems.

## Key rationale

### Deterministic-first default

Deterministic-first proposal generation improves reproducibility, auditability, and failure analysis.

### Explicit study-mode split

`compare` and `optimize` serve different operator goals and should stay explicit:

- `compare`: fixed candidate set ranking
- `optimize`: iterative incumbent/challenger promotion

### Narrow bounded search surface

A narrow surface keeps experiments interpretable and runtime-bounded.

### Separate repository responsibilities

Maintaining execution/scoring/orchestration separation avoids duplicated logic and contract confusion.

### Dev versus holdout split

Repeated dev-loop ranking can overfit; holdout must remain a post-search validation surface.

### Gated acceptance

Single-scalar optimization can hide harmful regressions; guardrails keep decisions operationally safe.

### Immutable candidate bundles

Immutable manifests preserve lineage and reproducibility and support summary regeneration.

## Tradeoffs

- Strong bounds reduce expressiveness but improve trust and auditability.
- CLI-first reduces product surface area but also reduces immediate discoverability.
- Static plots are simple and robust but less exploratory than interactive tooling.
- Strict role separation may require upstream/downstream contract updates rather than local shortcut fixes.

## Open questions

1. Optimize holdout target semantics:
Should holdout validate the highest dev score seen, or strictly the last promoted incumbent lineage head?

2. Deterministic pre-promotion checks:
Should these remain embedded in pipeline success semantics or become an explicit structured gate stage with dedicated fields?

3. Compare-mode non-promotion semantics:
Should compare records continue to use `not_promoted` for all candidates, or move to mode-specific neutral decision labels?

4. Plot contract hardening:
Should plot input contracts be explicit schemas so missing metric names fail with clearer diagnostics?

## Deferred items

- bounded optional confirmation reruns for top candidates
- optional bounded LM-assisted proposer
- advanced search algorithms beyond deterministic baseline proposer
- distributed execution scheduling
- UI/dashboard surfaces
- any code-editing or benchmark-editing automation

## Appendix - Historical implementation framing

Previous docs tracked progress by implementation batches. That framing is now superseded by durable product-area task sections in `specs/tasks.md`.
