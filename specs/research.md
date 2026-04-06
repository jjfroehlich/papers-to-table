# Extract Structured Info from Papers — `research.md`

## Purpose

This document summarizes the research that informed the current architecture and planning decisions for Extract Structured Info from Papers.

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

Updated: evidence quality, reviewer trust, text-guided targeted figure review, separate text/vision model direction, integrity/workflow refinements, and leakage-aware eval-mode rationale

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
- A stable **non-UI automation entrypoint** is still useful for downstream tooling such as optimizer loops, provided it reuses the same backend run pipeline and artifact contracts and does not displace the browser UI as the normal human workflow.
- The current practical MVP implementation direction is a **local browser app** centered on a **React frontend**, a **small Python FastAPI backend**, and a **raw/custom PDF.js evidence viewer**, with no desktop shell required for MVP. TypeScript, Vite, Tailwind, shadcn/ui, TanStack Table, and TanStack Virtual are sensible practical defaults rather than architectural requirements.
- The system should use **filesystem artifact bundles plus JSON files as the canonical and sufficient MVP state**, with no database required for MVP.
- Export should generate a **new updated XLSX workbook plus audit log**, not patch arbitrary workbooks in place, and **openpyxl** is the most realistic Python engine for that MVP behavior. The fidelity promise should be **content-only fidelity plus changed-cell highlighting**, with workbook behavior and advanced sheet features out of guarantee.
- The implementation should use a **deterministic staged pipeline first**, with only targeted LLM-assisted stages.
- The strongest current MVP runtime recommendation is that **runs are launched from the UI and executed under app-owned backend control using a lightweight in-process background mechanism for MVP; no external job framework is required**, with **Huey + SqliteHuey** as the first candidate background-job layer only if that approach later proves insufficient.
- Structured outputs should be the **default contract path**, with capability probes and a bounded recovery ladder rather than open-ended fallback behavior.
- Recent rebuild attempts showed that provider-path proof, readiness checks, and exact provider-contract parity must be explicit. A clean browser shell is not enough if the documented LM Studio path is broken, stubbed, mismatched, or silently degraded.
- The rebuild quality bar should require one canonical live-path proof target: the checked-in workbook fixture plus the checked-in set of four paper PDFs, with `tests/fixtures/tables/literature_fixture.xlsx` plus `tests/fixtures/papers/paper_1.pdf` as the default live-smoke pair, and text-based companion fixtures or assertions preferred over new binary artifacts.
- The provider architecture should remain **LM Studio first** for the local-default path, using the canonical config token `lm_studio`, while allowing **optional cloud providers behind the same typed interface**, using environment or secret-based credentials and opt-in live tests only.
- Heavy orchestration or graph-first agent systems should be **deferred** unless measured workflow complexity clearly justifies them.
- In MVP, evaluation should be based primarily on **reviewer-outcome summaries**, not on a single automated “correctness score” over heterogeneous field types.
- Existing filled spreadsheet cells should be processed through a **per-column preprocessing LLM** that produces a structured style/format profile. Heuristic-only default shaping is not sufficient, raw filled cells should **not** be passed into extraction prompts as semantic exemplars by default, and extraction must still work when a table or target column has no prefilled values.
- Figure-aware evidence should be **text-guided and targeted when vision capability is available**: the system should shortlist figures or panels using retrieved field text, caption relevance, and figure-reference snippets from the paper text before vision calls. Figure evidence may support any field type, strengthen text proposals, corroborate uncertain proposals, or rescue weak text-only results. The scope remains focused on shortlisted candidates rather than blanket per-page multimodal reasoning.
- **Evidence quality and reviewer trust are first-class requirements**: the system must rank evidence by source authority and field relevance rather than treating the first model-returned quote as automatically primary. Evidence types must be distinguished and labeled: direct quote, inferred reasoning, calculation, approximate highlight fallback, quote-plus-page fallback, `caption_grounded_figure_evidence`, and `visual_interpretation_figure_evidence`.
- **Exact quote highlighting should be produced from page-text alignment** rather than only from parser bounding boxes; if exact alignment fails, the system must degrade honestly to approximate highlight or quote-plus-page fallback, each clearly labeled as such.
- The review workspace must expose an ordered evidence list synchronized with the document viewer, with stable refocus when evidence or zoom changes.
- Reviewers still expect ordinary PDF-reading affordances. A practical MVP should preserve drag-based page movement, text selection and copy when the source PDF allows it, and an obvious path to browser-native PDF controls even when annotated evidence overlays are also supported.
- **Separate text-model and vision-model configuration** improves flexibility and transparency: the text model and vision model may differ, and both should be recorded in run artifacts and shown in reviewer-visible summaries.

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

Recent rebuild evidence adds three practical constraints to that baseline:

- provider contract parity must be enforced across runtime, config examples, docs, tests, and UI labels
- run-start preflight must catch provider, model, parser, dependency, and setup failures before nominal run execution
- completion should require either real proposal generation proof on the canonical fixture path or an explicit readiness failure, not a cosmetically complete app shell

Additional rebuild evidence from review-mode implementation adds four more practical constraints:

- reviewable proposals and diagnostics-only outcomes must be separate contracts, otherwise the UI will tend to load every blocked or skipped cell as if it were a review task
- reviewer-facing counts must distinguish actionable proposals from attempted-cell totals and diagnostic totals
- active-run visibility must not rely on manual refresh as the primary feedback path
- runtime-derived artifact filenames must be sanitized or abstracted so cross-platform filesystem differences do not surface as late-run failures
- evidence-viewer requirements must distinguish annotated evidence inspection from ordinary PDF reading, otherwise rebuilds tend to ship a technically correct canvas viewer that lacks normal pan/select/copy behavior

## Durable rebuild rules from recent testing

The latest rebuild and test cycle surfaced several rules that are broader than any one bug and should survive future implementation changes:

- Treat the README, checked-in config example, runtime config schema, and UI labels as one operator contract. Drift across those surfaces causes setup and review errors even when the underlying code path is otherwise functional.
- Keep at least one verified LM Studio model example in operator docs, but frame it as a known-working example rather than as the only acceptable model choice.
- Normalize commonplace ingestion artifacts at the boundary, especially BOM-affected CSV headers and Excel-native date or datetime cells.
- Persist resolved config and input context before deeper execution so readiness failures and early-run failures remain diagnosable in the UI and artifact bundle.
- Make parser selection explicit. Silent substitution from a configured parser to another parser hides real environment problems and breaks operator trust unless fallback was explicitly opted into and surfaced.
- Treat upstream parser API drift as a contract risk; normalize Docling iterator payload shape in the adapter and cover it with fixture-backed regression tests so text-based PDFs do not silently parse as empty.
- Treat structured-output support as a negotiated provider capability, not as one hardcoded protocol. Guided-JSON rejection should degrade gracefully only if the same proposal contract can still be validated, and one compatibility mismatch should not poison the rest of the run by default.
- Prefer `unclear` over guesses supported mainly by prior spreadsheet patterns, common practice, or weak implication rather than by current-paper evidence.
- Treat malformed model JSON as a partially recoverable transport or format problem first, not immediately as a semantic extraction failure. A compact repair-oriented recovery step is preferable to prematurely collapsing the target into a hard error.
- Quote plus page evidence remains valid reviewer evidence even when precise highlight geometry is unavailable.
- Treat low-text or parse-degraded papers as explicit diagnostics and degraded workflow states, not as normal-looking no-value review outputs.
- Treat figure review as incomplete unless real figure crop artifacts and page links are persisted for the same figures shown to the reviewer; caption-only figure metadata does not constitute a working vision path.
- Compute summary metrics and warnings from persisted facts, and distinguish provisional states from final results.
- Long-text fields need contract-level robustness; short-answer defaults and tight output shapes create systematic failure modes.
- A lower-quality parser fallback may still be useful for debugging or constrained environments, but it should be explicit opt-in behavior rather than a silent quality downgrade from a configured main parser.
- Treat already-filled cells outside Verify mode as out of scope, not as reviewer-facing blocked placeholders with synthetic rationale.
- Persist diagnostics for unmatched, ambiguous, duplicate-conflict, blocked, skipped, or failed outcomes, but do not assume each such record belongs in the main review queue.
- Make run cancellation and stale-refresh behavior explicit product concerns, not incidental UI polish.
- Reviewer-facing queue grouping should use meaningful citation context when available rather than leaking internal PDF ids as the primary label.
- Review ergonomics such as adjustable pane widths materially affect usability for evidence-heavy curation and should be specified rather than left to frontend taste.

These are not arguments for more fallback layers. They are arguments for tighter contracts, more truthful operator surfaces, and narrower but more reliable recovery behavior.

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

### Multiple evidence items are appropriate, but must be ranked

Some values are best supported by more than one snippet. The review surface should expose one primary evidence item and ordered supporting items. The primary item must be selected by evidence ranking, not by the arbitrary order in which the model returned quotes. Evidence ranking should consider source authority and field relevance.

### Evidence types must be distinguished and labeled

The system must distinguish: direct quote, inferred reasoning, calculation, approximate highlight fallback, quote-plus-page fallback, `caption_grounded_figure_evidence`, and `visual_interpretation_figure_evidence`. These are not interchangeable. A reviewer making a decision benefits from knowing whether quoted text is verbatim from the paper, caption-grounded, visually interpreted, or model-constructed.

### Exact quote highlighting requires page-text alignment

Parser bounding boxes give approximate region geometry but not character-level precision. Producing exact highlight overlays requires aligning the quote against the rendered page text layer. When that alignment succeeds, the result is an exact highlight. When it fails, the product must degrade honestly to an approximate highlight (labeled as such) or quote-plus-page fallback (also labeled). Presenting approximate geometry as exact undermines reviewer trust.

## Consequences for implementation

This research supports:

- typed chunks
- `retrieval_text`
- table-aware retrieval units
- `found` vs `inferred` proposal states
- a narrow evidence validator plus a simple locator path
- evidence ranking with primary and ordered supporting evidence
- evidence type taxonomy and distinct labels for each type
- page-text alignment for exact quote highlighting with honest labeled fallback
- synchronized quote list and document viewer
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
- visible run/reviewer summary context plus direct artifact-download affordances in the main review workspace
- progress counters and filter controls visible in the main review workspace

The default queue should favor actionable proposals over blocked or unresolved records, while still keeping blocked/unresolved items visible through warnings, filters, or dedicated inspection surfaces.

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

### Rationale formatting recommendation

Reviewer scanability improves when rationale is returned as concise markdown bullets rather than as dense prose.

The preferred guidance to the extraction layer is to request rationale in a compact bullet structure such as:
- `Observation`
- `Inference`

This is not mainly an aesthetic choice. It better matches rapid scientific review workflows, reduces dense paragraph explanations in the decision pane, and makes accept-with-edit and no-data review decisions faster to evaluate.

### Specification lesson from recent rebuilds

Recent rebuild attempts specified architecture, workflow sequencing, and runtime contracts more strongly than review information hierarchy and interaction details.

That left room for technically compliant but ergonomically weaker implementations, including:
- evidence that was present but visually weak
- flat noisy queues
- unclear handling of no-value states
- insufficiently interactive evidence review

For this product class, grouped triage behavior, explicit no-data handling, evidence interactivity, and visible distinctions between review state, support quality, and match outcome need to be specified as first-class requirements rather than left to implementation taste.

Recent implementation work added one more concrete lesson: a custom evidence overlay viewer alone is not enough. Reviewers often need the right pane to behave like a normal PDF reader for a stretch of time before they switch back to evidence-specific inspection. That means the spec should allow or require an explicit interactive reading mode, or an equivalent viewer foundation, rather than assuming highlight overlays alone satisfy evidence usability.

## Consequences for implementation

This research supports:

- dedicated review views
- a queue-first review model
- actionable-first queue ordering with blocked-item visibility preserved separately
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

However, recent implementation work also shows that a pure app-rendered canvas layer can under-deliver on ordinary PDF-reader ergonomics. For MVP, the safest contract is not “everything must be custom,” but “the evidence pane must preserve normal reading affordances as well as app-owned evidence behavior.” In practice, that can mean a hybrid approach where annotated evidence mode is app-owned while interactive reading mode relies on more native browser PDF behavior.

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

Within that artifact model, proposal identifiers still need to remain unique even when more than one PDF points at the same row/cell context, and review decisions should remain explicit persisted records so audit/export data can be reconstructed from artifacts rather than inferred from UI state alone.

---

## Research topic 8 — Orchestration and background jobs

## Why this mattered

The pipeline contains long-running stages such as parsing, indexing, extraction, narrow evidence-location support, export, and evaluation.

The question was whether v1 should be built around a heavyweight orchestration/agent framework or a simpler job pipeline.

## Main conclusion

Runs are launched from the UI and executed under app-owned backend control using a lightweight in-process background mechanism for MVP; no external job framework is required. If that approach later proves insufficient, **Huey + SqliteHuey** is the first likely queue layer.

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
- UI-launched execution under app-owned backend control using a lightweight in-process background mechanism, with no external job framework required for MVP

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
- a bounded recovery ladder: `json_schema`, `json_object` fallback only when `json_schema` is unsupported, explicit downgrade when the active request shape hits backend regex or grammar incompatibility, explicit prompt-only JSON fallback when both structured modes are unavailable, one stronger retry, bounded syntactic repair with wrapper stripping and balanced-object extraction, then fail

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

### Why `json_object` is the right bounded compatibility step

`json_object` is a useful bounded fallback because it still enforces a JSON object envelope and allows the same typed proposal validator to remain authoritative.

That preserves the core contract (validated structured proposals) without requiring open-ended prompt-only parsing behavior.

In contrast, broad prompt-only fallback increases silent contract drift risk and can blur the boundary between recoverable transport or formatting errors and true extraction failures. If prompt-only fallback is used, it should remain explicit, bounded, app-validated, and schema-validated.

### Why readiness truth and capability truth must stay separate

Provider reachability and structured-output compatibility are different failure classes with different operator actions.

- provider unreachable or unavailable usually indicates service startup, networking, or endpoint problems
- model unavailable or not loaded indicates model selection or provider-side model readiness issues
- `json_schema` unsupported indicates capability mismatch where bounded `json_object` fallback may still preserve the proposal contract
- no compatible structured mode available indicates explicit degraded prompt-only JSON fallback should be used when app-side parsing and schema validation can still preserve the proposal contract; otherwise truthful target-level failure is required

Collapsing these into one generic provider-unavailable label hides actionable diagnosis and can mislead operators about whether fallback was safely used.

## Current MVP provider choice

The initial MVP provider should be **LM Studio via its localhost API**. This keeps the default path local-first while preserving the same structured-output contract for future providers.

---

## Research topic 10 — Evaluation strategy and measurement integrity

## Why this mattered

The app needs both engineering regression protection and product-level usefulness measurement.

The key question was whether MVP should attempt an automated Verify-mode score across heterogeneous cell types, or whether it should use a simpler and more trustworthy measure.

## Main conclusion

For MVP, evaluation inside the main app should be based primarily on **reviewer-outcome summaries**, not on a single automated “correctness score” over heterogeneous field types. When benchmark-style comparisons are needed, the app should provide a separate leakage-aware Eval mode that emits score-ready artifacts for an external eval tool rather than performing the scoring itself.

## Recommended MVP measurement model

The strongest current recommendation is to measure:

- proposal coverage
- reviewed verified-cell count
- accepted as-is count/rate
- accepted with edit count/rate
- confirmed no-data count/rate
- rejected count/rate
- per-column reviewer outcome breakdown
- evidence coverage
- anchorable/highlightable evidence rates where applicable
- matched / unmatched / ambiguous PDF counts

This is more trustworthy and easier to interpret than an automated aggregate score over free text, numeric, categorical, range, and reasoning-heavy fields.

Eval mode should complement rather than replace that model. It lets the main app produce runs that are later comparable in a separate evaluation repo or CLI while keeping benchmark logic out of the production review workflow.

Later spec tightening adds four durable implementation constraints to that measurement and review model:

- `confirm no data` should remain a first-class reviewer outcome throughout summaries and pipeline artifacts rather than being folded into rejection.
- Browser-picker setup in a local browser app should materialize selected inputs into backend-readable staged files, directories, or explicit server-side input handles rather than assuming the browser can supply stable native paths.
- Evidence-to-input population should be a text-first staging action that replaces the active input by default, never auto-saves, and never silently truncates overlong text.
- Grouped triage should define default group ordering and minimum group-header counts or warnings so rebuilds do not diverge on basic review ergonomics.

## Why this conclusion won

### Human review is already the product’s ground truth

Since the product requires expert review before export, the reviewer’s decision is the most natural MVP signal of usefulness.

### Automated scoring is hard across mixed field types

A single automated scoring method that handles all field types well is possible later, but not necessary for MVP.

### Reviewer-outcome metrics are more honest for a first release

They align directly with the product’s purpose: reducing reviewer effort while preserving trust.

### Eval mode exists to support leakage-safe comparison without turning the main app into a benchmark framework

The product still benefits from reproducible benchmark runs, but the operational app should not expose gold values to its own extraction path or grow a large in-app scoring subsystem. A separate Eval mode lets the app:

- accept the same completed human-filled table operators already maintain
- mask target cells before extraction so proposals cannot see the gold values
- preserve enough metadata for later scoring
- keep the main app focused on launch, extraction, review, export, and truthful artifacts

### Full scoring belongs in a separate eval tool or repo

Benchmark scoring policy is likely to evolve faster than the main app's operator workflow. Keeping scoring outside the app avoids coupling product UX, benchmark math, and research iteration into one harder-to-maintain surface.

This separation is especially helpful for:

- field-type-specific comparison logic
- alternative aggregation policies
- experiment-specific filtering or cohort logic
- evolving benchmark conventions that should not destabilize the main review app

### Prompt identity must exist on every run

Downstream eval and reproducibility need a stable per-run prompt identity even before full prompt-version infrastructure exists. Requiring prompt identity on every run avoids a gap where some runs are comparable and others are not.

The practical decision is:

- use a small manifest-based prompt-bundle layout for controllable prompt variation
- persist prompt-bundle identity (`prompt_bundle_id`, optional `prompt_bundle_version`, `prompt_bundle_path`) and hashes (`prompt_manifest_hash`, `prompt_bundle_hash`)
- persist effective prompt-contract identity as deterministic `prompt_hash` (`prompt_version` when explicit versioning exists)
- persist prompt file provenance and logical keys used for reproducible run comparison
- allow `git_commit` or equivalent code identity as secondary provenance when useful, but do not treat it as the core requirement

## Evaluation hygiene and leakage

Leakage-safe benchmark design should now be handled through a dedicated Eval mode rather than by overloading Verify mode. The key rule is simple: the completed human-filled table may be loaded as gold input, but target-cell gold values must be masked before extraction and must stay unavailable to downstream extraction prompts, helper context, and style-shaping paths.

Future automated Verify-mode scoring is still deferred. Verify mode remains an in-app reviewer-comparison workflow, while Eval mode becomes the benchmark-preparation workflow.

### Gold-empty-cell handling belongs to the downstream eval policy

An empty cell in the human-filled gold table does not prove that the paper definitely omits the field. Treating gold-empty cells as automatic negatives inside the main app would overstate certainty and mix scoring policy into the extraction product.

The downstream eval tool may choose to score only gold-present cells by default or expose alternative policies, but that is a scoring-layer decision rather than a runtime behavior of the main app.

### Internal masked-workbook fidelity should stay narrow

The masked working copy is an internal staging artifact, not the user-facing export product. Requiring formatting preservation there would overstate what downstream eval actually needs and would blur the boundary between export fidelity and internal eval preparation.

The right contract is narrower:

- preserve sheet and cell structure
- preserve content relevance for extraction and later joins
- do not promise workbook-formatting fidelity for the masked copy

### Retrieval-style metrics should stay secondary

Retrieval coverage, evidence-anchor rates, or similar diagnostics can still be useful during experimentation, but they should remain supporting diagnostics. They are not a substitute for the core correctness comparison and should not become the main score reported by the app.

## Measurement integrity requirements

A run that produces many proposals and many evidence attachments is not necessarily a good run.

A run with empty or non-interpretable evaluation should be treated as a meaningful diagnostic state, not as a normal artifact. If no relevant reviewed/verified targets were evaluated, that state should be explicit and reviewer-visible rather than collapsing into an apparently valid zeroed summary.

## Consequences for implementation

This supports the current split between:

- synthetic/parser fixtures
- application-level review/verify summaries
- leakage-aware eval-mode artifact emission for later external scoring
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
- future leakage-aware Eval mode design without changing the schema-first extraction contract

---

## Research topic 12 — Figures, charts, and vision-based fallback extraction

## Why this mattered

Some target fields may be stated only or most clearly in figures, especially charts, panel figures, diagrams, and image-heavy result summaries.

The question was whether the app should include a vision-capable path for extracting information from figures, and if so, how that should fit into the workflow without turning the whole system into a multimodal-by-default pipeline.

## Main research conclusion

The strongest research-backed pattern is still:

1. parse text, captions, and tables first
2. run normal schema-driven extraction
3. build a text-guided shortlist of figures or panels using retrieved evidence, caption relevance, and figure-reference snippets
4. route shortlisted candidates to vision for corroboration, rescue, or approximation where helpful
5. store the result as a normal proposal with explicit figure-derived evidence and subtype-aware review cues

In other words, vision works best as a targeted, context-guided stage that can corroborate or rescue text extraction without becoming an untargeted default pass over every page.

## Important note about current product direction

The current product direction is intentionally user-friendly and schema-light:

- no explicit schema-level per-column vision policy should be required
- text-guided targeted figure review is in scope when vision capability is available
- figure evidence is allowed for all field types, not only fields explicitly classified as figure-derived
- figure evidence may strengthen text proposals, corroborate uncertain text outcomes, supplement weak evidence, or rescue failed text-only proposals
- graph-derived approximate or range-style numeric proposals are useful when honestly labeled
- the scope is targeted (shortlisted figures or panels) rather than blanket per-page vision

This is the correct product direction. Requiring manual schema vision policies would add user burden and reduce adoption. The risk of false precision from figure reasoning is addressed by strong human review expectations and clear evidence labeling, not by requiring users to pre-classify columns.

## Why proactive targeted figure review is better than narrow trigger-based fallback

### Narrow fallback creates systematic blind spots

If figure evidence is only gathered when text extraction fails, the reviewer never sees figure evidence for proposals where text extraction succeeded but the figure would have provided stronger or more direct support. The reviewer cannot benefit from evidence that was never collected.

### Figures often complement text evidence

In scientific papers, figures frequently contain the clearest statement of a result even when the same result is also stated in the text. A reviewer whose text evidence shows an ambiguous passage in the methods section might make a more confident decision if they could also see the relevant figure.

### The cost concern is addressed by targeting, not by schema burden

Running vision on every page of every paper for every field would be expensive and slow. But reviewing the set of extracted figures per paper (typically a small number compared to all pages) is a targeted operation with bounded scope. The key constraint is "relevant extracted figures per paper," not "every page."

A better operational boundary is text-guided shortlisting: use retrieved passages, captions, and figure-reference snippets to rank likely figures or panels first, then inspect only the shortlist.

### Honest labeling replaces precision restriction as the quality mechanism

Instead of restricting figure evidence to prevent low-confidence results, the product should allow figure evidence freely and label it clearly. The reviewer sees whether support is caption-grounded or visual interpretation, makes their own judgment, and either accepts it or rejects it.

## Why text-guided targeted vision is preferred at the research level

### Vision is feasible, but expensive and noisier than text-first extraction

Modern multimodal systems can use page images and figure crops effectively, especially for focused extraction prompts, but running vision over every page by default would add significant cost, latency, and operational complexity.

### Text-guided targeting matches how strong existing systems behave

Established multimodal document systems often ingest both text and visuals, then route only shortlisted images or panels to a vision model when retrieval and document structure suggest visual reasoning is likely useful.

### Human review remains essential

Figure-derived values are often more ambiguous than table- or text-derived values. The review UI therefore becomes even more important for these cases.

## Recommended product behavior

The app should include a **text-guided targeted figure review stage** after text/table extraction and evidence recovery, running whenever vision capability is available.

### What changed from the narrow fallback design

The narrow fallback design ran figure review only when:
- the field appeared figure-derived
- text retrieval failed
- text-first extraction remained insufficient after evidence recovery

The improved design runs figure review using a text-guided shortlist when a vision model is configured. The trigger is evidence-aware availability: if a vision model is configured and text, captions, or figure references indicate likely value, figure review runs.

### Suggested scope definition

The scope should remain targeted rather than blanket. Candidate figures or panels can be selected by:
- figures with captions that mention the target column or related terms
- figures on pages that also contain the best text evidence
- explicit figure-reference snippets in the main text (for example, Fig. 2a or Figure 3B)
- an LLM-assisted relevance selection step for papers with many figures

The goal is to review the strongest candidates first, not to process every page image for every field.

## Suggested figure-fallback inputs

The vision step should receive a tightly scoped package rather than the whole paper:

- figure crop if available, otherwise page image
- figure caption
- nearby narrative text mentioning the figure
- row context
- target column definition
- structured extraction schema

## Suggested outputs

The targeted figure-review step should produce a normal proposal object, but with figure-aware evidence metadata such as:

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

### Stage C — Targeted figure review

Use the text-guided shortlist for a context-aware vision pass. Weak, contradictory, unresolved, or confirmation-sensitive text outcomes should prioritize this pass, while still allowing vision corroboration for strong but high-impact claims when useful.

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

MVP does not require a separate automated evaluation track for figure-derived proposals. Figure-derived evidence should remain visible and reviewable, but usefulness is assessed through the same human reviewer outcomes used elsewhere in the product.

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

This research supports:

- figure-aware evidence sources as a normal supplemental stage, not a last-resort fallback
- proactive targeted figure review when vision capability is available
- figure evidence allowed for any field type
- figure-derived review evidence in the UI, with caption-grounded vs. visual-interpretation distinction
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

## Research topic 14 — Evidence quality, reviewer trust, and evidence ranking

## Why this matters

A proposal with evidence attached is only as useful as the quality of that evidence from the reviewer's perspective. If the most authoritative quote in the paper is buried as supporting evidence while an arbitrary less-relevant quote is shown as primary, the reviewer must do extra work to find the passage that would actually inform their decision. If evidence types are not distinguished, the reviewer cannot tell whether they are reading verbatim text from the paper or a model-constructed summary.

This research addresses why evidence quality and reviewer trust must be first-class product requirements.

## Why ordered evidence rather than one arbitrary quote

When the model returns multiple quoted passages as evidence for a proposal, the order in which they were returned is usually determined by context-window order or the model's internal ranking, not by their relevance to the reviewer's decision. The first quote may be less authoritative than the second or third.

A reviewer making a decision deserves to see the most directly relevant, most authoritative evidence item first. Supporting items should be presented in ranked order so the reviewer can navigate them systematically rather than having to evaluate an arbitrary sequence.

Evidence ranking should consider:
- source section authority for the field type (methods sections for procedural fields, results sections for outcome fields)
- quote directness: a quote that uses the exact terminology of the field is more authoritative than one that uses general language
- proximity to data: a quote from a results table is more authoritative than a quote from a discussion paraphrase

## Why evidence types must be distinguished

A direct quote from the paper is fundamentally different from a model-constructed reasoning chain about the paper. Both may appear as evidence items, but they have different epistemic statuses:
- a direct quote can be verified by finding the text in the paper
- an inferred reasoning chain requires the reviewer to evaluate whether the inference is valid
- a calculation requires the reviewer to check the arithmetic

If these are not visually distinguished, the reviewer cannot efficiently apply the appropriate scrutiny to each. A product that mixes them without labels forces every reviewer to mentally categorize every piece of evidence rather than letting the system do that work.

The review UI must show direct quotes separately from reasoning and calculations, labeled as what they are.

## Why approximate and fallback highlights must be labeled

A highlight overlay that covers the wrong region of the page, or that approximates rather than precisely marks the quoted text, can mislead the reviewer. The reviewer may trust the highlight as exact when it is not. This is a truth problem, not an aesthetics problem.

The product must distinguish:
- exact highlight: produced from page-text alignment, precise
- approximate highlight: derived from parser geometry, may not be character-precise
- quote-plus-page fallback: no reliable geometry, reviewer must find the text manually

Each of these requires different reviewer behavior, so each must be labeled distinctly.

## Main conclusion

Evidence quality is a first-class product requirement. A future implementation must not satisfy evidence requirements by attaching any quote and calling it done. The following are required:
- evidence ranking with primary and ordered supporting evidence
- evidence type taxonomy and distinct labels
- exact quote highlighting from page-text alignment with honest labeled fallback
- direct quotes visually separated from reasoning and calculations in the review UI

---

## Research topic 15 — Separate text-model and vision-model configuration

## Why this matters

The best text model and the best vision model for this product are usually not the same model. In local deployments via LM Studio, text and vision capabilities are often served by separate model endpoints. Requiring operators to use one unified model for both text extraction and visual figure review either forces a suboptimal text model or a suboptimal vision model.

## Why separation improves flexibility and transparency

### Flexibility

Separate model identifiers allow operators to:
- choose the best available text model independently of vision capability
- disable vision review entirely when no vision model is configured, without breaking text extraction
- update one model without affecting the other
- configure a strong vision model for papers with complex figures without changing the text model

### Transparency

When a reviewer is assessing a proposal, they deserve to know which model generated the text evidence and which model generated the figure evidence. If the same model identifier appears for both, it is less informative than showing the reviewer exactly which capability was used.

Run summaries and reviewer context should identify both the text model and the vision model when both were used.

## Main conclusion

Provider configuration must carry separate model identifier fields for text extraction and vision extraction. Both fields must be recordable in run artifacts. Both must be reported in run summaries and reviewer context. A future implementation that uses a single model identifier for both modalities does not meet this requirement.

---

## Research topic 16 — Integrity and workflow refinements from rebuild validation

## Why this matters

Recent rebuild and review cycles validated additional trust and usability constraints that should be explicit in this research baseline. These refinements do not replace the existing architecture direction; they tighten it so reviewer-visible behavior, provider readiness semantics, and schema-driven extraction stay consistent and defensible.

## Main conclusions

### Style-profile anti-leakage and schema-first extraction

Extraction must not depend on prefilled spreadsheet cells. Prefilled cells are optional helpers for output-shape guidance only, not semantic exemplars. The extraction contract remains schema-first: column name, column description, and optional field type define what the model is expected to produce.

This keeps empty-table workflows first-class and reduces leakage risk where raw example values bias proposals toward prior spreadsheet content rather than current-paper evidence.

### Eval mode as the explicit leakage-aware benchmark path

The rebuild should make leakage handling explicit rather than leaving it as a future caution. Eval mode is the clean way to do that:

- load the completed table normally as the gold source
- create an app-owned masked working copy of target cells before extraction
- keep Verify mode separate for in-app reviewer comparison workflows
- persist enough stable metadata for a separate eval tool to score the run later

This gives benchmark users a defensible path without forcing the main app to own scoring policy, metric design, or a second evaluation UI.

### Practical eval-table provenance is path/reference + hash + snapshot

For downstream eval joins, relying only on source paths is too fragile, while requiring a heavier dataset registry would be overkill for a local-first app. The practical middle path is to persist:

- gold table: source path or reference, content hash, and copied run-bundle snapshot when feasible
- masked table: run-bundle path, content hash, and copied masked snapshot artifact

This keeps provenance simple, inspectable, and robust across local runs.

### Optional per-field schema typing

A small optional schema extension is justified for better extraction and evaluation consistency:

- optional `field_type` for text, number, categorical, or boolean
- optional `allowed_values` for categorical outputs only
- numeric representation that supports exact, range, and approximate value forms

`normalization_notes` should not become a required schema field for MVP.

This extension should remain optional so MVP does not become schema-heavy.

### Better schema descriptions as a product-quality lever

Because extraction is schema-driven, better column descriptions are a high-leverage quality control. Documentation should guide users to specify:

- what the field means
- what answer shape is expected
- key distinctions, boundaries, or exclusions

This is typically more valuable than adding many extra tuning knobs.

### Matching heuristics: lower title dominance, strengthen exact signals

Matching should stay deterministic-first but reduce over-reliance on title similarity alone. The practical direction is to combine interpretable signals such as:

- DOI or other stable identifiers
- first author and author overlap
- publication year consistency
- abstract similarity when available

This keeps matching explainable, strengthens robustness to title variation, and makes ambiguous or duplicate outcomes easier to defend.

### Duplicate-row conflicts as first-class outcomes

Duplicate-row conflicts are integrity outcomes, not ordinary ambiguity. When multiple papers compete for the same row mapping, extraction should be blocked for all involved PDFs until manual resolution. This prevents wrong-row proposal leakage into review.

### Provider-unavailable must hard-fail at run start

If the configured provider is unavailable at startup, the run should fail early with an explicit readiness failure. `completed_with_warnings` is reserved for partial-success runs where meaningful extraction work actually happened.

This preserves operator trust by preventing cosmetically complete but non-functional runs from appearing successful.

### Warning/status semantic consistency

Warning and status semantics must be canonical across persisted extraction artifacts, review APIs, and UI summaries. Reviewer-facing state should derive from persisted facts, not UI-local interpretation.

Mode truth belongs in that same rule. If a run was normal, Verify, or Eval, summaries, config snapshots, diagnostics, and UI labels should all agree, and Eval mode should make gold-table versus masked-working-table context auditable rather than implicit.

### Remove dead retrieval.chunk_size

If `retrieval.chunk_size` is not consumed by the runtime retrieval path, it should be removed from config surfaces. Dead settings violate operator-contract parity across config example, runtime schema, README, and actual behavior.

### Deterministic recall rescue for "model did not see it"

When first-pass extraction returns unclear, recall should be improved through a bounded deterministic rescue path:

1. focused retrieval pass
2. expanded retrieval or section-level/full-text fallback on unclear outcomes
3. optional whole-document mode when parsed text fits active model context

This is a measured extension for recall and diagnostics, not a default whole-document strategy.

### Keep retrieval simple by default

Baseline retrieval direction remains:

- typed chunks
- contextualized retrieval text
- simple lexical retrieval
- no reranker, HyDE, or query expansion by default

Structural improvements and deterministic rescue should be prioritized before advanced retrieval stacks.

### Simpler structured-output fallback

Use bounded structured-output recovery:

1. `json_schema` first
2. `json_object` fallback only when `json_schema` is unsupported for the configured provider-model path
3. explicit downgrade when the active request shape hits backend regex or grammar incompatibility
4. prompt-only JSON fallback only when both structured modes are unavailable for the configured provider-model path
5. one stronger-instruction retry if invalid
6. minimal JSON repair for purely syntactic errors, including wrapper stripping and balanced-object extraction
7. otherwise clean extraction failure

Prefer honest bounded failure over long silent fallback ladders.

Do not treat open-ended unvalidated prompt-only fallback as baseline behavior. When prompt-only mode is used for compatibility, keep it explicit and bounded with app-side parsing and schema validation.

### Direct evidence must require anchored direct quote

Direct-evidence support labels should require an anchored direct quote with exact or approximate page anchoring when possible. A loosely related quote is not sufficient to claim direct support.

If support depends on reasoning over quotes rather than direct statement, the state should be `inferred_from_evidence` or another weaker support category.

### Figure evidence split: caption-grounded vs visual interpretation

Figure evidence should be split into at least:

- `caption_grounded_figure_evidence`
- `visual_interpretation_figure_evidence`

Caption-grounded figure evidence is generally easier to verify and should usually rank above generic inferred reasoning. Pure visual interpretation remains useful but should carry higher review scrutiny.

### Multiple quotes when genuinely needed

Some values legitimately require more than one quote (for example condition plus result, or numerator plus denominator). The system should support multiple typed evidence items per proposal, ordered by relevance.

### Proposals persistence refinement: `proposals.jsonl` plus index

Filesystem-first persistence remains the MVP baseline, but per-proposal file sprawl should be avoided as run size grows. A practical refinement is `proposals.jsonl` plus an index for efficient listing/filtering/loading while preserving inspectability and portability.

### Actionable-only progress counts

Reviewer-facing progress headlines should default to actionable proposals. Attempted totals and diagnostic outcomes remain visible but should not dominate primary progress messaging.

### Keyboard navigation, evidence cycling, and fast sequential review

Keyboard support is a workflow-efficiency requirement for high-volume review, not optional power-user polish. Key actions should include next or previous proposal navigation, focus edit input, cycle evidence, and decision shortcuts.

### Auto-advance after decision

After recording a decision, the UI should auto-advance to the next proposal by default to preserve review momentum. Decision recording remains explicit and reviewer-safe.

### Config path plus Browse button

A text path field remains valuable for reproducibility and advanced control. A `Browse...` affordance improves first-run usability in browser workflows while preserving config authority.

### PDF viewer priority: highlight quality and evidence navigation

Annotated evidence inspection and ordinary PDF reading are related but not identical. If one in-app viewer cannot do both perfectly, the higher-priority product contract is:

- trustworthy quote and highlight display in-app
- robust evidence navigation in-app
- obvious handoff to OS PDF viewing for broader reading, selection, and search

### Manual export trigger from review UI

Export should remain an explicit post-review user action rather than an implicit side effect of run completion.

### Changed-cell highlighting as audit closure

Changed-cell highlighting in exported workbooks is part of auditability and review closure, not cosmetic formatting. It enables fast visual reconciliation between review decisions and output workbook changes.

### README screenshots and Playwright-based capture

Because this product is workflow- and UI-dependent, README screenshots add practical onboarding value. Playwright-based capture is preferred for repeatable, updatable screenshots tied to real UI behavior.

### Lightweight trustworthiness checklist

A compact README trust checklist should clarify core trust boundaries such as:

- local versus cloud path status
- evidence type labeling
- fallback visibility
- review requirement before export
- eval-mode masking and downstream-eval boundary
- export fidelity boundary
- audit artifact availability

## Consequences for implementation and docs

These refinements strengthen existing direction rather than replacing it:

- schema-first extraction remains primary, with anti-leakage constraints made explicit
- Eval mode becomes the explicit leakage-aware benchmark-preparation path while Verify mode stays reviewer-centered
- deterministic matching and retrieval remain baseline, with bounded rescue improvements
- evidence semantics are tightened around anchored direct support and figure evidence subtypes
- status/warning truthfulness is enforced end-to-end across persistence, API, and UI
- review ergonomics are treated as throughput and trust requirements, not optional polish

## Remaining open questions

The current direction is strong enough for implementation, but these details remain implementation choices rather than open strategy questions:

- what exact proposal-index shape best balances append-only writes with fast filter lookups for `proposals.jsonl`
- what token or parsed-length threshold should gate optional whole-document mode cleanly for the default LM Studio path
- whether the chosen in-app viewer can preserve strong highlight navigation and native-like text selection in one mode, or whether the local-PDF-viewer fallback should remain the clearer primary split

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
- Which figure categories deliver enough reviewer value to justify deeper visual tooling beyond the text-guided targeted figure review stage?
- What is the minimum set of structural and reference-aware heuristics sufficient to shortlist relevant figures or panels without processing too many irrelevant ones?
- At what point does synchronous execution become unacceptable for the target batch sizes, justifying the first background-job layer?
- Which provider capability probes are sufficient to distinguish reliable structured-output support from prompt-only JSON behavior?
- What is the minimum saved-view or queue-preset feature set that materially improves review speed without adding UI complexity?
- Which JSON files inside the artifact bundle are safe to treat as stable interfaces for tooling and tests in MVP, and which should remain internal implementation details?
- What is the most practical implementation of page-text alignment for exact quote highlighting across a range of PDF text layer qualities?

---

## Recommendations for next documents

This research supports the current direction of `plan.md` and suggests the following documentation additions only when they become useful:

1. optional ADRs
   - low-level PDF library and licensing posture
   - background-job/runtime choice if synchronous execution becomes insufficient
   - workbook fidelity policy
   - parser baseline decision
   - UI shell or viewer-stack decision
   - evidence ranking algorithm and authority heuristic design

2. README or runbook additions
   - a small real-example set
   - stub/synthetic PDFs for deterministic testing
   - figure-heavy test examples
   - examples showing evidence type labeling in review output
   - Verify-mode review outcome tracking examples
   - explicit clone/install/config/LM Studio onboarding (including both text model and vision model configuration) so future README edits do not collapse back to architecture-only notes

3. test harness hardening
   - keep Playwright startup shell-independent
   - separate fixture preparation from backend/frontend server startup
   - report missing browser runtimes as environment limitations rather than application regressions
   - capture screenshots, traces, or similarly useful browser-failure artifacts when practical
   - include viewer synchronization and evidence navigation in e2e test coverage

---

## Concise summary

The current research supports a clear implementation direction:

Extract Structured Info from Papers should be built as a **local-first, workflow-centered paper-to-table review system** with:

- a dedicated queue-first local browser app built around a React frontend, a FastAPI backend, and a raw/custom PDF.js review viewer
- Docling as the main parser with PDFium/pypdfium2 as the complementary low-level PDF backend for rendering/geometry/crops/highlight support and fallback page/image access
- OCRmyPDF plus Tesseract as the scanned-PDF fallback
- typed retrieval units with source-preserving evidence display
- filesystem artifact bundles and JSON files as the complete MVP persistence model
- runs launched from the UI and executed under app-owned backend control using a lightweight in-process background mechanism for MVP
- LM Studio localhost API, using the canonical config token `lm_studio`, as the default structured-output provider, with separate model identifier fields for text extraction and vision extraction
- evidence quality as a first-class requirement: evidence ranking by source authority and field relevance, evidence type taxonomy (direct quote, inferred reasoning, calculation, approximate highlight, quote-plus-page fallback, `caption_grounded_figure_evidence`, `visual_interpretation_figure_evidence`), primary evidence selected by ranking, ordered supporting evidence, direct quotes visually separated from reasoning and calculations
- exact quote highlighting from page-text alignment with honest labeled fallback to approximate highlight or quote-plus-page; no fallback presented as exact
- synchronized quote list and document viewer with stable refocus, previous/next/jump-to-page navigation, and figure-to-full-page context
- text-guided targeted figure review with shortlisted figures or panels when a vision model is configured; figure evidence allowed for any field type; figure evidence may strengthen, corroborate, supplement, or rescue proposals
- reviewer-outcome-based MVP evaluation
- preprocessing-LLM-derived style/format profiles rather than raw semantic examples
- reviewed XLSX export into a new workbook and audit log with content-only fidelity plus changed-cell highlighting

It also needs explicit measurement integrity requirements so empty or non-interpretable evaluation states cannot quietly masquerade as normal results.

This keeps the system aligned with its actual purpose: trustworthy human-reviewed extraction from scientific papers into structured tables, with evidence quality and reviewer trust as first-class requirements.
