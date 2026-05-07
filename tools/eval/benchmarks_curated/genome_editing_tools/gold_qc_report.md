# Gold QC Report: genome_editing_tools

## Counts
- Papers annotated: 5
- Columns: 17
- Filled cells: 85
- NOT_FOUND cells: 8
- NOT_APPLICABLE cells: 1
- UNCERTAIN_REVIEW cells: 0
- Cells needing human review: 10

## Hard fields checked
- Best or selected variant
- Representative editing efficiency (%)
- Calculated improvement over comparator
- Main or best editor architecture
- Number of bar-chart panels in Figure 1
- DNA extraction or genotyping method

## Calculation fields checked
- GE02 improvement recomputed from 67% / 35% = 1.91x.
- GE01, GE03, and GE04 were checked and set to `NOT_FOUND` because exact numerator/denominator pairs were not recoverable.
- GE05 was checked and set to `NOT_APPLICABLE` because no meaningful same-assay comparator denominator exists.

## Vision fields checked
- GE01 Fig. 1 count and Fig. 7 architecture.
- GE02 Fig. 1 count and Fig. 1a architecture.
- GE03 Fig. 1 count and Fig. 1a architecture.
- GE04 Fig. 1 count and Fig. 6a architecture.
- GE05 Fig. 1 count and Fig. 3a/c architecture.

## Most ambiguous cells
- GE01 PE5max/epegRNA exact efficiency not text recoverable.
- GE03 selected T1391A exact efficiency not text recoverable.
- GE04 BE4-Gam exact efficiency not text recoverable.
- GE05 year/DOI absent from active PDF/source log; reporter percentage is not canonical editing efficiency.

## Suggested human review order
1. GE05 metadata and representative efficiency.
2. GE01 selected PE5max/epegRNA numeric fields.
3. GE03 T1391A versus K1389A selected variant.
4. GE04 BE4-Gam versus SaBE4-Gam selected variant.
5. Graph-only numeric values if visual digitization is allowed.

## Schema problems discovered during annotation
- The schema does not say whether graph digitization is allowed for gold values.
- The schema does not resolve efficiency-versus-specificity tradeoffs for best variant selection.
- Recombination reporter percentages are awkward in an editing-efficiency field.
