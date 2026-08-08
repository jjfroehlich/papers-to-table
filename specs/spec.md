# papers-to-table Integrated Specification

- Status: Canonical integrated spec
- Owner: System Integration
- Depends on: `architecture.md`, `contracts.md`, `ui-review-workflow.md`, `eval-and-optimizer.md`, `contracts/schemas/*.json`
- Consumed by: README, AGENTS, docs, app, eval, optimizer, tests

This file is the integrated product and system truth. Focused specs own deeper detail, but a capable coding agent should understand the whole current system from this file alone.

## 1. Product Purpose

papers-to-table is a local-first paper-to-table review app. It ingests scientific PDFs plus a structured spreadsheet and schema, generates source-linked cell proposals, supports human review in a browser UI, and exports audited workbook updates. Target fields can request technical parameters, descriptions of reported results, or claims made in a publication. Proposal evidence lets reviewers inspect where extracted information came from; the app does not evaluate whether publication claims are scientifically supported or true, which requires downstream systems outside the app.

The monorepo has three coordinated surfaces:

- Main app: extraction, review, export, and run-bundle emission.
- Eval companion: scores run bundles or external filled tables against gold data.
- Optimizer companion: orchestrates bounded candidate studies using the main app and eval.

Eval and optimizer support the main app. They do not redefine the product.

The repo also ships `skills/papers-to-table-agent-kit/` as a portable extraction and optional-review handoff for external agents. It does not run the main app, FastAPI backend, LM Studio provider path, or local extraction pipeline. The agent authors evidence-backed proposals in `RUN_DIR/extraction/review_input.json`; kit scripts validate and normalize them, write a root filled CSV plus extraction provenance, and build a local review UI only after the user opts in.

## 2. Operating Principles

Repo-wide requirements:

- local-first by default
- browser UI is the primary human operator surface
- JSON config is the authoritative advanced-control surface
- run bundles are the cross-tool artifact contract
- source workbooks are never mutated in place
- unknown or obsolete provider identifiers fail early and clearly
- degraded, fallback, and readiness truth must stay explicit in runtime, UI, tests, docs, specs, and artifacts
- current behavior must be reconstructible from the active spec set without reading archive material

## 3. Main-App Inputs And Outputs

Inputs:

- one table file, normally CSV or XLSX when supported by current runtime paths
- one schema file whose descriptions are extraction instructions
- one PDF directory
- one JSON config

The config controls provider selection, parser behavior, retrieval settings, prompt bundle, diagnostics, figure review, candidate selection, and default paths.

`app/config.example.json` is the checked-in template. `app/config.json` is the normal local operator config. Browser mode may leave `table_path`, `schema_path`, `pdf_dir`, and `output_dir` blank so the operator can choose them per run.

Outputs:

- one run bundle under `{output_dir}/{run_id}/`
- proposal, evidence, review, summary, diagnostic, and export artifacts
- an exported workbook copy only after explicit accepted decisions
- audit artifacts explaining what was proposed, decided, and exported

## 4. Run Modes

### 4.1 Normal Browser Review

The default workflow:

1. operator starts the local app
2. operator chooses or confirms table, schema, PDF, and output paths
3. preflight resolves inputs and checks readiness
4. extraction starts only if readiness passes
5. operator reviews proposals in the browser
6. operator accepts, edits, rejects, or confirms no data
7. export writes a new workbook and audit artifacts

### 4.2 Verify Mode

Verify mode supports reviewer comparison on already-filled cells. It must preserve explicit run-mode truth and must not blur into normal extraction.

### 4.3 Eval Mode

Eval mode is for leakage-aware benchmark runs. It must use an app-owned masked working copy for target cells and preserve gold/masked provenance in the run bundle. Gold target values must not be exposed to extraction prompts.

### 4.4 Headless / Agent Mode

Headless mode is a stable non-UI automation path. It must:

- run extraction from terminal inputs
- return machine-readable status
- write the same run-bundle contract as browser mode
- reject unattended export when reviewable proposals remain pending unless the caller passes explicit `--accept-all`
- record `automation_accept_all` decisions when `--accept-all` is used

Headless auto-accept is additive. It must not silently change the default human-review workflow.

## 5. Backend Pipeline Phases

The backend extraction pipeline is phase-separated:

1. resolve config and selected paths
2. preflight provider, input, parser, and output readiness
3. initialize provider capabilities and model residency, including structured-output negotiation
4. create the run bundle skeleton, input snapshots, config snapshot, early summaries, and diagnostics directories
5. load table and schema, classify target-cell eligibility, and create eval-mode gold/masked snapshots when needed
6. parse PDFs into normalized documents, page images, figures, captions, and diagnostics
7. match PDFs to table rows and stage unmatched PDF rows when allowed
8. generate style profiles once per column when enabled and filled cells exist, otherwise use heuristic or schema-only guidance
9. build or load a per-paper prepared retrieval index and retrieve text, table, caption, and figure-level evidence for each eligible target cell
10. produce text-model proposals through the provider adapter
11. run at most one selective recall-rescue pass when enabled and evidence-quality signals justify it
12. run optional targeted figure review for cells whose evidence triggers vision review
13. run at most one candidate-selection call when competing or weak candidates require adjudication
14. merge, normalize, validate, and filter proposal candidates deterministically
15. persist one best proposal per cell with evidence, diagnostics, and provider metadata
16. write final summaries, provider diagnostics, reviewer summaries, artifact inventory, and model cleanup results

The optimizer must not start eval until the candidate extraction run has completed proposal production, written final summaries, and left the run bundle readable from disk.

## 6. Row And PDF Matching

Each PDF is matched to at most one row.

Matching is a distinct stage before proposal generation. It uses extracted metadata and front-matter diagnostics, preserves candidate-score breakdowns, and surfaces unmatched, ambiguous, and duplicate-row cases explicitly.

If a PDF does not match an existing row, the normal browser workflow stages a new row from extracted paper metadata when available and generates proposals for schema-defined target cells. Ambiguous and duplicate-row conflicts remain blocked or diagnostic rather than silently coerced.

Metadata extraction has its own lane. Parser-first metadata truth, ambiguity, source, and failure attribution must remain visible in matching artifacts and downstream summaries.

## 7. Retrieval And Extraction

Extraction is schema-first. Column name, description, optional type metadata, row context, and paper metadata define what reported information should be extracted.

Current defaults:

- retrieval mode: `hybrid_experimental`
- retrieval top-k: `12`
- recall rescue: disabled by default
- whole-document mode: disabled by default
- default text model in config example: `google/gemma-4-e4b`

Retrieval should remain row-aware and column-aware rather than defaulting to whole-document prompts. Whole-document and recall-rescue paths are bounded configured modes and must remain explicit in artifacts.

Retrieval persists a prepared per-paper/per-run index under `retrieval/_indexes/` and reuses it across cells with the same document, retrieval mode, caption/table inclusion policy, and typed scoring context. Each prepared index carries schema version, document fingerprint, PDF id, retrieval mode, caption/table policy, typed scoring context, source-grounded chunks, candidate chunks, chunk counts, and lexical scoring metadata. Disk loads must reject mismatched document fingerprints, mode, inclusion policy, or typed scoring context and rebuild rather than silently using stale indexes. Per-cell and per-run diagnostics report whether the index source was `built`, `disk`, or `memory`, along with index path, schema tag, load/build time, and load error if a stale or invalid index was ignored.

Retrieval chunks keep separate source-preserving `display_text` and contextual `retrieval_text`. Current retrieval scoring text canonically prepends conservative typed markers for chunk type, section context, existing figure references, and table-region status. Page-number tokens are deliberately excluded from scoring text. Extraction prompt passage headers may also expose typed orientation metadata such as section, figure reference, and table marker while the passage body remains source text that reviewers can audit. This typed scoring behavior is part of the main app, not an operator config flag.

After lexical or hybrid scoring and before top-k selection, current retrieval applies a canonical evidence-aware reranking pass. The reranker is additive and deterministic: numeric-looking queries receive small boosts for answer-like numeric text and table chunks, visual/figure/panel queries receive small boosts for caption or figure chunks, identifier/name-like queries receive small boosts for acronym, hyphenated, or digit-bearing source identifiers, and broad abstract/section chunks receive a small demotion. This is main-app behavior, not a durable operator config flag. Retrieval policy and run stats expose `rerank_profile=evidence_aware_v1`, rerank time, and the count of changed top-k positions so optimizer reports can separate retrieval behavior from model behavior.

The app persists one best proposal per eligible target cell. It should prefer `proposal_status=unresolved` over weak guessing when current-paper evidence is not strong enough.

Style profiles may improve output format from existing filled cells, but they are formatting aids, not semantic labels or hidden row-level answer leakage. Eval mode must avoid target-answer leakage.

## 8. Provider Policy And Structured Output

The default live local provider path is LM Studio.

- Config token: `lm_studio`
- Operator label: `LM Studio`
- Locality: `local` unless configured otherwise

Provider readiness must distinguish provider reachability, model availability, model load failures, negotiated structured-output mode, degraded fallback, extraction-contract validity, and model-management diagnostics.

The bounded structured-output recovery ladder is:

1. `json_schema`
2. `json_object`
3. prompt-only JSON with app-side parsing when explicitly allowed

Prompt-only fallback is degraded and must be recorded as such. If no compatible validated path exists, the run must fail or emit explicit cell-level failures rather than silently treating unstructured output as successful.

LM Studio is treated as one shared local server unless configured otherwise. Load, unload, structured-output probes, text completions, vision completions, and eval judge completions acquire the shared lock by default. Timeout, lock, model-management, and classified operational failure diagnostics must be persisted.

Operational failure classifications should distinguish client disconnect, channel error, model-load canceled, timeout, model unavailable, and load/unload conflict-like failures when observable.

## 9. Figure Review And Candidate Selection

The main path is text/table/caption extraction. Vision is optional supplemental evidence.

Figure review requirements:

- persisted retrieval figure chunks are whole-figure chunks only
- vision is targeted and evidence-gated, not blanket page analysis
- direct figure context alone is not enough to call vision when strong non-visual text evidence exists
- the app may inspect a crop, full-page fallback, or planner-preferred full page
- prompt-only vision responses may be repaired for recoverable schema issues
- a figure response proposing a value must place the extracted answer in `proposed_value`
- diagnostics record actual calls, retries, image source, fallback reason, repair status, failure/suppression reason, no-hit outcomes, dropped result states, accepted figure hits, planner skip reasons, and per-run ROI rollups

Candidate selection is optional and bounded to one selector call per cell by default. Candidate sources are generic: first-pass text, rescued text, evidence recovery, and figure review. Figure candidates may support or compete with text candidates, but must directly answer the cell request before overriding strong text evidence. If text and figure conflict without a clear winner, selection should keep stronger text evidence or return unresolved.

## 10. Review And Export Semantics

Valid explicit review outcomes:

- accepted
- accepted with edit
- confirmed no data
- rejected

Decision sources for new artifacts:

- `human_individual`
- `human_bulk_accept`
- `automation_accept_all`

Legacy `human_reviewer` remains readable for backward compatibility.

The default browser review viewport is a compact review bar plus three-panel workspace: proposal queue, proposal detail/decision controls, and evidence/PDF inspection. Diagnostics are secondary and opened intentionally.

Export writes a new workbook and audit artifacts. Export includes only accepted and accepted-with-edit changes. The source workbook is never mutated in place.

## 11. Run Bundle And Shared Contracts

The run bundle rooted at `{output_dir}/{run_id}/` is the stable artifact contract consumed from files alone.

Current canonical artifact tags:

- `run.json.artifact_schema_version`: `main_run_bundle`
- evidence records' `evidence_schema_version`: `main_evidence`

These are stable current-contract identifiers, not semver-style compatibility channels. Active producers must write the canonical tags. Active consumers and verification tools must reject missing, old `.v2`, or unknown artifact tags clearly instead of accepting legacy bundles by default.

Stable categories include:

- inputs
- style profiles
- parsed artifacts
- matching artifacts
- retrieval artifacts
- proposals
- evidence
- review decisions
- summaries
- diagnostics
- exports

Stable join identity:

- `row_id`
- `column_name`
- `cell_id`

Proposal/evidence semantics are canonical-only: `proposal_status`, `evidence_status`, derived/validated `review_bucket`, and `reason_codes`. Legacy persisted `state` and `support` fields are not part of new proposal records.

Machine-readable schemas live under `specs/contracts/schemas/` and are consumed by:

```bash
python scripts/papers_to_table.py verify-contract --run /abs/path/to/run_bundle
```

### 11.1 Portable Agent-Kit Review Contract

The portable agent kit owns a separate authoring contract for external agents. One task uses `OUTPUT_DIR`, with final CSVs at its root and run provenance under `OUTPUT_DIR/runs/RUN_ID/`. The only authored control artifact is `RUN_DIR/extraction/review_input.json`; it references PDFs, source tables, and schemas by path instead of copying them into the run.

The default build writes:

- `OUTPUT_DIR/<requested_or_dataset>_filled.csv`
- `RUN_DIR/extraction/proposals.jsonl`
- `RUN_DIR/extraction/evidence.jsonl`
- `RUN_DIR/extraction/validation_report.json`
- `RUN_DIR/extraction/extraction_summary.json`

The filled CSV is agent-extracted and not human-reviewed. Before handoff, `finalize_extraction_handoff.py` must validate required artifacts and provenance warnings. The agent then asks exactly whether the user wants browser review. Review is optional and must not be built or served before opt-in.

When requested, `launch_review_servers.py` builds `RUN_DIR/human_review/`, starts and probes detached localhost servers, and returns exact URLs ending in `/human_review/index.html`. Applied decisions write `OUTPUT_DIR/<stem>_reviewed.csv`; only accepted and accepted-with-edit values populate that file.

`review_input.json` uses `papers_to_table.review_input.v1`. `proposal_id`, `evidence_id`, `cell_id`, and `created_at` are optional authoring fields. When absent, `build_review_package.py` generates stable deterministic IDs; when present, validation checks uniqueness and references.

Every non-empty proposed value must carry at least one structured Tier A/B/C evidence record and a concise value-specific rationale. Strong direct evidence requires `pdf_id`, `page_number`, and quote/table/caption/evidence text, exact/approximate bbox regions, or `figure_ref` plus `caption_text`. Page-plus-reasoning evidence remains reviewable but is visibly labeled weak/attention. Region-bearing evidence must validate finite numeric coordinates, positive pages, nonzero area, normalized-coordinate ranges when applicable, and emit warnings for ambiguous coordinate conventions. Generic rationales and unjustified evidence reuse are handoff-blocking provenance warnings.

The kit's generated evidence stream uses the canonical `main_evidence` tag plus main-compatible `source_type` values so downstream audit tooling can reuse evidence semantics. Kit-specific text evidence kinds are preserved separately in `authored_evidence_kind`. The generated bundle is not a main-app run bundle unless an optional later `main_compat/` export is explicitly generated and validated.

## 12. Eval Companion

Eval is CLI-first and file-driven. It reads run bundles or external filled tables, scores against gold data, keeps correctness and evidence metrics separate, preserves dual-judge details, and writes stable output artifacts under the caller's output directory.

Eval phases:

1. load and validate run bundle or external table plus gold data
2. join proposals to gold cells by stable row and column identity
3. resolve canonical field types from proposal metadata, eval schema, or inference
4. score structured fields and explicit deterministic text overrides
5. record structured deterministic failure diagnostics without changing structured correctness
6. collect judge-backed text cells, including normalized exact matches by default
7. execute judging in judge-major batches grouped by judge label, provider, model, and settings
8. merge per-judge verdicts back into scored cells
9. aggregate metrics, evidence audits, comparison rows, and output artifacts

Dual-judge runs must preserve per-judge verdicts and disagreement metrics instead of collapsing uncertainty away.

Eval accepts canonical field types `boolean`, `categorical`, `numeric`, and `text`, with aliases such as `bool`, `enum`, `number`, and `free_text`. Unknown field types fail early. Inference prioritizes allowed values, then numeric parsing, then clear boolean vocabulary; bare `0`/`1` numeric pairs must not infer boolean. Structured fields remain deterministic-only, but scored structured cells preserve `deterministic_failure_kind` and `adjudication_eligible` diagnostics plus aggregate structured-failure counts. Structured LLM adjudication is deferred unless normal eval diagnostics show that likely deterministic false negatives materially affect benchmark interpretation.

Eval join diagnostics distinguish true target-cell join failures from proposals for intentionally excluded metadata columns. A proposal for a schema-excluded or otherwise unscored column is emitted as `excluded_proposal`, counted in `excluded_proposal_count`, and listed in `excluded_proposal_diagnostics`; it must not increment `join_failure_count` or true `unmatched_proposal_count`. Non-excluded proposals without matching gold cells remain `unmatched_proposal` join failures.

## 13. Optimizer Companion

Optimizer is orchestration-only. It loads explicit candidate bundles and search spaces, launches main-app and eval runs, distinguishes compare and optimize workflows, and reports raw winners separately from recommended defaults when trust caveats differ.

Canonical execution is:

```text
candidate x suite x benchmark x replicate
```

One-benchmark suites are supported. `smoke`, `dev`, and `holdout` are convenience aliases that resolve into explicit suites.

Optimizer phases:

1. resolve study preset, suite, benchmarks, replicates, candidates, and search space
2. materialize candidate bundle and resolved app config overlay
3. launch main app in headless/eval mode
4. validate completed run-bundle artifacts
5. launch eval against the completed run bundle
6. validate eval summary artifacts
7. write candidate result rows
8. aggregate replicate, benchmark, suite, and study summaries
9. rank raw winners, apply trust caveats, and write reports, plots, and recommendation metadata

Optimizer is sequential by default. Future parallel mode must be explicit and preserve local provider locking and model-residency safety.

Canonical model comparisons score completed external-agent tables plus gold-derived positive and negative controls through the same Eval path as local candidates. External systems and controls remain visible in comparison rows and replicate distributions but are excluded from winner selection, recommended-default rationale, and benchmark-best plots. Replicate-distribution boxplots show each candidate mean as a compact numeric label above that candidate's highest plotted observation, with enough automatic y-axis headroom to avoid clipping. For the bounded `content_correctness`/`correctness` replicate distribution, the report boxplot uses a lower y-axis bound of zero while retaining automatic upper scaling.


## 14. Benchmark Datasets

The current curated benchmark suite lives at repository root under `benchmark_datasets/`.

Active datasets:

- `massively_parallel_reporter_assays`
- `genome_editing_tools`
- `spatial_transcriptomics`

Each active dataset exposes app-facing inputs through `table_template.csv`, `schema.csv`, source PDFs under `pdfs/`, and human-curated answers in `table_gold.csv`.

Benchmark correctness is agreement under the current Eval rubric with the human-curated gold data, not a literal percentage of objectively true and false values. Some current fields are objectively recoverable, while interpretive fields such as a paper's main finding may allow multiple reasonable answers and can impose an effective score ceiling below 100% for realistic systems. The gold positive control reaches 100% by construction. Consistently evaluated comparisons remain useful, but reports and documentation must qualify absolute score interpretation and surface judge disagreement and per-cell diagnostics. Future benchmark revisions should prefer objectively verifiable tasks and use tighter rubrics or explicit acceptable-answer sets where interpretation cannot be eliminated.

External comparison outputs and gold-derived control tables live under `benchmark_datasets/data/`. The canonical controls include the gold positive control, a weak within-cell word-order shuffle, and a strong cross-field value derangement. Negative controls preserve headers, row identity, metadata, and the target blank/non-empty mask; their checked-in tables are generated deterministically from the active templates and gold tables, with source hashes, seeds, and change counts recorded in generation manifests. Failed external workflow attempts without complete filled tables may be documented, but they must not be assigned fabricated scores or registered as scored external results.

## 15. Command Surface

Primary wrapper commands:

- `python scripts/papers_to_table.py install`
- `python scripts/papers_to_table.py review`
- `python scripts/papers_to_table.py preflight --config app/config.json`
- `python scripts/papers_to_table.py headless --config app/config.json --accept-all --export`
- `python scripts/papers_to_table.py verify-contract --run /abs/path/to/run_bundle`
- `python scripts/papers_to_table.py eval --run /abs/run --gold /abs/gold.csv --schema /abs/schema.json --out /abs/eval_out`
- `python scripts/papers_to_table.py optimizer compare-models`
- `python scripts/papers_to_table.py optimizer compare-models --initial-model MODEL_ID`
- `python scripts/papers_to_table.py optimizer dev-check`
- `python scripts/papers_to_table.py optimizer full-benchmark`
- `python scripts/papers_to_table.py optimizer full-benchmark --initial-model MODEL_ID`
- `python scripts/papers_to_table.py docs serve`
- `python scripts/papers_to_table.py docs build`

Optimizer wrapper commands support `--label` where applicable. `dev-check` defaults to `google/gemma-4-e4b` on `bench_genome_editing`.

## 16. Diagnostics And Failure Truth

The system must remain truthful about:

- input and output path readiness
- parser availability and fallback
- provider reachability and model availability
- structured-output mode and degraded fallback
- row/PDF matching ambiguity
- metadata extraction failures
- evidence weakness and fallback anchors
- retrieval typed scoring, reranking, prepared-index reuse, and changed top-k diagnostics
- recall rescue and whole-document eligibility, use, and skips
- figure planner and figure-review attempts, suppression, failures, repairs, and no-hit outcomes
- candidate-selection attempts and value changes
- headless auto-accepted decisions
- LM Studio lock waits, timeouts, channel errors, client disconnects, and model-load cancellation
- eval judge failures and disagreements
- optimizer low-replicate, degraded-score, unscored, failed, or trust-caveated outcomes

Silent fallback to demo, stub, disabled, or misleadingly successful behavior is not acceptable.

## 17. Documentation And Maintenance Surface

Active current truth lives in:

- `specs/README.md`
- `specs/spec.md`
- `specs/architecture.md`
- `specs/contracts.md`
- `specs/ui-review-workflow.md`
- `specs/eval-and-optimizer.md`
- `specs/decisions.md`
- `specs/improvement-ideas.md`
- `specs/experiment-results.md`
- `specs/plan.md`
- `specs/tasks.md`
- `specs/contracts/schemas/*.json`

`README.md` is the concise repository entry point. `docs/` is the operator/developer manual. `skills/` contains reusable external agent procedures.

Original project software and documentation are distributed under the Apache
License 2.0, with attribution recorded in the root `NOTICE`. Dependency
licenses and rights in bundled vendor assets, scientific papers, benchmark
source PDFs, datasets, models, and other third-party material remain separate
and are not overridden by the project license.

The manual is generated with MkDocs Material. Local preview and build remain
available through the repository wrapper commands. The root
`.readthedocs.yaml` is the canonical hosted-build configuration: it uses the
MkDocs configuration at `tools/docs/mkdocs.yml`, installs the pinned docs-only
dependencies from `tools/docs/requirements.txt`, and targets Read the Docs
Community after the repository becomes public. A private repository is not an
assumed Community build path; hosting it directly requires Read the Docs
Business or another private-repository-capable host.

Archive material under `specs/archive/` is historical only. Current behavior must not require archive files.

Drift-prevention rules:

- update `spec.md` and the focused owner when substantial behavior, architecture, workflow, config, artifact, provider, UI, eval, optimizer, or CLI behavior changes
- update JSON schemas when machine-readable contract requirements change
- update README/docs/tests/screenshots in the same pass when their truth changes
- do not fix drift by duplicating the same statement across many files
- promote durable truth into the owning canonical spec, replace stale references, and archive obsolete duplicates
