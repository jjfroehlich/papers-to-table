# Spatial transcriptomics curated benchmark

## Dataset purpose

Curated benchmark for realistic app-facing extraction tasks on spatial transcriptomics papers, emphasizing platform identification, tissue context, capture-resolution reasoning, figure-backed findings, and method/validation fields that appear in the main PDF.

## Active and excluded PDFs

- Active PDFs: 5
- Excluded backup PDFs preserved in `backup_excluded_papers/`: 1

### Active papers

- `ST01` `ST01_open_st_3d.pdf` — Open-ST: High-resolution spatial transcriptomics in 3D. Selected for a modern Cell layout, explicit 2D-to-3D workflow figures, and clinically relevant tissue heterogeneity results that combine platform and interpretation tasks.
- `ST02` `ST02_slide_tags_multimodal.pdf` — Slide-tags enables single-nucleus barcoding for multimodal spatial genomics. Selected because it adds a multimodal Nature layout, strong image-plus-map figures, and clear assay/reporting differences from spot-based methods.
- `ST03` `ST03_hdst_tissue_profiling.pdf` — High-definition spatial transcriptomics for in situ tissue profiling. Selected for its methods-focused manuscript style, explicit capture-unit language, and tissue-domain interpretation that is concise but still figure rich.
- `ST04` `ST04_slide_seq_high_resolution.pdf` — Slide-seq: A Scalable Technology for Measuring Genome-Wide Expression at High Spatial Resolution. Selected as a foundational bead-based platform paper with clear numeric resolution language, compact methods/results structure, and strong map-based figures.
- `ST05` `ST05_spacebar_clone_tracing.pdf` — SpaceBar enables clone tracing in spatial transcriptomic data. Selected to preserve a preprint layout and a distinct clone-tracing plus spatial-transcriptomics task mix that is not duplicated by the other selected platform papers.

### Excluded backup papers

- `nihms-1001922.pdf` — Three-dimensional intact-tissue sequencing of single-cell transcriptional states. Excluded because the selected set already includes a modern 3D workflow and a distinct imaging-style preprint, making this the most redundant relative to the final mix.

## App inputs versus annotation and traceability files

- `table_template.csv` is the app-facing spreadsheet input. It contains one row per active PDF and only the user-facing columns described in `schema.csv`.
- `schema.csv` is the app-facing schema input. It always uses exactly two columns: `column_name` and `description`.
- `schema.json` and `schema.md` are richer gold-annotation guides, not the normal main-app schema input.
- `source_log.csv` and `rename_map.csv` preserve traceability for internal `paper_id`, active PDF filenames, original filenames, selection status, and access notes.
- `curation_notes.md` records dataset construction rationale, uncertainty, and human-review guidance.

## App-facing columns

- `Authors` (easy)
- `Publication Year` (easy)
- `Title` (easy)
- `Journal` (easy)
- `DOI` (easy)
- `Spatial platform or method` (medium)
- `Species` (medium)
- `Tissue or disease context` (medium)
- `Sample or section type` (medium)
- `Spatial resolution or capture unit` (hard)
- `Calculated capture area from diameter` (hard)
- `Main analysis output` (medium)
- `Key spatial domain or cell-type finding` (hard)
- `Representative spatial figure` (medium)
- `Number of bar-chart panels in Figure 1` (medium)
- `Library preparation or chemistry` (medium)
- `Validation or follow-up method` (medium)

## Difficulty, vision, calculation, and protocol summary

- Easy columns: Authors, Publication Year, Title, Journal, DOI
- Medium columns: Spatial platform or method, Species, Tissue or disease context, Sample or section type, Main analysis output, Representative spatial figure, Number of bar-chart panels in Figure 1, Library preparation or chemistry, Validation or follow-up method
- Hard columns: Spatial resolution or capture unit, Calculated capture area from diameter, Key spatial domain or cell-type finding
- Vision-dependent columns: Key spatial domain or cell-type finding, Representative spatial figure, Number of bar-chart panels in Figure 1
- Calculation-style columns: Calculated capture area from diameter
- Protocol/kit/reagent columns: Library preparation or chemistry
- Columns likely to need human review during gold annotation: Spatial resolution or capture unit, Calculated capture area from diameter, Key spatial domain or cell-type finding, Validation or follow-up method

## Why internal traceability fields are not app-facing columns

- `paper_id`, `pdf_filename`, and `publisher_family` are internal traceability fields, not realistic user extraction targets.
- Keeping those fields out of `table_template.csv` makes the benchmark look like a normal main-app input while preserving row-to-PDF traceability in the helper files.

## Notes for gold annotation

- Keep the representative figure and key finding aligned so the biological claim traces back to one main spatial map.
- Use NOT_APPLICABLE for calculated capture area when the platform has no meaningful circular diameter.
- Expect human review for mixed-sample papers where more than one tissue or species could plausibly count as main.
