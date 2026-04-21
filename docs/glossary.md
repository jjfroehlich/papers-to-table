# Glossary and concrete examples

## Key terms

- **Run preflight**: the setup step that resolves paths, checks provider/model readiness, counts scope, and tells the operator what will happen next before a run starts.
- **Run bundle**: the filesystem artifact bundle at `{output_dir}/{run_id}/` that the main app writes and downstream tools consume.
- **Reviewable proposal**: a proposal that belongs in the main queue because it can receive an explicit reviewer decision.
- **Diagnostics-only outcome**: a persisted outcome such as unmatched PDFs, ambiguous matches, duplicate conflicts, or blocked extraction that should stay visible but not dominate the main queue.
- **Staged handle**: an app-owned input reference created when browser-selected files are copied into a backend-readable staging area.
- **Provider mode**: the persisted truth about how model access actually ran, for example `live_local` or `unavailable`.

## Payload examples

### Run preflight response

```json
{
  "run_mode": "normal",
  "resolved_inputs": {
    "table_path": {
      "source_kind": "config",
      "logical_source": "/data/table.xlsx",
      "runtime_locator": "/data/table.xlsx"
    },
    "pdf_dir": {
      "source_kind": "staged_handle",
      "logical_source": "3 picked PDF(s): paper_1.pdf, paper_2.pdf, paper_3.pdf",
      "runtime_locator": "/repo/app/runs/.staged_inputs/staged_pdf_dir_abc123/pdf_dir"
    }
  },
  "scope": {
    "table_rows": 42,
    "schema_columns": 8,
    "pdf_count": 12
  },
  "readiness": {
    "ok": true,
    "provider_mode": "live_local",
    "errors": [],
    "warnings": []
  }
}
```

## State examples

- `running` + `current_stage=parse`: the run is live and parse-stage updates should stream into the UI.
- `completed_with_warnings`: the run produced reviewable proposals, but the operator still needs to inspect warnings and diagnostics.
- `failed` with `provider_readiness_error`: setup failed early enough that extraction never became trustworthy.

## Workflow examples

- **Normal operator flow**: run preflight -> start run -> watch live SSE status -> review queue -> open diagnostics drawer as needed -> export explicitly.
- **Picker override flow**: choose a config -> stage a replacement table or PDFs -> rerun preflight -> launch with staged handles.
- **Docs-refresh flow**: change UI -> run screenshot capture test -> commit updated images with the workflow doc changes.

## File-ownership examples

- Product behavior -> `specs/product/*.md`
- Shared contracts -> `specs/contracts/*.md`
- Integration or layout boundaries -> `specs/architecture/*.md`
- Testing and change policy -> `specs/process/*.md`
- Human contributor quickstart -> `CONTRIBUTING.md`
- Agent rules -> `AGENTS.md` and `specs/AGENTS.md`
