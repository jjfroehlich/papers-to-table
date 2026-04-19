# Restoration Summary

## Purpose

This note records what had been materially compressed or lost in the earlier reorganization and how the lossless migration restored it.

## Material previously compressed or lost

- The former root main-app `spec.md` had been replaced by shorter split files without preserving the full functional-requirement matrix, trust requirements, non-functional requirements, user stories, and detailed acceptance criteria in a traceable location.
- The former root `plan.md` had been compressed into a short support index, leaving much of the parser, retrieval, extraction, evidence, provider, evaluation, risk, and alternatives detail without a structured archival home.
- The former root `research.md` had been effectively dissolved into partial summaries and scattered notes, making the original rationale, alternatives considered, and topic-by-topic research harder to recover.
- The former eval and optimizer spec stacks had been consolidated into concise current files, but their more detailed module-layout, data-flow, rationale, deferred-item, and task-history material was no longer preserved inside the spec system.

## How this migration restored it

- Restored the full legacy main-app spec stack under `../main-app/` as:
  - `../main-app/legacy-spec.md`
  - `../main-app/legacy-plan.md`
  - `../main-app/legacy-research.md`
- Restored the full legacy eval spec stack under `../eval/` as:
  - `../eval/legacy-spec.md`
  - `../eval/legacy-plan.md`
  - `../eval/legacy-research.md`
  - `../eval/legacy-tasks.md`
- Restored the full legacy optimizer spec stack under `../optimizer/` as:
  - `../optimizer/legacy-spec.md`
  - `../optimizer/legacy-plan.md`
  - `../optimizer/legacy-research.md`
  - `../optimizer/legacy-tasks.md`
- Added `legacy-section-mapping.md` so every major old section now has an explicit disposition.
- Updated `../../README.md`, `../../plan.md`, and `../../AGENTS.md` so the archive is part of the official spec system rather than an accidental side area.

## Current distinction

- Normative current behavior lives under `../../product/`, `../../tools/`, `../../contracts/`, `../../architecture/`, and `../../process/`.
- Historical, superseded, exploratory, or implementation-detail-heavy material lives under `../`.
- Shared contracts remain centralized in current files, but the older fuller explanations remain preserved in archive files instead of being silently discarded.

## Contributor rule going forward

When shortening or reorganizing spec material:

- keep the current source of truth concise where appropriate
- preserve older detail in archive files when it is still informative
- add or update explicit disposition notes instead of assuming a large deletion is safe