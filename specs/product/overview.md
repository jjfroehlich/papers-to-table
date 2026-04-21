# Product Overview

- Status: Normative
- Owner: Product
- Depends on: README.md
- Consumed by: README.md, docs/main-app/README.md, app/backend/src/backend/app/

## Purpose

Extract Structured Info from Papers is a local-first paper-to-table review workflow.

The primary product is the main app, which turns a folder of scientific PDFs plus a structured spreadsheet into reviewed spreadsheet updates. The monorepo also contains two internal companion tools:

- eval, which scores run bundles produced by the main app
- optimizer, which orchestrates bounded candidate studies using the main app and eval

The companion tools exist to support the main app. They do not redefine the product.

## Problem statement

The repo exists because normal paper-chat or paper-search tools do not solve the real workflow problem.

Researchers need reviewed spreadsheet updates with explicit row alignment, field-specific extraction, evidence inspection, and export discipline. A generic PDF chat surface can help explore papers, but it does not provide the queueing, auditability, stable identifiers, or export controls required for trustworthy table curation.

## Product principles

- The main app is the product. Eval and optimizer exist to support it.
- Human review is required before spreadsheet updates.
- Evidence, provenance, and auditability matter more than conversational flexibility.
- The reviewer is reviewing what the paper supports, not grading the model.
- The product should stay a focused paper-to-table workflow rather than widening into a general document assistant.

## Actors

- Primary actor: a researcher or curator reviewing extracted spreadsheet updates.
- Secondary actor: a developer or evaluator benchmarking run quality, evidence quality, and configuration choices.
- Supporting actor: an optimizer operator running bounded candidate studies against the main app and eval outputs.

## Product outcome

The system must let a researcher:

1. load a config-driven extraction run
2. parse papers and match them to spreadsheet rows
3. generate one reviewable proposal per eligible target cell with inspectable evidence
4. review proposals in a browser UI
5. export only explicitly accepted spreadsheet changes to a new workbook with audit artifacts

## Primary and subordinate surfaces

- Primary product surface: the main app browser workflow
- Internal companion surfaces: eval CLI and optimizer CLI

The main app owns extraction, review, and export.
Eval owns scoring of persisted run bundles.
Optimizer owns orchestration of bounded candidate studies.

## Goals

- Reduce manual effort for extracting structured information from papers into tables.
- Keep a human reviewer in control of every spreadsheet change.
- Preserve evidence, provenance, and auditability for every proposal.
- Keep run artifacts directly consumable by internal evaluation and optimization tooling.
- Maintain one coherent monorepo contract for shared artifacts, schemas, and metrics.

## Scope boundary

The product is successful when the main app behaves as one coherent operator workflow:

- setup and next actions are obvious
- run readiness and failure states are truthful
- review stays queue-first and evidence-centered
- export remains explicit and auditable

The companion tools should improve evaluation and optimization of that workflow, not redefine the product around benchmarking.

## MVP boundary

The MVP includes:

- local-first run creation from a config file
- schema-driven proposal generation
- queue-first browser review with evidence inspection
- explicit reviewed export to workbook plus audit artifacts
- run artifacts that downstream eval and optimizer tooling can consume from files alone

The MVP does not require:

- autonomous workbook editing without review
- a general-purpose PDF chat product
- turning eval or optimizer into equal end-user products
- broad platform or service orchestration beyond the bounded local-first workflows already defined here

## Non-goals

- Fully autonomous spreadsheet editing without human review.
- A general chat-over-PDF product.
- Replacing expert scientific judgment.
- Turning eval or optimizer into separate end-user products.
- Rewriting product scope as part of this spec-system reorganization.

## Success metrics

The product is succeeding when:

- a reviewer can reach a reviewable queue quickly from a truthful run setup flow
- proposed values are inspectable together with evidence and provenance rather than appearing as opaque model outputs
- accepted changes export cleanly into a new workbook with audit artifacts
- downstream eval and optimizer tooling can consume the same run bundle without hidden runtime coupling

## Assumptions and future extension boundary

- The app assumes a human reviewer remains the final authority for spreadsheet updates.
- The app assumes schema descriptions, stable row identity, and explicit evidence remain more important than open-ended conversational flexibility.
- Future extensions may improve parser choices, provider coverage, figure handling, and downstream benchmarking, but they should remain subordinate to the reviewed spreadsheet workflow rather than widening the product into a general assistant.

## Monorepo document ownership

- Main-app product behavior is specified in `main-app.md` and `review-workflow.md`.
- Companion-tool behavior is specified in `../tools/`.
- Shared cross-tool contracts are specified once in `../contracts/`.
- Monorepo and integration boundaries are specified in `../architecture/`.

Those boundaries are normative and should be used to avoid duplicated truth.