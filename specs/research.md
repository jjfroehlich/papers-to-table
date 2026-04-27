# Research and rationale

## Purpose

This file keeps rationale, tradeoffs, and historical notes that still matter for current work without polluting the integrated spec.

## Why the command surface was consolidated

The repo had several partially overlapping entrypoints:

- root README install and run snippets
- wrapper scripts for backend, frontend, eval, and optimizer
- backend automation CLI
- tool-local CLIs for eval and optimizer

That made it too easy for operators and coding agents to start in the wrong place.

The current repo keeps those lower-level entrypoints available but makes `scripts/papers_to_table.py` the central command surface.

## Why browser-first still matters

Even with headless mode, the product remains browser-first because:

- evidence review is part of the product promise
- manual accept/edit/reject decisions remain the safest default
- export should remain an explicit action

Headless mode exists for agent and batch workflows, not to erase review semantics.

## Why headless auto-accept is explicit

The product needed a real non-interactive path, but silent review bypass would make the repo less truthful.

So the current rule is:

- unattended export is allowed only with explicit `--accept-all`
- artifacts must record that automation performed the acceptance

## Why eval and optimizer stay separate

Keeping eval and optimizer as companion tools preserves clean boundaries:

- main app = extraction and review
- eval = scoring
- optimizer = orchestration

That separation keeps the run bundle an explicit shared contract instead of a hidden in-process interface.

## Historical context that still matters

- the repo is Windows-primary, but Git Bash-friendly commands remain preferred in docs
- LM Studio remains the default documented live path
- fixture and smoke configs are useful for contract checks but are not substitute benchmark evidence
- archive material under `specs/archive/verbatim/` remains historical only
