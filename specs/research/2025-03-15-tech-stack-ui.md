Please research the best technical stack for implementing Paper Table Agent’s queue-first review UI.

## Context

We already have a recommended interaction model:
- queue/list of proposals
- focused detail pane
- PDF/page evidence viewer
- text highlight overlays
- figure crop + full page display
- filters by row, column, PDF, evidence status, figure-based evidence, ambiguous match
- progress counters
- local-first single-user MVP

We now need to choose the best technical stack to implement this UI.

## Research questions

1. Which frontend frameworks or desktop-friendly stacks best fit this UI?
2. Which PDF viewer/highlighting libraries are best for:
   - page rendering
   - text highlights
   - page navigation
   - crop/full-page coordination
3. Which grid/list components are best for the proposal queue?
4. What stack best fits a local-first MVP with modern UI quality?
5. Should the app be:
   - a local web app
   - a desktop wrapper around a web app
   - a Python UI framework
   - something else
6. What are the best choices for:
   - performance
   - maintainability
   - PDF highlighting reliability
   - local packaging

## Deliverables

Please produce a structured markdown report with:
- Executive summary
- Candidate technical stacks
- PDF viewer/highlighting comparison
- Queue/grid component comparison
- Recommended MVP stack
- Recommended later improvements
- Open questions

## Constraints

- Local-first single-user use is enough for MVP.
- The UI should feel modern and efficient.
- We care more about review trust and usability than flashy visuals.
- Please include citations/links.

I’m comparing practical UI stacks, PDF viewing/highlighting options, and queue/grid components, then I’ll synthesize them into an MVP recommendation with a clear product boundary.

I’ve narrowed this toward a web-tech stack rather than a Python-native UI, and the biggest decision point is whether packaging matters in MVP enough to justify a desktop shell. The PDF layer is the make-or-break part, so I’m grounding that recommendation in viewer APIs rather than just general frontend taste.

Thought for 4m 6s
Paper Table Agent — queue-first review UI stack research
Executive summary

The best MVP implementation path is a desktop wrapper around a web app, specifically Tauri 2 + React + TypeScript + Vite, with a queue-centric React UI and a custom PDF evidence pane built on PDF.js. This gives you a modern UI stack, strong local-file ergonomics, smaller native packaging than Electron, and better long-term control over evidence overlays than Python-first UI frameworks. Tauri is designed for small, fast desktop binaries and lets you keep a web frontend while constraining file access through scoped plugins; Electron is mature and capable, but it embeds Chromium and Node.js and needs more careful security hardening and typically carries more runtime overhead.

For the proposal queue, the best fit is TanStack Table + virtualization rather than a spreadsheet-heavy enterprise grid. TanStack Table is headless, which is a good match for a review workflow where the list is only one pane inside a more specialized UI. If later the queue becomes much more spreadsheet-like, AG Grid becomes the stronger option. MUI X is a solid middle ground if you decide to adopt Material UI broadly, but it is open-core and pushes you more strongly into the MUI ecosystem.

For the PDF viewer, the right default is PDF.js as the rendering engine, wrapped in your own React viewer layer. PDF.js is the standard open foundation, but its core layer is explicitly considered advanced and unstable for direct low-level use, so the practical approach is to build a thin app-specific viewer on top of the stable display/viewer layer concepts. If you want the fastest path and are comfortable with a paid dependency, React PDF Viewer is the best shortcut because it already provides page navigation, toolbar/sidebar layout, search, and text-highlight plugins. If you want the strongest off-the-shelf commercial SDKs, Apryse and Nutrient are the most capable, especially for selection, highlighting, and annotation APIs, but they are heavier and more expensive than an MVP usually needs.

Candidate technical stacks
1. Local web app in the browser

This is the simplest to start, and modern browsers can read and write local files via the File System Access API after explicit user permission. But that API requires secure contexts and is mainly a Chromium story rather than a truly universal desktop product surface, which makes it weaker as the primary long-term packaging boundary for a polished local-first app. It is viable for an internal prototype, but not the best MVP boundary if you want reliable installable desktop behavior.

Verdict: good for a throwaway prototype, not the best product shell.

2. Desktop wrapper around a web app with Tauri

Tauri 2 is built for “tiny and fast binaries” and lets you use any web frontend while keeping native capabilities behind plugins. Its file-system plugin supports scoped access rules and explicitly prevents path traversal via parent-directory traversal patterns, which is a strong fit for a local document-review tool. It also has an updater plugin for later packaging polish.

Verdict: best overall MVP shell.

3. Desktop wrapper around a web app with Electron

Electron is still the most mature desktop web-app shell and has excellent ecosystem coverage. But it embeds Chromium and Node.js directly, and its own docs emphasize context isolation and process sandboxing as key security measures. It is a valid fallback when you want a pure-JavaScript shell and maximum plugin maturity, but it is not the best default for a local-first single-user MVP that mainly needs a modern UI plus local file access.

Verdict: strong fallback, not first choice.

4. Python-first UI frameworks

PySide6 is the official Qt-for-Python binding and can absolutely build desktop apps, but it moves you into the Qt widget/QML ecosystem instead of the richer web PDF/viewer ecosystem. Streamlit is explicitly positioned as a framework for data scientists and AI/ML engineers to ship data apps quickly, which is not the same thing as building a dense, multi-pane review workstation UI. Flet gives Python developers cross-platform apps and can open in a native OS window, but its abstraction is best when you want to avoid frontend work, not when your product’s hardest problem is a custom evidence viewer with specialized overlay behavior. This is an inference from their positioning and ecosystems, not a hard limitation.

Verdict: not recommended for this product.

PDF viewer / highlighting comparison
PDF.js

PDF.js is the foundational open-source choice. Mozilla describes it as a general-purpose, web-standards-based PDF rendering platform. Its documented architecture separates core parsing from higher layers, and the core layer is described as advanced usage whose API is likely to change. That makes PDF.js excellent as an engine, but it also means you should not treat “raw PDF.js core” as a drop-in finished viewer.

Best use here: build a thin custom React evidence viewer around PDF.js rendering and text-layer primitives.

React-PDF (wojtekmaj/react-pdf)

React-PDF positions itself as a way to “display PDFs in your React app as easily as if they were images.” That is useful when you mainly need page rendering, but it is not, by itself, a review-oriented viewer with built-in search, sidebar, or rich highlight tooling.

Best use here: only as a thin rendering helper, not as the whole evidence-viewer strategy.

React PDF Viewer

React PDF Viewer provides a much more product-like viewer surface: default layout, toolbar, thumbnails, page navigation, search, and highlight plugins. Its highlight plugin supports text selection and highlight areas, and its search plugin supports customizable highlighted elements and programmatic keyword highlighting. The tradeoff is that it is commercially licensed rather than MIT.

Best use here: fastest MVP shortcut if paid dependency is acceptable.

Apryse WebViewer

Apryse has strong APIs for text selection, highlight annotations, and search/highlight by text position. Its docs show text-selected events, text quads, and programmatic highlight annotation creation, which maps well to anchored evidence overlays.

Best use here: if you want a commercial SDK with strong document-viewer primitives from day one.

Nutrient Web SDK

Nutrient exposes reliable, cross-browser text selection APIs, including retrieving selected text, text lines, change events, and selection bounding boxes. That is exactly the kind of API surface that helps with evidence selection UX.

Best use here: another strong commercial option if viewer reliability is worth paying for.

Recommendation for the PDF layer

For best long-term product fit, use PDF.js under a thin custom React viewer. For fastest MVP delivery, buy time with React PDF Viewer. For highest-capability commercial path, choose Apryse or Nutrient.

Queue / grid component comparison
TanStack Table + virtualization

TanStack Table is a headless table library, which means it gives you table logic without forcing markup or styling. Its docs explicitly note that virtualization is not built in, but it works with libraries like TanStack Virtual. TanStack Table is also designed to handle large client-side datasets well enough for tens of thousands of rows in many cases. For a queue-first review UI, that flexibility is a feature: you can make the list feel like a review inbox, not a spreadsheet.

Best fit: yes.

AG Grid

AG Grid has built-in row and column virtualization and a very strong feature set. Community is free; enterprise adds grouping, server-side row model, clipboard/range features, master/detail, and more. This is the strongest option if the queue becomes increasingly spreadsheet-like or if bulk analyst operations become central.

Best fit: later, if the queue evolves toward spreadsheet power-user workflows.

MUI X Data Grid

MUI X Data Grid is fast, extensible, includes filtering, sorting, and more, and the community tier is MIT while advanced features are in Pro/Premium. It is a good option if you are already committed to Material UI, but less compelling if you want a custom design system with shadcn/ui and Tailwind.

Best fit: good middle ground, but not my first choice here.

Recommendation for the queue

Use TanStack Table + TanStack Virtual for MVP. Move to AG Grid only if the queue becomes a quasi-spreadsheet with heavy bulk operations.

Recommended MVP stack
App shell

Use Tauri 2 as the desktop shell. It gives you native packaging, scoped file access, and a modern web frontend without taking on Electron by default.

Frontend foundation

Use React + TypeScript + Vite. React remains the safest choice for a custom split-pane workstation UI, and Vite is optimized for a faster, leaner development experience with fast HMR.

UI layer

Use Tailwind CSS + shadcn/ui. Tailwind is utility-first and fast for dense UI work, and shadcn/ui gives you accessible, open-code components without locking you into a monolithic component package.

Routing and filter state

Use TanStack Router if you want filters and pane state to be deep-linkable. Its typed search-parameter APIs are particularly valuable for a review UI where filters like row, column, PDF, evidence status, and ambiguity should survive refreshes and be shareable.

Async app data

Use TanStack Query for proposal lists, counts, document metadata, and review actions against the local backend. It handles caching and stale/background refresh behavior well.

Queue pane

Use TanStack Table + virtualization with a custom row renderer. This matches the product better than dropping in a spreadsheet grid.

Evidence pane

Use PDF.js as the core engine and build a thin custom evidence viewer around it:

full page render

anchored text highlights

page jump and thumbnails

figure crop thumbnail synchronized to the full page

overlay layers for evidence and accepted/rejected proposal context

That custom layer is where your product differentiation lives.

Optional acceleration path

If you want to ship the viewer faster and are okay with licensing, swap the custom viewer shell for React PDF Viewer during MVP, and keep your evidence model independent so you can later move back down to raw PDF.js if needed.

Testing

Use Playwright for end-to-end testing. It supports Chromium, WebKit, and Firefox, and its trace viewer is well suited to debugging complex multi-pane interactions.

Recommended later improvements

Add auto-updates once packaging matters. Tauri has an updater plugin, and Electron also supports auto-updating, though Electron’s built-in auto-updater has platform caveats.

If reviewer workflows become more spreadsheet-like, revisit AG Grid. If PDF highlight fidelity or annotation UX becomes a bottleneck, revisit Apryse or Nutrient. If you later want a browser-only distribution, a local web build remains possible, but it should be treated as a secondary deployment target rather than the primary MVP boundary because of file-system API constraints.

Open questions

Is a paid PDF viewer dependency acceptable?
This is the clearest fork in the road: raw PDF.js gives maximum control, while React PDF Viewer or commercial SDKs reduce upfront UI work.

Will the queue stay “review inbox” shaped, or become spreadsheet-like?
If it stays queue-first, TanStack Table is the right fit. If bulk editing and analyst operations expand, AG Grid becomes more attractive.

How much of the backend stays in Python?
My recommendation is to keep the UI web-native even if extraction/parsing stays Python-native, and bridge them locally. That is an architectural recommendation rather than a researched ecosystem fact.

What exact evidence model will the frontend receive?
The frontend gets much simpler if highlights/crops arrive as normalized page coordinates plus stable evidence IDs, instead of asking the UI to infer them.

How keyboard-driven should the review flow be?
This affects queue component choice, focus management, and whether the app should behave more like an inbox, a data grid, or a power-review workstation.

My bottom-line recommendation is:

Tauri 2 + React + TypeScript + Vite + Tailwind + shadcn/ui + TanStack Router + TanStack Query + TanStack Table/Virtual + PDF.js (custom evidence viewer).