# Old to New Path Mapping

This note records the main path changes introduced by the monorepo migration.

Historical note: the old repository names below refer to the pre-monorepo sibling repositories that were imported into the current `papers-to-table` repo.

## Main app moves

| Old path | New path |
| --- | --- |
| `backend/` | `app/backend/` |
| `frontend/` | `app/frontend/` |
| `tests/` | `app/tests/` |
| `config.example.json` | `app/config.example.json` |
| `config.json` | `app/config.json` |
| `pyproject.toml` | `app/pyproject.toml` |
| `uv.lock` | `app/uv.lock` |

## Tool imports

| Old repository | New in-repo location |
| --- | --- |
| `extract-structured-info-from-papers-eval` | `tools/eval/` |
| `extract-structured-info-from-papers-optimizer` | `tools/optimizer/` |

## Common optimizer path updates

| Old assumption | New path |
| --- | --- |
| sibling main app repo | `app/` |
| sibling eval repo | `tools/eval/` |
| old main-app fixture path roots | `app/tests/fixtures/...` |
| old eval fixture path roots | `tools/eval/tests/fixtures/...` |

## Documentation moves

| Old path | New path |
| --- | --- |
| `docs/operator-workflow.md` | `docs/main-app/operator-workflow.md` |
| `docs/run-artifacts.md` | `docs/main-app/run-artifacts.md` |
| detailed eval README content | `docs/eval/README.md` |
| detailed optimizer README content | `docs/optimizer/README.md` |
