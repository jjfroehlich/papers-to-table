# Privacy and local-first data handling

papers-to-table is local-first by default. With default LM Studio localhost settings, data stays on the local machine.

## Local host-side actions guard

- The `open in local viewer` (add where this appears, in browser ui?) is restricted to trusted loopback clients by default (`127.0.0.1`, `::1`, `localhost`).
- Non-local clients receive a clear error unless explicitly overridden with `P2T_ALLOW_NONLOCAL_HOST_ACTIONS=true`.
- This prevents silent host-OS action execution when the backend is exposed beyond local loopback.

## Optional hardened output root policy

- By default, output directory access remains permissive for trusted local workflows.
- Set `P2T_ENFORCE_OUTPUT_ROOT_POLICY=true` to enforce output-dir root allowlisting.
- Configure allowed roots via `P2T_ALLOWED_OUTPUT_ROOTS` (path-separated list).

## Data being read
- input table
- schema file
- PDFs directory
- JSON configs

## Data written
- run output bundle artifacts
- exported content-only spreadsheet
- export audit logs

## Sensitive content warning
Run bundles can contain extracted text snippets, quotes, and evidence context from source PDFs. Treat run bundles as containing sensitive information.

## Provider egress
- Local LM Studio: requests sent to configured localhost API base.
- Non-local/cloud endpoints: proposal/evidence prompt context leaves the machine to that provider.

## Retention and sharing guidance
- Keep run bundles only as long as needed.
- Review `evidence/` and `exports/audit_log_*.json` before sharing externally.
- Avoid verbose logging when source text is sensitive.
