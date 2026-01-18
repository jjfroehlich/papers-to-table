# Spec: Paper Table Agent — UI/UX Iteration (v0.4)

This v0.4 spec updates the UI/UX to minimize friction, accelerate review, and make evidence trustworthiness explicit while keeping the app responsive for large runs.

---

## 0) Goals

- **Minimize user friction**: click/select instead of typing.
- **Optimize review**: fast, focused, low cognitive load.
- **Trustworthy proposals**: every proposal shows evidence + source + highlight and failure states are explicit.
- **Responsive on large runs**: avoid rendering huge tables, lazy-load row proposals, persist decisions immediately.

---

## 1) Global UI principles

- Two-level navigation: **Run | Review | Advanced | Settings | Help**.
- Consistent layout:
  - Top: app title + selected run indicator + status chip.
  - Left: navigation + context selectors (run, row, PDF).
  - Main: working panels.
- Every screen supports:
  - Back/forward actions without losing state.
  - Persistent selection stored in session state (selected run, row, proposal index).
  - No hard failures: missing data shows clear empty states.

---

## 2) Run tab (Batch execution)

### 2.1 Run configuration panel (left)

Required controls (click/select):

- **Table input**: file uploader (XLSX/CSV), show filename + last modified.
- **PDF folder**: folder picker OR text input with “browse” helper.
- **Schema source**: dropdown:
  - Use schema sheet from XLSX (default)
  - Select separate schema XLSX (optional)
- **Run name**: auto-generated, editable.
- **Mode**: toggle
  - Propose (default)
  - Verify-only (optional)
- **Locked cells policy**: read-only display (non-empty except " " locked).
- **Models**: dropdowns for
  - LLM for extraction
  - Embedding model
  - Reranker model (if enabled)
- **Retrieval strength**: preset
  - Fast | Balanced | Thorough
- **OCR fallback**: checkbox (off by default)
- **GROBID**: checkbox (off by default) + URL field if enabled

Validation UX:
- Required fields show green check / red warning.
- **Start run** disabled until minimum fields are valid.

### 2.2 Run execution panel (main)

- Progress display:
  - overall progress bar
  - current step label (parse → match → index → extract)
  - current PDF filename
- Live logs (collapsible):
  - recent events
  - filter toggles: errors only, warnings, info
- Run actions:
  - Pause (graceful checkpoint)
  - Resume
  - Stop (graceful, keeps partial results)
- Completion summary card:
  - matched / ambiguous / unmatched PDFs
  - proposals generated count
  - needs_more_evidence count
  - run duration
  - Button: **Go to Review** (run selected)
- Post-run output visibility:
  - Show artifacts path `runs/<run_id>/...`
  - “Copy path” helper

---

## 3) Review tab (Optimized human review)

### 3.1 High-level structure

- Two-panel layout:
  - **Left panel**: row context + proposal stepper + decisions
  - **Right panel**: PDF viewer + evidence list

### 3.2 Top bar (always visible)

- Run selector dropdown (completed runs only)
- Filters:
  - Status: proposed | unclear | needs_more_evidence | accepted | rejected
  - Confidence range slider
  - Columns (multi-select)
- Search field:
  - search within column names + proposed values + evidence quote
- Row navigation:
  - Prev row / Next row
  - Row index jump
  - “Row X of Y” + fully reviewed indicator

### 3.3 Row context card (left, top)

- Displays locked cells relevant to understanding the row:
  - Title, Authors, Year (always)
  - Optional “key columns” from schema
- Mapping status + confidence:
  - matched row + PDF metadata side-by-side
  - if ambiguous: show top candidates with mapping action (if allowed)

### 3.4 Proposal stepper (left, middle)

- Shows one proposal at a time for the selected row.
- Buttons: Prev / Next
- Keyboard shortcuts (optional):
  - A accept
  - E accept+edit
  - R reject
  - ←/→ stepper navigation

Proposal card contents:
- Column name (large)
- Current table value (read-only)
- Proposed value (editable only when “accept+edit”)
- Status chips:
  - proposed / unclear / needs_more_evidence
  - confidence (numeric)
- Evidence summary:
  - page number(s)
  - short quote snippet(s)
  - highlight status: highlighted | not found | ocr-only

### 3.5 Decision controls (left, bottom)

Exactly three decisions:
- **Accept** → accepted_value = proposed_value
- **Accept with edit** → accepts edited text as accepted_value
- **Reject** → sets rejected; cell stays empty in export

Additional UI:
- “Add note” textarea
- “Mark as Needs more evidence” toggle
  - allowed if highlight missing or evidence weak
  - does not accept; tags for rerun targeting
- Auto-advance to next proposal (default on, toggleable)

### 3.6 PDF panel (right)

Split into:
- **PDF viewer**
- **Evidence list**

PDF viewer requirements:
- Shows cited page by default.
- Highlights rectangles if available.
- Click evidence entry to jump/highlight.

Evidence list requirements:
- Each entry shows:
  - page number
  - quote
  - “Go to location”
  - if highlight failed: “Try re-locate” (local search)
- If OCR enabled: show OCR confidence (if available) and note that highlight may be approximate.

### 3.7 Completion indicators

- Row completion: % decided; optional “Mark row complete”.
- Run completion: overall % decided; **Export updated table** enabled only after confirmation.

---

## 4) Advanced tab (Debuggable but usable)

Selectors (dropdown/multi-select):
- Run selector
- PDF selector
- Row selector
- Column selector
- Retrieval query selector

Panels:
- **Matching diagnostics**: candidate table with component scores.
- **Retrieval diagnostics**: top chunks with BM25/dense/fused/rerank scores + source page.
- **LLM I/O**: prompt template name + parameters, JSON output, validation errors.
- **Evidence locator**: input quote + page, output rectangles + preview.

---

## 5) Settings tab (Models, providers, performance)

Provider selection:
- Local: LM Studio | Ollama
- Cloud: OpenAI-compatible URL + API key (masked)

Model routing:
- Header extraction model
- Match adjudication model
- Extraction model
- Query expansion model (optional)
- Embedding model
- Reranker model

Performance controls:
- Concurrency (PDFs in parallel)
- Retry counts (JSON repair retries = 1 recommended)
- Cache toggle (embeddings, parsed pages)

---

## 6) Help / Troubleshooting

Required content:
- “How to get started in 3 steps”
- Common failure modes:
  - No proposals appear → checks
  - Highlight missing → locator rules
  - Ambiguous mapping → resolve guidance
- Link to run folder + logs + DB

---

## 7) Non-functional UI requirements

- Handles large runs:
  - Lazy-load proposals per row
  - Avoid rendering huge tables
- Persist UI state across tab switches.
- Never lose review decisions on refresh (write to DB immediately).
- Good defaults:
  - Filters default to show proposed first, hide unclear unless toggled
  - Auto-advance enabled
  - Review order: rows with highest count of proposed values → needs_more_evidence → unclear

---

## 8) Definition of done

- UI implements Run/Review/Advanced/Settings/Help layout with persistent session state.
- Run tab validates required inputs and disables Start until valid.
- Review tab supports row-by-row stepper, filters, PDF highlight panel, decisions stored immediately.
- Advanced tab exposes matching + retrieval diagnostics and evidence locator.
- Settings tab supports provider/model routing/performance controls.
- README updated to reflect UI and workflow changes.
