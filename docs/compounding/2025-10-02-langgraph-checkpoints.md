# Compounding lesson: checkpointed batch runs + stop flags

## Observation
Building resume/stop controls alongside LangGraph checkpoints is easier when the workflow state stays minimal (pdf_index + pdf_ids) and the rest of the business state lives in SQLite. A simple `STOP` flag checked between PDFs provides a safe, low-friction stop mechanism in a non-interactive environment.

## Impact
- Keeps checkpoint payloads small and stable across schema changes.
- Allows safe mid-run termination without corrupting the proposal store.

## Durable rule?
Yes: prefer file-based stop flags for long-running batch pipelines and keep LangGraph state minimal, with SQLite as the source of truth for domain state.

## Proposed update
Add to `AGENTS.md` a note to keep LangGraph checkpoint state minimal and to use file-based stop flags for batch workflows.
