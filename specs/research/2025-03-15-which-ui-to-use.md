
Research the best UI/UX design patterns for Paper Table Agent’s **proposal review workflow** and recommend an MVP interaction model.

Please research the best UI/UX design patterns for Paper Table Agent’s **proposal review workflow** and recommend an MVP interaction model.

## Context

Paper Table Agent extracts proposed values for spreadsheet cells from scientific PDFs and presents them for human review.

For each proposal, the reviewer may need to see:
- row context
- target column name and description
- proposed value
- whether it is directly supported or inferred
- evidence source
- PDF page highlight for text evidence
- figure crop + caption + full page for figure-derived evidence
- concise rationale or calculation when the proposal is derived
- existing cell value in Verify mode
- accept / accept-with-edit / reject controls

The user may need to review many proposals in sequence.

We are currently considering patterns such as:
1. **single-proposal detail view**
   - one proposal at a time
   - step through sequentially
2. **interactive table + detail panel**
   - click a table cell to open detailed review
3. **list + detail review queue**
   - sortable/filterable list of proposals on one side
   - focused detail review panel on the other
4. hybrid designs

We also want filtering by:
- row
- column
- PDF
- evidence quality
- figure-based evidence
- ambiguous match

We also want:
- navigation without recording a decision
- progress counters
- possible “accept all remaining proposals” action

## Research questions

1. What review UI patterns are used in current tools for:
   - annotation workflows
   - document review systems
   - data curation tools
   - labeling tools
   - human-in-the-loop AI review products
2. What interaction model best fits our task:
   - single-item sequential review
   - list/detail queue
   - spreadsheet-first interaction
   - hybrid model
3. What are the tradeoffs in speed, clarity, and cognitive load?
4. How should the UI best show:
   - evidence
   - rationale/calculation
   - existing value vs proposed value
   - figure crop + full page
   - proposal state (found, inferred, etc.)
5. What should be MVP versus later improvement?

## Deliverables

Please produce a report with:

### 1. Executive summary
Recommend the best MVP interaction model for Paper Table Agent.

### 2. Survey of relevant UI/UX patterns
Include examples from current products/tools if possible.

### 3. Comparison of candidate layouts
Compare:
- single-proposal detail flow
- list/detail queue
- spreadsheet-first interaction
- hybrids

For each, explain:
- advantages
- disadvantages
- likely fit for our task

### 4. Recommended MVP design
Describe:
- the main screen layout
- how proposal review works
- how evidence is displayed
- how Verify mode differences are shown
- where filters and progress indicators should live

### 5. Recommended later improvements
Describe what could be added after MVP.

### 6. Open questions
List what still needs user testing or design validation.

## Constraints

- MVP is local-first, single-user desktop-style use.
- We care more about trustworthy review than flashy interaction.
- The design should work for repeated batch review of many proposals.
- Please include examples/citations/links where possible.

## Output format

Return a structured markdown report with headings:
- Executive summary
- Relevant UX patterns
- Comparison of candidate interaction models
- Recommended MVP UI
- Later improvements
- Open questions

I’m pulling together current review patterns from annotation tools, document-AI products, and general UX guidance, then I’ll map them onto Paper Table Agent’s specific review task and recommend an MVP.

I’ve got the main pattern families now: annotation-review queues, list/detail interfaces, and document-extraction review with grounded evidence. I’m filling the last gaps on evidence presentation and where bulk actions should live, then I’ll synthesize into an MVP recommendation.

Thought for 5m 49s
Executive summary

For Paper Table Agent, the best MVP is a queue-first list/detail review workflow with an on-demand spreadsheet jump, not a wizard-only flow and not a spreadsheet-first primary UI. In practice, that means a desktop split view where the reviewer keeps a sortable/filterable proposal queue visible, selects any proposal without committing to a decision, and reviews it in a rich detail workspace with evidence and controls side by side. This matches how current annotation/review tools handle high-volume work: Label Studio centers work around a Data Manager task list with filtering, sorting, and review entry points, while Windows’ list/details guidance recommends the pattern for large collections where users need to locate, prioritize, and switch quickly between items.

A pure single-proposal sequential flow is too rigid for this task. NN/g notes that users of complex applications often work in nonlinear workflows and should be able to skip ahead, loop back, and move fluidly between steps rather than being forced through a rigid sequence. Wizards reduce visible complexity, but NN/g also warns that they become tedious for repetitive item-by-item entry compared with table-like entry patterns. That tradeoff fits Paper Table Agent: you need focused review per proposal, but also flexible triage across many proposals.

A spreadsheet-first UI should be secondary, not primary. Tables are excellent for scanning and locating data, but Carbon explicitly warns that when row expansions become cramped, users should be taken to a dedicated page or side panel to complete the task; it also says data tables are not a replacement for spreadsheet apps, which is a good reminder that dense tables and rich review work are different jobs. Because each Paper Table Agent review may need PDF highlights, figure crops, captions, rationale, and Verify-mode comparisons, a detail workspace is necessary.

So the MVP recommendation is a hybrid: queue-first master/detail as the default, with spreadsheet context preview inline and a “jump to sheet” action when the reviewer wants to think in full-table context. That gives speed, trust, and flexibility without overcomplicating the first version.

Relevant UX patterns
1. Queue/list + detail review

This is the most directly relevant family. Label Studio’s Data Manager treats each row as a task and supports filtering, sorting, and ordering by things like prediction score; reviewers can start review from the Data Manager instead of being trapped in a strict stream. Microsoft’s list/details pattern likewise recommends a list pane plus a details pane for large collections where users need to locate, prioritize, and move back and forth between contexts.

This pattern fits Paper Table Agent because proposals are not just “next items.” They are a review backlog that benefits from sorting by row, column, evidence type, ambiguity, or Verify mismatch. The queue should therefore be a first-class object, not an afterthought.

2. Focused single-item adjudication

Prodigy shows the strengths of a focused one-item review surface: accept/reject/ignore actions, keyboard shortcuts, undo, save, and a history of recent decisions in the sidebar. Its review interface can present multiple versions of the same task, show session information, and let the reviewer override or correct the decision. INCEpTION’s curation page similarly auto-merges agreements, highlights differences, and lets the curator accept an annotation by clicking it.

These are strong patterns for the detail pane of Paper Table Agent. They suggest that the review surface should feel decisive and keyboard-friendly, with strong support for adjudicating between alternatives and correcting a proposal rather than only accepting/rejecting it.

3. Grounded document review

Document-review products emphasize grounded evidence and uncertainty-based routing. AWS describes human review as focusing attention on uncertain document portions and recommends confidence thresholds for routing items to review; its document-automation stack exposes confidence scores, visual grounding, and bounding boxes for extracted fields. Azure Document Intelligence likewise exposes bounding polygons and confidence for extracted words.

This is highly relevant to Paper Table Agent. Reviewers should not just see a value; they should see where it came from, whether it was directly found or inferred, and how much the system trusts it. That makes grounded evidence presentation a core UI concern, not a “nice to have.”

4. Bulk operations, progress, and state tracking

Label Studio puts bulk labeling in the list layer: reviewers select filtered rows and open a side panel for batch actions. Its dashboards and state model also track tasks through Needs Review, In Review, and Done, with counters for accepted annotations, rejected annotations, and time spent. Carbon’s data-table guidance similarly places search, filtering, and batch actions in the table toolbar.

That suggests two things for Paper Table Agent: progress and bulk operations should live near the queue/header layer, and any “accept many” action should operate on a visible filtered subset, not on hidden items.

5. Progressive disclosure, side panels, and nonmodal review

NN/g recommends progressive disclosure to reduce cognitive load by showing what is needed for the current task and deferring secondary material. Carbon’s forms guidance recommends a side panel for forms with more than five inputs and advises against hiding essential information in tabs or accordions. NN/g also warns that modal dialogs interrupt workflow and increase context-recovery cost.

For Paper Table Agent, that means the main review UI should be nonmodal, with the core proposal, evidence, and decision controls visible together, while secondary technical detail can be collapsible.

Comparison of candidate interaction models
Single-proposal detail flow

Advantages:
It minimizes on-screen clutter and makes the reviewer focus on one decision at a time. This is aligned with wizard-style benefits: less information per screen and lower initial overwhelm. It is also a natural fit for keyboard-heavy accept/reject/edit loops like Prodigy’s.

Disadvantages:
It is weak for triage, reordering, and selective review. NN/g’s guidance on complex apps argues against rigid linear flows for nonlinear work, and wizard-style flows become tiring when users need to compare, revisit, or jump around many items.

Fit for Paper Table Agent:
Good as a secondary focus mode for hard cases, not as the primary model. Your reviewers will often want to skip, compare, filter, and revisit proposals before deciding.

List/detail queue

Advantages:
This best supports batch review. It combines triage, filtering, prioritization, and navigation with a rich detail workspace. It matches Label Studio’s Data Manager + review pattern and Microsoft’s list/details guidance for large collections that require quick switching between items.

Disadvantages:
If poorly designed, it can feel busy. The risk is overloading the detail pane or turning the queue into a second spreadsheet. The answer is progressive disclosure and careful hierarchy, not abandoning the model.

Fit for Paper Table Agent:
Best primary fit. It handles many proposals, variable evidence types, Verify-mode mismatches, and nonlinear reviewer behavior better than the alternatives.

Spreadsheet-first interaction

Advantages:
It is familiar, good for scanning overall row/column context, and efficient for quick low-context edits. NN/g explicitly notes that spreadsheet-like entry can outperform wizard-style entry for repetitive tabular input.

Disadvantages:
Evidence-heavy review does not fit naturally in cells. Carbon warns that expanded table rows become cramped and should move to a dedicated page or panel when the work gets more complex. Figure crops, caption context, PDF highlights, rationale, and Verify comparisons will quickly exceed what a table cell can comfortably hold.

Fit for Paper Table Agent:
Useful as a secondary context mode, not the primary review surface. The sheet is the destination for final accepted values, but it should not be where most evidence review happens.

Hybrid models

Advantages:
A hybrid can combine the best parts: queue-first triage, rich detail review, and spreadsheet jump-in for context. This mirrors how mature tools separate backlog management, adjudication, and bulk actions rather than forcing everything into one surface.

Disadvantages:
Hybrids can sprawl if too many modes are introduced too early. The MVP should therefore be a disciplined hybrid, not multiple equal-first-class workspaces.

Fit for Paper Table Agent:
Best overall, as long as it stays queue-first. In other words: hybrid architecture, but one clear primary workflow.

Recommended MVP UI
Main screen layout

Use a three-pane, nonmodal desktop layout:

Left pane: proposal queue
A sortable/filterable list of proposals. Each row should show enough metadata to triage quickly: row ID, column, short proposed value preview, evidence badge, state badge, PDF/page indicator, and Verify mismatch status. This is the “work queue.”

Center pane: evidence viewer
This is where the PDF page, text highlight, figure crop, caption snippet, and full-page view live. It should be the largest pane, because trust depends on seeing evidence directly in context. Grounding and confidence are established document-review patterns in current systems.

Right pane: proposal detail + decision panel
This should contain row context, column name/description, proposed value, badges, Verify comparison, rationale/calculation, and accept/edit/reject controls. Carbon’s guidance points toward a side-panel style for complex forms and warns against hiding core information in tabs/accordions.

Do not make review happen inside modal dialogs. NN/g’s guidance is clear that modals interrupt workflow and increase the cost of recovering context.

How proposal review works

The reviewer selects any proposal from the queue. Selection does not record a decision. They inspect the evidence, optionally edit the value, and then choose:

Accept

Accept with edit

Reject

Skip / leave undecided

Keyboard shortcuts should be first-class, borrowing from annotation tools like Prodigy: accept/reject/ignore-like actions, undo, save, and next-item navigation. Also include a visible recent-history/undo affordance for confidence and recovery.

The system should support navigation without decision via queue clicks, next/previous, and filter changes. That aligns with complex-app guidance for nonlinear work rather than a forced wizard sequence.

How evidence is displayed

For text-grounded proposals, show:

page number

exact quote/snippet

synchronized page highlight in the PDF

one-click jump to the full page

For figure-derived proposals, show:

figure crop first

caption snippet directly next to it

one-click toggle to the full page

clear label that this is figure-based evidence rather than direct text extraction

For derived/inferred proposals, add a compact “How derived” box that shows the rationale or calculation and references the supporting evidence items. AWS explicitly distinguishes explicit extraction from implicit extraction, which maps well to a visible direct-vs-inferred badge in the UI.

Use progressive disclosure for secondary material only: raw OCR text, normalization trace, model metadata, alternate evidence candidates. Keep the core evidence visible by default.

How Verify mode differences are shown

In Verify mode, place a compare card near the top of the detail pane:

Existing value

Proposed value

optional editable Final value

Also show a simple status badge such as:

Matches existing

Differs from existing

Existing empty

This is where Paper Table Agent should emphasize trust. The reviewer should see the difference immediately before reading the rationale. Prodigy and INCEpTION both show the value of adjudication-oriented views that expose competing versions clearly and support override/correction.

Where filters and progress indicators should live

Put filters and progress in a sticky top bar above the queue, not buried in settings. At minimum, include filters for:

row

column

PDF

evidence quality

figure-based evidence

ambiguous match

verify mismatch

review state

For progress, show both a simple global indicator and decision counts, for example:

Reviewed / Remaining

Accepted

Accepted with edit

Rejected

Skipped

Label Studio’s dashboards and task states show why this matters: people need to know not just how much is done, but what state work is in and where bottlenecks are.

Bulk actions in MVP

I would not ship a blanket “accept all remaining proposals” in the first MVP. It is too risky for a trust-first system. If you need a bulk action early, make it a guarded “Accept all visible” action that only applies to the current filtered subset, shows a preview count, requires confirmation, and is fully undoable. Label Studio and Carbon both place batch actions at the list/table layer, which is the right place for this control.

Later improvements

Add a focus mode that temporarily hides the queue and gives a single-proposal full-screen review surface for hard cases. That gives you the benefits of a sequential detail flow without making it the default. This is a good second step after the queue-first MVP.

Add a synchronized table mode where the reviewer can jump from a proposal to the sheet, inspect broader row/column context, and return to the queue without losing position. This should remain a companion mode, not the primary review surface.

Add safe bulk review tools after you have strong undo/history and reviewer trust. Good candidates are “accept all visible direct-supported items,” “reject all unresolved ambiguous matches,” or “mark visible items for later.” Keep bulk actions filter-scoped and reversible.

Add smarter prioritization such as low-confidence first, Verify mismatches first, or figure-based first, since current document-review systems commonly use confidence to decide what should be reviewed by humans.

Add lightweight reviewer aids: saved filter views, notes on why a proposal was rejected, and session resume cues. NN/g’s guidance for complex applications highlights the value of supporting interruptions and helping users resume work.

Open questions

How much row context is enough in the detail pane: a mini row strip, several neighboring cells, or a larger table preview?

For figure-derived evidence, is crop-first sufficient, or do reviewers want the full page visible by default?

How much rationale/calculation detail helps trust before it starts to feel noisy?

Are the proposed state labels intuitive, or do reviewers need more explicit wording than badges like Direct, Inferred, and Ambiguous?

What default ordering produces the best throughput: original row order, low-confidence first, Verify mismatches first, or grouped by PDF?

Do reviewers want a single queue for everything, or separate saved views such as easy direct text, figure cases, and Verify conflicts?

At what point do users trust any bulk action enough for it to save time rather than create anxiety?

The strongest next step is a small usability test with 5–8 realistic review sessions comparing:

queue-first split view

pure single-item flow

spreadsheet-first + detail drawer

My expectation is that the queue-first hybrid will win on speed and confidence, while the spreadsheet-first version will feel familiar but too cramped for evidence-heavy decisions.

Using your intuition and user-friendliness answer the open questions yourself please. We need a great ui/ux. 

I’m turning the remaining open questions into concrete product decisions now, grounded in the review-tool patterns and general UX guidance rather than leaving them as “needs testing.”

Thought for 43s

Yes — I’d stop treating those as open questions and make these product decisions for MVP.

The overall principle stays the same: queue-first list/detail review, because that pattern is specifically good for locating and prioritizing large collections and working back and forth between list context and item detail. For dense data, search/filter/batch actions belong in the list toolbar, while the detail view should carry the heavier evidence and editing work. Progressive disclosure should hide secondary complexity, not the core information needed for a decision.

My decisions on the open questions
1) How much row context is enough?

Show a compact row strip by default, not the full spreadsheet.

My recommendation:

Show the target cell, plus 2–4 most relevant neighboring columns in the same row.

Always include the row identifier/title column if one exists.

Add a “show full row” toggle in the detail pane.

Add a “jump to spreadsheet” action for rare cases where table-wide reasoning is needed.

Why: reviewers usually need just enough context to understand what this row is about, not a full spreadsheet embedded in the review panel. Full-row or full-sheet views should be available, but secondary.

2) For figure-derived evidence, what should be shown first?

Show figure crop first, with caption directly attached, and keep full page one click away.

My recommendation:

Default view: figure crop + caption snippet

Secondary controls: open full figure and open full PDF page

If multiple subpanels exist in the figure, let the crop include a subtle locator like “Fig. 2b”

Keep the crop fairly large; do not make it thumbnail-sized

Why: the crop answers “what am I looking at?” fastest. The caption answers “what does the paper say this is?” The full page is important, but usually for validation, not first-pass comprehension.

3) How much rationale/calculation detail is helpful?

Use a three-level rationale pattern:

Level 1: one-line verdict

“Derived from Fig. 3C by comparing WT vs KO bar labels.”

Level 2: compact steps

2–4 bullet-like lines or short sentences:

source used

transformation or comparison

confidence caveat if relevant

Level 3: expandable raw reasoning/calculation

exact arithmetic

parsing details

normalization/rounding notes

For direct text extraction, often Level 1 is enough.
For inferred values, show Level 1 + Level 2 by default.
For calculations, make Level 3 expandable.

Why: reviewers need confidence, not a wall of reasoning. The main question is “do I trust this enough to accept or edit it?”

4) Are state labels intuitive enough?

No — I would make them more explicit.

Instead of terse labels like:

found

inferred

ambiguous

Use:

Direct evidence

Inferred from evidence

Ambiguous match

Figure-based evidence

Weak evidence

No supporting evidence found only if that case exists

Then use color and icon support, but keep the wording human-readable.

Why: “found” and “inferred” are system-centric words. “Direct evidence” and “Inferred from evidence” tell the reviewer what matters immediately.

5) What should the default ordering be?

Default to highest review risk first, not original row order.

My recommended priority order:

Verify mismatches

Ambiguous matches

Weak evidence

Figure-based evidence

Inferred from evidence

Direct evidence

Within each bucket:

sort by column, then row

or optionally by PDF/page order if people tend to review paper-by-paper

Why: this front-loads the decisions where human review adds the most value. Easy direct-text proposals can wait. Reviewing the riskiest items first is more trustworthy and more efficient.

6) One queue or multiple saved views?

Use one master queue with saved preset views.

Default presets:

Needs attention

Verify conflicts

Figure evidence

Weak / ambiguous

Direct evidence

All proposals

Why: one queue avoids fragmentation and confusion. Presets give users the feeling of multiple workflows without actually splitting the system into separate worklists.

7) When is “accept many” trustworthy enough?

Not in the first release for all items.

My rule:
Only allow bulk acceptance for a narrow, low-risk subset:

direct evidence

high-confidence

no ambiguity

no existing-value conflict

no figure-only inference

same filtered view, fully visible to the user

So the MVP bulk action should be:

Accept all visible low-risk proposals

Not:

“Accept all remaining proposals”

Also require:

confirmation with count

undo

a short explanation of the filter that defines the batch

Why: users trust bulk actions when the system explains exactly what subset is affected and that subset feels obviously safe.

The concrete UX I would lock in
Queue pane

Each proposal row should show:

status badge

row label

column name

short proposed value preview

PDF/page

Verify mismatch marker if applicable

That lets users triage without opening every item.

Detail pane

Top to bottom:

Column name + description

Row context strip

Existing value / proposed value / editable final value

State badges

Evidence block

Rationale block

Decision controls

This order reflects reviewer questions:

what field is this?

what row is this?

what is proposed?

how strong is it?

what supports it?

do I accept it?

Evidence block behavior

For text evidence:

quote first

highlighted PDF synchronized beside it

For figure evidence:

crop first

caption attached

full page toggle nearby

For derived values:

evidence first

rationale immediately below

Decision controls

Buttons:

Accept

Accept with edit

Reject

Skip

Keyboard:

A accept

E edit/accept

R reject

S skip

J/K next/previous

Progress

Show:

Reviewed / total

accepted

edited

rejected

skipped

And show the active filter scope, so users understand what progress bar they are looking at.

The decisions I’d formally adopt

If I were writing the product spec, I’d state it this way:

Paper Table Agent uses a queue-first master/detail review UI

Review is nonlinear by default

The detail pane shows compact row context, not the full spreadsheet

Figure evidence is crop-first, caption-attached, full-page-on-demand

Rationale uses progressive disclosure

Proposal states use plain-language labels

Default ordering is highest-risk-first

There is one queue with saved views

Bulk accept is limited to visible, low-risk subsets, with undo

That is the version most likely to feel both fast and trustworthy.

If you want, I can turn this into a very concrete wireframe/spec with exact pane layout, component hierarchy, and button labels.

For my app what are the options for the interface? A local browser-based app? What packages or frameworks are best to use here? Do research, pull ideas, evaluate, compare, suggest best decisions. Some background on the app: "concise product statement

Paper Table Agent is a local-first paper-to-table review system. It matches papers to spreadsheet rows, proposes values for missing or verified cells with anchored evidence, and lets a human reviewer accept, edit, reject, or bulk-accept a filtered proposal subset before exporting an audited XLSX table update."

I’m comparing realistic interface architectures now: plain local web app, desktop shell around a web app, and native desktop. I’m also checking the ecosystem pieces that matter most for your workflow: table/grid, PDF evidence viewing, and Python integration.

I’ve narrowed this to three viable interface architectures for your app: plain local web app in the browser, web UI packaged as a desktop app, and native desktop. The key discriminator is not just “can it render UI,” but how cleanly it handles local files, PDF evidence, Python extraction, and audited export.

Thought for 3m 26s
Bottom line

For Paper Table Agent, I would build a local desktop app with a web UI, not a plain website and not a fully native Qt-style UI.

The best MVP decision is:

Tauri 2 + React + TypeScript + Vite + Python FastAPI sidecar + PDF.js + TanStack Table/TanStack Virtual + SQLite/local files

Why this is the best fit:

your app is local-first

it needs strong file-system access

it needs a rich review UI with tables, filters, PDF evidence, and split panes

it likely already has or will have Python-heavy extraction logic

it should feel like a desktop work tool, not a webpage in a tab

Tauri is a strong match because it uses the system webview rather than bundling a full browser, can package external binaries as sidecars, and exposes desktop plugins for dialogs and filesystem access. Tauri’s own docs also explicitly warn that using a localhost-served frontend in production brings “considerable security risks,” which is a good reason to bundle the frontend assets directly instead of shipping a desktop wrapper around a local web server.

The realistic interface options
1. Plain local browser app

This means something like:

FastAPI backend running on localhost

React frontend opened in Chrome/Edge

files opened and saved through browser file APIs

This is a real option and the fastest way to get a prototype working. FastAPI is an ASGI framework typically run with Uvicorn, and the browser File System Access API can read, write, and even enumerate local files/folders after user permission. However, the modern File System Access API is mainly available in Chromium-based browsers, and permissions are not reliably persistent across sessions unless handles are cached. That makes it workable for prototyping, but weaker as a polished desktop review tool.

Best for: fastest prototype, internal dogfooding, no installer
Main downside: browser-dependence, weaker desktop feel, more friction around file handling and persistence

2. Desktop app with web UI in a system webview

This is the Tauri path.

Tauri is built around a web frontend rendered in the operating system webview, and its docs emphasize small binaries because it does not bundle a browser engine with every app. It also supports packaging external binaries as sidecars, which is very relevant if your extraction engine is Python-based. On top of that, Tauri has plugins for native dialogs, filesystem access, SQL, updater, and window APIs.

Best for: your app
Main upside: desktop UX without giving up web-stack velocity
Main downside: some packaging complexity, especially around bundling Python

3. Desktop app with bundled Chromium

This is the Electron path.

Electron embeds Chromium and Node.js into the app binary, which gives you a very stable rendering target and broad web-platform support. It also has native dialogs and a utility-process model for heavier work. The tradeoff is a heavier runtime and a bigger operational/security surface. Electron’s security docs are very explicit that rendering remote or untrusted content locally is dangerous, and its sandboxing guidance exists because this is a real concern in the platform.

Best for: teams already deep in Electron/Node, or apps needing a fully consistent embedded browser everywhere
Main downside: heavier than you need for a local scientific review tool

4. Native desktop UI in Python

This means PySide6 / Qt for Python.

Qt for Python provides the official Python bindings for Qt, and QtWidgets is specifically for classic desktop-style UIs. This route is fully viable, especially if you want everything in Python. But for your specific product, a lot of the UX you want—review queues, split panes, interactive grids, PDF evidence panels, custom badges and stateful filters—is easier and faster to iterate in a web UI than in a widget-first native stack.

Best for: Python-only teams that strongly prefer native widgets
Main downside: slower UI iteration and weaker ecosystem for this kind of custom review workflow

5. Python-first wrapper around a webview

This is pywebview.

pywebview is a lightweight cross-platform wrapper around a native webview and includes a built-in HTTP server. It is a decent shortcut if you want a very Python-centric stack but still want HTML/CSS/JS for UI. The reason I would still choose Tauri over it is product robustness: Tauri has a more deliberate desktop-app platform model, stronger plugin story, better packaging direction, and better long-term structure for a serious end-user tool.

Best for: quick Python-first internal tools
Main downside: less compelling as the long-term foundation for a polished desktop product

My recommendation
Best MVP architecture

Use:

Tauri 2 for the desktop shell

React + TypeScript + Vite for the frontend

FastAPI as the local extraction/review API

Python sidecar binary packaged with Tauri

PDF.js for the evidence viewer

TanStack Table + TanStack Virtual for the proposal queue and spreadsheet-like views

SQLite for local review state and audit trail

native file dialogs for opening PDFs/XLSX and choosing export paths

This gives you:

a desktop experience

a local-first model

a modern, flexible UI

reuse of Python extraction code

room to grow into a robust audited review tool

Why not just make it a local browser app?

You can, and it would be a good first internal prototype.

But for your product statement—

“a local-first paper-to-table review system … before exporting an audited XLSX table update”

—there are several reasons I would still package it as a desktop app:

it feels more like a dedicated work tool than “a localhost page”

native dialogs and filesystem integration are cleaner

you avoid browser-specific edge cases around file APIs

you can ship one controlled environment instead of “please use Chromium browser X”

you can later add proper installer, window state, updater, and file association behavior more naturally

The biggest technical clue is that the browser file APIs are useful, but still shaped by browser permission/session rules, while Tauri is explicitly built to expose filesystem and dialog capabilities in a desktop model.

Frontend framework decision
React or something else?

I would choose React.

Not because other frameworks are bad, but because your app is unusually dependent on:

advanced table/grid options

PDF viewer integrations

mature state-management/data-fetching libraries

custom review-panel composition

That ecosystem is strongest and easiest to compose in React right now. The strongest evidence is indirect but practical: the most mature and flexible table/grid options you’re likely to want here—TanStack Table, AG Grid, MUI X, React PDF Viewer—are all first-class in React.

Vite or Next.js?

Use Vite, not Next.js, for MVP.

Vite is built as a fast frontend build tool with a fast dev server and HMR. Your app does not need SEO, server rendering, or a hosted web deployment model as a primary goal. For a local-first desktop product, Vite is the simpler and cleaner choice.

Data grid / table choice

This is one of the most important decisions.

Option A: TanStack Table

TanStack Table is a headless table library: it gives you the logic and state, but not the rendered UI. That is excellent when the table is not just a generic spreadsheet, but part of a custom workflow. It also works well with TanStack Virtual for large lists and grid-like rendering.

Why it fits your app well:
Your primary interface is not “a spreadsheet editor.” It is a review queue + detail evidence workspace. Headless tools let you design exactly that instead of fighting a one-size-fits-all data grid.

Option B: AG Grid

AG Grid is a very feature-rich, high-performance data grid with Community and Enterprise editions. Community is free/open-source and already includes core grid features; Enterprise adds more advanced capabilities.

Why it might fit:
If you decide the app should feel much more like a spreadsheet and you want lots of built-in grid behavior quickly, AG Grid is strong.

Why I would not start here:
It is more opinionated, and your review workflow is more custom than “just a big table.”

Option C: MUI X Data Grid

MUI X Data Grid is capable and polished, but it is open-core: advanced features are paid Pro/Premium. MUI’s own docs note that Pro/Premium are commercially licensed, and the pricing/licensing model changed again in 2026.

Why I would avoid it for MVP:
For a local-first research tool, I would rather not build core interaction assumptions around paid grid tiers unless you already know you want that ecosystem.

My decision

Use TanStack Table + TanStack Virtual for MVP.
Keep AG Grid Community as the fallback if later you decide spreadsheet behavior should dominate.

PDF / evidence viewer choice

Use PDF.js as the foundation.

PDF.js is Mozilla’s web-standards-based platform for parsing and rendering PDFs in the browser/webview. Since your app needs synchronized page highlights, evidence anchoring, figure crops, and probably custom overlays, starting from PDF.js gives you maximum control.

If you want a quicker scaffold for a viewer, React PDF Viewer is a valid wrapper option; it is a React PDF viewer powered by PDF.js and uses a worker model for parsing/rendering. But because your evidence experience is central and custom, I would still treat PDF.js as the real core dependency.

Backend/API choice

Use Python + FastAPI for the local backend.

FastAPI is modern, ASGI-based, and production-friendly. It is a good fit for:

extraction jobs

proposal generation

PDF/figure preprocessing

audit-log writes

Excel import/export services

Then package that Python backend as a sidecar binary with Tauri rather than making the UI talk to a browser-hosted localhost service in production. Tauri explicitly supports bundling external binaries.

App state and local storage

For the frontend, I would use:

Zustand for local UI state

TanStack Query for async job/result state

Zustand presents itself as a small, fast, scalable state-management solution, which is a good match for local panel state, selected proposal, filters, and UI preferences. TanStack Query is strong for async state such as loading proposals, running extraction, refreshing evidence, and retrying tasks.

For persisted app state, use SQLite locally. If you want the frontend to talk to it directly inside Tauri, there is an official SQL plugin supporting SQLite; otherwise the Python backend can own the database.

Routing

You may not need much routing at all.
This could be a mostly single-workspace app with a few top-level views:

Import / Match

Review

Export / Audit

If you want routing, use React Router in a minimal way. Its docs explicitly describe it as usable “as minimally as you want,” which is the right posture for a desktop work app.

The stack I would choose
Recommended stack

Shell

Tauri 2

Frontend

React

TypeScript

Vite

Review UI

TanStack Table

TanStack Virtual

your own split-pane layout and review components

PDF evidence

PDF.js

State

Zustand

TanStack Query

Backend

Python

FastAPI

Uvicorn

packaged as a Tauri sidecar

Persistence

SQLite

audit log + proposal states + saved filters + review history

File handling

native open/save dialogs

local filesystem access via desktop shell

The product decisions I would make now

Do not ship MVP as only a plain localhost browser app.
Use that for rapid prototyping if needed, but target a packaged desktop app.

Choose Tauri over Electron.
Electron is fine, but Tauri is a better fit for a local scientific workbench that does not need bundled Chromium.

Choose React + Vite.
It is the fastest path to the kind of custom review UI you need.

Choose TanStack Table, not a spreadsheet-first grid, as the main review surface.
Your app is a review workflow first, spreadsheet viewer second.

Use PDF.js directly for the evidence pane.
The evidence viewer is too central to outsource completely to a black-box viewer.

Keep Python in the architecture.
Your extraction and audit logic will likely benefit from it, and Tauri sidecars make that practical.

One-sentence recommendation

Build Paper Table Agent as a Tauri desktop app with a React/Vite frontend and a packaged Python/FastAPI sidecar, using TanStack Table for the review queue and PDF.js for evidence, because that gives you the best balance of local-first UX, control, extensibility, and implementation speed.