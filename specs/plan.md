# Technical direction

## Purpose

This file describes the current architecture direction and near-term roadmap for the monorepo.

## Current architecture

### Main app

- backend: FastAPI plus stable run-bundle artifact writing
- frontend: React review UI
- automation: stable terminal entrypoint for preflight, start, status, wait, and headless workflows

### Companion tools

- eval reads run bundles and writes score artifacts
- optimizer launches repeated main-app and eval studies from explicit configs

## Direction

### Usability and operability

- keep one obvious repo-level command surface
- keep install, review startup, headless mode, eval, and optimizer discoverable from one place
- keep browser-first human workflow and config authority intact

### Contract clarity

- keep run bundles consumable from files alone
- keep auto-accept and degraded-mode truth visible in summaries and audit artifacts
- keep config families clearly labeled by purpose and benchmark intent

### Documentation and specs

- keep README concise and task-oriented
- keep docs navigable from a single central index and local/static MkDocs Material site
- keep `spec.md` as the canonical product/system truth
- keep `plan.md` limited to roadmap and technical direction
- keep `tasks.md` limited to verified status and backlog
- keep JSON schemas under `contracts/schemas/` as the machine-readable contracts
- retire or pointer-replace older normative-looking markdown after downstream links have been updated
- keep external agent usage guidance compact through a reusable headless skill package

### Local model operations

- prefer stable serialized LM Studio use over parallel local throughput
- keep model load/unload/completion phases explicit across main app, eval, and optimizer
- keep timeout, lock, and model-management diagnostics visible in artifacts

## Near-term roadmap

- expand focused validation for docs-referenced commands and presets
- keep screenshots aligned with UI truth when the review workflow changes
- continue reducing stale or personal-path assumptions inside benchmark presets
- finish archiving or pointer-replacing older scattered spec markdown once links are clean

## Extraction accuracy and speed implementation plan

This plan implements `specs/extraction-accuracy-speed-improvements.md` as runnable main-app behavior, not provenance-only scaffolding.

### P0 guardrails

- Keep normal `per_cell` extraction as the default control path.
- Treat schema-defined blank required metadata cells as eligible while preserving filled metadata, row order, headers, non-target columns, and unsupported blank values.
- Record text calls, vision calls, planner calls, batch calls, batch retries, fallback calls, blank rate, throughput, and score-per-minute inputs in run stats and optimizer summaries.

### P1 column planning

- Produce `planning/column_plan.json` for every run.
- Use `extraction.column_planning.mode=llm_primary` to call the text model once per schema when live provider capability is available.
- Clamp all planner output through deterministic validation: supported extraction kinds, groups, visual policies, blank policies, retrieval profiles, and schema allowed-values only.
- Fall back to deterministic schema-derived planning on provider failure or invalid planner output.

### P2 evidence cards and retrieval profiles

- Produce one compact `evidence_cards/{pdf_id}.json` for each parsed PDF.
- Use column-plan retrieval profiles to shape retrieval query hints, allowed chunk types, captions/tables inclusion, neighbor-window policy, and effective top-k.
- Include evidence-card summaries in field-group prompts so the batched path sees paper-level context before per-column passages.

### P3 field-group extraction

- Implement `extraction.mode=field_group` as a real candidate path.
- Group eligible cells by matched PDF and column-plan group.
- Make one structured text-model call per `(pdf_id, group)`, returning multiple cell results.
- Split successful group results into existing `ProposalRecord` and `EvidenceRecord` artifacts without changing proposal/evidence join keys or export semantics.
- Retry only failed, invalid, unclear-without-evidence, or missing-result cells through the existing per-cell extractor.

### P4 vision and lazy rendering

- Trigger figure review from column-plan `visual_policy=prefer` or from explicit evidence/reasoning fallback, not from caption presence alone.
- Keep eager rendering as the default; support `parser.page_render_policy=lazy` by skipping parse-time page image generation and generating page images on demand for figure review or review assets.

### P5 optimizer quantification

- Add optimizer knobs for extraction mode, planner mode, page render policy, and vision policy.
- Compare the control `per_cell` mode with `field_group` candidates in extraction-feature configs.
- Surface accuracy, wall time, text calls, vision calls, batch success rate, retry rate, blank rate, and score per minute in optimizer outputs.
