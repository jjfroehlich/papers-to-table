Please research the best low-level PDF library choice for Paper Table Agent’s MVP and recommend one.

## Context

Paper Table Agent is a local-first app that:
- parses scientific PDFs
- shows reviewable evidence in a UI
- needs page rendering
- needs quote anchoring and text-to-page mapping
- needs text highlights when possible
- needs crop extraction for figures
- needs fallback support even when the higher-level parser is separate

We already expect to use one main parser for structured extraction, but we still need a low-level PDF layer for rendering, anchoring, and review support.

## Research questions

1. Which libraries are best suited for:
   - page rendering
   - text extraction / text-location mapping
   - highlight anchoring
   - crop extraction
   - figure/page image generation
2. How do the main candidates compare for:
   - technical capabilities
   - reliability on scientific PDFs
   - integration difficulty
   - performance
   - licensing
3. What known limitations do the main candidates have for:
   - text coordinate accuracy
   - hyphenation / layout weirdness
   - scanned PDFs
   - page rendering quality
4. Which option is the best fit for our local-first single-user MVP?

## Deliverables

Please produce a structured markdown report with:
- Executive summary
- Candidate libraries compared
- Strengths/weaknesses of each
- Licensing comparison
- Recommended choice for MVP
- Fallback or abstraction recommendation
- Open questions

## Constraints

- We care about local-first use.
- We care about review UI quality.
- We need a recommendation that balances technical fit and licensing risk.
- Please include citations/links.

I’m comparing the practical MVP options now with emphasis on rendering quality, text coordinates, highlights, crop extraction, and license risk. The most likely finalists are MuPDF/PyMuPDF, PDFium/pypdfium2, Poppler, and PDF.js.

The licensing picture is becoming the main differentiator: MuPDF/PyMuPDF looks excellent technically, but the AGPL/commercial model is a real product risk. PDFium/pypdfium2 is looking like the safer default if you want one backend library that can render, map text to coordinates, and produce crops.

Thought for 5m 29s
Low-level PDF library choice for Paper Table Agent MVP
Executive summary

Recommendation: use PDFium via pypdfium2 as the authoritative low-level PDF backend for the MVP. It gives you the core review primitives you need in one permissively licensed stack: page rasterization with cropping, text extraction/search with character boxes and text rectangles, page↔bitmap coordinate conversion for overlays, and access to page objects and embedded images. pypdfium2 also ships with prebuilt packages and no mandatory runtime dependencies beyond Python/PDFium, which fits a local-first single-user app well.

Runner-up: PyMuPDF/MuPDF. If I ignored licensing, PyMuPDF is arguably the nicest single-library developer experience for this problem: clipped rendering, rich text extraction modes, quads-based search results, image metadata, and even direct highlight annotations are all excellent. But PyMuPDF/MuPDF are offered under AGPL or commercial terms, which is a materially bigger product/licensing risk than PDFium for an MVP that may evolve into closed or mixed-source distribution.

My bottom line is:

Best balance of fit + license safety: pypdfium2

Best pure developer ergonomics if AGPL/commercial is acceptable: PyMuPDF

Best browser viewer layer, but not ideal as sole backend source of truth: PDF.js

Candidate libraries compared
1) PDFium via pypdfium2 — best MVP choice

pypdfium2 wraps PDFium, describes PDFium as a “powerful and liberal-licensed library,” and exposes both helper APIs and the raw PDFium API when needed. On the page/text side, it supports page rendering with a crop= parameter, text extraction from bounded regions, text search, character boxes, text rectangles, and coordinate conversion between rendered bitmap space and PDF page space. It also exposes page objects with bounds/quads and can extract image objects. That is a very good match for your review UI primitives.

Strengths

One backend can own rendering, anchoring, crop generation, and coordinate math. search() returns character index/count; count_rects(), get_rect(), and get_charbox() let you turn that into highlight geometry; PdfPosConv translates page coordinates to rendered bitmap coordinates for UI overlays.

Good for figure/page image generation: render(crop=...) handles clipped page images, and image/page objects expose bounds and extraction paths.

License posture is MVP-friendly: PDFium is BSD-style; pypdfium2 itself is Apache-2.0 / BSD-3-Clause.

Packaging is straightforward for local apps because pypdfium2 supports prebuilt binaries.

Weaknesses

It is more low-level/C-like than PyMuPDF. The docs explicitly note that many PDFium components are not yet wrapped by helpers, so you may sometimes dip into the raw API.

PDFium is not thread-safe; the docs recommend processes rather than threads for expensive parallel rendering. For a single-user MVP this is manageable, but it matters if you later batch-render aggressively.

It does not implement layout analysis such as word/line/paragraph detection itself, so it is better as the low-level geometric layer than as the high-level parser. That is fine for your architecture because you already expect a separate main parser.

2) PyMuPDF / MuPDF — best ergonomics, biggest license risk

PyMuPDF gives you clipped raster rendering via get_pixmap(..., clip=...), multiple text extraction modes including "words"/"rawdict", search_for() with optional quads, default dehyphenation behavior, and rich image metadata via get_image_info(). It also supports direct highlight annotations from search results. Technically, that is an extremely strong fit for quote anchoring and review UI work.

Strengths

Excellent developer experience for search/highlight workflows: search_for(..., quads=True) plus add_highlight_annot(...) is unusually convenient.

Better built-in handling of some PDF text oddities, including dehyphenated search by default.

Very strong all-in-one page/image/text API surface.

Weaknesses

License risk is the main blocker: PyMuPDF is distributed under AGPL or commercial terms, and MuPDF itself is likewise offered under AGPL/commercial licensing. That may be totally fine for an AGPL project, but it is a poor default if you want to keep future distribution options open.

Search behavior still has PDF quirks: regex is not supported in search_for(), and multi-line matches can split into multiple returned boxes/quads.

3) PDF.js — best viewer layer, not best single backend layer

PDF.js is an Apache-2.0, browser-oriented PDF platform with a clear layered model: Core, Display, and Viewer. Its viewer is the basis for Firefox’s PDF viewer and is explicitly presented as a starting point for building your own viewer. It can load documents, render pages, and expose text content through getTextContent().

Strengths

Best candidate if your main concern is browser-native viewing UX.

Good permissive license: Apache-2.0.

Mature rendering/viewer stack with worker-based loading and rendering options.

Weaknesses

It is a viewer-first system, not the ideal single source of truth for backend evidence generation, image crops, and persistent anchoring metadata.

Coordinate work is more fiddly because the viewport applies transforms between PDF user space and canvas space; the official example explicitly calls out that PDF coordinates are bottom-left-origin while canvas coordinates are top-left-origin.

getTextContent() normalizes whitespace to standard spaces, which is useful in some cases but can complicate exact quote matching.

4) Poppler — mature, but not the best MVP fit

Poppler is a mature PDF rendering library based on xpdf. It is widely packaged in Linux ecosystems, but its license footprint is more complex/copyleft-heavy than PDFium/PDF.js, and in practice the integration story tends to be more fragmented across wrappers and utilities.

Strengths

Mature rendering engine with lots of downstream adoption.

Weaknesses

The packaging/licensing surface is more complex: one current Linux package lists GPL, LGPL, MIT, and other licenses together.

Less attractive than pypdfium2 for a clean, single-library Python MVP.

Licensing comparison

PDFium / pypdfium2: safest of the finalists for a product MVP. PDFium uses a BSD-style license; pypdfium2 is Apache-2.0 / BSD-3-Clause.

PyMuPDF / MuPDF: AGPL or commercial. Great technically, but you should choose it only if that licensing model is a deliberate decision.

PDF.js: Apache-2.0. Very safe from a licensing perspective.

Poppler: more complex/copyleft-heavy licensing footprint; not my first recommendation for this MVP.

Recommended choice for MVP

Use pypdfium2 as the single authoritative low-level PDF backend.

That gives you a practical MVP path:

Render each page to a bitmap for the review UI.

Anchor quotes using PDFium text search + char/rect geometry.

Convert page coords to bitmap coords for highlight overlays.

Generate crops for figures or evidence snippets from either:

page-level raster crops, or

image/page-object bounds where available.

That is the cleanest “one engine owns the geometry” model, which is exactly what you want for an audited human-review workflow.

Fallback / abstraction recommendation

Wrap the PDF layer behind a small internal interface from day 1:

render_page(page, scale, crop=None) -> bitmap

extract_text_regions(page) -> spans / chars / rects

search_text(page, query) -> matches

page_to_bitmap(page, x, y, render_params) -> bx, by

extract_image_objects(page) -> image metadata / bounds

make_crop(page, bbox, scale) -> image

Design recommendation: store evidence in canonical PDF page coordinates, not viewer pixel coordinates. Then any viewer can be swapped later.

That abstraction gives you two clean future options:

Add PDF.js later as a richer browser viewer while keeping PDFium as the backend source of truth.

Swap to PyMuPDF later if you decide AGPL/commercial is acceptable and want faster high-level developer workflows.

Open questions

Scanned PDFs / OCR fallback
This report is about the low-level PDF engine, not OCR. You still need to decide what the OCR sidecar will be for image-only pages.

Canonical highlight granularity
For MVP, decide whether anchors are stored as:

char ranges,

rects/quads,

or both.
My recommendation is both when possible: text quote + page number + geometric boxes.

Viewer strategy
If the app is browser-based, decide whether MVP uses:

server-side PDFium-rendered page images with custom overlays, or

a later PDF.js viewer integration.
For MVP simplicity and geometry consistency, I would start with PDFium-rendered page images plus your own overlays.

Figure evidence policy
Decide whether figure evidence is always a raster crop from the page, or whether you also try to detect embedded image objects and captions separately.