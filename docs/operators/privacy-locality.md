# Privacy and local-first data handling

papers-to-table is local-first by default. With default LM Studio localhost settings, data stays on the local machine except what you intentionally share.

## Local host-side actions guard

- The `open in local viewer` API action is restricted to trusted loopback clients by default (`127.0.0.1`, `::1`, `localhost`).
- Non-local clients receive a clear error unless explicitly overridden with `P2T_ALLOW_NONLOCAL_HOST_ACTIONS=true`.
- This prevents silent host-OS action execution when the backend is exposed beyond local loopback.

## Optional hardened output root policy

- By default, output directory access remains permissive for trusted local workflows.
- Set `P2T_ENFORCE_OUTPUT_ROOT_POLICY=true` to enforce output-dir root allowlisting.
- Configure allowed roots via `P2T_ALLOWED_OUTPUT_ROOTS` (path-separated list).

## Data read
- input table/workbook
- schema file
- PDFs directory
- JSON config

## Data written
- run bundle artifacts (`run.json`, proposals, evidence, decisions, summaries)
- exported content-only workbook copy
- export audit logs

## Sensitive content warning
Run bundles can contain extracted text snippets, quotes, and evidence context from source PDFs. Treat run bundles as potentially sensitive.

## Provider egress
- Local LM Studio: requests sent to configured localhost API base.
- Non-local/cloud endpoints: proposal/evidence prompt context leaves the machine to that provider.

## Retention and sharing guidance
- Keep run bundles only as long as needed.
- Review `evidence/` and `exports/audit_log_*.json` before sharing externally.
- Avoid verbose logging when source text is sensitive.
