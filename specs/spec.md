# papers-to-table integrated specification

- Status: Normative integrated spec
- Owner: System Integration
- Depends on: specs/contracts/schemas/*.json for machine validation
- Consumed by: README.md, AGENTS.md, docs/, app/backend/src/backend/app/, app/frontend/src/, tools/eval/, tools/optimizer/

This file integrates current system truth across the main app, companion tools, shared contracts, architecture, and process rules.

This file is the canonical markdown source for durable product and system behavior. `plan.md` owns roadmap direction, `tasks.md` owns verified status and backlog, and JSON schemas under `contracts/schemas/` own machine-readable validation. Other markdown files under `product/`, `tools/`, `contracts/`, `architecture/`, and `process/` are compatibility references unless explicitly promoted here.

## 1. Product purpose

papers-to-table is a local-first system for extracting structured information from scientific papers into a spreadsheet while preserving reviewability.

The product has three coordinated surfaces:

- **main app**: browser-first extraction, review, and export workflow
- **eval companion**: scores run bundles against gold data
- **optimizer companion**: orchestrates repeated main-app plus eval studies

## 2. Core philosophy

Repo-wide requirements that must remain visible across all owning specs are:

- local-first by default
- browser UI is the primary human operator surface
- JSON config is the authoritative advanced-control surface
- run bundles are the canonical cross-tool contract
- unknown or obsolete provider identifiers fail early and clearly
- degraded-mode truth must stay explicit in UI, runtime, tests, docs, specs, and artifacts

## 3. Main-app inputs

The main app consumes:

- one table file
- one schema file
- one PDF directory
- one JSON config

The config controls provider selection, parser behavior, retrieval settings, prompt bundle, diagnostics, figure review, and default paths.

`app/config.example.json` is the canonical checked-in template. `app/config.json` is the normal local operator config.
In browser mode, `table_path`, `schema_path`, `pdf_dir`, and `output_dir` may be blank in `app/config.json`; the operator can choose them in the interface for each run.

## 4. Main-app modes

### 4.1 Human review mode

Human review mode is the default product workflow.

Required behavior:

1. operator starts the local app
2. operator chooses or confirms table, schema, PDF, and output paths
3. operator starts the run; preflight runs first and extraction continues only if readiness passes
4. operator reviews proposals in the browser UI
5. operator accepts, edits, rejects, or confirms no data explicitly
6. export writes a new workbook and audit artifacts

### 4.2 Headless / agent mode

The backend also exposes a stable non-UI automation path.

Headless mode must:

- run extraction from terminal inputs
- return machine-readable JSON
- preserve the same run-bundle truth as the browser workflow
- reject unattended export when reviewable proposals remain pending unless the caller passes explicit `--accept-all`
- record auto-accepted decisions explicitly in artifacts when `--accept-all` is used

Headless `--accept-all` is additive. It must not silently change the default human workflow.

## 5. Main-app workflow and backend phases

### 5.1 Preflight and readiness

Preflight resolves:

- config path
- runtime input overrides
- run mode
- output directory
- provider model ids and locality
- table row count, schema column count, and PDF count when possible

Preflight must fail early on readiness defects instead of allowing cosmetically successful runs.

### 5.2 Parsing and normalized document contract

The parser layer produces normalized parsed documents with:

- paper metadata and front matter
- per-page text visibility
- typed blocks in reading order
- figure and caption relationships when available
- parser truth, fallback truth, and diagnostics

### 5.3 Matching

Each PDF is matched to at most one row.

If a PDF does not match an existing row, the normal browser workflow must stage a new row from extracted paper metadata and generate proposals for the schema-defined target cells. Ambiguous and duplicate-row conflicts remain blocked and explicit in artifacts and review diagnostics.

### 5.4 Retrieval and extraction

- extraction is schema-first
- default retrieval path is `hybrid_experimental` with `top_k=12`
- recall rescue and whole-document mode are bounded optional modes
- one best proposal is persisted per eligible target cell
- evidence quality stays explicit and honest
- figure review is planner-guided and evidence-gated, not blanket page vision
- figures are first-class retrieval chunks at the figure level only; panel-level chunks are out of scope
- candidate selection is a bounded optional final adjudication over collected text, rescue, recovery, and figure candidates

Backend extraction phases are ordered:

1. resolve config and selected paths
2. preflight provider, input, parser, and output readiness
3. initialize provider capabilities and model residency, including structured-output mode negotiation
4. create the run bundle skeleton, input snapshots, config snapshot, early summaries, and diagnostics directories
5. load table and schema, classify target-cell eligibility, and create eval-mode gold/masked snapshots when `eval_mode` is enabled
6. parse PDFs into normalized documents, page images, figures, captions, and diagnostics
7. match PDFs to table rows and stage unmatched PDF rows when needed
8. generate style profiles once per column when enabled and filled cells exist, otherwise use heuristic or schema-only guidance
9. retrieve text, table, caption, and figure-level evidence for each eligible target cell
10. produce text-model proposals for target cells through the provider adapter
11. run at most one selective recall-rescue pass, with optional whole-document context only when enabled and size-bounded
12. run optional targeted figure review for cells whose evidence triggers vision review; a generic figure planner may first skip vision, select figure-level targets, or request full-page images
13. run at most one candidate-selection call when competing or weak candidates require adjudication
14. merge, normalize, validate, and filter proposal candidates deterministically
15. persist one best proposal per cell with evidence, diagnostics, and provider metadata
16. write final summaries, provider diagnostics, reviewer summaries, artifact inventory, and model cleanup results

The optimizer must not start eval for a candidate until the candidate's extraction run has finished proposal production, written final summaries, and left the run bundle readable from disk.

Figure review requirements:

- `figure` is the only figure-derived retrieval chunk type. The app does not create panel-level figure chunks.
- figure review may inspect a valid crop, a full-page fallback when crop assets are missing or suspicious, or a planner-preferred full page for layout or panel-counting questions.
- direct figure context is not a standalone reason to call vision. Vision requires weak, unclear, missing, or contradictory text evidence; a genuinely visual request with figure-promising retrieval; or another generic evidence-quality trigger.
- prompt-only vision responses are repaired locally for recoverable schema issues, including omitted optional diagnostics, invalid `numeric_value_form` values such as `N/A`, and common value-proposal variants such as `yes`, `present`, `visible`, `clear`, `success`, `succeeded`, `possible`, `propose`, and `propose_value`.
- a figure response that proposes a value must place the extracted answer itself in `proposed_value`; blank placeholders are not usable figure evidence.
- actual vision calls, retries, image source, fallback reason, repair status, failure reason, suppression reason, promoted unclear values, and successful calls without usable hits remain visible in diagnostics.

Candidate selection requirements:

- candidate selection is optional and bounded to one selector call per cell by default.
- candidate sources are generic: first-pass text, rescued text, evidence recovery, and figure review.
- figure-derived candidates may support or compete with text candidates, but must directly answer the cell request before overriding strong text evidence.
- if text and figure candidates conflict and neither clearly satisfies the column contract, selection should keep the stronger text answer or return `proposal_status=unresolved` rather than switching to semantically mismatched figure evidence.

### 5.5 Proposal and evidence truth

The proposal/evidence contract must preserve:

- one best proposal per eligible target cell
- stable join identity (`row_id`, `column_name`, `cell_id`)
- reviewer-visible canonical proposal semantics from `contracts/proposals-and-evidence.md`: `proposal_status`, `evidence_status`, derived/validated `review_bucket`, and `reason_codes`
- auditable evidence linkage
- degraded-mode, fallback, metadata-lane, and failure-attribution truth when relevant
- optional candidate answers, figure planner diagnostics, figure review diagnostics, and selection diagnostics when the app planned, reviewed, or chose among competing evidence sources

### 5.6 Review semantics

Valid explicit review outcomes are:

- accepted
- accepted with edit
- confirmed no data
- rejected

Decision records must distinguish `human_individual`, `human_bulk_accept`, and `automation_accept_all`. Legacy `human_reviewer` records remain readable for backward compatibility, but newly recorded manual decisions use explicit individual/bulk values.

The default browser review viewport must stay focused on the proposal-review loop: a compact review bar plus a contained three-panel workspace for queue, decision detail, and evidence inspection. Queue, detail, and evidence panes must scroll independently, while diagnostics and broader run summaries remain secondary surfaces that open intentionally instead of permanently displacing the review task.

### 5.7 Export semantics

Export writes a new workbook and audit artifacts.

Export includes only explicitly accepted changes.

The source workbook is never mutated in place.

## 6. Run bundle contract

A run bundle remains the stable artifact rooted at `{output_dir}/{run_id}/` and must stay consumable from files alone by the main app, eval, and optimizer.

Stable categories include inputs, parsed artifacts, matching artifacts, retrieval artifacts, proposals, evidence, review decisions, summaries, diagnostics, and exports.

Schemas for machine validation live under `specs/contracts/schemas/` and are consumed by `verify-contract`.

## 7. Provider policy

At the integrated level, the default live provider path is LM Studio with config token `lm_studio`, and the repo must preserve truthful distinctions for provider reachability, model availability, negotiated structured-output mode, degraded fallback, extraction-contract validity, and model-management diagnostics.

### 7.1 LM Studio runtime policy

LM Studio is assumed to be one shared local server unless the operator configures otherwise. Stability takes priority over local parallel throughput.

Runtime requirements:

- main-app extraction, eval judges, and optimizer-launched subprocesses use the same default shared lock path for a given LM Studio server
- model load, model unload, structured-output probes, text completions, vision completions, and eval judge completions acquire the lock before touching LM Studio
- the lock is enabled by default for `lm_studio`; advanced operators may disable or redirect it with environment/config overrides
- extraction may unload non-kept models after all extraction calls finish
- eval judge cleanup happens only after a judge-major batch has completed
- cleanup must never unload while another local process is actively generating through the shared lock
- request, vision request, model load, model unload, and lock wait limits are configurable and default to conservative values for 26B+ local models
- provider diagnostics include timeout settings, lock path/enabled state, lock wait/count metadata, model-management events, before/after loaded-model state, and classified LM Studio operational failures

Operational failure classification must distinguish at least client disconnect, channel error, model-load canceled, timeout, model unavailable, and load/unload conflict-like failures when those signals are observable in HTTP or transport errors.

## 8. Eval companion

At the integrated level, eval remains CLI-first and file-driven: it reads run bundles from files alone, scores against gold data, keeps correctness and evidence metrics separate, preserves dual-judge details, and publishes stable output artifacts under the caller's output directory.

The current curated eval benchmark suite lives at the repository root in `benchmark_datasets/` and currently includes `massively_parallel_reporter_assays`, `genome_editing_tools`, and `spatial_transcriptomics`. Each dataset keeps active PDFs under `pdfs/`, exposes app-facing inputs through `table_template.csv` and `schema.csv`, and keeps human-curated answers in `table_gold.csv`.

Eval execution is phase-separated:

1. load and validate the run bundle and gold dataset
2. join proposals to gold cells by stable row and column identity, recording missing proposals and join failures explicitly
3. score structured fields and explicit deterministic text overrides first
4. collect judge-backed text cells, including normalized exact text matches by default, into a pending queue
5. execute judging in judge-major batches grouped by judge label, provider, model, and settings
6. unload/cleanup a judge model only after that judge-major batch is complete
7. merge per-judge verdicts back into scored cells while preserving disagreement, request failures, and unscored states
8. aggregate metrics, judge disagreements, evidence metrics, comparison rows, and output artifacts

Dual-judge runs must preserve per-judge verdicts and expose disagreement metrics instead of collapsing uncertainty away.

## 9. Optimizer companion

At the integrated level, optimizer remains orchestration-only: it loads explicit candidate bundles and search spaces, launches main-app and eval runs, keeps compare and optimize workflows distinct, distinguishes real benchmark presets from fixture and smoke presets, and reports raw winners separately from recommended defaults when trust caveats differ.

Benchmark-suite and replicate execution is canonical for optimizer studies. One-benchmark suites are the supported simple case, while `smoke`, `dev`, and `holdout` remain convenience aliases that resolve into explicit suites.

Optimizer execution is sequential by default. A candidate extraction run finishes before that candidate's eval starts. The next candidate does not begin until the current candidate's eval and report artifacts are complete. Future parallel optimizer mode must be explicit and must preserve LM Studio locking and model-residency safety.

Optimizer reports and analyses must include candidate-level, benchmark-level, suite-level, replicate-level, and run-level artifacts where applicable. Reports must distinguish raw winners from recommended defaults when trust caveats, replicate count, benchmark coverage, degraded scoring, or operational failures weaken the winner claim. Plots and tables must carry `n=1` and low-replicate warnings when relevant.

Optimizer candidate execution phases are:

1. resolve the study preset, selected suite, benchmarks, replicates, candidates, and search space
2. materialize a candidate bundle and resolved app config overlay
3. launch the main app in headless/eval mode for the whole candidate x benchmark x replicate
4. wait for proposal generation, final summaries, and run-bundle contract artifacts
5. validate the main-app launch contract
6. launch eval against the completed run bundle
7. validate eval summary and comparison artifacts
8. write candidate result rows with nested main-app and eval artifact references
9. aggregate replicate, benchmark, suite, and study summaries
10. rank raw winners, apply trust caveats, and write reports, plots, and recommended-default metadata

The optimizer does not interleave proposal and judge work at cell granularity. Proposal generation is main-app-owned and happens for the whole candidate run before eval starts. Judging is eval-owned and happens after eval has collected all judge-needed cells for the completed run.

Optimizer reports must expose capability use and suppression when run stats are present. At minimum this includes text and vision call counts, figure planner attempts/success/skips/fallbacks, figure-review attempts/success/failure/suppression, successful vision calls without usable hits, figure-derived evidence count, candidate-selection attempts and value changes, recall-rescue eligibility/use/skips, and whole-document eligibility/use/skips. Runtime diagnostics should group figure review by image source (`crop`, `full_page_fallback`, `full_page_preferred`) when available.

## 10. Config families

### 10.1 Main app

Canonical template: `app/config.example.json`

### 10.2 Eval

Primary surface: CLI arguments plus optional eval schema JSON

### 10.3 Optimizer

Canonical presets:

- `compare_models.json`
- `compare_prompts.json`
- `compare_retrieval_parameters.json`
- `compare_extraction_features.json`
- `optimize_parameter_sweeps.json`

Smoke and fixture-manual configs remain explicitly labeled non-canonical benchmark evidence.

Eval and optimizer config semantics are canonical in this file, with operator examples summarized in the MkDocs manual.

## 11. Operator command surface

The repo exposes one central operator and agent command surface:

- `python scripts/papers_to_table.py install`
- `python scripts/papers_to_table.py review`
- `python scripts/papers_to_table.py preflight --config ...`
- `python scripts/papers_to_table.py headless --config ... --accept-all --export`
- `python scripts/papers_to_table.py verify-contract --run ...`
- `python scripts/papers_to_table.py eval ...`
- `python scripts/papers_to_table.py optimizer compare-models`
- `python scripts/papers_to_table.py optimizer compare-models --initial-model ...`
- `python scripts/papers_to_table.py optimizer dev-check`
- `python scripts/papers_to_table.py optimizer full-benchmark`
- `python scripts/papers_to_table.py optimizer full-benchmark --initial-model ...`
- `python scripts/papers_to_table.py docs serve`
- `python scripts/papers_to_table.py docs build`

Optimizer wrapper commands support `--label` for run-directory naming where applicable. `compare-models --initial-model` and `full-benchmark --initial-model` materialize run-local configs so checked-in presets remain unchanged. `dev-check` is the fast development signal: one configured model, one benchmark, and one replicate, defaulting to `google/gemma-4-e4b` on `bench_genome_editing`.

## 12. Diagnostics, reports, and limitations

The system must remain truthful about:

- readiness defects
- parser availability and fallback
- matching ambiguity
- degraded structured-output modes
- evidence weakness
- selective recall-rescue and whole-document fallback eligibility, use, and skips
- figure planner and figure-review suppression, failure, retry, repair, image-source, and no-hit outcomes
- candidate-selection attempts, value changes, and conservative figure-over-text decisions
- auto-accepted headless decisions
- LM Studio channel errors, client disconnects, model-load cancellation, timeouts, and lock waits
- eval/optimizer trust caveats, low replicate counts, and judge disagreement

Known practical limits include parser dependency drift, live model readiness variance, judge disagreement on fuzzy text fields, and the need for real benchmark manifests outside the checked-in fixture set.

## 13. Documentation and agent-operating surfaces

- `README.md` is the concise repository entry point.
- `docs/` is the operator/developer manual and is also buildable as a local/static MkDocs Material site; its MkDocs config and optional docs requirements live under `tools/docs/`.
- `specs/` remains the canonical rebuild-grade implementation truth.
- `skills/papers-to-table-local-app/` provides a focused local-app/headless operating procedure for external coding agents and must not replace installation or runtime readiness checks.
- `skills/papers-to-table-agent-kit/` is a companion portable skill for agent-native extraction. It may use loose agent-owned extraction workspaces and only normalizes data at optional review/export/report-handoff boundaries; it is not part of the main app runtime contract.
