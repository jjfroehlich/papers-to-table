# Paper Table Agent — `plan.md`

## Status

Updated: evidence-first, proactive figure review, separate text/vision model direction

## Purpose

This document defines the technical approach for implementing the product requirements in `spec.md`.

It is the technical counterpart to the product specification:

- `spec.md` defines **what** the product must do and **why**.
- `plan.md` defines **how** the system will satisfy those requirements.
- `research.md` holds supporting detail that should not overload either the product spec or this plan.

This plan is intentionally opinionated. It chooses a concrete MVP architecture so implementation can proceed without drifting into a general-purpose RAG platform, a chat product, or an overcomplicated agent framework.

---

## Relationship to other documents

- `spec.md` is the source of truth for user-facing requirements and acceptance criteria.
- `research.md` records the research and tradeoffs behind the decisions in this plan.

The core documentation set for this phase is `spec.md`, `plan.md`, and `research.md`. `tasks.md` becomes useful when implementation starts, and optional ADRs or runbooks should be added only if a concrete decision or operator workflow needs them.

## Implementation handoff rules

The intended implementation model for this repository is:

- `tasks.md` remains exhaustive, but execution should happen in the explicit batches defined there rather than as one giant undifferentiated pass.
- Each batch should be delivered as a polished, coherent slice that a later batch can safely build on.
- The JSON config file remains authoritative for advanced behavior and reproducibility.
- The browser UI owns the normal operator workflow for launch, status visibility, review, and export.
- The local onboarding path should stay clear and singular: start backend, start frontend, open the browser UI, supply a config path, start the run.
- Treat `README.md`, the checked-in config example, the runtime config schema, and operator-visible UI copy as one operator-facing contract. Keep provider, parser, model, Verify-mode, and run-state terminology aligned across those surfaces.
- Do not let early batches stop at a structurally correct shell. Provider-path scaffolding, placeholder proposal generation, or silent degraded modes do not count as a finished slice.
- If a batch changes operator-facing truth, update `README.md`, `spec.md`, `plan.md`, and `tasks.md` together in the same work pass.
- End-of-batch documentation updates are mandatory for operator-facing changes; `README.md` must trail implementation by zero batches, not by a later cleanup pass.
- `README.md` and any other user-facing docs must only describe commands, config behavior, lifecycle states, review actions, downloads, exports, and limitations that exist in the implemented slice.
- When operator docs describe LM Studio setup, include at least one verified model example while keeping the implementation contract open to stronger or newer models that satisfy the same interface.

---

## Definition of done

Implementation for this phase is complete when the system satisfies the functional requirements and acceptance criteria in `spec.md` and the following technical outcomes are true:

1. A user can run an end-to-end workflow:
   - start a run from the UI using a config file
   - understand the first valid next step even when no run exists yet
   - see the run move through ready/validating/running/completed-or-failed states
   - see coarse running progress as current stage plus current item when available
   - understand why review is unavailable while a run is still validating, running, or failed
   - load table + schema + PDF folder
   - parse documents
   - match PDFs to rows
   - generate schema-driven proposals with evidence
   - review proposals in a dedicated UI
   - export an updated workbook and audit log

2. PDFs are normalized into one internal parsed-document contract that downstream systems use regardless of parser backend.

3. Evidence remains reviewable and auditable even when retrieval uses contextualized text.

4. Run artifacts, proposal state, review decisions, and exports are persisted in a reproducible local-first manner.

5. The implementation supports structured-output-first extraction with graceful downgrade when providers lack strong schema support.

6. Diagnostics explain failures and low-quality results without requiring developers to inspect raw prompts manually.

7. Verify mode works end-to-end:
   - proposes values for already-filled cells
   - exposes them in review
   - allows reviewed export changes
   - produces reviewer-outcome summaries automatically

8. The first shipping system remains focused on the paper-to-table review workflow and does not expand into a chat-first, multi-user, or SaaS platform.

9. The documented local startup path, browser-first operator workflow, and artifact/export behavior remain truthful and usable rather than drifting behind the implementation.

10. The shipped `README.md` and operator-facing documentation truthfully match the implemented app:
   - real startup commands
   - real config preparation and launch flow
   - real run lifecycle and review flow
   - real artifact, export, and download behavior
   - real limitations and unsupported cases
   - no speculative helpers or unimplemented workflows

11. The canonical provider contract is stable across runtime validation, config examples, tests, README/docs, and operator-visible UI labels, with unknown provider identifiers rejected explicitly.

12. Run-start preflight checks catch invalid provider config, provider unreachable state, model unavailable state, missing parser or OCR dependencies, and other broken local setup conditions before the operator waits through a misleading run.

13. The canonical LM Studio live path is proven on the checked-in canonical fixture set by producing at least one non-empty proposal with reviewer-usable evidence, or the app fails early with a clear readiness error instead of looking nominally complete.

14. Run artifacts and run summaries record whether proposal generation was live local, live cloud, unavailable, disabled, or explicitly degraded/demo, and the UI reports that state truthfully.

---

## Constraints and non-goals

### Constraints

- Local-first operation in this phase.
- Single-user local browser app operation is sufficient for MVP.
- Human review is required before spreadsheet updates.
- UI remains minimal and task-focused, but not thin to the point that startup, lifecycle visibility, or review/export workflow becomes guesswork.
- The UI must behave as a reviewer-centered scientific curation workstation where the reviewer is judging what the paper supports, not grading model output.
- The product must preserve one primary local onboarding/start path instead of expecting users to infer a preferred route from multiple equivalent but differently documented commands.
- Pipeline must preserve auditable run artifacts.
- Parser, model, and retrieval backends must remain replaceable behind stable contracts.
- Provider/model behavior must be transparent enough for users to know whether a run stayed local or used cloud services.
- Provider config examples must not require committed cloud secrets; optional cloud providers should rely on environment or secret references.
- Setup should remain config-authoritative but picker-driven for normal browser use rather than path-heavy.

### Non-goals

- No hosted backend or SaaS deployment in this phase.
- No multi-user collaboration workflow in v1.
- No broad chat-oriented document assistant features.
- No graph-first orchestration unless the workflow later clearly requires it.
- No giant user-facing config surface.
- No assumption that more fallback layers automatically improve the product.

---

## Technical decisions and rationale

### TD-1: The product is a workflow application, not a general RAG chat app

The system will be implemented as a focused workflow service plus review UI, not as a conversational RAG product.

**Rationale:**
The core user journey is table ingestion, proposal generation, review, and audited export. A chat-centric architecture would add surface area without helping the main task.

---

### TD-2: Use a deterministic staged runner, not graph-first orchestration

The initial system will use a mostly deterministic staged pipeline with a few LLM-assisted steps:

- paper metadata extraction
- ambiguous row adjudication
- schema-driven proposal extraction
- optional evidence recovery
- optional figure fallback

**Rationale:**
The workflow is structured and auditable. The prior implementation showed that graph orchestration added less value than expected around a mostly sequential loop. The rewrite should stay simple for MVP: one run executes straight through, and an interrupted run is restarted as a new run rather than resumed in place.

**Operator consequence:**
Runs are launched from the UI and executed under app-owned backend control using a lightweight in-process background mechanism for MVP; no external job framework is required.

---

### TD-3: Use one main parser first, with a stable parser contract

All parser outputs must normalize into a shared `ParsedDocument` contract, but the shipping MVP should begin with one main parser rather than a multi-parser runtime.

**Rationale:**
Parser abstraction is valuable; multi-parser runtime complexity is not justified as a baseline. The parser contract prevents lock-in while preserving a simpler default path.

---

### TD-4: Parser baseline is Docling + PDFium via pypdfium2

The primary ingestion stack for MVP will be:

- **Docling** as the main parser
- **PDFium via pypdfium2** as the low-level PDF backend for rendering, crop extraction, text search, and evidence anchoring
- a small internal abstraction layer that isolates backend-specific code

**Rationale:**
Docling is currently the strongest main parser candidate for structured scientific PDF parsing, layout awareness, figure handling, and table support. PDFium provides a strong low-level foundation for page rendering, geometry, and evidence display with a more favorable licensing posture than MuPDF/PyMuPDF.

**Note:**
GROBID remains an optional later enrichment path if measured lift justifies it.

**Parser-truth requirement:**
Runtime behavior must make parser selection explicit. The run contract should record the configured parser choice and the actual parser used. Silent substitution from a configured parser to another parser is not the baseline behavior; any fallback parser path must be explicitly enabled and surfaced in readiness results, run artifacts, and summaries.

---

### TD-5: Filesystem artifact bundles are the canonical MVP state

The system will use:

- per-run artifact folders in the output directory as the canonical run record
- JSON files inside each run bundle for proposals, explicit review-decision records, diagnostics, summaries, and export bookkeeping

**Rationale:**
For a local-first, single-user MVP, artifact bundles are simpler, easier to inspect, and easier to debug than introducing a database. This keeps state reproducible without adding operational complexity that the product does not yet need.

---

### TD-6: Export generates a new workbook, not an in-place workbook patch

The system will export a new updated workbook plus audit log rather than mutating arbitrary workbooks in place.

**Rationale:**
Workbook fidelity is difficult to guarantee across complex Excel features. A generated export is safer, easier to validate, and more auditable.

**Implementation direction:**
Use `openpyxl` as the main XLSX round-trip engine. Guarantee content-only fidelity plus changed-cell highlighting. Do not promise preservation of workbook behavior or advanced sheet structure.

---

### TD-7: Use one typed provider abstraction, structured outputs first, with LM Studio localhost API as the default live path, and separate text-model and vision-model configuration

LLM interaction will be schema-first using typed contracts. The initial supported live provider path is LM Studio via its localhost API, with each cell request returning structured JSON plus page-grounded evidence. Optional cloud providers can be added later behind the same contract without changing the operator workflow or broadening the UI into a settings editor.

The provider configuration must support separate model identifiers for text extraction and vision extraction. The text model and vision model may differ: local deployments often have separate chat and vision endpoints, and operators should be able to configure each independently.

When both a text model and a vision model are used in a run, the run summary and reviewer-visible context must identify both models separately so the reviewer understands what capability extracted what.

**Rationale:**
The extraction path depends on predictable proposal and evidence objects. Separating text and vision model identifiers improves flexibility (the best text model and the best vision model are often not the same), supports running without vision capability when no vision model is configured, and gives reviewers transparent context about what generated each evidence type.

**Contract policy:**
- the canonical LM Studio config token is `lm_studio`
- the canonical LM Studio operator-visible label is `LM Studio`
- provider identifiers come from one canonical enum or equivalent central registry
- provider config carries separate model identifier fields for text extraction and for vision extraction
- compatibility aliases, if any, must normalize into canonical stored values and stay documented in one place
- unknown provider identifiers fail early
- cloud-provider credentials are resolved from environment or secret references, not committed example secrets
- stub/demo/degraded provider modes must be explicit, never silent

---

### TD-8: Review requires a dedicated queue-first local browser app

The review product surface will be a dedicated Run/Review application delivered as a local browser app, not a notebook or chat interface. Tauri is only a possible future packaging option, not an MVP shell requirement.

**Rationale:**
The main value of the product is human verification of proposed spreadsheet updates with visible evidence.

**Interaction model:**
Queue/list of proposals + focused detail pane + custom PDF.js evidence viewer, with visible run/reviewer summary context in the main review workspace.

The same UI must also provide:
- a small run launcher centered on config-file path entry or selection
- a clear run setup summary derived from the resolved config snapshot
- visible lifecycle status and actionable failure messaging before review begins
- explicit pre-review empty/loading/warning states that tell the operator what to do next
- unresolved-match inspection that keeps PDF names and rationales visible without forcing the operator into raw artifact files

When switching runs, the UI may preserve the active queue filter, but proposal selection, proposal detail, and evidence-viewer state must always be refreshed for the currently loaded run.

---

### TD-9: MVP evaluation is reviewer-outcome-based

The MVP will evaluate performance primarily through reviewer outcomes rather than an automated correctness score across heterogeneous field types.

**Rationale:**
The product already requires human review. Reviewer decisions are the most trustworthy MVP measure of usefulness, while automated verify-mode scoring across mixed field types is still an open research problem.

---

### TD-10: Existing filled cells feed a preprocessing LLM that produces structured style profiles

Existing filled cells should be processed per column through a preprocessing LLM that generates a structured style/format profile. That profile may guide output shape, tone, and detail level, but raw filled cells must not be passed as semantic few-shot exemplars to extraction prompts by default.

**Rationale:**
This keeps the benefit of column-specific output shaping while avoiding heuristic-only format inference and avoiding direct semantic anchoring to historical cell content.

---

### TD-11: Figure review is proactive and targeted when vision capability is available

When vision capability is available (a vision model is configured), the system must review all relevant extracted figures as a normal supplemental evidence stage, not only when text extraction has already failed.

Proactive figure review allows the system to:
- provide figure evidence that strengthens or corroborates text-derived proposals
- supplement weak or ambiguous text proposals with figure evidence
- rescue weak, unclear, or failed text-only proposals when figure evidence is available

Figure evidence must be allowed to support any field type when it materially strengthens the answer. The system must not restrict figure evidence to fields explicitly classified as figure-derived.

The distinction between proactive figure review and unrestricted full-page multimodal reasoning is important:
- proactive figure review: all relevant extracted figures are reviewed as a supplemental evidence stage
- unrestricted full-page reasoning: every page of every paper is sent to a vision model for every field

The second is explicitly out of scope. The first is required when vision capability is available.

**Rationale:**
The prior narrow-fallback design meant figures were only consulted when text had already failed. But figures often contain complementary information that strengthens text evidence, and a reviewer cannot benefit from figure evidence that was never collected. Proactive targeted figure review makes figure evidence available as a first-class evidential source while staying within a reasonable operational scope.

**Implementation direction:**
The figure review stage receives all figures extracted from the parsed document for the current paper. The stage should select relevant figures rather than processing every figure indiscriminately. Relevance can be determined by structural heuristics, captions, or an LLM-assisted selection step, as long as the scope remains targeted rather than blanket per-page vision.

---

## Alternatives considered

### A-1: Generic RAG/chat platform foundation

**Alternative:** Build on a generic RAG/chat platform and extend it.

**Rejected because:**
The review/export workflow would become an awkward extension rather than the product core.

---

### A-2: Multi-agent or graph-first orchestration first

**Alternative:** Use LangGraph or an equivalent orchestration layer as the center of the architecture.

**Rejected because:**
The initial workflow is mostly sequential and structured. Heavy orchestration would add complexity before it improves quality.

---

### A-3: Multi-parser runtime by default

**Alternative:** Use a parser matrix from day one.

**Rejected because:**
A clean parser abstraction is valuable, but baseline multi-parser runtime complexity is not yet justified.

---

### A-4: Database-first architecture

**Alternative:** Store all intermediate state only in a database.

**Rejected because:**
Filesystem artifacts are too important for reproducibility, debugging, and export packaging.

---

### A-5: In-place workbook editing

**Alternative:** Patch the original workbook directly.

**Rejected because:**
Workbook fidelity risks are too high for arbitrary real-world workbooks.

---

## Supporting notes

This plan depends on `research.md` for supporting tradeoffs and decisions. Additional implementation notes, runbooks, or a future task breakdown can be added later if they become useful. The operator-facing README should preserve both architecture truth and practical onboarding steps so a new user can install dependencies, configure LM Studio, run the app, and understand artifact/export boundaries without reconstructing that flow from source. Optional ADRs may still be useful for decisions that evolve, especially:
  - low-level PDF backend
  - runtime/background jobs
  - workbook fidelity policy
  - UI stack

The stable run, provider, review, and export surfaces may later support richer APIs, MCP-style integrations, or larger agentic systems, but that is a later extension. The current MVP requirement is a truthful, working local-first app with one real proposal-generation happy path.

Implementation should normally proceed batch-by-batch according to `tasks.md`. The detailed task list remains exhaustive, but the practical implementation unit is a coherent batch with its own verification and doc-sync expectations.

---

## System architecture overview

## High-level architecture

The system will consist of five major layers:

1. **Local web frontend UI**
   - local browser app
   - Run and Review views
   - queue-first proposal review
   - PDF/page/figure evidence display

2. **API and application service layer**
   - receives UI requests
   - creates runs
   - exposes run/proposal/review/export data
   - serves artifacts and document views

3. **Pipeline runner and lightweight run-execution layer**
   - executes parse/match/extract/evidence/export stages
   - writes checkpoints and artifacts
   - updates run/proposal state

4. **Parsing/retrieval/extraction layer**
   - parser adapters
   - low-level PDF rendering/anchoring
   - retrieval/indexing
   - extraction and figure fallback

5. **Persistence layer**
   - filesystem run artifacts
   - JSON state files within each run bundle

---

## MVP implementation stack

The MVP implementation stack is best understood in two layers.

### Core MVP architecture

- **Frontend UI**: React local browser app
- **Backend API**: small Python FastAPI service
- **PDF ingestion/parser**: Docling
- **Low-level PDF rendering/geometry**: PDFium via `pypdfium2`
- **PDF review viewer**: raw/custom PDF.js viewer with app-owned evidence/highlight overlays
- **LLM provider (MVP default)**: LM Studio localhost API
- **Persistence**: filesystem artifact bundles + JSON files only
- **Spreadsheet export**: `openpyxl`
- **OCR fallback**: OCR fallback path enabled for scanned/text-inaccessible PDFs
- **No database in MVP**
- **No desktop wrapper in MVP**
- **No background job framework by default in MVP**

### Practical default implementation choices

- **Frontend language/build**: TypeScript + Vite
- **UI components/layout**: app-owned React components plus repository-local CSS
- **Review queue/list**: app-owned queue/list-detail components; virtualization is optional only if measured proposal volume demands it

This section is intentionally explicit so the MVP does not drift back toward Tauri, SQLite, Huey, or other optional components as baseline requirements.

---

## One-config-file control model

The MVP uses a single JSON config file as the main control surface.

This config file is the source of truth for:

- inputs
- parser settings
- matching settings
- style-profile preprocessing
- retrieval settings
- model/provider settings
- figure fallback settings
- review settings
- export settings

Provider settings should follow one typed schema that covers at least:

- canonical provider token
- provider locality (`local` or `cloud`)
- base URL or endpoint where relevant
- text and vision model identifiers where relevant
- timeout and structured-output capability settings where relevant
- credential environment-variable or secret references for cloud providers
- explicit disabled or stub/demo mode only when intentionally supported

The UI should not expose a large parameter-tuning surface in MVP. Advanced behavior is configured by editing the config file directly.

The UI should still expose enough config-derived context for safe operation: config path, resolved input locations, output location, Verify-mode status, and provider/model summary.

The UI may allow picker-driven overrides for relevant input paths, but those overrides should be treated as explicit run-input selections layered over the config rather than as a broad in-UI settings surface.

For MVP browser mode, picker behavior should rely on browser-compatible file or directory selection patterns rather than assuming a desktop shell or native OS dialog.

Because a pure browser client cannot be assumed to expose stable backend-visible native paths, picker-selected inputs should be materialized into backend-readable staged files or directories, or into another explicit app-owned server-side input handle, before validation and execution begin.

The resolved run context should preserve both the logical source of each input, such as config-declared path, typed backend path, or picker-staged override, and the backend-visible locator actually used at runtime.

This split is intentional: the config file owns advanced behavior and reproducibility, while the UI owns launch, status visibility, review, artifact access, and first-run usability.

The config file should be sufficient to reproduce a run together with the input files and output artifact bundle.

The config schema and checked-in example are not secondary docs. Runtime validation, persisted config snapshots, README terminology, and UI labels must all describe the same operator-facing settings. If a compatibility alias is supported, it should normalize into the same canonical stored value and appear consistently in docs and diagnostics.

---

## Pipeline stages

The MVP pipeline should run in these explicit stages:

1. **Load config and inputs**
   - read config
   - resolve defaults and persist a config snapshot early enough that readiness-failed runs still retain the resolved context
   - expose `ready` before starting, then `validating` while checking config and input readiness
   - validate canonical provider token and provider-config shape
   - run provider/model readiness checks when live proposal generation is configured
   - verify parser, OCR, and other required dependency availability for configured paths
   - verify output-path writability and other obvious broken-setup conditions
   - resolve relative paths, browser-selected inputs, and platform-specific path spellings into one explicit resolved run context
   - materialize picker-selected files or directories into backend-readable staged inputs or explicit server-side input handles rather than relying on browser-native absolute paths
   - load spreadsheet and schema
   - normalize BOM-marked or whitespace-padded headers in CSV or schema inputs before field validation
   - normalize workbook date and datetime cells into a stable internal representation that preserves their intended meaning
   - persist a resolved input summary before later stages can fail
   - validate required metadata columns
   - detect missing and already-filled cells
2. **Build per-column style profiles**
   - read existing filled cells per column
   - run a preprocessing LLM step per column
   - produce a structured style/format profile for each column
3. **Parse PDFs once**
   - parse each PDF with Docling
   - generate normalized parsed-document artifacts
   - generate page/crop artifacts needed for review and figure fallback
   - trigger OCR fallback only when PDF text is inaccessible or clearly insufficient
4. **Match PDFs to rows**
   - extract grounded publication metadata
   - run deterministic matching
   - run fallback adjudication only for plausible ambiguous cases
   - block ambiguous matches
   - block duplicate-row PDF conflicts
5. **Build retrieval artifacts**
   - generate typed chunks
   - generate contextualized retrieval text
   - generate table-aware retrieval units when available
6. **Extract proposals per target cell**
   - gather row context, column definition, style profile, and retrieved context
   - prompt the model once per target cell
   - require structured JSON output
   - store one best proposal per target cell
7. **Validate and recover evidence**
   - validate page-grounded evidence
   - run one narrow recovery step if evidence is missing/weak/unusable
   - preserve weak-but-reviewable proposals
8. **Review relevant figures as supplemental evidence when vision capability is available**
   - when a vision model is configured, review all relevant extracted figures for the current paper as a normal supplemental evidence stage
   - select relevant figures by structural heuristics, captions, or LLM-assisted selection rather than processing every figure indiscriminately
   - use crop + caption + nearby text + full page as the input package
   - figure evidence may strengthen text-derived proposals, supplement weak proposals, or rescue failed text-only proposals
   - figure evidence is allowed for any field type, not restricted to figure-classified fields
9. **Write proposal artifacts**
   - write proposals, evidence, diagnostics, and run summaries as JSON artifacts
   - record provider mode, readiness results, and any explicit degraded or disabled status in run artifacts and summaries
10. **Review in UI**
   - show resolved run setup context and direct access to config snapshot
   - keep the queue clearly non-actionable until the run is review-ready
   - queue-first review
   - record accept / accept-with-edit / confirm-no-data / reject / bulk-accept-visible-subset decisions
11. **Export**
   - generate new XLSX
   - apply accepted changes
   - highlight changed cells
   - write audit log
12. **Write reviewer-outcome summaries**
   - reviewed count
   - accepted-as-is
   - accepted-with-edit
   - confirmed-no-data
   - rejected
   - per-column breakdown

This explicit stage list is the canonical implementation sequence for MVP.

---

## Traceability from product requirements to implementation

This plan should remain easy to audit against `spec.md`. The main requirement group to implementation mapping is:

- **FR-1 to FR-4** → ingest, parse, match, retrieval, and extraction stages plus parser and provider contracts.
- **FR-5 to FR-8** → extraction contracts, evidence validation, rationale display, and figure-fallback routing.
- **FR-9 to FR-11** → queue-first review UI, review-state persistence, export engine, and audit-log generation.
- **FR-12 to FR-14** → run summaries, diagnostics, completion semantics, and warning states for empty or weak runs.
- **NFRs / trust requirements** → local-first architecture, filesystem artifact bundles, provider transparency, inspectable evidence, and deterministic testing strategy.

When implementation changes one side of this mapping, the corresponding section in `spec.md` or `plan.md` should be updated in the same work pass.

---

## UI architecture

## MVP interaction model

The review UI will use a **queue-first / list-detail** design with an explicit three-pane layout plus visible run/reviewer summary context. The design target is a reviewer-centered scientific curation workstation: the operator should be able to decide what the paper supports with minimal friction, not merely inspect model output.

### Layout roles

- **Left pane**: grouped review queue or sidebar used for triage
- **Center pane**: proposal detail and decision workflow
- **Right pane**: evidence viewer or PDF viewer
- **Summary/top context area**: run metrics, reviewer-outcome context, and direct artifact downloads
- **Top bar / queue controls**: grouping toggle, filters, saved-view or preset access, progress counters, and warning cues

The left pane remains triage-first, the middle pane remains decision-first, and the right pane remains evidence-first. A rebuild should not swap those responsibilities or blur them into one generic card grid.

### Run/setup surface

The run/setup tab should remain in the same app and should stay config-authoritative without feeling path-heavy.

It should present:
- config path and resolved run context
- picker-driven overrides for relevant input files or folders
- a compact target-columns preview that expands only on demand
- a concise action-oriented summary of whether the last run worked, what needs attention, and what the operator should do next

When picker-driven overrides are used, the run/setup surface should show both the logical override source and the backend-visible staged locator or server-side input handle actually used for execution.

For MVP browser mode, setup should rely on browser-compatible picker behavior first. Native OS dialogs are a future desktop-packaging concern, not part of the baseline UI contract.

### Shared UI state model

The client state architecture should explicitly track at least:
- selected run id
- sidebar grouping mode: `paper` or `column`
- queue filters
- saved view or preset selection when implemented
- collapsed or expanded group state
- selected proposal id
- active decision mode: inspect, accept, edit, confirm-no-data, reject
- edit buffer and active value-input target
- selected evidence item
- evidence-viewer focus state
- evidence-viewer zoom and pan state

When switching runs, the app may preserve filters, grouping mode, or saved-view selection when useful for triage continuity, but it must reset proposal selection, decision draft state, edit buffers, evidence selection, and viewer state so stale context does not leak across runs.

### Left pane: grouped triage sidebar

The sidebar must support two grouping modes:
- `Group by Paper`
- `Group by Column`

The grouping-mode toggle should live at the top of the sidebar and should update the queue projection without changing the underlying proposal records.

The grouped queue data structure should support:
- group header metadata such as paper name or column name
- per-group counts for total, pending, resolved, and manual-attention items
- per-group match warnings where relevant
- collapsible group sections when density benefits from collapse
- stable group ordering rules
- stable item ordering within groups

Group headers should surface at least the group label, total count, pending count, and any match-warning or manual-attention badge needed for triage.

Default group ordering should place groups with pending actionable items ahead of groups that are fully resolved or only manual-attention.

Within that priority bucket:
- column groups follow configured target-column order
- paper groups follow stable matched-row order when available, otherwise stable PDF-name order

The queue rendering should use compact grouped cards rather than tall repetitive cards.

Each compact queue card should expose only the high-value triage fields:
- target column
- triage-oriented status
- support or confidence level

Compact cards should also expose visually distinct markers for:
- review decision state
- evidence or support quality
- match outcome when relevant

Those distinctions must not collapse into one ambiguous badge.

The compact triage projection should use a strong scan marker such as a colored left border or equivalent indicator. At minimum:
- yellow = pending or undecided
- green = accepted
- red = needs manual entry or unresolved manual action

Queue density and fast scanning remain first-class. The sidebar should support both:
- rapid triage across many proposals
- deeper investigation through preserved filters, grouping, and saved views or presets

### Middle pane: detail and decision workflow

The middle pane is the primary decision surface and should include at least:
- explicit row context near the top
- target column definition
- current value block when Verify mode is active
- proposed value block
- concise support-state labeling
- short rationale summary by default
- expandable fuller rationale
- editable value input
- primary review actions

If rationale is delivered as markdown bullets, the middle pane should render it through a concise markdown renderer rather than flattening it into a paragraph blob.

The decision workflow must make no-value cases actionable. When there is no usable proposal value, the pane should still expose:
- an explicit edited-value entry path
- an explicit `Confirm No Data` path or equivalent

`Confirm No Data` is a review resolution meaning the reviewer believes the paper does not report the target value. The UI and persisted review state must keep that meaning distinct from rejecting a wrong or untrustworthy model output.

Non-accepted or manually resolved outcomes should carry a structured resolution reason so later summaries and diagnostics can distinguish at least:
- not reported in paper
- insufficient evidence
- model wrong
- needs manual entry

Accept-with-edit remains a first-class explicit workflow rather than a minor variant of acceptance.

### Right pane: evidence viewer and PDF interaction

The right pane should be built around a PDF evidence viewer with:
- zoom support
- pan support
- previous and next page navigation
- jump to page by number
- highlight overlay support when geometry is available
- approximate highlight fallback, labeled as approximate, when only parser geometry is available and page-text alignment failed
- quote-plus-page fallback, labeled as fallback text evidence, when no reliable geometry is available
- crop-first figure evidence with attached caption and full-page access
- figure-to-full-page context: figure evidence must be accessible both as a focused crop and as full page context

The viewer must stay synchronized with the currently selected evidence item. When the reviewer selects a different evidence item in the quote list, the viewer must scroll to and highlight that item. When evidence selection or zoom changes, the viewer must refocus stably rather than jumping arbitrarily.

Highlight overlays must come from actual page geometry derived from page-text alignment or parser coordinates. Approximate parser geometry should be labeled as approximate. If no reliable highlight geometry is available, the UI should explain that limitation rather than fabricating highlight boxes.

The evidence interaction model should support a click-to-populate flow: when the reviewer clicks selected quote text or a highlight-linked evidence element, the UI should be able to populate either the proposed-value input or the edited-value input, depending on the active editing state.

Populate-from-evidence should be a reviewer-assist staging action only. It should not auto-save, auto-accept, or silently record a decision.

Default populate behavior should replace the active input with normalized text from the explicitly clicked evidence span. Append behavior may exist only as a separate explicit action.

Automatic populate should apply only to textual evidence, including quote-plus-page text and figure-caption text, not to raw image crops with no textual payload.

If the reviewer has not explicitly selected multiple spans, the populate action should use only the clicked span rather than concatenating all visible evidence.

If populated text is obviously longer than the target field shape or violates known field-format guidance, the UI should stage it without silent truncation and require reviewer trimming or confirmation before save.

When no scoped evidence is available, the right pane should still present a useful fallback action such as opening the full PDF.

### Summary and download context

The main review workspace should expose:
- run-summary context
- reviewer-summary context
- direct access to workbook, audit-log, run-summary, and reviewer-summary downloads

When those files are not available yet, the workspace should say so explicitly instead of presenting them as ready downloads.

The unresolved-match area remains inspect-only in MVP. It is a visibility and diagnosis surface, not a corrective-action workspace.

If no verified cells have been reviewed yet, keep per-column verify coverage visible only as evidence-coverage context with explicit wording that reviewer outcomes are not yet meaningful.

### Actions and shortcut surfacing

The main review actions should be:
- accept
- accept with edit
- confirm no data
- reject
- next
- previous
- bulk accept visible subset

The top bar should show:
- total proposals
- reviewed proposals
- accepted as-is
- accepted with edit
- confirmed no-data outcomes when applicable
- rejected
- pending or undecided

The MVP should support:
- next/previous proposal navigation
- accept current proposal
- reject current proposal
- focus proposed-value edit control
- open or focus the evidence viewer

Keyboard shortcuts should be surfaced on the relevant controls through tooltips or equivalent inline affordances rather than being discoverable only in a distant legend.

## Bulk review behavior

The MVP should support bulk acceptance only for the currently visible filtered subset of undecided proposals.

Bulk acceptance should require explicit user confirmation.

A global “accept everything blindly” action should not be the default MVP behavior.

---

## API and service architecture

The FastAPI layer should expose a small stable set of application-facing endpoints such as:

- create/list/get runs
- get run summary
- list proposals with filters and enough compact triage fields to support grouped sidebar rendering by paper or column
- get proposal detail
- submit review decision, including edited values, confirm-no-data resolutions, and structured resolution reasons
- inspect unmatched/ambiguous PDFs
- request export
- fetch export bundle
- fetch direct run artifact downloads
- fetch reviewer-outcome summary
- fetch document pages/crops/highlights

The service layer should remain thin and should not duplicate pipeline logic. It should read and update per-run JSON artifacts rather than depending on a database.

---

## Pipeline architecture

## Guiding principle

The pipeline should be **stage-based and explicit**, with a clear default path and a small number of limited fallbacks.

The canonical stage list is defined in `## Pipeline stages` above. The sections that follow describe the main contracts and policies that each stage must obey.

---

## Parser strategy

## Objective

Create a robust scientific-PDF ingestion layer that preserves structure for retrieval while keeping enough source fidelity for evidence display and highlighting.

## Baseline parser stack

### Primary parser
- Docling

### Low-level PDF support
- pypdfium2 / PDFium

### OCR fallback
- OCRmyPDF + Tesseract, writing searchable-PDF artifacts before the normal parse path when needed

## OCR fallback policy

OCR is fallback-only in MVP and should run only when PDF text is inaccessible or clearly insufficient.

The default OCR fallback is **OCRmyPDF**.

Born-digital PDFs remain the primary target and should not go through OCR unnecessarily.

OCR outputs must still be normalized into the same parsed-document contract as non-OCR documents.

If the configured parser is Docling, the default expectation is that the run either uses Docling successfully or fails clearly with actionable messaging. A lower-quality parser may exist only as an explicit opt-in fallback for debugging or constrained environments, and any such fallback must be surfaced in readiness results, diagnostics, and summaries rather than activated silently.

### Optional later enrichment
- GROBID if measured lift justifies it

## Parser contract requirements

All parser outputs must normalize into one `ParsedDocument` contract.

Minimum internal fields should include:
- document identity
- metadata
- pages
- typed elements
- source-preserving text
- normalized text
- table regions
- figure/caption links when available
- provenance links
- geometry if available

## Storage rule

Parser-native outputs should be stored as artifacts for debugging and reproducibility even if downstream systems consume only the normalized representation.

---

## Matching strategy

## Objective

Match each PDF to the most likely row while minimizing incorrect row assignment.

## Approach

### Pass 1 — Deterministic scoring
Use publication metadata signals such as:
- title similarity
- author overlap
- year tolerance
- identifiers when available

### Pass 2 — Model adjudication
Use only for plausible ambiguous cases.

### Conflict policy
- if match remains ambiguous: block extraction
- if two or more PDFs match the same row: block all involved until manual cleanup

### User visibility
Unmatched, ambiguous, and duplicate-row-conflict PDFs must remain visible in the UI.

---

## Retrieval strategy

## Objective

Improve extraction quality by retrieving over contextualized typed chunks while keeping reviewer-visible evidence anchored to source-preserving text.

## Retrieval units

The MVP retrieval defaults are:
- paragraph chunks
- section chunks
- caption chunks
- table-region chunks
- `top_k = 6`
- include captions/tables when relevant
- one neighbor window around selected text chunks

## Retrieval text versus display text

Retrieval may use contextualized `retrieval_text`, but evidence display and quote validation must use source-preserving text.

## Baseline retrieval philosophy

The default retrieval stack should be intentionally narrow:

- typed chunking
- contextualized text
- sparse or simple baseline retrieval
- table-aware units where useful
- no reranker in the MVP baseline
- no HyDE in the MVP baseline
- no query expansion in the MVP baseline

Advanced helpers must prove lift before becoming baseline behavior.

## Context strategy

The runner should start with:
- one primary context strategy
- one fallback

The current preferred direction is:
- primary: focused retrieval-based extraction
- fallback: broader full-document context for cases where retrieval is insufficient or not applicable

Memory-mode summarization is not baseline MVP behavior.

---

## Extraction strategy

## Objective

Generate schema-driven proposals with enough context to maximize usefulness while preserving trust and inspectability.

## Behavior

- column-driven extraction
- at most one best proposal per target cell per run
- one proposal JSON object per target cell per run
- value-first behavior retained
- structured-output-first
- concise rationale/calculation when the value is derived
- proposal states should include at least `found`, `inferred`, `unclear`, `blocked`, and `error`
- prefer `unclear` over guesses grounded mainly in prior spreadsheet values, common practice, or weak implication
- keep long-text or narrative fields as first-class targets through field-aware output handling rather than assuming every value fits a short-answer contract
- prefer concise markdown-bullet rationale over dense prose when a rationale is returned

## LLM interaction model

The MVP LLM interaction model is:

- parse once
- retrieve relevant passages
- ask the model per target cell
- require structured JSON output
- store page-grounded evidence

The extraction model should receive, at minimum:

- row context
- column name
- column description
- per-column style/format profile
- retrieved evidence context
- instructions for proposal state and evidence output

The model is allowed to:

- extract directly supported values
- derive values from calculations
- provide concise reviewer-facing rationale when inference or calculation is required

When rationale is requested, the preferred output shape is concise markdown bullets, for example short `Observation` and `Inference` bullets, because the review pane is optimized for fast scientific scanning rather than long narrative justification.

The model must not rely on hidden chain-of-thought as a product feature.

The MVP should use:

- one primary text-capable reasoning model, configured separately from any vision model
- one vision-capable model for figure review when configured, separate from the text model
- both model identifiers recorded in run artifacts and shown in run summaries and reviewer context

## Verify mode

Verify mode is not a separate extraction architecture. It is the same extraction flow applied to already-filled cells with different review/export/evaluation semantics.

## Style-profile preprocessing

Before extraction, the system should run a preprocessing LLM step per schema column over existing filled cells.

This step must produce a structured style/format profile that may include:

- expected output type
- expected length/detail level
- tone/style
- unit conventions
- whether outputs are terse, categorical, numeric, or explanatory

This profile is used only to shape output form.

It must not encode likely scientific content for the target cell.

Raw existing filled cells must not be injected into extraction prompts as semantic few-shot exemplars by default.

---

## Evidence strategy

## Objective

Preserve plausible values while making evidence quality visible, recoverable, and reviewable. Give the reviewer the information needed to make confident decisions, not merely proof that the model found something.

## Evidence quality as a first-class requirement

Evidence quality and reviewer trust are first-class product requirements. The system must not assume that the first model-returned quote is automatically the best evidence. Evidence must be ranked and ordered so the most authoritative item becomes primary.

Evidence selection should consider source authority and field relevance. For example, a methods section is generally more authoritative for procedural fields, while a results section is more authoritative for outcome fields. The ranking logic may use structural heuristics, section type classifications, or an LLM-assisted selection step.

## Evidence type taxonomy

The system must distinguish and label the following evidence types. These types must be rendered and labeled distinctly in the review UI:

- `direct_quote`: a verbatim passage from the paper that directly states the value
- `inferred_reasoning`: a reasoning chain or argument constructed from one or more quoted passages; distinct from the quote itself
- `calculation`: a calculation or derivation performed on quoted numeric evidence; distinct from the quote(s) used as inputs
- `approximate_highlight`: a highlight region produced from approximate parser geometry rather than precise page-text alignment; labeled as approximate, not presented as exact
- `quote_plus_page`: a quote plus page reference when precise highlighting fails; labeled as fallback text evidence
- `figure_based`: evidence derived from a figure, chart, diagram, or image, with figure crop, caption, and full-page context

The review UI must show direct quotes separately from reasoning and calculations. The reviewer must be able to distinguish verbatim text from model-constructed inference.

## Exact quote highlighting and honest fallback

Exact quote highlighting should be produced from rendered page text or an equivalent page-text alignment strategy whenever possible. Parser bounding boxes are often approximate; character-level alignment against the rendered text layer produces more precise highlights.

If exact quote matching against the rendered page text fails, the system must degrade honestly:
- if an approximate region can be derived from parser geometry, it may be shown as an `approximate_highlight`, labeled as approximate
- if no reliable geometry is available, the evidence degrades to `quote_plus_page` fallback, labeled as such
- fallback evidence must never be presented as exact highlighting

The UI must explain the fallback state rather than fabricating placeholder geometry.

## MVP evidence contract

The evidence model should be narrower and stricter than in the old system. Each proposal should link to separate evidence objects rather than embedding every evidence detail directly into the proposal object.

### Proposal object shape in prose

Each proposal JSON object should include, at minimum:
- run identifier
- proposal identifier that remains unique within the run even if more than one PDF targets the same row/cell context
- row identifier
- column identifier
- proposal state
- proposed value
- rationale field
- calculation field when the value is derived
- primary evidence identifier, pointing to the highest-ranked evidence item
- ordered supporting evidence identifiers, ranked by authority and relevance, most authoritative first

### Evidence object shape in prose

Each evidence object should capture, at minimum:
- evidence identifier
- source PDF
- page reference
- evidence type (one of: `direct_quote`, `inferred_reasoning`, `calculation`, `approximate_highlight`, `quote_plus_page`, `figure_based`)
- direct quote text when the evidence type includes verbatim text
- exact highlight regions when available from page-text alignment
- approximate fallback regions when exact alignment failed but parser geometry is available
- figure reference, caption text, crop path, and full-page path when evidence is figure-based
- anchor confidence level
- enough anchor information for the UI to render or fall back gracefully

### Text proposals
Preferred:
- quote + page + exact highlight from page-text alignment

First fallback:
- quote + page + approximate highlight from parser geometry, labeled as approximate

Final fallback:
- quote + page only, rendered clearly as text evidence, labeled as quote-plus-page fallback

### Figure proposals
Preferred minimum:
- crop + caption + page access

### Review emphasis
- one primary evidence item by default, selected by evidence ranking
- ordered supporting evidence items, navigable in ranked order
- separate rationale and calculation fields for derived values
- direct quotes visually distinct from reasoning and calculations in the review UI

## Quote list and viewer synchronization

The review workspace presents an ordered list of evidence items alongside the document viewer. These must stay synchronized:
- selecting an evidence item in the quote list must update the viewer to show that item's location on the page
- when the selected evidence changes, the viewer must refocus stably rather than jumping arbitrarily
- when zoom changes, the viewer must maintain focus on the selected evidence item

## Validation and recovery

MVP should use:
- one strict evidence validator
- one simple locator/recovery path
- honest fallback labeling when exact highlighting cannot be recovered

Do not build a broad salvage ladder by default.

---

## Table and figure handling strategy

### Tables

Tables are first-class evidence sources.

The system should:
- preserve table structure where possible during parsing
- generate table-aware retrieval units
- prefer table-derived context for fields likely to be answered from tabular results
- include nearby captions or narrative context when useful

### Figures

Figures are first-class evidence sources, not a last-resort fallback.

When vision capability is available, the system should review all relevant extracted figures as a normal supplemental evidence stage. This proactive approach means:
- figure evidence may strengthen or corroborate any proposal, not just those whose field type is explicitly classified as figure-derived
- figure evidence may rescue weak, unclear, or failed text-only proposals
- figure evidence may supplement text evidence to increase reviewer confidence

The MVP should:
- extract figure/caption relationships when available at parse time
- generate crops and page references for review
- run relevant extracted figures through vision review when a vision model is configured, selecting by structural heuristics or relevance rather than exhaustively processing every figure

Figure-derived proposals remain normal proposals, but their evidence source must be marked as figure-based.

The scope is targeted: relevant extracted figures per paper, not every page of every paper for every field. This keeps the approach focused while ensuring figure evidence is available where it matters.

## Evaluation boundary

MVP does not require a separate automated figure-evaluation track. Figure-derived proposals should remain identifiable in artifacts and the UI, but usefulness is judged through the same human review outcomes as other proposals.

---

## Export strategy

## Objective

Produce safe, review-authorized outputs without mutating the original source workbook.

## Planned behavior

- always export XLSX
- preserve original workbook untouched
- preserve accepted cell content only
- highlight changed cells
- include audit log

## Engine

- use `openpyxl`

## Workbook fidelity policy

The MVP export promise is content-only fidelity plus highlighting of changed cells, not workbook-behavior fidelity.

Guaranteed:
- accepted cell values are written into the exported XLSX
- unchanged cell content is carried forward
- changed cells are visually highlighted
- formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, and similar workbook features are not guaranteed

Out of guarantee:
- formulas
- filters
- frozen panes
- hidden rows or columns
- merged cells
- conditional formatting
- comments
- named ranges
- charts
- shapes
- images or drawings
- macros

This boundary should be documented explicitly and treated as the stable MVP contract.

---

## Persistence strategy

## Objective

Support local-first auditability and inspectability with the smallest coherent persistence model.

## Canonical persistence model

### Filesystem artifacts
Canonical run bundle:
- input snapshots/fingerprints
- parser outputs
- retrieval artifacts
- run metadata JSON
- proposals JSON
- evidence JSON
- review decisions JSON
- diagnostics JSON
- exports
- summary/report JSON

## Artifact bundle layout

The MVP persists state as a run-specific artifact bundle in the output directory.

The bundle should contain stable top-level categories such as:

- `run.json`
- `config.snapshot.json`
- `inputs/`
- `style_profiles/`
- `parsed/`
- `matching/`
- `retrieval/`
- `proposals/proposals.jsonl`
- `evidence/evidence.jsonl`
- `review/decisions.jsonl`
- `review/reviewer_summary.json`
- `exports/updated_table.xlsx`
- `exports/audit_log.csv`
- `logs/`

This artifact bundle is the canonical persisted state for MVP.

---

## Artifact bundle contract

The bundle layout is the canonical persistence mechanism, but not every JSON file needs to be treated as a stable interface. For MVP, the stable artifact categories for tooling, tests, and operator inspection are:

- run metadata and configuration snapshots
- parsed-document artifacts and parser diagnostics
- proposal and evidence JSON
- review decisions and decision history
- reviewer-outcome and run-summary JSON
- exported workbook and audit-log outputs

Lower-level intermediate files may still evolve as implementation details so long as these categories remain discoverable and semantically consistent.

---

## Ownership rule

The run directory is the canonical audit bundle and the only required MVP persistence mechanism.

The MVP does not need pause/resume semantics within a run. If a run is interrupted, the partial artifacts may remain for inspection, and a new attempt should create a new run directory.

Proposal identifiers must remain unique within a run, including blocked or unresolved cases where multiple PDFs may surface the same row/cell context.

Review decisions should be persisted as explicit records rather than only as proposal-state mutations so audit logs and summaries remain derivable from artifact data.

Persisted review semantics should preserve a distinct no-data confirmation meaning so later summaries can separate `paper does not report this value` from `model wrong` or `insufficient evidence` outcomes.

When an audit log includes a decision timestamp, that timestamp should come from the persisted review-decision record when one exists.

Even when a run fails during readiness or before later summaries exist, the artifact bundle should retain the resolved config snapshot plus the best available input/output context so the UI and diagnostics remain informative.

---

## Runtime and background jobs

## Objective

Run the pipeline simply and predictably without reintroducing graph-runtime complexity.

## Recommended MVP shape

- app-owned staged runner
- runs launched from the UI and executed under app-owned backend control using a lightweight in-process background mechanism
- no job queue required by default
- add **Huey + SqliteHuey** first if async execution becomes a practical necessity

Runs are launched from the UI and executed under app-owned backend control using a lightweight in-process background mechanism for MVP; no external job framework is required.

## Why this shape

It keeps:
- execution simple
- local deployment simple
- workflow ownership in the app
- queue complexity low

while keeping the first implementation simple and inspectable.

For MVP, the runner is single-pass: once started, it runs until completion or interruption. Interrupted runs remain as incomplete artifacts, and a new attempt creates a new run directory.

---

## Model/provider strategy

## Objective

Keep proposal extraction robust across local and external providers.

## Approach

- typed request/response contracts
- structured-output-first execution with capability negotiation
- structured JSON per proposal as the stable contract
- compatible fallback when a provider rejects a stronger guided-JSON mode
- prompt-only JSON fallback only when the same proposal contract can still be validated

The provider layer should be one typed interface with explicit locality, capability, and readiness reporting. The same provider abstraction should support LM Studio as the default local-first path and optional cloud providers later without changing the browser-first operator workflow.

## Initial provider decision

The initial provider path is LM Studio via its localhost API. The plan should assume local execution by default and treat other providers as later extensions behind the same interface.

## Canonical token and alias policy

- the canonical LM Studio config token is `lm_studio`
- the canonical LM Studio operator-visible label is `LM Studio`
- provider names are centrally defined and stored canonically
- config parsing, tests, docs, and UI labels must use the same canonical tokens
- explicit aliases may exist only as a documented normalization layer
- unknown or obsolete identifiers fail during validation rather than being guessed at runtime

## Provider config schema expectations

Each provider entry should capture, as applicable:

- canonical provider token
- declared locality (`local` or `cloud`)
- endpoint or base URL
- model identifier for text extraction
- model identifier for vision extraction (separate field; may be the same model or a different one)
- timeout and capability-probe settings
- credential environment-variable or secret references for cloud providers
- explicit disabled flag or explicit stub/demo mode only when intentionally supported

Committed examples should show LM Studio as the default live path with both text model and vision model fields. Cloud examples, when present, should demonstrate environment-based credential resolution rather than committed secrets.

Operator docs should include at least one verified LM Studio text model example and, where applicable, a vision model example, clearly marked as known-working examples rather than as the only acceptable models.

When a vision model is configured and used, run artifacts and run summaries must record it separately from the text model so the reviewer can see which model generated which evidence type.

## Structured-output compatibility and response recovery

Provider adapters should probe or negotiate structured-output compatibility per provider/model path rather than assuming one guided-JSON mechanism will work everywhere.

If a provider rejects the preferred guided-output mode, the adapter should fall back to another compatible structured-response path only if the same proposal contract can still be validated.

One structured-output mismatch or guided-JSON rejection must not poison an entire run by default. Compatibility handling should be contained to the affected provider-model path, request shape, or target-cell attempt, with truthful diagnostics and continued processing where the contract can still be preserved safely.

Malformed structured responses should go through a bounded repair path before the target is finalized as a hard extraction error. The repair path should use a compact repair-oriented instruction or equivalent narrowly scoped recovery mechanism rather than reopening the full extraction request indefinitely.

If a compatible structured path cannot be established, the run should record a clear provider or extraction failure rather than silently accepting unstructured output as a valid proposal.

## Preflight and readiness policy

Before normal run execution begins, the app should perform the smallest coherent readiness check set for the configured path:

- config schema and canonical provider-token validation
- provider reachability for live providers
- configured model availability or capability failure where it can be checked cheaply
- parser and OCR dependency availability for configured paths
- output-path writability and other obvious broken local setup conditions

If these checks fail, the run should stop before misleading downstream stages and persist a readiness failure that the UI can present directly.

## Provider mode recording and truthfulness

Run artifacts and normal summaries should record at least:

- configured provider token
- resolved canonical provider token
- model identifiers used
- locality (`local` or `cloud`)
- proposal-generation mode (`live`, `unavailable`, `disabled`, or explicit `stub/demo/degraded`)
- readiness checks performed and failing reasons where applicable

## Transparency

The system should record and surface:
- text model name and vision model name separately when both are used
- whether the run stayed local or used cloud providers
- whether proposal generation was live, unavailable, disabled, or explicitly degraded/demo
- whether figure review was performed and with which vision model

At minimum this should appear in the normal run summary.

The normal run summary should include:
- text model name
- vision model name (when a vision model was configured or used)
- whether execution stayed local or used cloud services
- provider mode and readiness outcome for proposal generation
- PDFs processed
- matched, unmatched, and ambiguous PDF counts
- proposals generated
- proposals reviewed
- accepted as-is, accepted with edit, confirmed no-data, and rejected counts
- accepted change count
- warning flags for limited review or weak evidence situations

---

## Evaluation and measurement strategy

## Canonical fixture strategy

The checked-in workbook fixture with schema tab plus the checked-in set of four paper PDFs should remain the primary canonical fixture baseline for MVP rebuilds when they cover the intended scenarios.

The canonical live-smoke fixture target for the LM Studio proof path is:

- `tests/fixtures/tables/literature_fixture.xlsx`
- `tests/fixtures/papers/paper_1.pdf`

That pair is the normative minimum live-path proof target for MVP unless the fixture audit explicitly revises it in the same work pass.

Implementation and verification work should prefer:

- reusing those existing binary fixtures
- adding text-based companion configs, manifests, expected outputs, or assertions when more specificity is needed
- avoiding new binary fixtures unless a real coverage gap cannot be addressed otherwise

This keeps the rebuild burden realistic for coding agents while preserving one stable happy-path proof target.

## Objective

Measure usefulness honestly in MVP without overcommitting to brittle automated scoring.

## Reviewer-outcome summaries

MVP run quality should be summarized primarily through reviewer outcomes rather than automated correctness scoring.

At minimum, the run summary should include:

- PDFs processed
- matched / unmatched / ambiguous PDFs
- target cells
- proposals generated
- reviewed proposals
- accepted-as-is
- accepted-with-edit
- confirmed-no-data
- rejected
- changed cells exported
- Verify mode on/off
- provider/model names
- local vs cloud status

## MVP measurement model

Use reviewer-outcome statistics as the primary product-level measurement:

- reviewed proposal count
- accepted as-is count/rate
- accepted with edit count/rate
- confirmed no-data count/rate
- rejected count/rate
- proposal coverage
- per-column reviewer outcome breakdown
- evidence display success
- matched/unmatched/ambiguous counts

## Verify mode semantics

Verify mode should:
- expose already-filled-cell proposals to review
- allow accepted edits to export
- contribute to reviewer-outcome summaries automatically

It does **not** require a sophisticated automated correctness score in MVP. In MVP, Verify mode supports review and reporting, not benchmark-grade scoring.

## Measurement integrity

Always distinguish:
- proposal production
- evidence presence
- reviewer acceptance
- evaluation emptiness/skips

Never let zero-evaluable-target runs masquerade as normal scored runs. Leakage-safe benchmark design can be deferred until a later phase because MVP does not depend on automated verification scoring.

Run-summary and reviewer-summary counters and warning flags should be computed from persisted artifact facts rather than ad hoc UI heuristics, and provisional states should stay visibly provisional until their triggering conditions are truly met.

---

## Testing strategy

## Core layers

### Unit tests
- parser normalization
- matching logic
- chunk typing
- retrieval text construction
- evidence validation
- export transformation
- provider capability routing

### Integration tests
- end-to-end stub run
- review API and UI smoke
- export generation
- figure fallback path
- Verify mode flow

### Deterministic offline tests
Use stub/mock providers and deterministic fixtures by default.

Playwright/browser-based e2e startup should remain shell-independent: prepare fixture run data in a dedicated script first, then start backend and frontend with direct process spawning or Playwright global setup/teardown rather than shell heredocs or shell command chaining.

Browser-based test failures should distinguish environment/runtime problems from application failures whenever practical.

Screenshots, traces, or equivalent browser-failure artifacts are desirable where practical so review-workflow regressions are easier to diagnose.

### Live integration tests
Keep opt-in only.

## Fixture strategy

Maintain a compact fixture set that covers:
- easy papers
- table-heavy papers
- figure-heavy papers
- ambiguous matching
- weak evidence
- no-value cases
- Verify-mode reviewed cells

---

## Implementation phases

## P0 — Core workflow foundation
- finalize parser contract
- implement ingest + validate inputs
- implement per-column style-profile preprocessing
- implement main parser + low-level PDF fallback
- implement OCR fallback for scanned PDFs
- implement matching
- implement proposal/evidence persistence
- implement queue-first Run/Review UI skeleton
- implement XLSX export + audit log
- implement reviewer-outcome summaries
- implement Verify mode basic flow

## P1 — Retrieval and review hardening
- typed chunking
- contextualized retrieval text
- table-aware retrieval artifacts
- narrow evidence validator + locator
- figure fallback
- review filters, counters, and progress UX

## P2 — Measured extensions
- optional parser enrichments
- optional retrieval helpers if they prove lift
- optional richer figure handling
- optional automated Verify-mode scoring research prototype
- optional stronger diagnostics and developer tooling

---

## Risks and mitigations

### R-1: Parser normalization drift
**Mitigation:** one normalized contract, adapter tests, stored raw artifacts.

### R-2: Evidence anchoring brittleness
**Mitigation:** PDFium low-level backend, strict evidence contract, one simple locator path, fallback quote+page reviewability.

### R-3: Figure scope too broad for reliable MVP behavior
**Mitigation:** review-first figure UX, explicit fallback triggers, visible figure-based evidence, and human reviewer judgment as the governing quality check.

### R-4: Workbook fidelity expectations exceed implementation reality
**Mitigation:** explicitly document the content-only export boundary and the non-guaranteed workbook features.

### R-5: Provider incompatibility or weak structured output
**Mitigation:** capability probes, typed validation, prompt-only fallback.

### R-6: Runtime complexity grows back through helper passes
**Mitigation:** helper passes remain opt-in until measured lift is shown.

### R-7: Config sprawl reappears
**Mitigation:** keep user-facing config small; keep policy/internal tuning separate; avoid exposing every experimental knob.

---

## Open technical questions

Most previously blocking architecture questions are resolved for MVP. The remaining implementation-level questions to validate during delivery are:

- whether the first PDF evidence overlay should be fully custom or should borrow limited interaction patterns from existing highlighter libraries while keeping normalized anchors internal
- whether CSV input should receive additional import warnings when workbook-only fidelity expectations could confuse users
- how much saved-view or preset support is necessary in the first review queue without expanding into a large personalization surface
- if synchronous execution proves insufficient, whether Huey + SqliteHuey remains the right first background-job layer to adopt

These are intentionally narrow questions. They should not reopen the larger architectural choices already recorded in this plan.

---

## Concise implementation summary

Paper Table Agent will be implemented as a local-first workflow application with:

- a React local browser UI
- PDF.js in the frontend and PDFium/pypdfium2 in the backend
- one main parser first, behind a normalized parser contract
- OCRmyPDF plus Tesseract as the scanned-PDF fallback
- typed retrieval units and source-preserving evidence
- runs launched from the UI and executed under app-owned backend control using a lightweight in-process background mechanism for MVP, with Huey + SqliteHuey as the first likely async addition if needed
- filesystem artifact bundles and JSON state files as the complete MVP persistence layer, with no database required
- reviewer-outcome-based MVP evaluation
- a preprocessing LLM that turns existing filled cells into structured style profiles
- evidence ranking and evidence type taxonomy with primary and supporting evidence semantics
- exact quote highlighting via page-text alignment with honest labeled fallback to approximate highlight or quote-plus-page
- synchronized quote list and document viewer around the currently selected evidence item
- viewer navigation: previous/next page, jump to page, zoom with stable refocus on evidence
- proactive figure review across all relevant extracted figures when a vision model is configured, with figure evidence allowed for any field type
- separate text-model and vision-model configuration, with both recorded in run artifacts and shown in summaries
- new XLSX export plus audit log with content-only fidelity plus changed-cell highlighting

This keeps the system aligned with its real purpose: trustworthy, human-reviewed extraction from scientific papers into structured tables, with evidence quality and reviewer trust as first-class requirements.
