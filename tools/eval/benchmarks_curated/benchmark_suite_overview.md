# Benchmark Suite Overview

## Overall purpose
This suite provides three small, curated PDF-to-table benchmark datasets for evaluating local extraction of evidence-backed scientific table cells. The CSVs intentionally contain only safe metadata; human annotators should fill gold-standard extraction targets later.

## Datasets
| Dataset | Sub-field | Papers | Columns | Main challenge mix |
|---|---:|---:|---:|---|
| genome_editing_tools | CRISPR/base/prime editor engineering | 5 | 12 | Editor names, selected variants, efficiency values, architecture schematics |
| molecular_neuroscience | Molecular and cellular synaptic neuroscience | 5 | 12 | Species/cell type, perturbation, assay, quantitative readout, figure anchoring |
| spatial_transcriptomics | Spatial transcriptomics and spatial omics | 5 | 12 | Platform, tissue context, resolution/capture unit, spatial map interpretation |

## Task mix summary
Across the suite there are 36 columns: 17 easy metadata/system columns, 10 medium method/context columns, and 9 hard synthesis, quantitative, architecture, or spatial-interpretation columns.

## Vision-dependent columns across the suite
- genome_editing_tools: construct_or_editor_architecture_compact, architecture_source_figure
- molecular_neuroscience: figure_panel_for_primary_result
- spatial_transcriptomics: key_spatial_domain_or_cell_type_finding, representative_spatial_figure_panel

## Suggested next manual step for human gold-standard annotation
Annotate in this order: genome_editing_tools first for architecture normalization, molecular_neuroscience second for quantitative result conventions, and spatial_transcriptomics third after deciding how strictly to normalize resolution/capture-unit wording.

## Caveats about access, licensing, or missing PDFs
Classic PMC-hosted genome-editing and spatial-transcriptomics papers were considered but not included when the tooling downloaded PMC placeholder HTML instead of actual PDFs. The final suite uses directly downloadable open-access publisher PDFs and records substitutions in each curation note. No final selected PDF failed validation.
