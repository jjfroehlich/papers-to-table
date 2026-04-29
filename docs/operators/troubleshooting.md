# Troubleshooting (Canonical)

This is the canonical troubleshooting page. If another page links troubleshooting guidance, treat this page as the source of truth.

- **Missing backend test deps / `respx`**: `cd app && python -m pip install -e ./backend[test]`
- **`backend.app` not importable**: run install command above from repo root workflow.
- **Missing MkDocs**: `python -m pip install -r requirements-docs.txt`
- **LM Studio unreachable**: verify LM Studio server is running and `provider.api_base` is reachable.
- **Configured model missing**: load/download configured model in LM Studio, then rerun preflight.
- **Parser dependency missing**: reinstall backend deps (`cd app && python -m pip install -e ./backend[test]`).
- **Config path mistakes**: use `--config app/config.json` or absolute path and rerun `preflight`.
- **Export blocked by pending proposals**: finish review decisions or run headless with explicit `--accept-all`.
- **Live smoke skipped**: live provider checks are optional in CI/offline; run locally with LM Studio configured.
