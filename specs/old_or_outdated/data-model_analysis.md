# Paper Table Agent - data-model analysis

## Purpose

This report compares `specs/data-model.md` to the current structure and implementation of the app as it exists in the repository today.

The goal is to answer a practical question:

Is `data-model.md` describing the system we have now, or the system we intend to grow into?

## Executive summary

`data-model.md` is a strong target-state domain model, but it is not an accurate description of the app's current persisted structure.

The current implementation is a local-first CLI + Streamlit + LangGraph pipeline with:

- filesystem run artifacts as a major source of truth
- a relatively small SQLite schema in `paper_table_agent/store/schema.sql`
- several rich concepts stored as JSON blobs instead of first-class relational entities
- parsed-document structure represented in Python dataclasses and artifacts, not as normalized database tables

The document is directionally aligned with the product and much of the pipeline logic, but it currently overstates the level of normalization and persistence in the app.

The main conclusion is:

`data-model.md` should be treated as a hybrid of target-state domain model and migration guide, not as a literal description of the current storage model.

If it remains the "source of truth for the main application objects," it should be revised to clearly separate:

1. current implemented model
2. near-term target model
3. optional future entities

## What I checked

This analysis is based on the current repository structure and implementation, especially:

- `paper_table_agent/store/schema.sql`
- `paper_table_agent/store/db.py`
- `paper_table_agent/pdf/parsed_document.py`
- `paper_table_agent/ui/app.py`
- `paper_table_agent/graph/evaluation.py`
- `paper_table_agent/graph/reporting.py`
- `paper_table_agent/graph/runner.py`
- `README.md`
- `pyproject.toml`
- `specs/plan.md`

## Current implementation snapshot

## Architecture reality

The app is currently implemented as:

- a CLI entrypoint via `paper_table_agent/cli.py`
- a Streamlit UI via `paper_table_agent/ui/app.py`
- a LangGraph-oriented pipeline and checkpoint flow
- local SQLite persistence for operational state
- filesystem run bundles for reports, exports, parsed artifacts, retrieval indexes, and logs

This matters because the current app is not built around a web API + React frontend + worker farm. That broader architecture appears in the current `plan.md`, but it is not what the repository actually implements today.

For the data-model comparison, the relevant implication is that many "entities" in the model are not first-class application objects in code yet. They are either:

- implicit in JSON blobs
- represented only in artifacts on disk
- represented as in-memory Python structures
- or not explicitly represented at all

## Persistence reality

The SQLite schema currently contains these main tables:

- `pdfs`
- `rows`
- `locks`
- `matches`
- `pdf_metadata`
- `match_candidates`
- `proposals`
- `retrieval_chunks`
- `extraction_attempts`
- `debug_extraction`
- `reviews`
- `events`

This is materially simpler than the 20-entity model in `data-model.md`.

The main pattern in the implementation is:

- core operational records get a table
- rich nested structures go into JSON columns like `evidence_json`, `flags_json`, `payload_json`, or `metadata_json`
- run-level and artifact-level state live primarily in the run directory, not in normalized DB tables

## High-level comparison

## Overall fit

### Strong alignment

The data model is well aligned with the product workflow in these ways:

- It is centered on runs, PDFs, rows, proposals, evidence, review, and export.
- It preserves the "proposal first, evidence attached, human review required" product shape.
- It correctly treats filesystem artifacts as important to reproducibility.
- It captures the growing importance of structured parsing and typed retrieval chunks.

### Partial alignment

The data model partially matches implementation where the concept exists but is not normalized or not fully enforced:

- matching
- proposal storage
- review decisions
- retrieval chunks
- diagnostics
- evaluation outputs

### Weak alignment

The model is currently ahead of implementation in these areas:

- run-level normalized persistence
- schema-level persistence
- table-cell-level persistence
- parsed-document and parsed-element persistence
- evidence as a first-class table
- highlight anchors as a first-class table
- export bundles as first-class records
- provider probes as first-class records
- many of the proposed invariants and latest-version semantics

## Entity-by-entity assessment

The statuses below use:

- `Implemented`: directly represented in current code/storage
- `Partial`: concept exists but shape differs materially
- `Target-state only`: described in the model but not implemented as a first-class object

| Entity | Status | Current implementation reality | Conclusion |
| --- | --- | --- | --- |
| `Run` | Partial | Run identity exists primarily through the run directory and config/report files. There is no `runs` table in `schema.sql`. | The concept is real, but not normalized in DB. |
| `InputTable` | Partial | The input table is loaded and used, but not persisted as a first-class table record. | The model is ahead of implementation. |
| `SchemaColumn` | Target-state only | Schema-driven extraction exists, but schema columns are not persisted in SQLite as first-class rows. | Important domain object, but currently implicit. |
| `TableRow` | Partial | `rows` table exists, but only stores a reduced row shape: `row_id`, `row_index`, `title`, `authors`, `year`, `doi`, `status`. | Current DB supports matching context, not the full modeled row object. |
| `TableCell` | Partial | Cell-level logic exists conceptually through locks, missing-cell detection, verify mode, and audit mode, but there is no normalized `table_cells` table. | Current app reasons over cells without persisting them as first-class records. |
| `PdfDocument` | Partial | `pdfs` table exists and covers basic ingestion state, but does not include the richer modeled metadata or grouping semantics. | Good current anchor entity, but narrower than the spec model. |
| `ParsedDocument` | Partial | Parsed documents exist in code as `ParsedDocument` dataclasses and artifact files. They are not stored in SQLite as first-class records. | Real concept, artifact-backed rather than DB-backed. |
| `ParsedElement` | Partial | Parsed elements exist in Python dataclasses and parser adapters, but are not normalized into database rows. | Implementation supports the concept, but persistence does not. |
| `Chunk` | Partial | `retrieval_chunks` table exists and is a real implemented entity. However, it is narrower than the modeled `Chunk` and uses JSON metadata for extensibility. | One of the strongest matches. |
| `RowMatch` | Partial | `matches` and `match_candidates` together approximate this entity. However, match stage, winner semantics, duplicate grouping, and richer evidence fields are not normalized as modeled. | The concept is implemented, but split and simplified. |
| `ExtractionTarget` | Partial | `extraction_attempts` exists, but it is payload-oriented logging, not a normalized target/coverage table with stable status transitions. | Useful candidate for future normalization. |
| `Proposal` | Partial | `proposals` table is a core implemented entity. But proposal kind, evidence strength, validation summaries, latest-version semantics, and many fields are stored in `flags_json` or omitted entirely. | Implemented, but flatter and less explicit than the model. |
| `EvidenceItem` | Partial | Evidence is real and central, but is stored inside `proposals.evidence_json` rather than its own table. | Core concept, not first-class persistence. |
| `HighlightAnchor` | Partial | Highlight anchors appear inside evidence payloads and UI logic, not as their own table. | Real behavior, non-normalized storage. |
| `ReviewDecision` | Partial | `reviews` table exists, but does not implement append-only version semantics, `is_latest`, or explicit supersession fields. | Important mismatch because auditability is a core requirement. |
| `ExportBundle` | Partial | Export files are written to the run directory, but there is no export-bundle table. | Artifact-backed only. |
| `EvalResult` | Partial | Evaluation outputs exist as files and are reflected into `run_report.json`, but not as a first-class DB entity. | Real output, artifact/report based. |
| `RunArtifact` | Partial | Artifacts absolutely exist, but there is no artifact inventory table in SQLite. | Real concept, not normalized. |
| `ProviderProbe` | Target-state only | Capability probes exist in logic and are surfaced in run reports, but not as a first-class persisted table. | Good future entity if probe history becomes important. |
| `RunDiagnostic` | Partial | Diagnostics are currently spread across `events`, `run_report.json`, logs, and debug artifacts. | The concept exists, but the model is more structured than the implementation. |

## Important structural mismatches

## 1. The model is more normalized than the codebase

`data-model.md` assumes a normalized domain model with explicit entities and relationships.

The codebase instead uses a pragmatic hybrid:

- relational tables for a small number of operational concepts
- JSON blobs for evidence, flags, metadata, and debug payloads
- filesystem artifacts for most run-level reproducibility

This is not inherently wrong. In fact, it is consistent with a local-first tool evolving quickly. But it means the current document should not imply that these objects all exist as stable first-class persisted records today.

## 2. `Run` is conceptually central but not structurally central in SQLite

The model puts `Run` at the center of almost every relationship. That is a sound domain choice.

However, the SQLite schema does not reflect that. Most tables do not carry `run_id`, because each run gets its own `proposals.sqlite` file.

This creates an important modeling difference:

- the document models multi-run identity inside one logical database
- the implementation isolates runs by database file and directory structure

Recommendation: explicitly document that `run_id` is currently implicit in the run-scoped database file and run directory, even where the target-state model treats it as an explicit field.

## 3. Schema and cell state are core workflow concepts, but not persisted as first-class entities

The product and extraction logic are schema-driven, but there is no current `SchemaColumn` table.

Likewise, cell-level states such as empty, locked, review-only, and audit-target are central to the workflow, but persistence is split across:

- source table contents in memory
- `locks` table
- proposal flags
- evaluation logic

This is one of the biggest gaps between the conceptual model and the implementation.

Recommendation: decide whether `SchemaColumn` and `TableCell` should become first-class persisted entities soon, or whether `data-model.md` should describe them as "canonical workflow objects, not necessarily persisted in SQLite in v1".

## 4. Evidence is central in the product but denormalized in storage

This is the most important domain-model tension.

The product heavily emphasizes evidence review, evidence quality, evidence rescue, and highlighting. The data model reflects that well with `EvidenceItem` and `HighlightAnchor`.

But the current implementation stores evidence inside `proposals.evidence_json`.

That makes iteration faster, but it weakens:

- relational invariants
- indexing
- queryability for analytics and review prioritization
- versioning of evidence independently from proposals

Recommendation: if evidence-heavy review remains the heart of the product, `EvidenceItem` is the strongest candidate to promote from JSON blob to first-class table.

## 5. Review history is under-modeled in the current DB compared to the spec intent

The data model correctly wants review decisions to be append-only in spirit and auditable over time.

The current `reviews` table is much simpler:

- no explicit `is_latest`
- no supersession pointer
- no run_id column
- no explicit enforcement of one active decision per proposal

This is not just a documentation mismatch. It is a substantive product-risk area because review auditability is a core product value.

Recommendation: strengthen `ReviewDecision` sooner rather than later, either in schema or at least in documented invariants and access patterns.

## 6. Parsed-document support exists in code, but persistence is lighter than the model implies

The implementation already has `ParsedDocument` and `ParsedElement` dataclasses and parser adapters such as GROBID conversion.

That means the modeling direction is correct.

But the model currently reads as if parsed documents and parsed elements are operationally persisted entities. In practice, they are mostly:

- in-memory structures
- parser artifacts on disk
- chunk inputs

Recommendation: explicitly separate "domain entity" from "persisted DB table" in this part of the model.

## 7. Diagnostics and evaluation are artifact/report oriented, not entity oriented

The current app writes `run_report.json`, logs, evaluation files, and debug artifacts. That is how a lot of useful operational truth is exposed today.

`RunDiagnostic`, `EvalResult`, and `RunArtifact` are good abstractions, but they are currently mostly report-level concepts rather than normalized operational records.

Recommendation: do not force these into SQLite unless there is a clear query or UI need. The model should allow artifact-backed canonicality.

## 8. `data-model.md` is closer to the intended product than to the exact code

This is the biggest overall conclusion.

The document captures the right product-centered nouns. It is not random or overdesigned. But several of its claims are about the desired stable architecture of the application rather than the concrete current implementation.

That is acceptable only if the document clearly says so.

Right now it says:

"This is the source of truth for the main application objects."

That statement is too strong unless the file is revised to distinguish implemented versus target-state objects.

## Comparison to the current app structure

## Where the model fits the codebase well

- The proposal/evidence/review/export workflow is the right center of gravity.
- The app is local-first and artifact-oriented, matching the model's reproducibility emphasis.
- Retrieval chunks and parsed-document concepts are real and active parts of the code.
- Audit/eval behavior and diagnostics are real, even if not represented as first-class entities.

## Where the model mismatches the codebase structure

- The model assumes more normalized persistence than the actual SQLite schema.
- The model implies stronger relational invariants than the DB currently enforces.
- The model implies a more mature run-centered object system than the implementation currently uses.
- The model makes review, evidence, and export history sound first-class and versioned, while the implementation still relies heavily on flattened tables and JSON fields.
- The broader architecture implied elsewhere in the specs has drifted from the real Streamlit-based implementation.

## Clear conclusions

1. `data-model.md` is useful, but it currently documents a target domain architecture more than the exact implemented app model.

2. The strongest currently implemented entities are:

- PDF records
- row records
- matches and match candidates
- proposals
- retrieval chunks
- reviews
- events

3. The weakest alignment areas are:

- run-level normalized persistence
- schema-column persistence
- cell-state persistence
- evidence and highlight normalization
- review-decision versioning
- artifact inventory and provider probe persistence

4. The current model should not be presented as if every major entity is already first-class persisted state.

5. The biggest product-risk mismatch is review and evidence auditability. Those are central product promises, but the current storage model still compresses too much into JSON blobs and simplified tables.

6. The best path forward is not to shrink the model down to the current DB. The better path is to distinguish current-state, target-state, and optional future-state explicitly.

## Recommendations

## Priority 1: Reframe `data-model.md` as implemented model + target model

Revise the document structure so each major entity or section states one of:

- implemented now
- partially implemented
- target-state

This is the single most important documentation fix.

Without it, readers will assume a degree of persistence, normalization, and invariants that the code does not yet provide.

## Priority 2: Add an explicit persistence-status field per entity

For each entity, add a small status line such as:

- `Persistence status: first-class SQLite table`
- `Persistence status: JSON within parent record`
- `Persistence status: artifact-backed`
- `Persistence status: in-memory only`
- `Persistence status: planned`

This would immediately make the document far more truthful and operationally useful.

## Priority 3: Strengthen the review/evidence part of the real schema before expanding everything else

If schema changes are on the table, the most valuable upgrades are:

1. make `EvidenceItem` a first-class table
2. make review decisions explicitly append-only or versioned
3. make proposal kinds and evidence flags less dependent on opaque JSON blobs

These changes would directly support the product's trust and audit goals.

## Priority 4: Clarify that `run_id` is implicit in the current storage architecture

In the current app, each run has its own DB file. That is a valid design.

The model should explicitly explain that many entities are run-scoped by storage location even when `run_id` is omitted from their implemented table shape.

Otherwise the model reads like a multi-run relational schema that the code simply does not have.

## Priority 5: Separate "domain entity" from "required DB table"

For `ParsedDocument`, `ParsedElement`, `RunArtifact`, `EvalResult`, and possibly `ProviderProbe`, the better framing is:

- these are real domain objects
- they do not necessarily need first-class SQLite tables in v1

This would preserve the value of the model without forcing unnecessary database complexity.

## Priority 6: Align the model with the actual UI and runtime architecture

Related project documents should avoid describing the app as if it is already:

- FastAPI-based
- React-based
- worker-service-based

The current app is CLI + Streamlit + local SQLite + artifacts. The data-model analysis should remain grounded in that reality.

## Priority 7: Add a traceability appendix

Add a short appendix mapping:

- each model entity
- current implementation file or table
- persistence form
- gap status

That would turn `data-model.md` from a conceptual document into an actionable engineering reference.

## Suggested next revision shape for `data-model.md`

The most practical revision would be:

1. Keep the current entity list.
2. Add `Implementation status` and `Persistence status` to each entity.
3. Mark invariants as either:
   - enforced now
   - enforced in code only
   - target-state only
4. Add a short section called `Current storage mapping`.
5. Move ambitious but unimplemented details into `Target-state evolution notes`.

This preserves the document's value without pretending the system is more normalized than it really is.

## Bottom line

`specs/data-model.md` is a good domain-model document for where Paper Table Agent is trying to go.

It is not yet a faithful description of the exact application structure and persistence model that exists in the repository today.

The right correction is not to throw it away or collapse it into the current SQLite schema.

The right correction is to make the document honest about the difference between:

- current implementation
- intended stable domain model
- future optional expansion

That would make it much more useful for engineering, testing, and future refactoring.