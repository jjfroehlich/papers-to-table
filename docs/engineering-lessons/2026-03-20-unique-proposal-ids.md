# Unique proposal identifiers must include PDF context

## Lesson

For this repository, proposal identifiers must stay unique per run, PDF, and target cell rather than only per run and cell.

## Why it mattered

Blocked and ambiguous matches can still produce multiple review rows that point at the same spreadsheet cell from different PDFs. When proposal IDs were derived only from `run_id + cell_id`, those blocked records collided, which broke React list rendering, made review actions ambiguous, and violated the repository's own requirement that proposal IDs stay unique and traceable.

## Guardrail

When generating proposal IDs or any downstream review/export records that depend on them, include the PDF identity whenever more than one PDF can surface context for the same row/column target in one run. If a UI list starts emitting duplicate-key warnings, treat it as a contract bug first, not just a rendering issue.
