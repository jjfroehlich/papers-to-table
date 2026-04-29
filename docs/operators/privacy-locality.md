# Privacy and local-first data handling

papers-to-table is local-first by default. With default LM Studio localhost settings, data stays on the local machine except what you intentionally share.

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
