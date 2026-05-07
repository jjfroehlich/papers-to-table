# Curated benchmark suite overview

## Overall purpose

This suite packages repository-provided PDFs into traceable benchmark datasets while keeping the normal app-facing inputs realistic: `table_template.csv` acts like the spreadsheet a user would upload, and `schema.csv` acts like the simple schema CSV a user would provide to the app.

## Dataset counts

- `genome_editing_tools`: 5 active PDFs and 5 excluded backup PDFs.
- `spatial_transcriptomics`: 5 active PDFs and 1 excluded backup PDF.
- Suite total: 10 active PDFs and 6 preserved excluded PDFs.

## App-input versus annotation-file contract

- App inputs: each dataset exposes `table_template.csv` and `schema.csv` as the normal main-app inputs.
- Annotation guides: `schema.json` and `schema.md` keep richer difficulty, evidence, and scoring guidance for gold-standard creation.
- Traceability files: `source_log.csv` and `rename_map.csv` preserve `paper_id`, curated PDF filenames, original filenames, selection status, and access notes.
- Curation notes: `dataset_readme.md` and `curation_notes.md` explain active/excluded papers, review difficulty, and why internal traceability fields stay out of the app-facing table.

## Final app-facing columns

- `genome_editing_tools` (17 columns): Authors, Publication Year, Title, Journal, DOI, Editing modality, Main editor or system name, Best or selected variant, Primary assay system, Main comparator or baseline, Representative editing efficiency (%), Calculated improvement over comparator, Main or best editor architecture, Architecture source figure, Number of bar-chart panels in Figure 1, DNA extraction or genotyping method, Main improvement claim.
- `spatial_transcriptomics` (17 columns): Authors, Publication Year, Title, Journal, DOI, Spatial platform or method, Species, Tissue or disease context, Sample or section type, Spatial resolution or capture unit, Calculated capture area from diameter, Main analysis output, Key spatial domain or cell-type finding, Representative spatial figure, Number of bar-chart panels in Figure 1, Library preparation or chemistry, Validation or follow-up method.

## Removed internal columns from app-facing tables

- `paper_id`
- `pdf_filename`
- `publisher_family`

## Difficulty, vision, calculation, and protocol summary

- `genome_editing_tools` hard columns: Best or selected variant; Representative editing efficiency (%); Calculated improvement over comparator; Main or best editor architecture; Main improvement claim.
- `spatial_transcriptomics` hard columns: Spatial resolution or capture unit; Calculated capture area from diameter; Key spatial domain or cell-type finding.
- `genome_editing_tools` vision-dependent columns: Representative editing efficiency (%); Calculated improvement over comparator; Main or best editor architecture; Architecture source figure; Number of bar-chart panels in Figure 1.
- `spatial_transcriptomics` vision-dependent columns: Key spatial domain or cell-type finding; Representative spatial figure; Number of bar-chart panels in Figure 1.
- `genome_editing_tools` calculation column: Calculated improvement over comparator.
- `spatial_transcriptomics` calculation column: Calculated capture area from diameter.
- `genome_editing_tools` protocol field: DNA extraction or genotyping method.
- `spatial_transcriptomics` protocol field: Library preparation or chemistry.

## Gold-annotation review focus

- Review representative-value, comparator-pairing, and compact-architecture decisions carefully in the genome-editing set.
- Review main-species, tissue-context, representative-figure, and calculated-capture-area choices carefully in the spatial set.
- Keep excluded PDFs in `backup_excluded_papers/` so future swaps do not require new downloads.
