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
- `data-model.md` by explaining why certain entities and boundaries exist

Where a conclusion is still provisional, it is marked clearly with `TODO` or `[NEEDS MORE RESEARCH]`.

---

## Status

Draft

This document contains current conclusions plus explicit open questions. It should be updated whenever a major implementation decision changes.

---

## Research questions

The main research questions for this phase were:

1. Which PDF ingestion/parsing stack best fits scientific papers plus evidence review?
2. How should parsed outputs be normalized for retrieval and reviewer-visible evidence?
3. What retrieval design best supports schema-driven extraction from papers?
4. What UI shape best supports proposal review with PDF evidence?
5. Which technical stack best fits a local-first desktop review UI?
6. How should spreadsheet export work, and what are the realistic fidelity limits?
7. What should be canonical state: filesystem artifacts, database state, or both?
8. Does v1 need an orchestration/agent framework, or is a deterministic pipeline enough?
9. What background-job model best fits a local-first app?
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
- The current best low-level PDF recommendation is **PDFium via pypdfium2** as the authoritative low-level PDF backend for MVP because it balances rendering/highlight/crop capabilities with a safer licensing posture than PyMuPDF/MuPDF. :contentReference[oaicite:6]{index=6}
- The system should normalize parser outputs into one internal **parsed-document contract**.
- Retrieval should operate over **typed chunks** and may use contextualized `retrieval_text`, but reviewer-visible evidence must remain anchored to source-preserving text.
- Table-aware retrieval looks like a likely structural improvement for this product, but more advanced retrieval helpers must prove lift before becoming baseline.
- The review experience requires a **dedicated Run/Review UI**, and the strongest current MVP recommendation is a **queue-first / list-detail review workflow** rather than a spreadsheet-first or wizard-only design. :contentReference[oaicite:7]{index=7}
- The strongest current UI stack recommendation is a **desktop wrapper around a web app**, specifically **Tauri 2 + React + TypeScript + Vite + PDF.js + TanStack Table/Virtual + a Python FastAPI sidecar + SQLite**. :contentReference[oaicite:8]{index=8}
- The system should use **filesystem run artifacts as the canonical run bundle** and **SQLite as the operational review/query store**.
- Export should generate a **new updated XLSX workbook plus audit log**, not patch arbitrary workbooks in place, and **openpyxl** is the most realistic Python round-trip engine for that MVP behavior. Advanced workbook artifacts should remain best-effort or out of guarantee. :contentReference[oaicite:9]{index=9}
- The implementation should use a **deterministic staged pipeline first**, with only targeted LLM-assisted stages.
- The strongest current MVP runtime recommendation is **an app-owned staged runner plus Huey with SqliteHuey** for background execution, rather than graph-first orchestration or a heavier workflow platform. :contentReference[oaicite:10]{index=10}
- Structured outputs should be the **default contract path**, with capability probes and graceful fallback for weaker providers.
- Heavy orchestration or graph-first agent systems should be **deferred** unless measured workflow complexity clearly justifies them.
- In MVP, evaluation should be based primarily on **reviewer-outcome statistics**, not on a single automated “correctness score” over heterogeneous field types.
- Existing filled spreadsheet cells should **not** be used as free-form semantic few-shot examples by default. If used at all, they should act as **format/style guidance only**, with explicit safeguards against hallucination and evaluation leakage. :contentReference[oaicite:11]{index=11}
- Figure-derived proposals should be monitored as a **separate evidence lane** with their own reviewer-outcome and reviewer-effort metrics from day one. :contentReference[oaicite:12]{index=12}

### Provisional conclusions

- GROBID may still be useful, but it should be optional or deferred unless measured lift justifies making it part of the default shipping path.
- Dense retrieval, reranking, HyDE, query expansion, and memory-style context modes may still be useful, but they must prove lift before becoming baseline behavior.
- Automated per-run scoring for Verify mode may still be useful later, but it is not necessary for MVP.
- A paid PDF-viewer layer may still be attractive later for faster delivery or richer annotation ergonomics, but the default recommendation remains a custom PDF.js-based evidence viewer. :contentReference[oaicite:13]{index=13}

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

- **one main parser** as the primary parser for v1
- **PDFium via pypdfium2** as the low-level PDF layer for page rendering, text search, coordinate mapping, highlighting support, and crop generation
- **parser abstraction preserved** so additional parsers can be added later if measured lift justifies it :contentReference[oaicite:14]{index=14}

## Why this combination won

### One main parser first

The prior implementation suggests that multi-parser runtime complexity should not be baseline behavior. The rewrite should start with one main parser that is good enough for the product loop and keep the contract stable around it.

### Likely initial main parser

Docling still looks like the strongest initial candidate because it is strong on structured document conversion, layout-aware parsing, figure/image extraction, and chart/table support.

### Low-level PDF layer choice

The current strongest recommendation is PDFium via pypdfium2 because it provides:
- page rendering with cropping
- text extraction/search with boxes/rectangles
- page-to-bitmap coordinate conversion
- page/image object access
- a more product-friendly licensing posture than PyMuPDF/MuPDF :contentReference[oaicite:15]{index=15}

### Why PyMuPDF is not the default

PyMuPDF/MuPDF looks excellent technically, but the AGPL/commercial licensing model makes it a riskier default for an MVP that may later want flexible distribution options. :contentReference[oaicite:16]{index=16}

### Why PDF.js is not the backend source of truth

PDF.js is the strongest open viewer foundation in the browser layer, but it is not the best sole backend source of truth for persistent anchoring, crop generation, and geometry authority. :contentReference[oaicite:17]{index=17}

### GROBID

GROBID remains a plausible enrichment path because it is specialized for scientific papers and may improve metadata and structure extraction, but it should not be assumed to be baseline shipping behavior unless measured lift justifies it.

## Implications for implementation

- Parser outputs must normalize into one internal format.
- The parser layer should be adapter-based even if only one main parser ships initially.
- The low-level PDF layer should be wrapped behind a small internal interface.
- Evidence anchors should be stored in canonical page coordinates, not viewer pixel coordinates. :contentReference[oaicite:18]{index=18}

## TODO / open follow-up

- [TODO: Confirm pypdfium2/PDFium as the final low-level PDF default after licensing posture review.]
- [TODO: Decide whether GROBID is in first shipping scope or deferred until measured lift is shown.]
- [TODO: Evaluate whether a table-specific rescue parser should be included in v1 or deferred to a later phase.]
- [TODO: Decide the OCR sidecar choice for image-only/scanned pages.]

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

## TODO / open follow-up

- [TODO: Decide whether full `ParsedElement` records need to be persisted in the operational DB or whether parser artifacts plus derived chunks are enough for v1.]
- [TODO: Define the exact normalized contract versioning strategy.]

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

## TODO / open follow-up

- [TODO: Decide the minimal retrieval stack for v1 before optional helpers are reconsidered.]
- [TODO: Decide the default context strategy and fallback for v1.]
- [TODO: Define the minimum required evidence states for the stable contracts.]
- [TODO: Define the first simple locator path for evidence anchoring and review.]
- [TODO: Decide whether table-cell summary chunks are part of v1 or introduced in P1.]

---

## Research topic 4 — Review UI and interaction model

## Why this mattered

The product’s core value is not just extraction. It is the ability for a human to review proposals safely and efficiently.

## Main conclusion

A dedicated **Run/Review UI** is required, and the strongest current recommendation is a **queue-first / list-detail review workflow**. :contentReference[oaicite:19]{index=19}

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

The strongest current recommendation is:

- a **proposal queue** or list on one side
- a **focused detail pane** for the currently selected proposal
- a **document/evidence viewer** showing the highlighted PDF page or figure crop/full page
- progress counters and filter controls visible in the main review workspace :contentReference[oaicite:20]{index=20}

This is preferable to:
- a pure spreadsheet-first UI as the main review surface
- a strict single-proposal wizard with no queue context

### Why this recommendation won

- It supports nonlinear review.
- It supports filtering and triage.
- It supports evidence-heavy decision making.
- It scales better when many proposals exist.
- It allows step-by-step review without forcing a rigid path. :contentReference[oaicite:21]{index=21}

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

## TODO / open follow-up

- [TODO: Finalize the frontend PDF-viewer choice and document the coordinate system used in highlight anchors.]
- [TODO: Decide whether bulk acceptance should apply to all remaining proposals or only to the currently visible filtered subset.]
- [TODO: Define the minimum MVP review filters, counters, and keyboard actions.]
- [TODO: Define the reviewer-facing labels for support states, e.g. “Direct evidence” vs “Inferred from evidence”.]

---

## Research topic 5 — UI technical stack

## Why this mattered

The product needs not only the right interaction model, but also the right implementation stack for:
- local-first file handling
- queue-based review UI
- PDF evidence rendering
- modern desktop UX
- integration with Python-heavy extraction logic

## Main conclusion

The strongest current MVP stack recommendation is:

- **Tauri 2** as the desktop shell
- **React + TypeScript + Vite** for the frontend
- **Tailwind + shadcn/ui** or a similarly lightweight custom component layer
- **TanStack Table + TanStack Virtual** for the review queue
- **PDF.js** as the core PDF evidence viewer
- **Python + FastAPI** packaged as a sidecar for extraction/review backend logic
- **SQLite** for local persistence :contentReference[oaicite:22]{index=22}

## Why this conclusion won

### Desktop wrapper around a web app beats browser-only MVP

A local browser app is fine for rapid prototyping, but a packaged desktop shell provides cleaner file handling, a more controlled runtime environment, and a more dedicated work-tool experience. :contentReference[oaicite:23]{index=23}

### Tauri is a better fit than Electron for this MVP

Tauri provides a strong local desktop shell without bundling a full Chromium runtime into every build, which better matches a local-first single-user scientific workbench. :contentReference[oaicite:24]{index=24}

### React ecosystem fit is strongest for this UI

The product depends on:
- advanced tables/queues
- PDF viewer integrations
- complex split-pane layouts
- custom evidence overlays

That ecosystem fit is strongest in React.

### PDF.js should remain the evidence-viewer foundation

PDF.js is the best open-source foundation for a browser/webview PDF evidence viewer, even if a more opinionated wrapper or commercial SDK could accelerate later implementation. :contentReference[oaicite:25]{index=25}

## Consequences for implementation

This research supports:

- a desktop-web hybrid architecture
- a React-first frontend
- Python extraction logic remaining in the architecture
- queue-first review implemented with headless table logic rather than a spreadsheet-first enterprise grid
- PDF evidence modeled in normalized page coordinates independent of the viewer implementation

## TODO / open follow-up

- [TODO: Decide whether MVP uses raw PDF.js with a custom evidence viewer or a paid wrapper/SDK for faster delivery.]
- [TODO: Decide whether AG Grid Community should be kept as a fallback if the queue becomes more spreadsheet-like than expected.]
- [TODO: Decide how much of the backend remains in Python versus any future Rust/desktop-native pieces.]

---

## Research topic 6 — Spreadsheet export and workbook fidelity

## Why this mattered

The product ends by updating spreadsheet content. This seems simple, but real Excel workbooks can contain formatting, formulas, charts, shapes, macros, and other artifacts that are difficult to preserve perfectly.

## Main conclusion

The product should generate a **new updated workbook plus an audit log**, not patch arbitrary workbooks in place.

## Current product-aligned conclusion

The current product direction is:

- export to a **new XLSX workbook**
- preserve formatting for the **main table sheet**
- visually highlight cells changed through accepted proposals
- keep the original input workbook unchanged

The most realistic Python round-trip engine for this is **openpyxl**. XlsxWriter is excellent for generating new files from scratch but cannot read/modify an existing workbook. xlwings can achieve higher fidelity through native Excel automation, but it is too platform- and installation-dependent to be the default MVP boundary. :contentReference[oaicite:26]{index=26}

## Practical expectation for v1

Preserving the main table sheet layout and ordinary cell formatting is part of the product promise. Perfect preservation of all advanced workbook features across arbitrary workbooks should not be assumed unless explicitly proven and documented.

The strongest current product boundary is:

### Realistic to guarantee on the main table sheet
- ordinary cell values and formulas on untouched cells
- ordinary cell formatting on untouched cells
- row/column sizing and hidden state
- freeze panes
- existing filters
- merged ranges, as long as the app does not structurally rewrite them

### Best-effort only
- conditional formatting
- comments
- named ranges

### Out of scope / no guarantee
- charts
- shapes
- images/drawings
- macros
- arbitrary workbook-wide advanced artifacts outside the main table sheet :contentReference[oaicite:27]{index=27}

## Consequences for implementation

This research directly supports the `plan.md` export strategy and the current product requirement that changed cells be visually highlighted.

## TODO / open follow-up

- [TODO: Define the exact scope of workbook fidelity promised for the main table sheet, especially for formulas, filters, frozen panes, hidden columns, merged cells, conditional formatting, comments, and named ranges.]
- [TODO: Decide whether workbooks with charts/shapes should be warn-only or hard-blocked in MVP.]
- [TODO: Decide whether CSV export parity needs to be documented separately.]

---

## Research topic 7 — Persistence model and artifact strategy

## Why this mattered

The app needs:

- reproducibility
- resumability
- inspectability
- efficient review queries
- auditability

A single storage approach does not serve all of those equally well.

## Main conclusion

Use a hybrid model:

- **filesystem run artifacts** as the canonical audit/reproducibility bundle
- **SQLite** as the operational state/query/checkpoint store

## Why this combination won

### Filesystem artifacts are best for

- debugging
- packaging runs
- preserving parser outputs and logs
- reproducibility

### SQLite is best for

- proposal lists
- review state
- filtering/triage
- checkpoints
- export bookkeeping

## Consequences for implementation

This directly supports the distinction in `plan.md` between canonical artifacts and operational DB state.

## TODO / open follow-up

- [TODO: Decide whether every parser artifact should be registered explicitly as a first-class `RunArtifact`, or only stable artifact categories.]
- [TODO: Document the exact resume/checkpoint model in a later technical note or contract.]

---

## Research topic 8 — Orchestration and background jobs

## Why this mattered

The pipeline contains long-running stages such as parsing, indexing, extraction, narrow evidence-location support, export, and evaluation.

The question was whether v1 should be built around a heavyweight orchestration/agent framework or a simpler job pipeline.

## Main conclusion

The app should use a **deterministic app-owned staged runner first** with a lightweight background job library. The strongest current MVP recommendation is **Huey + SqliteHuey**, with the queue library used only to execute stages, not to own workflow logic. :contentReference[oaicite:28]{index=28}

## Why this conclusion won

- It preserves a simple staged pipeline.
- It avoids graph-first orchestration.
- It avoids requiring Redis or heavier workflow servers for MVP.
- It still provides retries, scheduling, locks, revocation/rescheduling, and background execution. :contentReference[oaicite:29]{index=29}

### Why not heavier orchestrators

Prefect and Temporal solve bigger problems than the current MVP needs. Temporal especially is justified only if durable workflow replay becomes a top-tier requirement.

### Why not let the queue own the workflow

The reports strongly recommend that the app own:
- stage order
- progress semantics
- artifacts
- retries
- resume logic

The queue library should only run stage jobs in the background. :contentReference[oaicite:30]{index=30}

## Consequences for implementation

This research supports:

- simple stage-based pipeline execution
- background execution through Huey
- explicit checkpoints at stage boundaries
- “resume from last committed stage” semantics rather than durable replay of arbitrary mid-stage execution

## TODO / open follow-up

- [TODO: Confirm Huey + SqliteHuey as the final MVP runtime choice.]
- [TODO: Decide whether RQ becomes the fallback if Redis is acceptable and more queue visibility is desired.]
- [TODO: Decide whether the narrow evidence-location step should run inline in extraction or as a separate queued stage.]

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

## TODO / open follow-up

- [TODO: Define the minimum provider capability matrix required for supported local-first operation.]
- [TODO: Decide whether provider fallback by role is required in v1 or optional for later.]
- [TODO: Define what provider/model transparency must appear in the normal run summary versus only in advanced logs.]

---

## Research topic 10 — Evaluation strategy and measurement integrity

## Why this mattered

The app needs both engineering regression protection and product-level usefulness measurement.

The key question was whether MVP should attempt an automated Verify-mode score across heterogeneous cell types, or whether it should use a simpler and more trustworthy measure.

## Main conclusion

For MVP, evaluation should be based primarily on **reviewer-outcome statistics**, not on a single automated “correctness score” over heterogeneous field types.

## Recommended MVP measurement model

The strongest current recommendation is to measure:

- proposal coverage
- reviewed proposal count
- accepted as-is count/rate
- accepted with edit count/rate
- rejected count/rate
- per-column reviewer outcome breakdown
- evidence coverage
- evidence display / highlight success
- matched / unmatched / ambiguous PDF counts :contentReference[oaicite:31]{index=31}

This is more trustworthy and easier to interpret than an automated aggregate score over free text, numeric, categorical, range, and reasoning-heavy fields.

## Why this conclusion won

### Human review is already the product’s ground truth

Since the product requires expert review before export, the reviewer’s decision is the most natural MVP signal of usefulness.

### Automated scoring is hard across mixed field types

A single automated scoring method that handles all field types well is possible later, but not necessary for MVP.

### Reviewer-outcome metrics are more honest for a first release

They align directly with the product’s purpose: reducing reviewer effort while preserving trust.

## Evaluation hygiene and leakage

If filled cells from the same table are used both as prompt examples and as evaluation/verification targets, scores can be inflated.

The rewrite should therefore plan for leakage-safe evaluation rules, including split-aware example exclusion or equivalent safeguards, before treating any verify-mode metric as strong evidence of product quality.

## Measurement integrity requirements

A run that produces many proposals and many evidence attachments is not necessarily a good run.

A run with empty or non-interpretable evaluation should be treated as a meaningful diagnostic state, not as a normal artifact. If no relevant reviewed/verified targets were evaluated, that state should be explicit and reviewer-visible rather than collapsing into an apparently valid zeroed summary.

## Consequences for implementation

This supports the current split between:

- synthetic/parser fixtures
- application-level review/verify summaries
- first-class run-level metrics that keep proposal rate, evidence rate, and reviewer acceptance separate
- explicit warning states when evaluation is empty, skipped, or otherwise non-interpretable

## TODO / open follow-up

- [TODO: Define the initial run-level required metrics for proposal production, evidence coverage, reviewer outcomes, and review effort.]
- [TODO: Define leakage-safe verify/evaluation rules when existing cells are also used for prompt shaping.]
- [TODO: Decide whether a future automated score should exist in addition to reviewer-outcome metrics.]
- [TODO: Decide which public datasets, if any, become part of regular regression testing rather than one-time research.]

---

## Research topic 11 — Existing filled cells as prompt examples or format guidance

## Why this mattered

The app may benefit from knowing what kind of output a column typically contains: numeric, short categorical, long free-text explanation, units, or common formatting patterns.

The question was whether to use already-filled cells as examples in extraction prompts.

## Main conclusion

Do **not** use existing filled cells as free-form semantic few-shot examples by default.

The strongest current recommendation is to use them, if at all, only as **non-binding format/style guidance**, not as semantic evidence for what the answer should be. :contentReference[oaicite:32]{index=32}

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
- optionally derive a style/format profile from existing cells
- avoid feeding raw semantic examples by default
- if examples are ever used, constrain them to low-risk field types and exclude them from evaluation targets :contentReference[oaicite:33]{index=33}

## Recommended MVP design

- Use `column_name` and `description` as the primary specification.
- Allow optional **format/style guidance** derived from existing column entries.
- Keep that guidance limited to output shape and formatting, not semantic content.
- Avoid using raw existing cells as few-shot semantic exemplars in Verify mode.
- Do not allow example-derived guidance to override evidence from the current PDF.

## Consequences for implementation

This supports:
- schema-first extraction
- optional column style profiling
- stronger distinction between format guidance and semantic evidence
- leakage-aware Verify mode design

## TODO / open follow-up

- [TODO: Decide which field types may use format/style guidance in v1, e.g. numeric, boolean, categorical, ranges, templated short text.]
- [TODO: Decide whether format/style guidance should be derived heuristically or generated by a preprocessing model.]
- [TODO: Define the minimum safeguards if real existing entries are ever used more directly in prompts.]

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

- no proposal was produced from text/tables
- a proposal exists but `needs_more_evidence=true`
- the schema or product policy indicates figure-based information is plausible
- retrieved chunks mention figures, panels, or captions prominently
- the parser identified candidate figure-bearing regions/pages

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

## Figure-derived proposal monitoring

The strongest current monitoring recommendation is to treat figure-derived proposals as a **separate assistance lane** with their own metrics, rather than folding them into overall extraction metrics. Useful MVP metrics include:

- figure proposal count/share
- accept-as-is rate
- accept-with-edit rate
- reject rate
- median review time
- evidence-open rate
- edit burden
- figure-only fill contribution
- failure-code breakdown
- sampling-based second-review precision on accepted figure proposals :contentReference[oaicite:34]{index=34}

Figure classes should be tracked separately in a small taxonomy, such as:
- chart / quantitative plot
- diagram / schematic
- image-based scientific figure
- composite / mixed / other :contentReference[oaicite:35]{index=35}

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
- monitoring of figure-derived proposal outcomes separately enough to validate the broad MVP scope

## TODO / open follow-up

- [TODO: Define the minimum figure evidence object needed in `data-model.md` and `contracts/`.]
- [TODO: Decide whether a first-class `FigureItem` entity is needed or whether figure support can begin as parser/caption metadata plus evidence anchors.]
- [TODO: Evaluate whether chart-to-table enrichment is stable enough to include in the first shipping parser path.]
- [TODO: Define how figure-derived proposal outcomes should be tracked separately enough to monitor whether the broad MVP scope is working.]

---

## Research topic 13 — Licensing and deployment constraints

## Why this mattered

The chosen stack needs to remain compatible with the project’s intended distribution and usage model.

## Main conclusion

Licensing must remain visible in planning, especially for the low-level PDF layer.

## Current conclusion

- The parser stack choice is technically sound.
- The exact default low-level PDF implementation should remain somewhat provisional until licensing posture is explicitly documented.

## Deployment conclusions

- Local-first deployment remains the correct v1 assumption.
- Optional cloud fallbacks must be clearly disclosed in configuration and documentation.
- Provider/model transparency should appear in a concise run summary, not only in deep logs. :contentReference[oaicite:36]{index=36}

## Consequences for implementation

This supports:

- local-first default behavior
- provider transparency in summaries, logs, and config
- keeping the low-level PDF layer swappable

## TODO / open follow-up

- [TODO: Write a short licensing posture note covering internal use, open-source release, and possible future commercial/distributed scenarios.]
- [TODO: Confirm whether any cloud rescue paths should be completely out of scope for v1.]

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

These questions remain open and should be resolved explicitly rather than assumed away.

- [NEEDS MORE RESEARCH: What exact workbook fidelity guarantees should be promised for the main table sheet in v1 documentation?]
- [NEEDS MORE RESEARCH: Which background job/runtime library is the final concrete fit for v1, and is Huey + SqliteHuey sufficient once packaging and failure semantics are tested?]
- [NEEDS MORE RESEARCH: Which UI component stack best supports queue-first review, PDF highlighting, figure crop/full-page display, and efficient local-first desktop use?]
- [NEEDS MORE RESEARCH: Should a future automated Verify-mode score exist in addition to reviewer-outcome metrics, and if so, how should it be designed?]
- [NEEDS MORE RESEARCH: Which field types may safely use style/format guidance derived from existing filled cells in MVP?]
- [NEEDS MORE RESEARCH: What is the most robust way to monitor figure-derived proposal quality separately enough to validate the broad MVP figure scope?]
- [NEEDS MORE RESEARCH: Should a table-specific rescue parser be included in v1 or deferred?]
- [NEEDS MORE RESEARCH: Should full parsed elements be persisted in the operational database or only in artifacts with chunk projections stored in DB?]
- [NEEDS MORE RESEARCH: What exact provider/model transparency must appear in the normal run summary versus only in advanced logs?]

---

## Recommendations for next documents

This research supports the current direction of `plan.md` and suggests the following next deliverables:

1. `contracts/`
   - run create/status
   - proposal list/detail
   - review decision submission
   - export status/result

2. `tasks.md`
   - executable implementation sequence derived from the plan

3. optional ADRs
   - low-level PDF library and licensing posture
   - background-job/runtime choice
   - workbook fidelity policy
   - parser baseline decision
   - UI shell/stack decision

4. quickstart / fixture design
   - a small real-example set
   - stub/synthetic PDFs for deterministic testing
   - figure-heavy test examples
   - Verify-mode review outcome tracking examples

---

## Concise summary

The current research supports a clear implementation direction:

Paper Table Agent should be built as a **local-first, workflow-centered paper-to-table review system** with:

- a dedicated queue-first Run/Review UI
- a parser-contract-first ingestion stack
- one main parser first, with optional later enrichments if they prove lift
- PDFium/pypdfium2 as the low-level PDF backend for rendering/anchoring/crops
- typed retrieval units with source-preserving evidence display
- filesystem artifacts plus SQLite operational state
- a deterministic staged runner with lightweight background jobs
- structured-output-first extraction with provider fallbacks
- reviewer-outcome-based MVP evaluation
- optional style/format guidance rather than semantic few-shot examples
- figure-aware fallback plus separate monitoring of figure-derived proposal quality
- reviewed export into a new workbook and audit log

It also needs explicit measurement integrity requirements so empty or non-interpretable evaluation states cannot quietly masquerade as normal results.

This keeps the system aligned with its actual purpose: trustworthy human-reviewed extraction from scientific papers into structured tables.