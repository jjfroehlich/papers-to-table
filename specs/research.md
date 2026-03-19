# Paper Table Agent — `research.md`

## Purpose

This document summarizes the research that informed the current architecture and planning decisions for Paper Table Agent.

It is not the product spec and not the implementation plan. Its purpose is to record:

- which technical questions were researched
- which alternatives were considered
- what conclusions were reached
- what remains uncertain or deferred

This document supports:

- `spec.md` by clarifying constraints and feasibility
- `plan.md` by justifying technical decisions

It can also inform future implementation notes or runbooks if those become useful.

Where a conclusion is not fully settled, it should be marked clearly using the confidence levels defined below or called out as an open question.

---

## Status

Finalized baseline

This document contains the current baseline conclusions plus explicit open questions. It should be updated whenever a major implementation decision changes.

### Decision confidence levels

To keep this document actionable, conclusions should be read with these confidence levels in mind:

- **Baseline**: recommended for MVP unless new evidence overturns it.
- **Provisional**: favored today, but still worth re-checking during implementation.
- **Deferred**: intentionally out of the MVP baseline unless later evidence justifies promotion.

---

## Research questions

The main research questions for this phase were:

1. Which PDF ingestion/parsing stack best fits scientific papers plus evidence review?
2. How should parsed outputs be normalized for retrieval and reviewer-visible evidence?
3. What retrieval design best supports schema-driven extraction from papers?
4. What UI shape best supports proposal review with PDF evidence?
5. Which technical stack best fits a local-first review UI delivered as a browser app?
6. How should spreadsheet export work, and what are the realistic fidelity limits?
7. What should be canonical state: filesystem artifacts, database state, or both?
8. Does v1 need an orchestration/agent framework, or is a deterministic pipeline enough?
9. If synchronous execution proves insufficient, what background-job model should be adopted first for a local-first app?
10. How reliable is structured output across likely model providers?
11. How should the product evaluate quality in MVP, and what should be deferred?
12. Should existing filled spreadsheet cells be used as examples in extraction prompts?
13. How should figures, charts, and image-heavy panels be integrated into extraction and review?
14. Are there licensing or deployment constraints that could affect the chosen stack?

---

## Executive summary of conclusions

### Main conclusions

- The app should be implemented as a **focused workflow application**, not as a generic RAG chat tool.
- The postmortem indicates that the prior implementation validated the **core product loop**, but also accumulated too much adaptive runtime complexity around brittle PDFs, model outputs, retrieval, and evidence anchoring.
- The rewrite should carry forward conceptually, not by copying implementation: the core workflow, operator-facing evidence, hermetic end-to-end tests, parsed-document normalization, and typed/contextualized retrieval artifacts.
- The first shipping parser approach should be **one main parser plus low-level PDF fallback**, while preserving a parser abstraction for later measured expansion.
- The current practical low-level PDF direction is **PDFium via pypdfium2** as the complementary backend for rendering/highlight/crop and geometry-sensitive evidence operations because it balances those capabilities with a safer licensing posture than PyMuPDF/MuPDF.
- The system should normalize parser outputs into one internal **parsed-document contract**.
- Retrieval should operate over **typed chunks** and may use contextualized `retrieval_text`, but reviewer-visible evidence must remain anchored to source-preserving text.
- Table-aware retrieval looks like a likely structural improvement for this product, but more advanced retrieval helpers must prove lift before becoming baseline.
- The review experience requires a **dedicated Run/Review UI**, and the current practical MVP direction is a **queue-first / list-detail review workflow** rather than a spreadsheet-first or wizard-only design.
- The current practical MVP implementation direction is a **local browser app** centered on a **React frontend**, a **small Python FastAPI backend**, and a **raw/custom PDF.js evidence viewer**, with no desktop shell required for MVP. TypeScript, Vite, Tailwind, shadcn/ui, TanStack Table, and TanStack Virtual are sensible practical defaults rather than architectural requirements.
- The system should use **filesystem artifact bundles plus JSON files as the canonical and sufficient MVP state**, with no database required for MVP.
- Export should generate a **new updated XLSX workbook plus audit log**, not patch arbitrary workbooks in place, and **openpyxl** is the most realistic Python engine for that MVP behavior. The fidelity promise should be **content-only fidelity plus changed-cell highlighting**, with workbook behavior and advanced sheet features out of guarantee.
- The implementation should use a **deterministic staged pipeline first**, with only targeted LLM-assisted stages.
- The strongest current MVP runtime recommendation is **an app-owned staged runner executed synchronously inside the FastAPI service first**, with **Huey + SqliteHuey** as the first candidate background-job layer only if UI responsiveness later proves async execution necessary.
- Structured outputs should be the **default contract path**, with capability probes and graceful fallback for weaker providers.
- Heavy orchestration or graph-first agent systems should be **deferred** unless measured workflow complexity clearly justifies them.
- In MVP, evaluation should be based primarily on **reviewer-outcome summaries**, not on a single automated “correctness score” over heterogeneous field types.
- Existing filled spreadsheet cells should be processed through a **per-column preprocessing LLM** that produces a structured style/format profile. Heuristic-only default shaping is not sufficient, and raw filled cells should **not** be passed into extraction prompts as semantic exemplars by default.
- Figure-aware fallback should remain available, but the heavier reasoning-plus-vision path should remain a scoped escalation triggered only when the field is likely figure- or table-derived, text retrieval failed or remained insufficient, or the user explicitly requests fallback. Human review remains the only MVP evaluation path.

### Provisional conclusions

- GROBID may still be useful, but it should be optional or deferred unless measured lift justifies making it part of the default shipping path.
- Dense retrieval, reranking, HyDE, query expansion, and memory-style context modes may still be useful, but they must prove lift before becoming baseline behavior.
- Automated per-run scoring for Verify mode may still be useful later, but it is explicitly deferred beyond MVP.
- A desktop shell such as Tauri may still be attractive later for packaging, but the MVP recommendation is a local browser app with a custom PDF.js-based evidence viewer.

### Immediate planning impact

These conclusions directly support the current `plan.md` architecture and should be considered the baseline unless future research overturns them.

---

## Research topic 0 — Lessons from the prior implementation attempt

## Why the prior implementation matters

The prior implementation matters because it validated the product idea while also making the main rewrite risks concrete.

The prior implementation suggests that the app’s central workflow was real and useful:

- ingest table plus schema plus PDFs
- match papers to rows
- generate reviewable proposals
- attach at least some operator-visible evidence
- review and export audited changes

The postmortem indicates that the engineering drag came from trying to make one runtime absorb too many adaptive strategies at once. The rewrite should therefore preserve the product core while simplifying runtime shape, tightening contracts, and resisting fallback proliferation.

## What was genuinely valuable

### Core product loop

The strongest result from the prior implementation was not a particular parser or retrieval stack. It was validation that the paper-to-table review loop is a legitimate product.

### Evaluation discipline

The prior implementation showed that some form of built-in evaluation is valuable because it turns anecdotal runs into measurable runs. However, it also showed that naive or empty evaluation can be misleading. The rewrite should keep measurement discipline, but with stronger integrity rules.

### Operator-facing evidence

The prior implementation was right to make evidence visible to the reviewer rather than hiding it in prompts or internal reasoning. This should stay, but under a narrower and stricter contract.

### Hermetic end-to-end tests

The prior implementation’s deterministic end-to-end tests were strategically correct. The rewrite should preserve hermetic stub-based testing as a core engineering requirement.

### Parsed-document normalization

Normalizing parser outputs into a shared parsed-document representation remains one of the strongest architectural ideas from the prior implementation and related planning work.

### Typed/contextualized chunks

Typed chunks and contextualized retrieval text still look like high-value structural improvements because they improve retrieval quality without requiring a sprawling runtime.

### Table-aware retrieval as a likely structural improvement

The postmortem and later research together suggest that table-aware retrieval is more promising than many of the old adaptive ladders. It should be treated as a likely structural improvement area for the rewrite.

## What should be re-simplified

The prior implementation suggests that the rewrite should deliberately re-simplify these areas:

- graph runtime
- mega-context patterns
- provider-role/client matrices
- retrieval backend matrices
- multiple peer context modes
- helper LLM passes as baseline
- evidence salvage ladders
- config sprawl

## What should be deprioritized

The rewrite should explicitly deprioritize these until audited lift is shown:

- multi-parser runtime early
- GROBID as a guaranteed baseline dependency
- dense retrieval as a default baseline
- reranking as a default baseline
- HyDE and query expansion as default helpers
- broad fallback proliferation across parsing, retrieval, and evidence recovery

## Consequences for the rewrite

The rewrite should therefore begin from a smaller baseline:

- one main parser plus low-level fallback
- one primary context strategy plus one fallback
- one strict evidence contract
- one simple staged batch runner
- first-class reviewer-outcome measurement and hermetic tests
- typed/contextualized retrieval and table-aware retrieval as focused structural improvements

Any added sophistication should prove lift before becoming baseline.

---

## Research topic 1 — Parser and low-level PDF stack

## Why this mattered

The app depends on being able to ingest scientific PDFs in a way that preserves enough structure for retrieval and extraction, while also retaining enough source fidelity for evidence display and review.

A parser that only returns flattened text is not sufficient for this workflow.

## Candidate categories considered

### Scientific-paper-aware parsers

- GROBID

### Layout-aware local parsers

- Docling
- Marker
- Unstructured

### Cloud/managed parsers

- LlamaParse
- Azure Document Intelligence
- Google Document AI
- Amazon Textract

### Low-level PDF access layers

- PDFium via pypdfium2
- PyMuPDF / MuPDF
- PDF.js
- Poppler wrappers

### Table-focused supplements

- Camelot
- Tabula
- table-specific extraction tools

## What mattered most for this app

The most important criteria were:

- scientific-paper fit
- layout awareness
- table-region handling
- provenance and page anchoring
- usefulness for human review
- local-first operation
- fallback compatibility
- licensing risk

## Current conclusion

### Recommended parser stack for the rewrite baseline

- **Docling is the main parser** for v1
- **PDFium via pypdfium2 is the complementary low-level PDF backend** for page rendering, text search, coordinate mapping, highlighting support, crop generation, and fallback page/image access
- **parser abstraction preserved** so additional parsers can be added later if measured lift justifies it

Docling and PDFium/pypdfium2 are not competing parser choices in this baseline. Docling is responsible for primary document parsing and structured extraction, while PDFium/pypdfium2 complements it with low-level PDF capabilities needed for rendering, geometry, crops, highlight support, and fallback page/image access.

## Why this combination won

### One main parser first

The prior implementation suggests that multi-parser runtime complexity should not be baseline behavior. The rewrite should start with one main parser that is good enough for the product loop and keep the contract stable around it.

### Main parser choice

Docling is the main parser in the current baseline because it is strong on structured document conversion, layout-aware parsing, figure/image extraction, and chart/table support.

### Complementary low-level PDF backend

PDFium via pypdfium2 does not replace the parser. It complements Docling by providing:
- rendering
- geometry and coordinate mapping
- crops
- highlight support
- fallback page/image access
- text extraction/search with boxes/rectangles when low-level access is needed
- a more product-friendly licensing posture than PyMuPDF/MuPDF

### Why PyMuPDF is not the default

PyMuPDF/MuPDF looks excellent technically, but the AGPL/commercial licensing model makes it a riskier default for an MVP that may later want flexible distribution options.

### Why PDF.js is not the backend source of truth

PDF.js is the strongest open viewer foundation in the browser layer, but it is not the best sole backend source of truth for persistent anchoring, crop generation, and geometry authority.

### GROBID

GROBID remains a plausible enrichment path because it is specialized for scientific papers and may improve metadata and structure extraction, but it should not be assumed to be baseline shipping behavior unless measured lift justifies it.

## Implications for implementation

- Parser outputs must normalize into one internal format.
- The parser layer should be adapter-based even if only one main parser ships initially.
- The low-level PDF layer should be wrapped behind a small internal interface.
- Evidence anchors should be stored in canonical page coordinates, not viewer pixel coordinates.

## Follow-up status

- Resolved for MVP: use PDFium via pypdfium2 as the low-level PDF backend behind a small internal abstraction.

---

## Research topic 2 — Parsed-document contract

## Why this mattered

The app uses multiple parsing and retrieval steps. Without a normalized internal document representation, parser-specific assumptions would leak into matching, retrieval, extraction, evidence validation, and review rendering.

## Current conclusion

The system should define and enforce one internal `ParsedDocument` contract.

## Minimum required capabilities of the contract

The normalized contract should preserve:

- document identity
- document-level metadata
- pages
- typed elements/blocks
- reading order
- source-preserving text
- normalized text
- table-like regions
- figure/caption relationships when available
- provenance links to pages/elements
- optional geometry/bounding boxes

## Important modeling insight

There must be a distinction between:

- **source-preserving text** used for evidence display and validation
- **derived/contextualized retrieval text** used for ranking and context assembly

## Consequences for architecture

This research directly supports:

- `ParsedDocument`
- `ParsedElement`
- `Chunk`
- retrieval/display text separation

---

## Research topic 3 — Retrieval and evidence design

## Why this mattered

The app is not just retrieving snippets for chat. It must retrieve context that supports schema-driven extraction while preserving reviewer trust.

## Main retrieval conclusions

### Typed chunking is better than plain chunking

The retrieval layer should be aware of element types such as:

- abstract
- section header
- paragraph
- figure caption
- table region
- table-cell summary
- reference block

### Retrieval text and display text must be separated

Retrieval may benefit from contextualized text, but reviewer-visible quotes must stay tied to source-preserving text.

### Table-aware retrieval matters

Some schema fields are likely to be answered from tables, captions, or results sections rather than from narrative paragraphs. Retrieval should support these distinctions.

### Structural improvements look higher value than helper sophistication

The prior implementation suggests that typed chunks, contextualized retrieval text, table-aware retrieval, and retrieval/display text separation are the strongest structural improvements to preserve or deepen.

### Optional sophistication must prove lift

Dense retrieval, reranking, query expansion, and HyDE may improve quality, but the rewrite should not treat them as baseline assumptions. They must prove audited lift before becoming default behavior.

### Start with one primary context strategy and one fallback

The rewrite should start with one primary context strategy and one fallback, not three peer modes.

## Main evidence conclusions

### Evidence is not a hard gate on surfacing plausible values

If a value appears plausible, the system may still propose it even if evidence is weak, as long as the proposal is visibly flagged.

### Narrower evidence contracts are more important than broader rescue ladders

Weak or missing evidence should trigger at most a narrow recovery path at first. The rewrite should prefer a stricter evidence contract over reflexively adding salvage ladders.

### Multiple evidence items are appropriate

Some values are best supported by more than one snippet, but the review surface should emphasize one primary evidence item and make others expandable.

## Consequences for implementation

This research supports:

- typed chunks
- `retrieval_text`
- table-aware retrieval units
- `found` vs `inferred` proposal states
- a narrow evidence validator plus a simple locator path
- weak-evidence triage cues

---

## Research topic 4 — Review UI and interaction model

## Why this mattered

The product’s core value is not just extraction. It is the ability for a human to review proposals safely and efficiently.

## Main conclusion

A dedicated **Run/Review UI** is required, and the current practical MVP direction is a **queue-first / list-detail review workflow**.

## Why generic chat interfaces are not enough

The reviewer needs to see, side by side:

- the row context
- the target column definition
- the proposed value
- the proposal support state
- the evidence text or figure evidence
- the PDF page context
- the review action controls

This is a workflow interface, not a chat conversation.

## Main UI recommendation

### Recommended MVP interaction model

The current practical MVP direction is:

- a **proposal queue** or list on one side
- a **focused detail pane** for the currently selected proposal
- a **document/evidence viewer** showing the highlighted PDF page or figure crop/full page
- progress counters and filter controls visible in the main review workspace

This is preferable to:
- a pure spreadsheet-first UI as the main review surface
- a strict single-proposal wizard with no queue context

### Why this recommendation won

- It supports nonlinear review.
- It supports filtering and triage.
- It supports evidence-heavy decision making.
- It scales better when many proposals exist.
- It allows step-by-step review without forcing a rigid path.

### Spreadsheet-first interaction remains useful as a secondary context mode

A table or row overview may still be useful for orientation, but it should not be the main evidence review surface.

## Highlighting conclusions

The review UI should support:

- page navigation
- quote-based evidence display
- page-relative highlight overlays when geometry is available
- fallback behavior when precise highlight rectangles are not reliable
- figure crop plus full-page viewing for figure-derived evidence

## Consequences for implementation

This research supports:

- dedicated review views
- a queue-first review model
- `HighlightAnchor`
- quote + page + highlight evidence model
- crop-first figure review with full-page access
- progress counters and filtering as core review affordances

## Follow-up status

- Resolved for MVP: bulk acceptance applies only to the currently visible filtered subset, with explicit confirmation.
- Resolved for MVP: reviewer-facing support labels should use clear human-readable wording such as `Direct evidence` and `Inferred from evidence`, consistent with `spec.md`.

---

## Research topic 5 — UI technical stack

## Why this mattered

The product needs not only the right interaction model, but also the right implementation stack for:
- local-first file handling
- queue-based review UI
- PDF evidence rendering
- modern local review UX
- integration with Python-heavy extraction logic

## Main conclusion

A sensible current MVP stack is best understood in two layers.

### Core MVP architecture

- **local browser UI**
- **React frontend**
- **Python + FastAPI backend**
- **raw/custom PDF.js evidence viewer**
- **filesystem artifact bundles plus JSON files** for local persistence
- **LM Studio localhost API** as the initial LLM provider

### Practical default implementation choices

- **TypeScript**
- **Vite**
- **Tailwind**
- **shadcn/ui** or a similarly lightweight component layer
- **TanStack Table** for the review queue
- **TanStack Virtual** as an optional add-on only if proposal-list size makes virtualization useful

## Why this conclusion won

### Local browser app is sufficient for MVP

Because the app is single-user, local-first, and artifact-based, a local browser app plus a small FastAPI service is sufficient for MVP. It removes packaging complexity without weakening the core workflow. Tauri remains a possible future packaging option rather than an MVP requirement.

### React ecosystem fit is strongest for this UI

The product depends on:
- advanced tables/queues
- PDF viewer integrations
- complex split-pane layouts
- custom evidence overlays

That ecosystem fit is strongest in React.

### PDF.js should remain the evidence-viewer foundation

PDF.js is the best open-source foundation for a browser/webview PDF evidence viewer, even if a more opinionated wrapper or commercial SDK could accelerate later implementation.

## Consequences for implementation

This research supports:

- a local browser-app architecture
- a React-first frontend paired with a FastAPI backend
- PDF.js as the evidence-viewer foundation
- Python extraction logic remaining in the architecture
- queue-first review implemented with headless table logic rather than a spreadsheet-first enterprise grid
- practical default libraries such as Vite, Tailwind, shadcn/ui, and TanStack Table being treated as replaceable defaults rather than strict architectural requirements
- TanStack Virtual being optional and only introduced if proposal volume makes virtualization worthwhile
- PDF evidence modeled in normalized page coordinates independent of the viewer implementation

## Follow-up status

- Open implementation detail: decide whether the first viewer overlay is entirely custom or borrows limited interaction patterns from react-pdf-highlighter-style tooling.

---

## Research topic 6 — Spreadsheet export and workbook fidelity

## Why this mattered

The product ends by updating spreadsheet content. This seems simple, but real Excel workbooks can contain formatting, formulas, charts, shapes, macros, and other artifacts that are difficult to preserve perfectly.

## Main conclusion

The product should generate a **new updated workbook plus an audit log**, not patch arbitrary workbooks in place.

## Current product-aligned conclusion

The current product direction is:

- export to a **new XLSX workbook**
- preserve **cell content only**
- visually highlight cells changed through accepted proposals
- keep the original input workbook unchanged

The most realistic Python round-trip engine for this is **openpyxl**. XlsxWriter is excellent for generating new files from scratch but cannot read/modify an existing workbook. xlwings can achieve higher fidelity through native Excel automation, but it is too platform- and installation-dependent to be the default MVP boundary.

## Practical expectation for v1

The MVP promise is content-only fidelity plus changed-cell highlighting, not workbook-behavior fidelity.

### Guaranteed
- accepted cell values are written into the exported XLSX
- unchanged cell content is carried forward
- changed cells are visually highlighted

### Out of guarantee
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
- images/drawings
- macros
- arbitrary workbook-wide advanced artifacts outside plain cell content

## Consequences for implementation

This research directly supports the `plan.md` export strategy and the current product requirement that changed cells be visually highlighted.

## Follow-up status

- Open documentation detail: decide whether CSV import and export parity deserves its own explicit note in product docs.

Current MVP decision: do not add special warn/block behavior for workbooks with heavy non-cell artifacts. The product boundary remains content-only fidelity plus changed-cell highlighting, with other workbook features simply out of guarantee.

---

## Research topic 7 — Persistence model and artifact strategy

## Why this mattered

The app needs:

- reproducibility
- inspectability
- efficient review queries
- auditability

A single storage approach does not serve all of those equally well.

## Main conclusion

Use a filesystem-only MVP model:

- **filesystem run artifacts** as the canonical audit, reproducibility, and operational state bundle
- **JSON files** inside each run directory for proposals, evidence, review state, diagnostics, summaries, and export bookkeeping

## Why this combination won

### Filesystem artifacts are best for

- debugging
- packaging runs
- preserving parser outputs and logs
- reproducibility

### JSON artifacts are sufficient for MVP

For a single-user local app, JSON files inside a per-run bundle are sufficient for:

- proposal lists
- review state
- filtering and triage support
- export bookkeeping

The MVP does not need pause/resume semantics within a run. If a run is interrupted, the simplest behavior is to leave the partial artifacts in place and create a fresh run directory for the next attempt.

## Consequences for implementation

This directly supports the simplified artifact-only persistence strategy in `plan.md`.

---

## Research topic 8 — Orchestration and background jobs

## Why this mattered

The pipeline contains long-running stages such as parsing, indexing, extraction, narrow evidence-location support, export, and evaluation.

The question was whether v1 should be built around a heavyweight orchestration/agent framework or a simpler job pipeline.

## Main conclusion

The app should use a **deterministic app-owned staged runner first**, executed synchronously in the FastAPI service. No job queue is required for MVP. If async execution becomes necessary later, **Huey + SqliteHuey** is the first likely queue layer.

## Why this conclusion won

- It preserves a simple staged pipeline.
- It avoids graph-first orchestration.
- It avoids requiring a queue system before the app proves it needs one.
- It keeps the first implementation easier to inspect and debug.

### Why not heavier orchestrators

Prefect and Temporal solve bigger problems than the current MVP needs. Temporal especially is justified only if durable workflow replay becomes a top-tier requirement.

### Why not let the queue own the workflow

The reports strongly recommend that the app own:
- stage order
- progress semantics
- artifacts
- retries

The queue library should only run stage jobs in the background.

## Consequences for implementation

This research supports:

- simple stage-based pipeline execution
- synchronous execution first, with background execution deferred unless needed

For MVP, that staged runner can remain single-pass. It does not need pause/resume support or in-place rerun semantics; interrupted runs can simply be replaced by a new run.

---

## Research topic 9 — Model/provider compatibility and structured outputs

## Why this mattered

Proposal extraction depends on predictable object outputs. However, local and remote model providers differ in how well they support structured outputs, constrained decoding, JSON schema, and strict tool-like responses.

## Main conclusion

The app should be **structured-output-first**, with:

- typed contracts
- capability probes
- provider-specific compatibility handling
- prompt-only JSON fallback when needed

## Why this conclusion matters

This lets the app remain flexible across:

- local providers
- hosted APIs
- future provider swaps

without collapsing into brittle hand-parsing as the default design.

## Consequences for implementation

This supports:

- provider capability probes
- `ProviderProbe` records
- typed extraction contracts
- optional prompt/response logging

## Current MVP provider choice

The initial MVP provider should be **LM Studio via its localhost API**. This keeps the default path local-first while preserving the same structured-output contract for future providers.

---

## Research topic 10 — Evaluation strategy and measurement integrity

## Why this mattered

The app needs both engineering regression protection and product-level usefulness measurement.

The key question was whether MVP should attempt an automated Verify-mode score across heterogeneous cell types, or whether it should use a simpler and more trustworthy measure.

## Main conclusion

For MVP, evaluation should be based primarily on **reviewer-outcome summaries**, not on a single automated “correctness score” over heterogeneous field types.

## Recommended MVP measurement model

The strongest current recommendation is to measure:

- proposal coverage
- reviewed verified-cell count
- accepted as-is count/rate
- accepted with edit count/rate
- rejected count/rate
- per-column reviewer outcome breakdown
- evidence coverage
- anchorable/highlightable evidence rates where applicable
- matched / unmatched / ambiguous PDF counts

This is more trustworthy and easier to interpret than an automated aggregate score over free text, numeric, categorical, range, and reasoning-heavy fields.

## Why this conclusion won

### Human review is already the product’s ground truth

Since the product requires expert review before export, the reviewer’s decision is the most natural MVP signal of usefulness.

### Automated scoring is hard across mixed field types

A single automated scoring method that handles all field types well is possible later, but not necessary for MVP.

### Reviewer-outcome metrics are more honest for a first release

They align directly with the product’s purpose: reducing reviewer effort while preserving trust.

## Evaluation hygiene and leakage

Leakage-safe benchmark design is deferred because MVP does not depend on automated verification scoring. Future automated Verify-mode scoring is deferred and may be added later; if it is added, prompt-shaping inputs and evaluation targets will need explicit separation rules.

## Measurement integrity requirements

A run that produces many proposals and many evidence attachments is not necessarily a good run.

A run with empty or non-interpretable evaluation should be treated as a meaningful diagnostic state, not as a normal artifact. If no relevant reviewed/verified targets were evaluated, that state should be explicit and reviewer-visible rather than collapsing into an apparently valid zeroed summary.

## Consequences for implementation

This supports the current split between:

- synthetic/parser fixtures
- application-level review/verify summaries
- first-class run-level metrics that keep proposal rate, evidence rate, and reviewer acceptance separate
- explicit warning states when evaluation is empty, skipped, or otherwise non-interpretable

---

## Research topic 11 — Existing filled cells as prompt examples or format guidance

## Why this mattered

The app may benefit from knowing what kind of output a column typically contains: numeric, short categorical, long free-text explanation, units, or common formatting patterns.

The question was whether to use already-filled cells as examples in extraction prompts.

## Main conclusion

Do **not** use existing filled cells as free-form semantic few-shot examples by default.

Instead, run a **per-column preprocessing LLM** over existing filled cells to create a structured style/format profile. Heuristic-only default shaping is not sufficient. That profile may guide extraction output shape, tone, and level of detail, but not likely scientific content.

## Why this conclusion won

### Potential upside is mostly about output shape

Existing entries can help communicate:
- expected output length
- numeric vs short text vs long text
- formatting conventions
- common units or style patterns

### Risks are substantial

Using real existing entries as semantic examples can create:
- hallucination or anchoring bias
- copying of irrelevant patterns
- overfitting to style or content
- leakage in Verify mode if the same cells are later scored or reviewed as targets

### A safer middle path exists

The research supports a safer design:
- use schema descriptions first
- derive a structured style/format profile from existing cells using a preprocessing LLM
- avoid heuristic-only format inference
- avoid feeding raw semantic examples by default

## Recommended MVP design

- Use `column_name` and `description` as the primary specification.
- Use a preprocessing LLM for every column to derive a structured style/format profile from existing entries.
- Keep that profile limited to output shape and formatting, not semantic content.
- Avoid using raw existing cells as few-shot semantic exemplars by default.
- Do not allow example-derived guidance to override evidence from the current PDF.

## Consequences for implementation

This supports:
- schema-first extraction
- preprocessing-LLM column style profiling
- stronger distinction between format guidance and semantic evidence
- future leakage-aware Verify mode design if automated scoring is ever added

---

## Research topic 12 — Figures, charts, and vision-based fallback extraction

## Why this mattered

Some target fields may be stated only or most clearly in figures, especially charts, panel figures, diagrams, and image-heavy result summaries.

The question was whether the app should include a vision-capable path for extracting information from figures, and if so, how that should fit into the workflow without turning the whole system into a multimodal-by-default pipeline.

## Main research conclusion

The strongest research-backed pattern is still:

1. parse text, captions, and tables first
2. run normal schema-driven extraction
3. if a field remains unresolved or weakly supported, escalate to a figure-aware vision step
4. store the result as a normal proposal with explicit figure-based evidence and review cues

In other words, **vision works best as a targeted fallback**, not as the default extraction path for every page.

## Important note about current product direction

The current product direction is broader than the narrowest research recommendation:

- figure-aware fallback is in MVP
- all figure types are in scope
- all target field types may trigger figure fallback
- the heavier reasoning-plus-vision path still uses scoped triggers
- complex image-heavy figures are not excluded from scope

This is a valid product choice, but it is broader and riskier than the most conservative research recommendation. It increases the importance of:
- clear visual evidence display
- figure-based support labels
- strong human review expectations
- explicit monitoring of figure-derived proposal outcomes

## Why the fallback design still won at the research level

### Vision is feasible, but expensive and noisier than text-first extraction

Modern multimodal systems can use page images and figure crops effectively, especially for focused extraction prompts, but running vision over every page by default would add significant cost, latency, and operational complexity.

### A fallback design matches how strong existing systems behave

Established multimodal document systems often ingest both text and visuals, but only route images/pages to a vision model when retrieval or document structure suggests that visual reasoning is likely useful.

### Human review remains essential

Figure-derived values are often more ambiguous than table- or text-derived values. The review UI therefore becomes even more important for these cases.

## Recommended product behavior

The app should add a **figure fallback stage** after normal text/table extraction and evidence recovery.

### Suggested trigger conditions

Trigger the figure fallback when one or more of these are true:

- the field appears likely figure- or table-derived
- text/table extraction failed or remained insufficient
- the user explicitly requested fallback
- retrieved chunks mention figures, panels, or captions prominently
- the parser identified candidate figure-bearing regions/pages

The routing decision can be made by the extraction path itself, including an LLM-assisted decision, as long as it stays within these scoped triggers and does not make vision the default path for all fields.

## Suggested figure-fallback inputs

The vision step should receive a tightly scoped package rather than the whole paper:

- figure crop if available, otherwise page image
- figure caption
- nearby narrative text mentioning the figure
- row context
- target column definition
- structured extraction schema

## Suggested outputs

The figure fallback should produce a normal proposal object, but with figure-aware evidence metadata such as:

- evidence source type = `figure`
- figure/page identity
- caption text
- page anchor and/or crop reference
- vision model metadata
- extraction mode such as `caption_only`, `caption_plus_figure`, `chart_to_table`, or `page_vision`

## Recommended architecture for visual support

### Stage A — Ingestion-time figure preparation

At parse time, the pipeline should extract or register:

- figure or picture items when available
- associated captions
- page images or figure crops when needed
- optional figure type classifications
- links from figures to surrounding text

### Stage B — Text/table-first extraction

Normal extraction should still operate first on:

- narrative text
- tables
- captions
- document metadata

### Stage C — Figure fallback

Only unresolved or weak cases should escalate to a vision-capable extraction pass.

### Stage D — Review

The review UI should show:

- the proposed value
- whether the evidence came from figure/text/table
- the caption
- the crop image
- the full page
- the relevant page number and source context

## Figure types and expected difficulty

### Charts — highest-value early target

Bar charts, line charts, and pie charts are the most realistic early target because they are comparatively structured and increasingly supported by chart-understanding tooling.

### Diagrams and workflows — moderate difficulty

These can often support categorical or descriptive extraction, but are less reliable for precise quantitative extraction.

### Compound scientific figures — hard

Multi-panel figures with shared captions and panel-specific meanings are significantly harder and may require specialized panel/subcaption alignment logic.

### Microscopy, gels, blots, heatmaps — hard to very hard

These are difficult, but they are in the current product scope. That means the product must rely heavily on human review and evidence display rather than implying broad fully automatic reliability.

## Figure evaluation boundary

MVP does not require a separate automated evaluation track for figure-derived proposals. Figure-based evidence should remain visible and reviewable, but usefulness is assessed through the same human reviewer outcomes used elsewhere in the product.

## Useful tools and how they could help

### Docling

Docling is the most immediately useful tool in the current stack for visual support because it can:

- export figure, table, and page images
- preserve figure/picture objects in the parsed representation
- associate captions with visual elements
- classify picture types
- enrich supported charts into structured table-like data

### GROBID

GROBID is not a vision tool, but it remains useful because it improves scholarly structure and metadata extraction, which helps locate and interpret figure references in the surrounding text and captions.

### Low-level PDF layer

A low-level PDF access layer remains useful for:

- page rendering
- figure/page crop extraction
- fallback page text and geometry
- evidence anchoring in the review UI

### PDFFigures2-style figure extraction

A specialized scholarly figure-extraction component can be useful if the product later needs stronger figure/caption localization or compound-figure handling beyond what the primary parser provides.

### Figure/chart-specific rescue tools

Chart-focused tools or chart-to-table conversion methods are especially useful if the schema includes numeric values that may appear only in plots.

### Vision-capable LLM or multimodal model

A vision-capable model is useful for:

- targeted extraction from figure crops or pages
- interpreting diagrams or chart labels when text retrieval was insufficient
- combining caption text plus image evidence in one structured extraction step

## Consequences for the rest of the documents

This research suggests that both `spec.md` and `plan.md` should acknowledge:

- figure-aware evidence sources
- vision fallback as a non-default extraction path
- broader figure support in the current product scope
- figure-based review evidence in the UI
- human review as the governing evaluation path for figure-derived proposals

---

## Research topic 13 — Licensing and deployment constraints

## Why this mattered

The chosen stack needs to remain compatible with the project’s intended distribution and usage model.

## Main conclusion

Licensing must remain visible in planning, especially for the low-level PDF layer.

## Current conclusion

- The parser stack choice is technically sound.
- PDFium via pypdfium2 is the chosen low-level PDF backend for MVP, while the small backend abstraction preserves future flexibility.

## Deployment conclusions

- Local-first deployment remains the correct v1 assumption.
- Optional cloud fallbacks must be clearly disclosed in configuration and documentation.
- Provider/model transparency should appear in a concise run summary, not only in deep logs.

## Consequences for implementation

This supports:

- local-first default behavior
- provider transparency in summaries, logs, and config
- keeping the low-level PDF layer swappable

---

## Rejected or deferred alternatives

## 1. Generic RAG/chat platform as the main foundation

### Why considered

It could have provided ingestion, retrieval, and agent plumbing quickly.

### Why rejected for v1

The product is not primarily chat. The spreadsheet review/export workflow would become an awkward extension rather than the core design.

---

## 2. Multi-agent / graph-first architecture from day one

### Why considered

It could help with retries, decomposition, and future claim/evidence loops.

### Why rejected for v1

It adds complexity before the workflow requires it. The current product is mostly a structured pipeline with targeted model calls.

---

## 3. Permanent single-parser-with-no-abstraction design

### Why considered

It would simplify implementation.

### Why rejected for v1

A clean parser abstraction is still valuable even if only one main parser ships first. The rejected alternative is not “one main parser first”; it is “hard-code one parser forever with no abstraction or fallback planning.”

---

## 4. Database-only persistence

### Why considered

It would centralize state.

### Why rejected for v1

Filesystem artifacts are too valuable for reproducibility, debugging, and export bundling.

---

## 5. In-place workbook mutation

### Why considered

It sounds convenient for users.

### Why rejected for v1

Workbook fidelity risks are too high, and the audit model is cleaner with generated outputs.

---

## 6. Multi-user review in v1

### Why considered

It could support shared curation workflows.

### Why rejected for v1

It would add substantial complexity around authentication, concurrency, and review-state ownership before the core product is proven.

---

## Open research questions

These questions remain open and should be resolved explicitly rather than assumed away:

- How much measured lift does table-aware retrieval provide over simpler typed chunk retrieval on realistic paper batches?
- Which figure categories deliver enough reviewer value to justify deeper visual tooling beyond the scoped fallback path?
- At what point does synchronous execution become unacceptable for the target batch sizes, justifying the first background-job layer?
- Which provider capability probes are sufficient to distinguish reliable structured-output support from prompt-only JSON behavior?
- What is the minimum saved-view or queue-preset feature set that materially improves review speed without adding UI complexity?
- Which JSON files inside the artifact bundle are safe to treat as stable interfaces for tooling and tests in MVP, and which should remain internal implementation details?

---

## Recommendations for next documents

This research supports the current direction of `plan.md` and suggests the following documentation additions only when they become useful:

1. optional ADRs
   - low-level PDF library and licensing posture
   - background-job/runtime choice if synchronous execution becomes insufficient
   - workbook fidelity policy
   - parser baseline decision
   - UI shell or viewer-stack decision

2. README or runbook additions
   - a small real-example set
   - stub/synthetic PDFs for deterministic testing
   - figure-heavy test examples
   - Verify-mode review outcome tracking examples

---

## Concise summary

The current research supports a clear implementation direction:

Paper Table Agent should be built as a **local-first, workflow-centered paper-to-table review system** with:

- a dedicated queue-first local browser app built around a React frontend, a FastAPI backend, and a raw/custom PDF.js review viewer
- Docling as the main parser with PDFium/pypdfium2 as the complementary low-level PDF backend for rendering/geometry/crops/highlight support and fallback page/image access
- OCRmyPDF plus Tesseract as the scanned-PDF fallback
- typed retrieval units with source-preserving evidence display
- filesystem artifact bundles and JSON files as the complete MVP persistence model
- a deterministic app-owned staged runner executed synchronously first inside FastAPI
- LM Studio localhost API as the default structured-output provider
- reviewer-outcome-based MVP evaluation
- preprocessing-LLM-derived style/format profiles rather than raw semantic examples
- figure-aware fallback with scoped triggers for the heavier reasoning-plus-vision path
- reviewed XLSX export into a new workbook and audit log with content-only fidelity plus changed-cell highlighting

It also needs explicit measurement integrity requirements so empty or non-interpretable evaluation states cannot quietly masquerade as normal results.

This keeps the system aligned with its actual purpose: trustworthy human-reviewed extraction from scientific papers into structured tables.
