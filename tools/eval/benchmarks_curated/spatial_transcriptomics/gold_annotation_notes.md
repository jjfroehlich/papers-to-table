# Gold Annotation Notes: spatial_transcriptomics

## Annotation conventions actually used
- Annotated paper by paper from active PDFs in `pdfs/`; `backup_excluded_papers/` was not used.
- `table_gold.csv` has the exact columns and row order from `table_template.csv`.
- Metadata was preserved when supported by PDF front matter or `source_log.csv`.
- The representative spatial finding is chosen from a main figure with actual tissue/cell/domain maps, not workflow schematics.
- Capture-area calculations were made only for meaningful circular capture units. Imaging or nucleus-tagging methods use `NOT_APPLICABLE`.
- Figure 1 bar-chart counts use visual inspection and count only bar-chart or grouped-bar panels.

## Paper-by-paper notes
- ST01: Human metastatic lymph node was chosen for the tumor-boundary macrophage/cholesterol finding, although Open-ST also benchmarks mouse tissue.
- ST02: Human tonsil germinal centers were selected over mouse hippocampus because Figure 3 provides a specific spatial immune finding.
- ST03: Mouse main olfactory bulb was selected as the main Figure 1 analysis; breast cancer is a secondary application.
- ST04: Mouse cerebellum/hippocampus was selected as the main biological setting. Library-prep wording uses results/figure legend because the active manuscript has limited methods detail.
- ST05: Human melanoma cells in a mouse xenograft were represented as human species and melanoma xenograft context. Figure 1B is counted as one histogram-like bar panel and flagged for review.

## Unresolved ambiguities
- ST01: Species could be `human and mouse` if the benchmark wants method-wide metadata.
- ST02: Main tissue could be mouse hippocampus, human tonsil, or metastatic melanoma depending on benchmark intent.
- ST05: Species is biologically human melanoma but experimentally a mouse xenograft model.
- ST05: Figure 1B is histogram-like; it is counted as one bar-chart panel but should be reviewed if histograms are excluded.

## Decisions about representative values
- ST01 representative figure is Fig. 7d for the tumor-boundary finding.
- ST02 representative figure is Fig. 3h for TFH/follicular dendritic cell maps.
- ST03 representative figure is Fig. 1b/e for layer annotation and cell-type enrichment.
- ST04 representative figure is Fig. 3b/c for cerebellar spatial gene-expression bands.
- ST05 representative figure is Fig. 2e/f for MITF/VEGFA spatial expression in the tumor section.

## Decisions about figure counting
- ST01 Figure 1: 0; workflow/images/maps/QC plots only.
- ST02 Figure 1: 0; schematic, UMAP, maps, marker images, density/scatter plots only.
- ST03 Figure 1: 0; workflow, spatial maps, dot maps, and heatmaps only.
- ST04 Figure 1: 0; array schematics and spatial maps only.
- ST05 Figure 1: 1; panel B is a vertical-bar distribution of barcodes per cell.

## Decisions about calculations
- ST01: diameter 0.6 µm -> pi*(0.3)^2 = 0.2827 -> 0.3 square micrometers.
- ST02: `NOT_APPLICABLE`; beads transfer barcodes to nuclei but do not define a circular capture area.
- ST03: diameter 2 µm -> pi*(1)^2 = 3.1416 -> 3.1 square micrometers.
- ST04: diameter 10 µm -> pi*(5)^2 = 78.5398 -> 78.5 square micrometers.
- ST05: `NOT_APPLICABLE`; imaging-based GenePS/seqFISH has no circular capture unit.

## Cells requiring human review
- ST01 `Species` = `human`: Human is chosen for the main biological finding although the paper also includes mouse benchmarking.
- ST02 `Species` = `human`: Human is selected to match the representative tonsil spatial finding.
- ST02 `Tissue or disease context` = `human tonsil germinal centers`: Human tonsil germinal centers anchor the selected representative finding.
- ST05 `Species` = `human`: Human is chosen for the biological sample, with review flag because the assay is in a mouse xenograft.
- ST05 `Number of bar-chart panels in Figure 1` = `1`: Panel B is counted as one bar-chart-like distribution panel; this is flagged because it is histogram-like.

## Recommended improvements to schema descriptions
- Clarify whether `Species` should describe the representative result, all major samples, or the platform demonstration set.
- Clarify whether histograms count as bar-chart panels.
- Clarify whether imaging platforms should always use `NOT_APPLICABLE` for calculated circular capture area.
