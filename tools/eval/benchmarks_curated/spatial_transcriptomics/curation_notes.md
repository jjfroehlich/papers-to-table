# Spatial transcriptomics curated benchmark curation notes

## All PDFs found

- `PIIS0092867424006366.pdf` — Open-ST: High-resolution spatial transcriptomics in 3D (47 pages; Cell).
- `s41586-023-06837-4.pdf` — Slide-tags enables single-nucleus barcoding for multimodal spatial genomics (32 pages; Nature).
- `nihms-1536533.pdf` — High-definition spatial transcriptomics for in situ tissue profiling (14 pages; Nature Methods).
- `nihms-1036108.pdf` — Slide-seq: A Scalable Technology for Measuring Genome-Wide Expression at High Spatial Resolution (12 pages; Science).
- `ST03_Kinsler_2025_SpaceBar_bioRxiv.pdf` — SpaceBar enables clone tracing in spatial transcriptomic data (25 pages; bioRxiv).
- `nihms-1001922.pdf` — Three-dimensional intact-tissue sequencing of single-cell transcriptional states (22 pages; Science).

## Selected PDFs and why they were selected

- `ST01` `ST01_open_st_3d.pdf` from `PIIS0092867424006366.pdf` — Selected for a modern Cell layout, explicit 2D-to-3D workflow figures, and clinically relevant tissue heterogeneity results that combine platform and interpretation tasks.
- `ST02` `ST02_slide_tags_multimodal.pdf` from `s41586-023-06837-4.pdf` — Selected because it adds a multimodal Nature layout, strong image-plus-map figures, and clear assay/reporting differences from spot-based methods.
- `ST03` `ST03_hdst_tissue_profiling.pdf` from `nihms-1536533.pdf` — Selected for its methods-focused manuscript style, explicit capture-unit language, and tissue-domain interpretation that is concise but still figure rich.
- `ST04` `ST04_slide_seq_high_resolution.pdf` from `nihms-1036108.pdf` — Selected as a foundational bead-based platform paper with clear numeric resolution language, compact methods/results structure, and strong map-based figures.
- `ST05` `ST05_spacebar_clone_tracing.pdf` from `ST03_Kinsler_2025_SpaceBar_bioRxiv.pdf` — Selected to preserve a preprint layout and a distinct clone-tracing plus spatial-transcriptomics task mix that is not duplicated by the other selected platform papers.

## Excluded PDFs and why they were excluded

- `nihms-1001922.pdf` — Excluded because the selected set already includes a modern 3D workflow and a distinct imaging-style preprint, making this the most redundant relative to the final mix.

## App-facing input design notes

- `table_template.csv` now mirrors a realistic user spreadsheet with 17 columns and no internal traceability fields.
- Metadata columns are shared with the main app style: Authors, Publication Year, Title, Journal, and DOI.
- Extraction-target columns stay blank in `table_template.csv`; only metadata is prefilled when confidently recoverable from the provided PDFs.
- `schema.csv` is the normal app-facing schema input and uses exactly `column_name,description`.
- `schema.json` and `schema.md` remain richer gold-annotation guides so evaluator-facing difficulty, evidence, and scoring notes stay available without polluting the main-app input surface.

## Difficulty and review notes

- Hard columns: Spatial resolution or capture unit, Calculated capture area from diameter, Key spatial domain or cell-type finding
- Vision-dependent columns: Key spatial domain or cell-type finding, Representative spatial figure, Number of bar-chart panels in Figure 1
- Calculation-style columns: Calculated capture area from diameter
- Protocol/kit/reagent columns: Library preparation or chemistry
- Columns likely to need human review: Spatial resolution or capture unit, Calculated capture area from diameter, Key spatial domain or cell-type finding, Validation or follow-up method

## Traceability notes

- `source_log.csv` retains paper_id, active/excluded status, original filename, curated filename, venue metadata, selection rationale, and key figures to inspect.
- `rename_map.csv` keeps the original-to-curated filename mapping so the app-facing table does not need internal identifiers.
- Excluded PDFs stay under `backup_excluded_papers/` for future swaps or ablation studies without changing the active benchmark.

## Metadata uncertainty

- Several selected spatial papers describe resolution using different units such as spot, bead, single nucleus, or subcellular capture, so gold annotation should preserve the paper's own headline phrasing instead of forcing a false numeric normalization.
