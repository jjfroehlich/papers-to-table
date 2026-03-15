# Prioritized App Improvements For Paper Table Agent

## Goal

This report revises the previous improvement plan to focus only on improving the current app itself.

It deliberately does not prioritize benchmark harnesses, evaluation redesign, leakage-safe experiment workflows, or systematic parameter-search infrastructure. Those are still worthwhile, but they are out of scope for this plan.

The question here is narrower:

- given the current app
- given the web scan of related systems
- given the recent quality-first default analysis

what changes are most likely to improve real extraction quality and operator usefulness now?

Relevant prior notes:

- `2026-03-07-web-scan-related-projects-and-guidance.md`
- `2026-03-07-most-likely-optimal-defaults.md`
- `2026-03-07-benchmarking-and-parameter-tuning.md`

Only the first two are treated as primary inputs for prioritization here. The benchmarking note is used only where it helps interpret practical product behavior, not to drive the roadmap.

## Starting point

The app already has an unusually strong base for a local-first research-paper extraction tool:

- hybrid retrieval with sparse + optional dense retrieval
- query expansion, HyDE, reranking, and reciprocal-rank fusion
- broader quality-first defaults for retrieval context and retry headroom
- context planning across `fulltext`, `memory`, and `retrieval`
- evidence repair, highlight recovery, and quote anchoring
- proposal-first extraction with reviewable evidence metadata
- optional GROBID integration for scholarly sections and metadata

The recent defaults analysis also already pushed the repo in the right direction:

- wider retrieval breadth
- larger context budgets
- stronger neighbor and section context
- single-column extraction start
- larger whole-text and paper-memory budgets
- real retry expansion room

So the app does not mainly need another round of generic parameter widening.

The biggest remaining opportunities are more structural:

- improve what the system knows about the document before retrieval
- improve how chunks are represented for retrieval
- treat table-like content as first-class input
- make parser quality a real lever
- make the review workflow concentrate attention on risky proposals

## Core conclusion

The strongest next improvements are not more model calls and not broader benchmark machinery.

The strongest next improvements are:

1. contextualized chunk retrieval
2. typed parsed-document representation
3. stronger parser abstraction and parser backends
4. dedicated table-aware extraction artifacts
5. schema-aware retrieval and extraction policy
6. a clearer quality preset and review-triage workflow

This ordering follows the web scan closely and fits the current codebase shape.

## Recommended improvements

## 1. Add contextualized chunk indexing

### Why this is the top priority

This is the single best near-term improvement because it directly strengthens retrieval without requiring a full architectural rewrite.

The web scan identified contextual retrieval as the clearest next step that mature systems use and this repo does not yet center.

Today chunks are mostly indexed as local text spans. That loses the document situation around each chunk.

For scientific papers, local text alone is often not enough. A paragraph means more when retrieval also knows that it came from:

- Results
- a methods subsection
- a figure caption
- a table page
- a page discussing assay design or outcomes

### What to add

- deterministic context prefixes for each chunk
- separate retrieval text from display and quote text
- stronger use of section title, local heading, page range, and content role in retrieval

### Suggested implementation shape

- add `retrieval_text` to chunk records
- build it from lightweight deterministic context such as:
  - document title if available
  - section title if available
  - page marker
  - chunk type
- keep `text_raw` and `text` unchanged for evidence validation and UI display
- use `retrieval_text` for both sparse and dense indexing

### Why this should come first

- it matches the strongest actionable idea from the web scan
- it is likely to improve difficult-field recall quickly
- it complements the newly expanded context budgets instead of replacing them
- it is much less invasive than a full parser redesign

## 2. Introduce a typed parsed-document representation

### Why this is second

The web scan strongly supports a richer internal document model. Right now the parser output is still too thin relative to what strong document systems preserve.

The current app already handles retrieval and evidence well downstream. The next major quality gain is to give those downstream stages a better document representation upstream.

### What to add

- a canonical parsed-document schema with typed elements such as:
  - title
  - abstract
  - section_header
  - paragraph
  - figure_caption
  - table_region
  - table_cell_summary
  - reference_block
- reading-order and parent-child structure
- page provenance and geometry where available

### Suggested implementation shape

- introduce a `ParsedDocument` abstraction rather than passing around only `page_text`
- adapt current parser output and GROBID output into that abstraction
- keep the current retrieval pipeline working initially by deriving chunks from the parsed document

### Why this matters now

The app has already widened retrieval and context defaults. The next quality step is not mainly more breadth. It is better structure in what is being retrieved.

## 3. Strengthen parser abstraction and parser backends

### Why this is third

The web scan repeatedly supports the idea that parser quality is upstream of extraction quality.

The repo already has the beginning of this direction with optional GROBID. The next step is to make parsing a stronger modular layer rather than a mostly single-path implementation with optional side artifacts.

### What to add

- a parser interface that normalizes outputs from:
  - current PyMuPDF + pdfplumber path
  - GROBID
  - PyMuPDF4LLM
  - Docling
  - future table-aware parsers
- parser-specific artifact saving plus normalized parsed output
- parser confidence and parse-health diagnostics that help operators understand weak inputs

### Suggested implementation shape

- make parser selection explicit in config while preserving one stable default path
- normalize all backends into the same parsed-document schema
- compare parser outputs at the artifact level before changing extraction logic deeply

### Why this is not first

This is strategically very important, but contextual chunking is the faster app-level win. Parser work becomes easier and cleaner once the parsed-document abstraction exists.

## 4. Add a dedicated table-aware path

### Why this is fourth

The web scan is very clear that scientific PDF extraction should not flatten tables into ordinary text whenever better structure is available.

This matters especially for:

- numeric columns
- assay configuration columns
- matrix-like outputs
- condition/result mappings

### What to add

- typed `table_region` artifacts during parsing
- table-aware retrieval units separate from paragraph chunks
- coarse table summaries that preserve header, row-label, and value structure
- optional table-biased context assembly for columns that are likely table-derived

### Suggested implementation shape

- start with detection and typed chunking before attempting full cell-perfect reconstruction
- let retrieval surface table summaries alongside paragraph evidence
- later add richer table cell structures where parser support is good enough

### Why this is not lower

This is one of the clearest product-specific gaps in the current app. For some scientific fields, it is likely higher impact than general prompt improvements.

## 5. Move from generic chunks to typed structural chunks

### Why this is distinct from the parsed-document item

The parsed-document representation is the upstream architecture. Typed structural chunks are the retrieval-facing operational layer.

The repo currently has mostly `page`, `paragraph`, and optional `section` chunks. The next step is to let retrieval reason over more meaningful chunk types.

### What to add

- chunk types such as:
  - abstract
  - section_header
  - paragraph
  - figure_caption
  - table_region
  - table_cell_summary
  - reference_block
- chunk-type-aware retrieval weighting or inclusion rules
- chunk-type-aware context assembly

### Suggested implementation shape

- derive the initial typed chunks from the new parsed-document schema
- bias retrieval differently for different chunk types
- preserve the current section-injection concept, but make it type-aware rather than only section-aware

### Why this matters

It operationalizes the web scan's repeated recommendation to move from naive text slicing toward element-aware retrieval.

## 6. Make retrieval and extraction policy schema-aware

### Why this is sixth

The defaults analysis suggests global quality-first settings are worthwhile, but the true best behavior probably differs by column family.

Some columns likely want:

- table-first retrieval
- fulltext preference
- memory-mode preference
- paragraph-only retrieval
- metadata-only behavior

### What to add

- schema-level hints for preferred evidence sources and retrieval policy
- column-family rules for when to prefer table regions, captions, or sections
- optional suppression of expensive retrieval helpers when they are unlikely to help a given field

### Suggested implementation shape

- add optional schema fields for retrieval strategy hints
- start with simple human-defined policies rather than learning-based routing
- keep the current global defaults as fallback behavior

### Why this is after structural work

Schema-aware policy becomes much more valuable after chunks and parser output carry better types.

## 7. Expand whole-text and paper-memory behavior with better structure

### Why this is worth keeping on the roadmap

The defaults analysis was directionally right to preserve whole-text and paper-memory modes. But those modes can improve further if they operate over a stronger document structure instead of mostly flattened text.

### What to add

- section-aware fulltext assembly that better preserves structure
- memory notes tied to typed elements, not only page text spans
- more deliberate inclusion of captions, figure context, and table summaries in memory mode

### Suggested implementation shape

- keep the current context planner modes
- upgrade what each mode consumes once typed parsed artifacts exist
- ensure whole-text and memory modes preserve element boundaries clearly in prompts

### Why this is not higher

The mode framework already exists and the defaults are already stronger. The main missing improvement is better structured input to those modes.

## 8. Turn `max_success_mode` into a real quality preset

### Why this still matters

The defaults note correctly observed that the current quality-first behavior is partly implicit and partly scattered across config fields.

Operators should be able to select a coherent quality preset rather than manually maintaining a bundle of correlated settings.

### What to add

- explicit preset names such as:
  - `quality`
  - `balanced`
  - `fast`
- preset bundles that govern retrieval breadth, context budgets, batching, and helper usage coherently
- effective-config reporting so the operator can see what the preset actually changed

### Suggested implementation shape

- keep `run_config.json` as the final source of truth
- allow a preset to populate or override a consistent set of quality-related defaults
- make `max_success_mode` either alias a preset or be replaced by one

### Why this matters for app quality

It reduces operator drift and keeps the repo's quality-first intent legible in ordinary usage.

## 9. Improve review triage for risky proposals

### Why this belongs in the app plan

The system is human-in-the-loop. Better review prioritization is a direct app improvement, not just tooling polish.

The current UI already supports review, but it can direct user attention much better.

### What to add

- prioritize proposals by likely risk
- highlight why a proposal is risky, for example:
  - inferred without strong quote support
  - evidence found only after repair
  - table-like field without table evidence
  - highlight failure
  - low retrieval agreement
- filter views for weak-evidence, inferred, or table-derived proposals

### Suggested implementation shape

- reuse existing evidence flags and retrieval metadata
- introduce a simple triage score rather than a new model call
- surface the score and reasons in the review queue

### Why this is lower than retrieval work

It improves operator efficiency more than raw extraction quality, so it should follow the higher-leverage retrieval and parsing improvements.

## 10. Expand artifact-level observability

### Why this helps

As the app becomes more structure-aware, development and debugging will depend more on seeing where the pipeline lost important structure.

### What to add

- chunk inspection artifacts that show:
  - chunk type
  - retrieval text
  - source text
  - provenance
- parser artifacts that show sectioning, table detection, and caption extraction
- context assembly diagnostics that show why certain chunks were included

### Suggested implementation shape

- keep this debug-oriented and artifact-driven
- use it to support parser and retrieval improvements, not as a user-facing primary feature

### Why this is later

It is highly useful for engineering iteration, but it is not the main product-quality lever by itself.

## 11. Add acceptance-informed example banks and hints

### Why this is last

Using reviewed outputs to improve future runs is promising, but it should come after the document and retrieval foundations are stronger.

### What to add

- curated example banks derived from accepted outputs
- reusable per-column examples not tied to a single current table
- optional retrieval hints mined from accepted evidence

### Suggested implementation shape

- keep this explicit and reviewable
- do not make it the primary route for fixing weak retrieval or weak parsing

### Why this is later

The app will benefit more from better document structure than from smarter example reuse at this stage.

## Priority order

This is the recommended execution order for product work.

### Tier 1: strongest immediate app improvements

1. Contextualized chunk indexing
2. Typed parsed-document representation
3. Stronger parser abstraction and parser backends
4. Dedicated table-aware path

Why this tier comes first:

- it targets the biggest likely quality bottleneck: document representation feeding retrieval
- it matches the strongest repeated lessons from the web scan
- it builds directly on the new quality-first defaults rather than replacing them

### Tier 2: make retrieval smarter once structure improves

5. Typed structural chunks
6. Schema-aware retrieval and extraction policy
7. Better-structured whole-text and paper-memory modes

Why this tier comes second:

- these improvements become much more effective once the parser and chunk representation are stronger
- they convert better structure into better extraction behavior

### Tier 3: operator and configuration improvements

8. Real quality presets
9. Review triage for risky proposals
10. Artifact-level observability

Why this tier comes third:

- these meaningfully improve usability and iteration speed
- they are most valuable after the higher-impact structural work lands

### Tier 4: later optimization

11. Acceptance-informed example banks and hints

Why this is later:

- it is promising, but not as foundational as the structural retrieval and parsing work

## Best near-term roadmap

If only three initiatives should be started next, they should be:

### 1. Contextual retrieval upgrade

- add `retrieval_text`
- prepend deterministic context prefixes
- use contextualized text for sparse and dense retrieval

### 2. Parsed-document foundation

- define a canonical parsed-document schema
- normalize current parser output and GROBID into it
- derive current chunks from that schema as a compatibility layer

### 3. Table-aware extraction inputs

- detect `table_region` artifacts
- emit table-aware retrieval units
- surface coarse table summaries into retrieval and context assembly

That combination is the best balance of near-term impact and long-run leverage.

## Explicitly deferred for this plan

The following ideas are intentionally not part of the current priority order:

- benchmark harnesses
- leakage-safe benchmark workflows
- richer evaluation scoring systems
- systematic parameter sweeps
- retrieval-vs-extraction benchmark reporting

Those may still be worth revisiting later, but they are not the focus of this product-improvement roadmap.

## Concrete product implications

If the recommendations above are followed, the app should improve in the places that matter most for live extraction use:

- hard scientific fields should retrieve the right evidence more often
- multi-section reasoning should become easier because chunks carry more context
- numeric and table-derived fields should improve once table-like content is treated explicitly
- whole-text and memory modes should become more reliable because they will operate on stronger structure
- operators should spend more time reviewing genuinely risky proposals and less time skimming low-risk ones

## Bottom line

Paper Table Agent already has the right broad defaults for quality-first extraction: wider retrieval breadth, larger context budgets, preserved whole-text and memory modes, single-column extraction start, and meaningful retry headroom.

The next step is not to widen those defaults again. The next step is to make the information flowing into retrieval and extraction more structured and more document-aware.

The recommended order is:

1. contextualized chunks
2. typed parsed-document architecture
3. stronger parser layer and parser backends
4. table-aware extraction artifacts
5. schema-aware retrieval policy
6. clearer quality presets and review triage

That is the most defensible app-focused path to better real-world extraction quality in this repo.