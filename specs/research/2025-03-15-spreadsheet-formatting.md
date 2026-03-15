Please research what spreadsheet/workbook fidelity guarantees are realistic for Paper Table Agent’s MVP export behavior and recommend a product boundary.

## Context

Paper Table Agent reads a source table (CSV or XLSX) and exports an updated XLSX file after human review.

Current product direction:
- export must always be XLSX
- preserve the formatting/layout of the **main table sheet**
- visually highlight cells changed through accepted proposals
- original input table remains unchanged

We need to define what exactly can realistically be preserved and what should remain out of scope.

## Research questions

1. What can existing Python spreadsheet libraries realistically preserve when reading and writing XLSX?
2. What workbook features are commonly lost, degraded, or hard to preserve?
3. Which of these are realistic to guarantee in MVP for the **main table sheet**:
   - cell formatting
   - formulas
   - filters
   - frozen panes
   - hidden rows/columns
   - merged cells
   - conditional formatting
   - comments
   - named ranges
   - charts
   - shapes
   - macros
4. What product promise is realistic and honest?
5. What export strategy best supports:
   - preserving main sheet formatting
   - highlighting changed cells
   - avoiding workbook corruption

## Deliverables

Please produce a structured markdown report with:
- Executive summary
- What current spreadsheet libraries can/cannot preserve
- Risks and edge cases
- Recommended MVP product guarantee
- Recommended implementation approach
- Open questions

## Constraints

- We need a practical product boundary, not an idealized one.
- We are okay if advanced workbook features are out of MVP scope, but we need to say that clearly.
- Please include citations/links.

I’m checking what the main Python XLSX libraries actually guarantee in practice, then I’ll turn that into an honest MVP boundary and export strategy.

I’ve got the main fidelity picture now: for true “open existing workbook, modify cells, save” behavior, openpyxl is the realistic Python choice; XlsxWriter is excellent for generating new XLSX files but not for editing existing ones. I’m checking the feature-specific edge cases now so the product promise stays honest.

Thought for 5m 2s
Workbook fidelity for Paper Table Agent MVP export
Executive summary

For Paper Table Agent’s MVP, the realistic Python choice for editing an existing XLSX and exporting a reviewed XLSX is openpyxl. It can read and write Excel OOXML workbooks (.xlsx, .xlsm, etc.), exposes workbook/sheet/cell structures directly, and supports the core sheet features you care about. By contrast, XlsxWriter is excellent for creating new XLSX files but cannot read or modify an existing workbook, so it is not the right engine for “load workbook → review → save updated workbook.” xlwings can get closer to native Excel fidelity because it automates Excel itself, but it requires an installed Excel application and only works in that mode on Windows/macOS, which makes it a poor default MVP boundary for a local-first, portable app.

The honest MVP boundary is: guarantee preservation of ordinary cell/sheet structure on the main table sheet for standard XLSX workbooks, and do not guarantee fidelity for advanced workbook artifacts such as charts, shapes, macros, and other drawing/automation layers. That boundary matches the strengths and limitations documented by openpyxl: it supports normal cell styles and sheet properties, but explicitly warns that some features are not fully round-trippable, including comment formatting and shapes; older official docs also warned that images/charts could be lost on round-trip.

One more important boundary: CSV inputs have no workbook/layout fidelity to preserve. CSV is just tabular text, so when the source is CSV, the export should be described as a newly generated XLSX, not a preserved workbook.

What current spreadsheet libraries can and cannot preserve
1) openpyxl

Best fit for MVP XLSX round-trip editing.

What it does well:

Reads and writes Excel OOXML workbooks from Python.

Supports ordinary cell styling such as fonts, fills, borders, alignment, number formats, and protection.

Exposes and writes common sheet features such as freeze panes, filters, row/column dimensions, hidden state, merged cells, conditional formatting, tables, and defined names.

Can preserve VBA content only if loaded with keep_vba=True, but that does not mean the VBA is editable/usable by openpyxl.

Can preserve rich text formatting in cells only if loaded with rich_text=True.

Known limitations:

It never evaluates formulas; it stores formula strings, not recalculated results.

Comments are only partially supported: comment text is supported, but formatting, box size, and position are lost on read/write.

Current docs explicitly warn that shapes are lost on round-trip; older official docs warned that images and charts could also be lost when opening and saving an existing file.

Bottom line: openpyxl is strong for cell-centric workbook preservation, weak for the drawing/automation layer.

2) XlsxWriter

Best fit for generating a new XLSX from scratch, not for editing an existing one.

Its docs say it is only a file writer and cannot read or modify an existing Excel file.

It does have very high fidelity for the files it creates.

Bottom line: useful for a “new workbook export” path, not for Paper Table Agent’s main XLSX round-trip workflow.

3) pandas

Not a workbook-fidelity layer.

pandas.ExcelWriter writes DataFrames to Excel and uses engines such as openpyxl or XlsxWriter underneath.

That makes pandas fine for data export, but it is the wrong abstraction for preserving workbook structure and formatting with minimal disturbance.

Bottom line: use pandas for data ingest/manipulation if needed, but not as the workbook-preservation layer.

4) xlwings

Higher-fidelity option, but bad MVP boundary.

xlwings requires an installation of Excel and therefore only works in that interactive mode on Windows/macOS.

Bottom line: native-app automation can preserve more because Excel itself saves the workbook, but the platform and installation dependency make it a poor default for MVP.

Risks and edge cases
CSV input

There is nothing workbook-like to preserve from CSV. No formulas, merged cells, comments, filters, freeze panes, charts, or styling exist at the format level. A CSV import should therefore be treated as a fresh XLSX generation path.

Formula results vs formula strings

openpyxl preserves formulas as formulas, but it does not calculate them. So “formula fidelity” is realistic; “recalculated workbook state at export time” is not.

Comments

If users rely on comment appearance, openpyxl is not a safe fidelity promise. Only comment text is dependable; formatting/positioning is not.

Drawings and embedded artifacts

Shapes are explicitly called out as lossy; images/charts have historically been a risk area in official docs too. This is the clearest reason not to promise “full workbook fidelity.”

Defined names / named ranges

openpyxl supports defined names, but the docs describe them as very loosely defined: they can point to constants, formulas, cells, ranges, or multiple ranges. That makes them risky to promise if the app performs structural edits.

Conditional formatting

openpyxl supports conditional formatting, but it is a complex area and historical changelogs note only partial preservation for some rule families such as data bars. That argues for best-effort preservation, not a strong guarantee.

Macros

Macros are outside the MVP promise for two reasons: openpyxl only preserves VBA blobs rather than understanding them, and your product direction says the export must always be XLSX, which is not a macro-enabled output format.

Recommended MVP product guarantee
Recommended promise text

For XLSX inputs, Paper Table Agent preserves the main table sheet’s ordinary cell content and layout in a new XLSX export. Untouched cells on the main table sheet keep their existing values or formulas, basic cell formatting, row/column sizing, hidden state, merged ranges, freeze panes, and existing filters. Accepted proposals only change the reviewed target cells and add Paper Table Agent’s own change markers.

Paper Table Agent does not guarantee fidelity for advanced workbook artifacts such as charts, shapes, images, macros, or other embedded/automation features. Existing conditional formatting, comments, and named ranges are preserved on a best-effort basis only.

For CSV inputs, Paper Table Agent generates a new XLSX; no source formatting/layout preservation is implied.

Feature-by-feature recommendation

Realistic to guarantee on the main table sheet

Cell formatting: Yes, for ordinary cell styles on untouched cells; accepted cells are intentionally modified by PTA highlighting.

Formulas: Yes for preserving formula strings on untouched cells; no guarantee of recalculated results at export time.

Filters: Yes, if PTA does not resize/rebuild the filtered region or table.

Frozen panes: Yes.

Hidden rows/columns: Yes.

Merged cells: Yes, if PTA does not merge/unmerge or structurally rewrite those areas.

Best-effort only

Conditional formatting: Best-effort, not a hard guarantee.

Comments: Best-effort for comment text only; no guarantee for comment formatting/size/position.

Named ranges: Best-effort passive preservation; no guarantee that PTA will repair or retarget them after structural changes.

Out of scope / no guarantee

Charts: No guarantee.

Shapes: No guarantee.

Macros: Out of scope.

Recommended implementation approach
1) Use openpyxl as the XLSX round-trip engine

Use openpyxl for reading an existing workbook, applying accepted cell edits, and saving a new XLSX file. Do not use XlsxWriter or pandas for the existing-workbook edit path.

2) Keep the edit surface extremely narrow

For MVP, only allow PTA to:

change values in reviewed target cells on the main table sheet

add PTA change-highlighting to those cells

optionally add a hidden audit sheet

Avoid:

inserting/deleting rows or columns

moving ranges

merging/unmerging cells

renaming/reordering sheets

resizing table objects

rebuilding filters or conditional formatting rules

That narrow edit model is what makes the “preserve main sheet layout” promise believable given how openpyxl works. The more structural the edits, the weaker the fidelity story becomes.

3) Load with fidelity-preserving options

For XLSX input, use load_workbook(..., data_only=False, keep_links=True, rich_text=True). That preserves formulas as formulas, keeps external workbook links, and preserves rich text in cells.

4) Highlight changed cells without depending on comments

Do not use comments as the main audit/highlight mechanism because comment formatting is lossy in openpyxl. Prefer:

a subtle cell border/fill marker on changed cells, and

a separate hidden PTA_AUDIT sheet containing cell address, old value, new value, evidence ID, reviewer action, and timestamp.

5) Save-as-new, never overwrite the source

The export should always be a new XLSX file, leaving the original untouched. openpyxl’s save overwrites without warning, so the product should enforce a new output path/name.

6) Add a compatibility warning mode

At load time, inspect the workbook for risky features and downgrade the promise if needed. Warn when you detect things like:

drawing parts / shapes / charts

comments

heavy conditional formatting

defined names beyond simple ranges

macro-enabled files in any future scope

This is the simplest way to keep the product promise honest. The export can still proceed, but with a visible “best-effort workbook fidelity” warning. That recommendation follows directly from openpyxl’s documented limitations around shapes, comments, and complex workbook objects.

7) Reopen-and-verify after export

After writing the file, reopen it with openpyxl and verify:

workbook opens successfully

main sheet exists

edited cells contain expected values

preserved sheet properties still match expected invariants

This will not prove perfect Excel fidelity, but it is a cheap corruption/sanity check for MVP.

Open questions

Should workbooks with charts/shapes be warn-only or hard-blocked in MVP? The conservative product answer is warn-only, but a hard block would reduce support burden.

Should change-highlighting use a border, fill, or both? A border is usually less disruptive to existing formatting, while a fill is more noticeable. openpyxl supports both ordinary style changes.

Should named ranges be merely preserved passively, or should PTA attempt to validate them on export? Because defined names can be formulas/constants/multi-ranges, validation may not be worth MVP complexity.

Should there be a future “high-fidelity desktop mode” using native Excel automation? That would likely improve fidelity, but at the cost of requiring Excel and losing cross-platform simplicity.