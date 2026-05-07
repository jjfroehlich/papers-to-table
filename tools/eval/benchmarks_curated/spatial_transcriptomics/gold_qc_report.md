# Gold QC Report: spatial_transcriptomics

## Counts
- Papers annotated: 5
- Columns: 17
- Filled cells: 85
- NOT_FOUND cells: 0
- NOT_APPLICABLE cells: 2
- UNCERTAIN_REVIEW cells: 0
- Cells needing human review: 5

## Hard fields checked
- Species
- Tissue or disease context
- Spatial resolution or capture unit
- Calculated capture area from diameter
- Key spatial domain or cell-type finding
- Representative spatial figure
- Number of bar-chart panels in Figure 1
- Library preparation or chemistry
- Validation or follow-up method

## Calculation fields checked
- ST01 area: pi*(0.6/2)^2 = 0.3 square micrometers.
- ST02 area: `NOT_APPLICABLE`; no circular capture unit.
- ST03 area: pi*(2/2)^2 = 3.1 square micrometers.
- ST04 area: pi*(10/2)^2 = 78.5 square micrometers.
- ST05 area: `NOT_APPLICABLE`; imaging-based method.

## Vision fields checked
- ST01 Fig. 1 count and Fig. 7d spatial map.
- ST02 Fig. 1 count and Fig. 3h spatial map.
- ST03 Fig. 1 count and Fig. 1b/e maps.
- ST04 Fig. 1 count and Fig. 3b/c maps.
- ST05 Fig. 1 count and Fig. 2e/f maps.

## Most ambiguous cells
- ST01 and ST02 species/context choices because the papers include multiple tissue/species demonstrations.
- ST05 species choice because human melanoma cells are grown as mouse xenografts.
- ST05 Figure 1B count because the panel is histogram-like.

## Suggested human review order
1. ST05 Species and Figure 1B count.
2. ST02 Species and tissue/context choice.
3. ST01 Species choice.
4. ST04 library-prep wording from limited main-PDF methods.
5. Review all `NOT_APPLICABLE` capture-area decisions for imaging/nucleus-tagging platforms.

## Schema problems discovered during annotation
- The schema does not define whether Species should be representative-result species or all major samples.
- The schema should explicitly say whether histograms count as bar-chart panels.
- Capture-area guidance could explicitly cover nucleus barcoding and imaging-based platforms.
