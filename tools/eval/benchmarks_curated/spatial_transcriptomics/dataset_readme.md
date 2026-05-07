# Spatial transcriptomics curated benchmark

## Dataset purpose
Curated benchmark for extraction tasks centered on spatial platform identification, tissue context, resolution descriptions, computational outputs, and figure-backed biological interpretation.

## Why the selected papers are useful for this benchmark
The selected set spans Cell, Nature, Nature Methods, Science, and bioRxiv layouts with platform, multimodal, and computational diversity across tissue profiling and clone-tracing use cases.

## Selected paper summary
- `ST01` `ST01_open_st_3d.pdf` — Open-ST: High-resolution spatial transcriptomics in 3D. Selected for a modern Cell layout, explicit 2D-to-3D workflow figures, and clinically relevant tissue heterogeneity results that combine platform and interpretation tasks.
- `ST02` `ST02_slide_tags_multimodal.pdf` — Slide-tags enables single-nucleus barcoding for multimodal spatial genomics. Selected because it adds a multimodal Nature layout, strong image-plus-map figures, and clear assay/reporting differences from spot-based methods.
- `ST03` `ST03_hdst_tissue_profiling.pdf` — High-definition spatial transcriptomics for in situ tissue profiling. Selected for its methods-focused manuscript style, explicit capture-unit language, and tissue-domain interpretation that is concise but still figure rich.
- `ST04` `ST04_slide_seq_high_resolution.pdf` — Slide-seq: A Scalable Technology for Measuring Genome-Wide Expression at High Spatial Resolution. Selected as a foundational bead-based platform paper with clear numeric resolution language, compact methods/results structure, and strong map-based figures.
- `ST05` `ST05_spacebar_clone_tracing.pdf` — SpaceBar enables clone tracing in spatial transcriptomic data. Selected to preserve a preprint layout and a distinct clone-tracing plus spatial-transcriptomics task mix that is not duplicated by the other selected platform papers.

## Excluded paper summary
- `nihms-1001922.pdf` — Three-dimensional intact-tissue sequencing of single-cell transcriptional states. Excluded because the selected set already includes a modern 3D workflow and a distinct imaging-style preprint, making this the most redundant relative to the final mix.

## Task difficulty mix
- Metadata lanes stay easy so row-to-PDF alignment is deterministic.
- Medium fields emphasize method naming, assay context, and controlled-category extraction.
- Hard fields emphasize representative numeric choice, architecture compression or spatial interpretation, and concise evidence-backed reasoning.
- Hard columns in this dataset: spatial_resolution_or_capture_unit, key_spatial_domain_or_cell_type_finding.

## Proposal types tested
- Exact metadata transcription
- Controlled-category method labeling
- Short assay or tissue context extraction
- Numeric or capture-unit extraction
- Figure-panel citation
- Concise explanatory summary backed by text and figures

## Vision-dependent columns
key_spatial_domain_or_cell_type_finding, representative_spatial_figure_panel

## Manual gold-standard annotation instructions
1. Work row by row in the renamed `pdfs/` directory so annotations always reference the curated filenames.
2. Keep the metadata fields as already populated unless manual PDF review uncovers a confident correction.
3. For extraction-target columns, use the conventions in `schema.md`, especially the representative-value rules for nontrivial numeric fields.
4. Record only one final gold answer per column; if a paper provides several candidate values, prefer the one tied to the principal figure or headline result.
5. When a target is truly absent or not confidently recoverable from the provided PDF, leave it blank and note the reason in manual annotation notes outside this checked-in template.

## Known limitations
- This pass intentionally leaves all extraction-target cells blank.
- Some papers are author-manuscript or preprint PDFs, so pagination and figure labeling style are not perfectly uniform.
- Manual annotation still needs to confirm ambiguous metadata fields that were left blank for safety.
