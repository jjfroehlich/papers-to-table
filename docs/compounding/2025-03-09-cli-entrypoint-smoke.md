# CLI entrypoint smoke coverage

## What happened

`paper-table-agent` was missing from PATH in the Codex environment because console script metadata was not being validated. The UI could not be smoke-checked without launching Streamlit, making it easy to miss packaging regressions.

## Fix

- Added an entrypoint metadata test using `importlib.metadata` to assert the `paper-table-agent` console script points to `paper_table_agent.cli:main`.
- Added a headless `paper-table-agent ui --smoke` path for non-interactive environments.
- Added a `scripts/dev/smoke_cli.sh` operator script to validate install + smoke commands.

## Why it worked

Automated checks now verify packaging metadata and the CLI’s headless UI import path. This prevents regressions where the CLI appears to work locally but fails after installation.

## Durable rule?

Yes: whenever we change CLI wiring or packaging metadata, add/refresh a console script metadata test and a headless smoke path (plus a one-command operator script) to catch regressions early.
