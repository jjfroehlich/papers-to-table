# Default audit + eval must share a post-run hook

## Context
We switched the default run behavior to always generate audit proposals for filled cells and to always emit evaluation artifacts at the end of `paper-table-agent run`.

## Lesson
When a behavior is expected after every run (e.g., evaluation artifacts + run_report summaries), consolidate it into a shared post-run finalize hook so CLI and workflow entrypoints cannot drift. Also make audit defaults explicit (bounded + deterministic) so tests and local runs stay reproducible.

## Actionable guidance
- Use a single finalize function for write/eval/marker steps across entrypoints.
- Keep audit sampling deterministic and bounded to control runtime.
- Ensure eval artifacts are written even when there are zero audited cells, with a status note.
