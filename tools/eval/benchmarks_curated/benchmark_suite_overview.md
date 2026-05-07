# Curated benchmark suite overview

## Overall purpose
This suite packages repository-provided PDFs into traceable, mixed-layout benchmark datasets for evaluating local-first PDF-to-table extraction behavior without introducing new downloads.

## Active paper counts
- `genome_editing_tools`: 5 active PDFs in `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/pdfs` and 5 preserved backups in `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/backup_excluded_papers`.
- `spatial_transcriptomics`: 5 active PDFs in `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/pdfs` and 1 preserved backups in `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/backup_excluded_papers`.
- Suite total: 10 active PDFs and 6 preserved excluded PDFs.

## Excluded paper counts
- `genome_editing_tools`: 5 excluded papers preserved in backup.
- `spatial_transcriptomics`: 1 excluded paper preserved in backup.

## Journal and publisher diversity summary
- `genome_editing_tools` active set spans Cell, Nucleic Acids Research, Nature Biotechnology, Science Advances, and bioRxiv.
- `spatial_transcriptomics` active set spans Cell, Nature, Nature Methods, Science, and bioRxiv.
- Across the active suite, publisher families represented are Elsevier, Springer Nature, AAAS, Oxford University Press, and Cold Spring Harbor Laboratory.

## Column and task type summary
- `genome_editing_tools` columns (15 total): paper_id, pdf_filename, paper_title, doi, year, journal, publisher_family, editing_modality, main_editor_or_system_name, best_or_selected_variant, primary_assay_system, representative_editing_efficiency_percent, construct_or_editor_architecture_compact, architecture_source_figure, main_improvement_claim.
- `spatial_transcriptomics` columns (15 total): paper_id, pdf_filename, paper_title, doi, year, journal, publisher_family, spatial_platform_or_method, tissue_or_disease_context, sample_or_section_type, spatial_resolution_or_capture_unit, main_analysis_output, key_spatial_domain_or_cell_type_finding, representative_spatial_figure_panel, validation_or_followup_method.

## Hard-field summary
- `genome_editing_tools` hard fields: best_or_selected_variant, representative_editing_efficiency_percent, construct_or_editor_architecture_compact, main_improvement_claim.
- `spatial_transcriptomics` hard fields: spatial_resolution_or_capture_unit, key_spatial_domain_or_cell_type_finding.

## Vision-field summary
- `genome_editing_tools` vision-dependent fields: representative_editing_efficiency_percent, construct_or_editor_architecture_compact, architecture_source_figure.
- `spatial_transcriptomics` vision-dependent fields: key_spatial_domain_or_cell_type_finding, representative_spatial_figure_panel.

## Manual gold annotation plan
1. Use each dataset's `table_template.csv` as the starting sheet and keep only the prefilled metadata cells.
2. Follow the per-column conventions in each `schema.md` before entering any gold values.
3. Annotate active PDFs only; excluded PDFs remain available for future benchmark swaps or ablation studies.
4. Revisit blank safe-metadata cells only after direct manual PDF inspection confirms the missing value.

## Exact paths to key files
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/table_template.csv`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/schema.json`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/schema.md`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/dataset_readme.md`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/source_log.csv`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/curation_notes.md`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/genome_editing_tools/rename_map.csv`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/table_template.csv`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/schema.json`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/schema.md`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/dataset_readme.md`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/source_log.csv`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/curation_notes.md`
- `/home/runner/work/papers-to-table/papers-to-table/tools/eval/benchmarks_curated/spatial_transcriptomics/rename_map.csv`
