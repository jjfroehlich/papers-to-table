Here is the condensed summary of the ingestion-tool research for your Paper Table Agent.

Bottom line

The best overall core stack for your use case is:

Docling + GROBID + PyMuPDF.
That combination best matches your needs for scientific PDFs, structured extraction, table-aware parsing, provenance/evidence anchoring, human review, and local-first operation.

Why this stack is the best fit

Docling should be your primary parser because it is designed for document conversion with strong layout analysis, table structure recognition, local execution, and structured outputs, and its pipeline preserves text tokens plus page coordinates that are useful for downstream grounding and review. It also exposes a rich document representation rather than only flattened text.

GROBID should be your scientific-paper companion parser because it is specifically focused on technical and scientific publications and converts PDFs into structured XML/TEI, which is especially helpful for title/authors/year/DOI/header/reference extraction and paper-structure recovery.

PyMuPDF should be your low-level fallback and display layer because it gives you reliable page-level text extraction, optional OCR support for image-based text, and page-oriented access that is well suited for deterministic evidence rendering and recovery when higher-level parsers fail or disagree. PyMuPDF4LLM also supports Markdown output and page chunks, which is useful for retrieval and debugging.

My recommendation is therefore not “pick one parser,” but “use a layered stack”:

Docling for the main parsed-document representation

GROBID for scholarly metadata and structure

PyMuPDF for raw page truth, OCR fallback, and evidence anchoring/rendering

How the main alternatives compare

Marker is the strongest local alternative to Docling. It converts documents to markdown, JSON, chunks, and HTML, supports tables, equations, references, and code blocks, and runs on GPU, CPU, or MPS. It is attractive if you want aggressive markdown-first conversion, but I would still prefer Docling as your main parser because your product needs a review-oriented, provenance-friendly document representation rather than just excellent markdown export. Marker is also GPL-3.0, which may matter depending on your distribution plans.

Unstructured is a good ETL-style ingestion framework. It outputs structured document elements and tracks element-level metadata, and its PDF partitioning strategies expose different quality/speed tradeoffs. I see it as useful for broad document pipelines, but less tailored to your exact combination of scientific papers + evidence display + reviewer trust than Docling plus GROBID.

LlamaParse is a strong managed/cloud option. Its Layout Agent mode is explicitly aimed at preserving layout fidelity and is strong on tables, lists, headings, and body text using VLM-based parsing. It looks good for fast prototyping, but it is not ideal for your local-first, auditable, reproducible workflow.

Azure Document Intelligence is very strong for OCR/layout-heavy documents and returns tables/cells with bounding boxes, confidence, and references to lines/words. It is a serious fallback choice for difficult scans or ugly PDFs, but it is a cloud service and is more general-purpose document AI than scientific-paper-specific tooling.

Google Document AI / Gemini layout parser is also strong, especially because it produces layout-aware, context-rich chunks that preserve headings and table context. That is good for retrieval pipelines, but again it is more cloud-first and less specialized for the scholarly-paper workflow you care about most.

Amazon Textract is best viewed as a cloud table/OCR specialist. It can extract cells, merged cells, headers, titles, footers, and table types with geometry, so it is useful for hard table pages, but it is not the main parser I would choose for research-paper ingestion.

Camelot, Tabula, and Tabled are not full document parsers; they are table extractors. Camelot and Tabula only work on text-based PDFs, while Tabled is a small library dedicated to detecting and extracting tables into markdown/csv/html. These are good supplements for stubborn table pages, not foundations for your whole pipeline.

What this means for your architecture

For your app, I would implement ingestion like this:

Run Docling on every PDF to build the main parsed-document artifact.

Run GROBID in parallel to recover scientific-paper metadata and structure for matching and section-aware extraction.

Normalize both outputs into your own internal ParsedDocument contract.

Use PyMuPDF underneath for raw page text, OCR rescue, and evidence-display fallback.