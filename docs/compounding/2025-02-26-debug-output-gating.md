# Debug output gating

## What happened

We reduced default run artifacts to the minimal required set and gated mapping reports and proposal dumps behind `output.debug_reports=true` to keep runs lightweight and predictable.

## Why it mattered

Always-on debug artifacts add noise for operators and confuse downstream expectations about which files are required for normal runs. The pipeline should emit only what’s needed for review and export by default.

## Fix

- Gate mapping reports and proposal dumps behind the debug flag.
- Update tests and docs to match the new defaults.

## Durable rule?

Yes: keep optional diagnostics behind `output.debug_reports=true`, and treat exports as a minimal contract (updated table + audit log). If new diagnostics are added, they must be opt-in and documented.
