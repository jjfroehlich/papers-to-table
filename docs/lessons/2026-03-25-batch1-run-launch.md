# Compounding lesson: keep run creation asynchronous but artifact-first

## Context
Batch 1 required UI-driven run creation with visible lifecycle transitions while keeping the API responsive.

## Lesson
For local-first single-user runs, return the run immediately, persist `run.json` first, and then execute validation/pipeline in an in-process background worker. This keeps operator feedback immediate and preserves inspectable state even on early failures.

## Why this compounds
Future stages (parse/match/extract/review/export) can reuse the same lifecycle + artifact-first pattern without introducing a separate job framework prematurely.
