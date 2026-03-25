# Batch 2 lesson: keep parse-stage runtime bounded in asynchronous runs

## What happened

During Batch 2 implementation, parse + OCR work was moved into the run pipeline background executor.
Initial behavior could allow long-running parse/OCR work to continue after a test assertion finished, which made test sessions appear to hang and made lifecycle checks flaky.

## Why it mattered

Even with correct status transitions, unbounded parse/OCR work in background threads can distort operator expectations and make integration tests unreliable.

## Guardrails added

- Bounded parse scope for the baseline adapter (`max_pages`).
- OCR subprocess timeout handling (`ocr_timeout`) so fallback remains explicit but does not block indefinitely.
- Fast-path skip for very large PDFs in baseline parsing with a transparent diagnostic marker (`skipped_large_pdf_parse`).

## Reusable guidance

When adding heavier pipeline stages behind asynchronous run creation:

1. Bound worst-case work per input document.
2. Add explicit timeout/skip diagnostics instead of silent hangs.
3. Keep terminal-state tests resilient to asynchronous startup/teardown timing.
