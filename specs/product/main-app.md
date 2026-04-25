# Main App

- Status: Normative
- Owner: Product
- Depends on: product/overview.md, contracts/run-bundle.md, contracts/proposals-and-evidence.md
- Consumed by: docs/main-app/, app/backend/src/backend/app/, app/frontend/src/

## Purpose

The main app is the primary product in this monorepo.

It ingests PDFs plus a structured spreadsheet, proposes schema-defined values with evidence, supports human review in a browser UI, and exports audited XLSX updates.

Archive material may remain useful for historical background, but this current file is the complete active source of truth for the main app.

## End-to-end workflow

The main-app workflow is:

1. start a run from the UI using a config path and optional picker-driven input overrides
2. validate inputs, runtime readiness, and provider state before extraction begins
3. parse PDFs and resolve metadata needed for row matching
4. match each PDF to at most one row while surfacing unmatched, ambiguous, and duplicate-row issues
5. generate one best proposal per eligible target cell using schema-first extraction with evidence
6. let a reviewer inspect, filter, accept, edit, confirm no data, reject, or bulk-accept the visible filtered subset
7. export only explicitly accepted updates to a new workbook plus audit artifacts
8. preserve run artifacts so downstream eval and optimizer workflows can consume them from files alone

## Run modes

The main app supports three operator-visible run modes:

- normal extraction for empty targets
- Verify mode for reviewer comparison on already-filled cells
- Eval mode for leakage-aware benchmark runs

Eval mode must use an app-owned masked working copy of target cells. It must not expose target-cell gold values to extraction.

Shared run-bundle and eval-provenance rules are defined in `../contracts/run-bundle.md`.

## Run-state requirements

The operator-visible run states are:

- `ready`
- `validating`
- `running`
- `completed`
- `completed with warnings`
- `failed`

`completed with warnings` is allowed only when meaningful processing occurred and the run remains reviewable.

Provider-unavailable or provider-unreachable state discovered at run start must fail readiness. It must not surface as a cosmetically successful run.

## Config authority

The JSON config file is the authoritative control surface for advanced behavior, reproducibility, and resolved runtime parameters.

The browser UI is the normal operator surface for:

- selecting or entering the config path
- understanding resolved preflight context
- starting or aborting a run
- following lifecycle state and warnings through live updates
- reviewing proposals and matching issues
- exporting and downloading artifacts

The UI may expose narrow picker-driven input overrides, but it must not become the primary advanced-settings surface.

The backend may expose a stable non-UI automation entrypoint for tooling, but that path is additive. It must not replace the browser UI as the normal human workflow.

## Input requirements

- The app consumes a spreadsheet plus a schema and a PDF directory.
- Spreadsheet inputs may be CSV or XLSX when supported by the current runtime paths, but row identity and schema alignment must remain explicit.
- Schema descriptions are the primary semantic extraction contract.
- Existing filled cells may support bounded style-profile inference, but they must not become hidden row-level answer leakage for normal extraction.
- Path overrides staged through the UI must become backend-readable handles before the run starts.
- The UI should keep setup picker-driven and action-oriented rather than assuming raw filesystem path entry is the normal operator workflow.
- The launch surface should stay preflight-first so the operator can see resolved inputs, scope, readiness, and next steps before starting work.

## Output requirements

- Each run writes a run bundle consumable from files alone.
- Proposal persistence remains append-friendly and inspectable through `proposals/proposals.jsonl`, with lookup or index artifacts allowed as secondary helpers.
- Export writes a new workbook plus audit artifacts rather than mutating the source workbook in place.
- Eval-mode runs must preserve masked-table and gold-table provenance needed for reproducible downstream scoring.
- Reviewable proposals and diagnostics-only outcomes must remain distinct in artifacts and summaries.
- Review surfaces may persist compact lookup artifacts that accelerate row, column, and matched-paper context, but those helpers do not replace canonical proposal or evidence streams.

## Main-app behavior requirements

### Schema-first extraction

- Extraction is schema-first.
- Column name, description, and optional field typing define what should be extracted.
- Existing filled cells are optional format helpers only and must not become semantic exemplars by default.

### Matching strategy

- Row matching is a distinct stage before proposal generation.
- The app should match each PDF to at most one row.
- Unmatched, ambiguous, and duplicate-row situations must stay explicit rather than being silently coerced into a match.
- Matching artifacts and summaries must preserve enough detail for reviewer diagnostics and downstream eval-mode accountability.

### Parser and metadata behavior

- Metadata and front-matter extraction are a distinct lane from normal content extraction.
- Parser-first metadata resolution, metadata ambiguity, metadata source, and metadata-specific failure attribution must remain explicit.

### Retrieval strategy

- Retrieval should remain row-aware and column-aware rather than defaulting to whole-document prompting.
- The intended default extraction path is `retrieval.mode=hybrid_experimental`, `retrieval.top_k=12`, recall rescue disabled, and whole-document mode disabled.
- Retrieval preparation may be cached per parsed document when that preserves truthful provenance and repeatability.
- Whole-document or recall-rescue behavior may exist as bounded configured modes, but those choices must remain explicit in run artifacts and summaries.

### Extraction strategy

- Proposal generation occurs only for eligible target cells in the active mode.
- Eval/benchmark extraction must not send gold metadata values through LLM prompts, but it must emit parser/front-matter proposals for required metadata columns that eval scores, including `Title`, `Authors`, and `Publication Year`.
- A target cell is eligible only when the run has passed readiness, the source paper has a usable row match or allowed metadata path, and the cell is in scope for the selected run mode.
- The app persists one best proposal per eligible target cell, but weaker fallback evidence and failure attribution must remain explicit so reviewers and downstream tooling can tell why a proposal looks the way it does.
- The app should prefer `unclear` over weak guessing when current-paper evidence is not strong enough.

### Style-profile behavior

- Column-level style profiles may be inferred from existing filled cells to improve output shape consistency.
- Style profiles are formatting and expression aids, not hidden semantic labels for the row being extracted.
- Style-profile behavior should remain benchmark-safe in Eval mode and should not leak target answers into extraction.

### Retrieval and figure behavior

- The main path is text and table extraction.
- When vision capability is available, the app may use text-guided targeted figure review as supplemental evidence.
- Figure review must remain shortlisted and targeted, not blanket per-page multimodal analysis.
- Figure-derived evidence must stay visibly distinct from text-derived evidence in both review surfaces and persisted artifacts.

### Proposal and evidence truth

- One best proposal is persisted per eligible target cell.
- Evidence must remain inspectable, auditable, and clearly labeled by support quality.
- Weak but reviewable proposals may still be shown, but they must be labeled honestly.
- Evidence ranking must prefer source authority and field relevance rather than model-return order.

Shared proposal and evidence rules are defined in `../contracts/proposals-and-evidence.md`.

### Review and export behavior

- Human review is required before spreadsheet updates.
- Locked cells remain protected unless a human explicitly accepts a change in the appropriate mode.
- Export must generate a new workbook and an audit log.
- Export must include only explicitly accepted changes.

Detailed review behavior is defined in `review-workflow.md`.

## Provider truth and readiness

The product must preserve one canonical provider contract for proposal generation.

- The default local-first live path is LM Studio.
- The canonical config token for that provider is `lm_studio`.
- The canonical operator-visible label is `LM Studio`.
- Unknown or unsupported provider identifiers must fail early.
- Text-model and vision-model configuration remain separate even when one provider serves both.

Operator-visible status and persisted artifacts must distinguish at least:

- provider unreachable or unavailable
- model unavailable or load failed
- `json_schema` unsupported
- provider reachable but no compatible structured-output mode available
- explicit prompt-only degraded fallback when used
- extraction-contract validity and warnings

These states must not be collapsed into one generic label.

The bounded structured-output recovery ladder is:

- `json_schema`
- `json_object`
- prompt-only JSON mode with app-side parsing when that degraded path is explicitly allowed

Model-family differences must be isolated in a small policy layer, not by forking the extraction stack. Unknown and newly added models use a shared generic default policy. Explicit family overrides may adjust only request construction, fallback order, and failure classification. Gemma and GPT-OSS are schema-first. Qwen-compatible models prefer non-thinking JSON-object requests with an explicit JSON reminder, omit `max_tokens` on structured calls, skip same-mode malformed-response retry, and classify repeated malformed structured responses quickly.

## Readiness and preflight requirements

- Run start must validate input readability, output-path writability, parser prerequisites, and provider reachability before extraction begins.
- Missing live-provider readiness must fail early rather than surfacing as a cosmetically successful run.
- Optional OCR-dependent or parser-dependent paths must report truthful readiness when they are unavailable.
- The app must record the negotiated provider mode and degraded-mode truth in persisted artifacts so reviewers and downstream tools can tell what actually happened.
- The app should preserve resolved setup context early enough that readiness-failed runs remain diagnosable.
- Live run-state transport should favor push-based updates that reduce stale-state windows in the browser UI.

## Main-app quality bar

The main app is only acceptable when it behaves as one coherent local operator workflow rather than a collection of isolated components.

That means:

- startup and next actions are obvious
- run lifecycle and warnings are understandable
- review surfaces stay gated until the run is genuinely reviewable
- reviewer-facing counts default to actionable review work rather than diagnostic-only totals
- evidence handling supports real review, not just artifact browsing
- summaries and artifacts remain truthful enough for downstream tooling without importing runtime code
- the setup surface remains understandable without reading source code
- the documented LM Studio path is either genuinely usable or fails early with an actionable readiness error
- the app does not load every blocked, skipped, or diagnostic-only outcome into the main review queue by default

## Acceptance criteria

The main app is acceptable when:

1. A normal operator can start a run from a config path and see truthful readiness failures before extraction when setup is broken.
2. PDF-to-row matching never silently hides unmatched, ambiguous, or duplicate-row outcomes.
2a. Matching artifacts must preserve extracted metadata, front-matter diagnostics, candidate-score breakdowns, and threshold or gap reasoning for matched, unmatched, and ambiguous papers.
3. Proposal generation remains schema-first and keeps one best proposal per eligible target cell with inspectable support.
4. Weak, inferred, and fallback evidence remain visibly distinguished from direct support.
5. Review stays queue-first and export writes a new workbook plus audit artifacts only after explicit reviewer action.
6. Run artifacts remain sufficient for eval and optimizer tooling without runtime imports from the main app.
6a. Run artifacts must preserve enough page-text and evidence context for downstream anchor validation, plus compact reviewer-summary truth for degraded structured-output and extraction-contract state.
7. Reviewer-facing counts distinguish actionable review items from broader attempted or diagnostic totals.
8. Provider-unavailable state at run start fails readiness rather than surfacing as a cosmetically successful run.
9. Eval mode preserves masked-table and gold-table provenance without leaking target gold values into extraction.
10. The browser workflow remains the clear primary operator path, with automation treated as tooling support rather than the main product surface.

## Ownership boundaries

- Main-app product behavior belongs here.
- Shared run-bundle, proposal, evidence, and eval-summary contracts belong in `../contracts/`.
- Monorepo integration boundaries belong in `../architecture/`.

Do not duplicate those shared rules in this file.
