# Web Scan: Related Projects And Practical Guidance

## Goal

This note summarizes related projects and documentation from the web that are relevant to Paper Table Agent, and extracts the ideas that are most useful for improving a local-first scientific PDF extraction pipeline.

The focus is not generic RAG. The focus is extraction from research papers with:

- layout noise
- tables and figures
- section structure
- hard-to-infer fields
- evidence grounding
- evaluation needs

## Most relevant external projects and references

## 1. GROBID

Source:

- https://grobid.readthedocs.io/en/latest/Introduction/

Why it matters:

- It is purpose-built for scientific and technical PDFs.
- It extracts structured metadata, references, full text, section titles, figures, tables, and PDF coordinates.
- It has a mature benchmarking and training/evaluation story.

Useful ideas for this repo:

- Use a specialized scholarly parser whenever possible for header metadata and structural segmentation.
- Preserve PDF coordinates as first-class provenance, not just raw text.
- Treat document structure as a sequence labeling problem, not just plain text extraction.
- Keep end-to-end benchmarking explicit and dataset-based.
- Prefer parser outputs that separate section titles, paragraphs, references, figures, tables, and callouts.

Takeaway for Paper Table Agent:

- GROBID is the strongest external validation that scientific PDFs benefit from structure-aware preprocessing before LLM extraction.
- The existing optional GROBID integration in this repo looks strategically correct and probably deserves more emphasis, not less.

## 2. PDFFigures2

Source:

- https://github.com/allenai/pdffigures2

Why it matters:

- It is older, but still one of the clearest open descriptions of scholarly PDF layout processing and error modes.
- It explicitly documents implementation steps, evaluation datasets, and recurring failure cases.

Useful ideas for this repo:

- Remove headers, page numbers, and other formatting noise early.
- Keep section-title extraction and logical sectioning separate from body text.
- Treat captions, figure/table regions, and body text as different object types.
- Maintain explicit error taxonomies for parser failures.
- Build evaluation fixtures from real scholarly PDFs, not just synthetic happy paths.

Takeaway for Paper Table Agent:

- The project already strips headers/footers and records parsing sanity metrics. PDFFigures2 supports pushing further on page-region awareness and section-level document structure.

## 3. Docling

Source:

- https://github.com/docling-project/docling

Why it matters:

- It is a modern, actively maintained document parsing stack with advanced PDF understanding.
- It exposes a unified document representation and supports lossless JSON, Markdown, and structured export.
- It is explicitly designed to prepare documents for gen-AI workflows.

Useful ideas for this repo:

- Maintain a richer internal document model than just page text plus retrieval chunks.
- Keep layout, reading order, table structure, formulas, and image classification available as structured artifacts.
- Support lossless JSON export as a canonical parse artifact.
- Keep local execution as a first-class option.

Takeaway for Paper Table Agent:

- The single biggest architectural lesson is that a robust intermediate document representation is valuable. Paper Table Agent already has chunks and parsed text, but could benefit from a more explicit block-level representation with typed elements.

## 4. Marker

Source:

- https://github.com/VikParuchuri/marker

Why it matters:

- It is one of the strongest open-source PDF-to-LLM pipelines for practical parsing quality.
- It benchmarks directly against alternative tools.
- It uses a hybrid approach: deep learning layout/OCR plus optional LLM correction.

Useful ideas for this repo:

- Use specialized layout and OCR models first, then let the LLM improve already-structured content.
- Keep JSON and chunk outputs that preserve block types and geometry.
- Use LLMs selectively for quality-critical improvements like table merging, inline math repair, or structured extraction.
- Save rich debug artifacts for layout review.
- Benchmark parsing quality separately from downstream extraction quality.

Takeaway for Paper Table Agent:

- Marker strongly supports a two-stage philosophy: first parse the PDF into better structural blocks, then run schema-based extraction on top of that representation.
- It also supports the idea that tables deserve dedicated handling rather than being flattened into generic text retrieval.

## 5. PyMuPDF4LLM

Source:

- https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/index.html

Why it matters:

- It is directly relevant to your current parser stack.
- It emphasizes Markdown extraction, multi-column support, reading-order correction, table handling, and page chunking.

Useful ideas for this repo:

- Preserve reading order more explicitly for multi-column papers.
- Export Markdown and/or JSON forms that better preserve section and list structure.
- Use layout-aware extraction when possible rather than raw text alone.
- Keep page chunking as a first-class parse output.

Takeaway for Paper Table Agent:

- This is likely one of the easiest adjacent tools to test inside the current project because it is close to the existing technology choices.

## 6. RAGFlow

Source:

- https://github.com/infiniflow/ragflow

Why it matters:

- It is not a paper-extraction system, but it is a mature example of quality-first retrieval design.
- Its README emphasizes deep document understanding, template-based chunking, grounded citations, and fused retrieval/reranking.

Useful ideas for this repo:

- Prefer chunking strategies that preserve explainable document structure.
- Keep citations traceable and reviewable.
- Treat reranking and chunk visualization as first-class quality tools.
- Build around the principle of “quality in, quality out.”

Takeaway for Paper Table Agent:

- This supports the current direction of stronger retrieval, explicit evidence, and reviewable context. It also reinforces that chunking should be structure-aware, not generic sliding windows.

## 7. Unstructured

Source:

- https://docs.unstructured.io/open-source/introduction/overview

Why it matters:

- It represents a mature ingestion framework built around partitioning documents into semantic elements.
- Its docs make the element-first chunking philosophy very explicit.

Useful ideas for this repo:

- Chunk by document elements, not just by token counts.
- Preserve metadata per element.
- Separate partitioning, cleaning, extraction, and chunking as distinct stages.

Takeaway for Paper Table Agent:

- The open-source edition has clear limitations, but the conceptual model is useful: element-first partitioning aligns well with scientific PDF extraction.

## 8. Anthropic Contextual Retrieval

Source:

- https://www.anthropic.com/engineering/contextual-retrieval

Why it matters:

- It offers concrete retrieval guidance with reported gains.
- It is directly relevant to the hardest part of your app: retrieving enough context for difficult scientific fields without losing precision.

Useful ideas for this repo:

- Use embeddings plus BM25, not embeddings alone.
- Add chunk-specific context before embedding and BM25 indexing.
- Use reranking after broad retrieval.
- Passing top-20 chunks often outperformed top-5 or top-10 in their experiments.
- For smaller corpora that fit inside the context window, whole-document prompting can outperform RAG complexity.

Takeaway for Paper Table Agent:

- This strongly supports your current hybrid retrieval setup.
- The most actionable next idea is contextualized chunks: prepend brief per-chunk situating context derived from the whole paper before embedding.

## 9. LlamaIndex node parsing guidance

Source:

- https://developers.llamaindex.ai/python/framework/module_guides/loading/node_parsers/modules/

Why it matters:

- It gives a compact overview of chunking strategies that are more nuanced than fixed token slicing.

Useful ideas for this repo:

- Sentence-aware chunking
- sentence-window retrieval with hidden surrounding context metadata
- semantic chunking with tuned breakpoints
- hierarchical chunking with parent-child relationships and auto-merging

Takeaway for Paper Table Agent:

- Hierarchical retrieval and sentence-window context are especially relevant for hard scientific claims where a single sentence is too narrow but a full section is too broad.

## 10. Smaller illustrative repos

Sources:

- https://github.com/Zipstack/llmwhisperer-table-extraction
- https://github.com/hvrdhn/PDF-Extractor

Value level:

- `llmwhisperer-table-extraction` is useful mostly as an illustrative example of table text extraction plus schema-structured output through Pydantic.
- `PDF-Extractor` is a lightweight notebook-scale example and not a strong technical guide for this repo.

Takeaway for Paper Table Agent:

- The main useful lesson is not the code quality; it is the pattern of converting messy source text into explicit structured JSON schemas.

## Cross-cutting guidance from the web scan

The same themes show up repeatedly across mature systems.

## 1. Parsing quality is upstream of extraction quality

The strongest systems do not start with raw PDF text and hope the LLM can fix it all.

They first try to preserve:

- reading order
- section hierarchy
- table structure
- figure/caption boundaries
- coordinates / geometry
- page-level provenance

Implication for Paper Table Agent:

- Better parsing is likely a larger future win than endlessly tuning the extraction prompt.

## 2. Element-aware or structure-aware chunking beats naive chunking

Repeated guidance:

- chunk by document blocks or semantic units
- keep section and page metadata
- use hierarchical nodes when possible
- keep neighboring context available without always embedding the larger span

Implication for Paper Table Agent:

- Retrieval chunks should eventually evolve from mostly text spans into typed chunks such as paragraph, table, caption, abstract, method section, result section, figure caption, etc.

## 3. Retrieval should be hybrid and reranked

The Anthropic and RAGFlow material strongly support:

- embeddings + BM25
- rank fusion
- reranking
- enough retrieved breadth before final filtering

Implication for Paper Table Agent:

- The current choice to keep BM25-like sparse retrieval, dense retrieval, query expansion, HyDE, and reranking is directionally correct.
- If you simplify anything, do not simplify away hybrid retrieval first.

## 4. Contextualized chunks are a strong next step

This was the clearest web-sourced improvement idea that is not yet central in this repo.

Meaning:

- add a short chunk-specific context line derived from the whole paper, section, or page before embedding and lexical indexing

Example:

- instead of indexing only a paragraph, index `Results section, MPRA assay design, page 6:` plus the paragraph text

Implication for Paper Table Agent:

- This could be a better next retrieval improvement than simply increasing `top_k` again.

## 5. Tables deserve dedicated treatment

Marker, Docling, PDFFigures2, and the LLMWhisperer example all reinforce this.

Implication for Paper Table Agent:

- Table-like regions should not only be flattened into plain text chunks.
- A dedicated table extraction path or typed table chunks with cell-aware structure would likely help for numeric and matrix-like fields.

## 6. Evaluation should include parser and retrieval quality, not only final answer match

Marker benchmarks parsing quality.
GROBID benchmarks end-to-end structure extraction.
Anthropic benchmarks retrieval failure rates.

Implication for Paper Table Agent:

- You should eventually have separate offline metrics for:
  - parsing quality
  - retrieval recall / failure
  - extraction correctness
  - evidence anchor quality

## What this suggests for Paper Table Agent specifically

## Strongly supported current choices

These design choices in the repo look validated by external projects:

- value-first extraction with explicit evidence metadata
- hybrid retrieval instead of dense-only retrieval
- reranking
- whole-text and paper-memory modes
- page-aware evidence anchoring and highlight recovery
- audit-mode evaluation against filled cells

## Highest-value next improvements suggested by the web scan

### 1. Add contextualized chunk indexing

Likely impact: high

Suggested shape:

- for each chunk, generate a brief context string from section title, page range, and possibly a small LLM-generated situating note
- prepend that context to the text used for embeddings and BM25 indexing
- keep original raw chunk text separate for quote validation and UI display

### 2. Introduce typed structural chunks

Likely impact: high

Suggested types:

- abstract
- section_header
- paragraph
- caption
- table_region
- table_cell_summary
- figure_caption
- reference_block

### 3. Add a dedicated table-processing path

Likely impact: high for quantitative columns

Suggested shape:

- detect table-heavy pages or regions
- preserve row/column structure where possible
- generate table-aware retrieval units in addition to plain text chunks

### 4. Strengthen parser abstraction

Likely impact: medium to high

Suggested shape:

- keep current parser path
- optionally plug in PyMuPDF4LLM, Docling, or stronger layout-aware parse outputs behind a common parsed-document interface

### 5. Separate retrieval evaluation from extraction evaluation

Likely impact: medium

Suggested metrics:

- evidence-containing chunk retrieved in top-K
- first relevant chunk rank
- retrieval failure rate by column
- table-field retrieval failure rate

## Parameter and approach guidance reinforced by the web scan

The external guidance supports these operating assumptions:

- whole-document or near-whole-document context is worthwhile when a paper fits in context
- top-20 style retrieval breadth is often better than narrow top-5 retrieval
- reranking should stay on
- BM25-style sparse retrieval should stay on alongside embeddings
- structure-aware chunking is more valuable than raw chunk overlap tuning
- parser quality and OCR fallback policy matter a lot for downstream extraction

## Bottom line

The web scan supports the current quality-first direction of Paper Table Agent.

The strongest external guidance is:

1. invest further in structure-aware parsing
2. keep hybrid retrieval plus reranking
3. add contextualized chunks
4. add table-aware extraction artifacts
5. evaluate retrieval quality separately from final extraction quality

If I were choosing only one next technical direction based on this scan, it would be:

- contextualized, typed chunks built from a stronger parsed-document representation

That seems like the best intersection of what mature projects do well and what would most likely improve this repo.