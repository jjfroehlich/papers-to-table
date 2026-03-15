Some open questions answered: 

"Workbook fidelity boundary"
The exported spreadsheet only needs to preserve the content of cells (no need to preserve formulas, filters, frozen panes, hidden rows/columns, merged cells, conditional formatting, comments, named ranges, etc)

"Final low-level PDF backend decision"
The research clearly points to pypdfium2/PDFium, but you still need to decide whether to lock that in now, and whether to keep a formal abstraction that could later swap to PyMuPDF or another backend if needed.

"UI shell and PDF viewer implementation"
The current best recommendation is Tauri + React + PDF.js + TanStack. I also want:
raw/custom PDF.js
no need for AG Grid as fallback for MVP
(I let you decide exact MVP keyboard/filter/progress behavior)

"Runtime/background job choice"
For now we try Huey + SqliteHuey + an app-owned staged runner.

Verify-mode measurement boundary
You have a good MVP metric model now, but you still need to decide whether you want to pursue a future automated Verify-mode score in parallel with reviewer-outcome stats, or explicitly defer that until later.

Use of existing filled cells
The safer recommendation is clear — format/style guidance only — but you still need to decide:

which field types are allowed to use it in MVP

whether it is heuristic-only or can include a preprocessing model

exact leakage safeguards in Verify mode

Figure monitoring and scope control
Because your product scope is broad for figures, you need to decide:

the initial figure taxonomy

which figure-review metrics are mandatory

what thresholds would trigger narrowing figure scope if the broad MVP scope underperforms

Persistence granularity
You still need to decide whether full parsed elements belong in the operational DB or remain only in artifacts, with only derived chunks/state persisted in SQLite.

Run-summary transparency
You want provider/model names and local-vs-cloud status in a concise run summary, but you still need to define exactly what belongs in that normal summary versus only in advanced logs.

OCR sidecar choice
OCR is fallback-only, but you still need to choose what OCR component you would actually use for scanned PDFs and how it fits the low-level PDF/rendering pipeline.




- [NEEDS MORE RESEARCH: What exact workbook fidelity guarantees should be promised for the main table sheet in v1 documentation?]


- [NEEDS MORE RESEARCH: Which background job/runtime library is the final concrete fit for v1, and is Huey + SqliteHuey sufficient once packaging and failure semantics are tested?]


- [NEEDS MORE RESEARCH: Which UI component stack best supports queue-first review, PDF highlighting, figure crop/full-page display, and efficient local-first desktop use?]


- [NEEDS MORE RESEARCH: Should a future automated Verify-mode score exist in addition to reviewer-outcome metrics, and if so, how should it be designed?]


- [NEEDS MORE RESEARCH: Which field types may safely use style/format guidance derived from existing filled cells in MVP?]


- [NEEDS MORE RESEARCH: What is the most robust way to monitor figure-derived proposal quality separately enough to validate the broad MVP figure scope?]


- [NEEDS MORE RESEARCH: Should a table-specific rescue parser be included in v1 or deferred?]


- [NEEDS MORE RESEARCH: Should full parsed elements be persisted in the operational database or only in artifacts with chunk projections stored in DB?]


- [NEEDS MORE RESEARCH: What exact provider/model transparency must appear in the normal run summary versus only in advanced logs?]