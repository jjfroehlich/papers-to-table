Some open questions answered:

"main setup"
Frontend: UI: local browser app, React
Backend: small Python service, FastAPI
PDF ingestion/parser: Docling (with pypdfium2) 
Low-level PDF geometry/rendering: PDFium via pypdfium2 
LLM: LM Studio localhost API
Output format: structured JSON per proposal
Persistence: folders + JSON files
PDF viewer/highlight in review UI: PDF.js-style viewer, optionally with something like react-pdf-highlighter for overlay behavior 

"LLM interaction:"
parse once
retrieve relevant passages
ask the model per cell
require structured JSON
store page-grounded evidence

"Workbook fidelity boundary"
The exported spreadsheet only needs to preserve the content of cells (no need to preserve formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, etc)

"UI shell and PDF viewer implementation"
The current best recommendation is Tauri + React + PDF.js + TanStack. I also want:
raw/custom PDF.js
no need for AG Grid as fallback for MVP
(I let you decide exact MVP keyboard/filter/progress behavior)

"Verify-mode measurement boundary"
 Defer that until later.

"Use of existing filled cells"
Paper Table Agent will use a per-column preprocessing LLM to convert existing filled cells into a structured style/format profile. This profile guides extraction output shape, tone, and level of detail, but must not encode likely scientific content. Raw filled cells are not passed as semantic exemplars to the extraction prompt by default. 
Yes to a preprocessing LLM for all columns
Yes to using existing filled cells as input to that preprocessing step
No to heuristic-based format inference
No to raw example injection as the default extraction strategy
No need to solve Verify-mode leakage yet

"Figure monitoring and scope control"
Actually what I want is simply that a vision-capable model will look at the figures and use their content to answer the prompt to fill a cell. Use the bigger “reasoning + vision” approach only when:
the field is likely figure/table-derived
text retrieval failed
the user manually requests a fallback
We dont need to have any evaluation of this, we will do all the evals with human reviewers. 

"Persistence granularity"
"You still need to decide whether full parsed elements belong in the operational DB or remain only in artifacts, with only derived chunks/state persisted in SQLite."
I dont think we need a database at all. We could just create artifact bundles in the output directory. No need to make the app more complicated than necessary. We will run this locally and with single user. 

"Run-summary transparency"
"You want provider/model names and local-vs-cloud status in a concise run summary, but you still need to define exactly what belongs in that normal summary versus only in advanced logs." Please, just make sensible decisions for yourself, we can adjust in the future. 

"OCR sidecar choice"
"OCR is fallback-only, but you still need to choose what OCR component you would actually use for scanned PDFs and how it fits the low-level PDF/rendering pipeline." 
Please, just make sensible decisions for yourself, we can adjust in the future. 


These answers change the plan in a few important ways:

1. Persistence gets much simpler

The plan should now say:

canonical state = artifact bundles in the output directory

no SQLite in MVP

review state, proposals, diagnostics, and summaries are stored as JSON files

That is a major simplification.

2. Runtime gets simpler

Because you are local, single-user, and artifact-based, you may not even need a full job queue immediately.

My current recommendation:

use an app-owned staged runner

first implement it synchronously in the FastAPI service

only add a lightweight background job layer if UI responsiveness becomes a problem

So Huey can now move from “recommended MVP default” to “optional next step if needed.”

3. UI shell gets simpler

The plan should now prefer:

React local web UI

custom PDF.js viewer

no Tauri for MVP

no AG Grid fallback for MVP

4. Export boundary becomes crisp

The plan should explicitly say:

content-only fidelity

not workbook-behavior fidelity

changed cells highlighted

all other workbook structure/features out of guarantee

That is a very strong and implementable boundary.

5. Evaluation becomes much cleaner

The plan should now state that MVP evaluation is:

reviewer-outcome based

no automated correctness score required

Verify mode supports review and reporting, not benchmark-grade scoring yet

6. Prefilled-cell handling becomes much more specific

The plan should now include a preprocessing step:

take existing filled cells per column

run a preprocessing LLM

produce a structured style/format profile

feed only that profile into extraction

never pass raw filled cells as semantic few-shot examples by default