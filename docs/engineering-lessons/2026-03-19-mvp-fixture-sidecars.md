# MVP fixture sidecars and bounded fallbacks

## Lesson

For deterministic paper-to-table tests, prefer explicit PDF sidecar metadata/text fixtures over brittle assertions against arbitrary real PDFs.

## Why it mattered

The MVP needs real pipeline coverage, but PDF extraction quality varies by parser availability, OCR tooling, and document structure. Sidecars let tests lock expected matching, OCR-path selection, evidence anchoring, and figure-fallback behavior without pretending the environment always has the full production toolchain.

## Guardrail

Keep the sidecar path clearly test-oriented and preserve the same normalized parsed-document contract as the real parser path so downstream orchestration is exercised identically.
