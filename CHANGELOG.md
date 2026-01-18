# Changelog

## Unreleased

- Fixed Streamlit startup stability by launching via subprocess and pinning Streamlit 1.32.2.
- Updated two-pass matching to prioritize title/authors, add deterministic matching, and include candidate tables in mapping reports.
- Unified proposal schema (one record per column) and persisted verify results in proposals for review.
- Overhauled UI with run registry dropdowns, row-by-row Prev/Next review, and PDF side-panel highlighting.
- Added JSON repair + diagnostics for LLM parsing failures and new tests for matching/schema/registry.
