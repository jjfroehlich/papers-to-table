## Engineering lesson — `MatchResult` object is not subscriptable

**Date:** 2026-03-31

---

### Symptom

A run completed the matching stage but crashed during extraction with:

```
'MatchResult' object is not subscriptable
```

The traceback originated in `backend/app/runner.py` in the extraction stage, where the pipeline iterated over `match_results` and tried to read fields with dict-style subscript access (`mr["pdf_id"]`, `mr.get("blocked")`, etc.).

---

### Cause

`MatchResult` is a Pydantic `BaseModel`, not a plain `dict`. Pydantic models expose their fields as attributes (`mr.pdf_id`), not dictionary keys. Calling `mr["pdf_id"]` raises `TypeError: 'MatchResult' object is not subscriptable`.

The mismatch was introduced when earlier code that built `match_results` as a list of plain dicts was refactored to return typed `MatchResult` model instances. The runner's consumption code was not updated in lock-step.

---

### Fix

Replace all dict-style accesses on `MatchResult` values in `runner.py` with attribute access:

| Before (dict-style) | After (attribute) |
|---|---|
| `mr["pdf_id"]` | `mr.pdf_id` |
| `mr.get("blocked")` | `mr.blocked` |
| `mr.get("blocked_reason")` | `mr.blocked_reason` |
| `mr["outcome"]` | `mr.outcome` |

Also build the `matched` lookup dict typed as `dict[int, MatchResult]` and access it with `.pdf_id`, `.blocked`, `.blocked_reason` attributes throughout the extraction loop.

---

### Lesson

**When a data structure is promoted from `dict` to a typed model, audit every consumer at the same time.**

Pydantic `BaseModel` instances are not backwards-compatible with dict-access code (`obj[key]`, `obj.get(key)`). A simple grep for `mr[` or `.get(` on the result variable name catches all offending sites in one pass. This is easiest to do at the moment of the refactor, before the typed return value reaches distant consumers.

A lightweight defence: add a type annotation at the assignment site (`match_results: list[MatchResult] = run_matching(...)`) — static analysers and IDE type-checkers will flag subscript access on a `BaseModel` immediately, before the bug ever reaches runtime.
