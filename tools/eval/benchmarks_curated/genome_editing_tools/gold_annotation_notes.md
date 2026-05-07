# Gold Annotation Notes: genome_editing_tools

## Annotation conventions actually used
- Annotated paper by paper from active PDFs in `pdfs/`; `backup_excluded_papers/` was not used.
- `table_gold.csv` keeps exactly the app-facing columns from `table_template.csv` and uses no traceability columns.
- Metadata values were preserved when supported by PDF front matter or `source_log.csv`; GE05 year and DOI were set to `NOT_FOUND`.
- Representative editing efficiency uses exact main-text values only. Graph-only values were set to `NOT_FOUND`.
- Calculated improvement was filled only when explicit numerator and denominator percentages were recoverable from the same main comparison.
- Architecture strings use compact underscore-separated components in biologically meaningful order.

## Paper-by-paper notes
- GE01: PE5max with epegRNAs is selected from the authors' recommendation. Exact PE5max/epegRNA efficiency percentages are not stated in the main text.
- GE02: PEA1-Puro in HEK293T cells provides the clean exact representative value; 67 / 35 = 1.91x.
- GE03: T1391A is selected because the authors recommend it when specificity is paramount. Exact selected-variant representative efficiency was not recoverable.
- GE04: BE4-Gam is selected for the SpCas9 BE4-Gam architecture; SaBE4-Gam is also recommended for SaCas9-targetable sites.
- GE05: The bridge RNA paper is a recombination system. The 59.5% value is a GFP reporter recombination rate and needs domain review before use as editing efficiency.

## Unresolved ambiguities
- GE01: Whether PE4max with epegRNAs should be selected for purity-sensitive applications.
- GE03: Whether K1389A should be treated as best for high-activity tasks rather than T1391A for specificity.
- GE04: Whether SaBE4-Gam should be a parallel accepted selected variant.
- GE05: Whether a recombination reporter percentage belongs in an `editing efficiency` column.

## Decisions about representative values
- GE02 uses the main-text average correct PE efficiency of 67% and explicit approximately 35% comparator.
- GE05 uses the best main-text reporter value, 59.5%, but flags the cell for review.
- GE01, GE03, and GE04 numeric performance cells are `NOT_FOUND` where only graph extraction would provide the value.

## Decisions about architecture normalization
- PEmax/PE5max architecture includes CMV, PEmax, P2A_MLH1dn, epegRNA, and nicking sgRNA.
- PEA1-Puro architecture records EF1a/Cas9n_RT/T2A_Puro plus U6 guide cassettes.
- HiFi-DdCBE architecture records TALE, split DddAtox with T1391A, and UGI.
- BE4-Gam architecture records Gam, XTEN linkers, APOBEC1, Cas9n(D10A), and two UGI copies.
- Bridge RNA architecture records IS621 recombinase, bridge RNA, target DNA, and donor DNA.

## Decisions about figure counting
- GE01 Figure 1: 0; schematics/scatter-style panels only.
- GE02 Figure 1: 1; panel B is the only grouped bar chart.
- GE03 Figure 1: 0; schematic/structure/sequence panels only.
- GE04 Figure 1: 1; panel C is the product-purity bar chart.
- GE05 Figure 1: 0; no qualifying bar chart in Figure 1.

## Decisions about calculations
- GE02 `Calculated improvement over comparator`: source value 1 = 67%, source value 2 = 35%, formula = 67 / 35, computed = 1.914, rounded to 1.91x.
- GE05 calculation is `NOT_APPLICABLE` because the negative non-matching target is not a meaningful efficiency comparator.

## Cells requiring human review
- GE01 `Representative editing efficiency (%)` = `NOT_FOUND`: A graph-only approximate value would not be gold-standard evidence.
- GE01 `Calculated improvement over comparator` = `NOT_FOUND`: Fold-change cannot be independently recomputed from explicit source values.
- GE03 `Representative editing efficiency (%)` = `NOT_FOUND`: Selecting a graph-derived or different-variant value would be unsupported.
- GE03 `Calculated improvement over comparator` = `NOT_FOUND`: The requested fold-change cannot be recomputed from explicit source values.
- GE04 `Best or selected variant` = `BE4-Gam`: BE4-Gam is selected for the SpCas9-targetable main system.
- GE04 `Representative editing efficiency (%)` = `NOT_FOUND`: A visual estimate would not satisfy the gold standard.
- GE04 `Calculated improvement over comparator` = `NOT_FOUND`: Fold-change cannot be computed without unsupported graph extraction.
- GE05 `Publication Year` = `NOT_FOUND`: Unsupported metadata was not inferred from filenames or memory.
- GE05 `DOI` = `NOT_FOUND`: Unsupported metadata was not inferred from filenames or memory.
- GE05 `Representative editing efficiency (%)` = `59.5`: The best headline reporter rate is used, with review flag because it is recombination reporter efficiency rather than standard editing.

## Recommended improvements to schema descriptions
- Clarify whether graph-derived values may be used with explicit visual digitization.
- Clarify how recombination-reporter percentages should be represented in the editing-efficiency field.
- Clarify whether selected variants should optimize efficiency, purity, specificity, or author recommendation when those differ.
