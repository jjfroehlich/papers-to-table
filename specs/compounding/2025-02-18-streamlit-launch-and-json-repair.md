# Compounding Lesson: Streamlit launch stability + JSON repair discipline

## What happened

We hit repeated Streamlit runtime errors when launching via `streamlit.web.bootstrap.run` and intermittent LLM JSON parsing failures that silently dropped data.

## Fix

- Launch Streamlit via subprocess (`python -m streamlit run ...`) and pin Streamlit to a stable version.
- Add JSON repair prompts and record any remaining parse failures in error logs/events.

## Why it matters

These two changes improve operator trust: UI startups are predictable, and data loss from malformed LLM output is visible and diagnosable.

## Durable rule?

Yes.

### Proposed update to AGENTS.md

Add a rule: “Prefer CLI/subprocess launchers for Streamlit apps to avoid bootstrap/session initialization errors; always log JSON parsing failures with diagnostics and avoid silent drops.”
