# Genome editing tools curated benchmark curation notes

## All PDFs found

- `GE01_Chen_2021_enhanced_prime_editing.pdf` — Enhanced prime editing systems by manipulating cellular determinants of editing outcomes (48 pages; Cell).
- `gkab792.pdf` — Optimized nickase- and nuclease-based prime editing in human and mouse cells (11 pages; Nucleic Acids Research).
- `41587_2022_Article_1486.pdf` — Precision mitochondrial DNA editing with high-fidelity DddA-derived base editors (13 pages; Nature Biotechnology).
- `aao4774.pdf` — Improved base excision repair inhibition and bacteriophage Mu Gam protein yields C:G-to-T:A base editors with higher efficiency and product purity (9 pages; Science Advances).
- `GE05_Durrant_2024_bridge_RNA_recombination_bioRxiv.pdf` — Bridge RNAs direct modular and programmable recombination of target and donor DNA (61 pages; bioRxiv).
- `41587_2023_Article_2106.pdf` — Efficient prime editing in two-cell mouse embryos using PEmbryo (16 pages; Nature Biotechnology).
- `41587_2025_Article_2641.pdf` — QBEmax is a sequence-permuted and internally protected base editor (21 pages; Nature Biotechnology).
- `GE03_Doll_2023_temperature_tolerant_base_editor.pdf` — A temperature-tolerant CRISPR base editor mediates highly efficient and precise gene editing in Drosophila (17 pages; Science Advances).
- `nihms-1541141.pdf` — Search-and-replace genome editing without double-strand breaks or donor DNA (39 pages; Nature).
- `nihms969743.pdf` — Improving cytidine and adenine base editors by expression optimization and ancestral reconstruction (11 pages; Nature Biotechnology).

## Selected PDFs and why they were selected

- `GE01` `GE01_enhanced_prime_editing.pdf` from `GE01_Chen_2021_enhanced_prime_editing.pdf` — Selected for a dense Cell layout, clear prime-editing architecture figures, multiple named editor variants (PE4/PE5/PEmax), and strong text-plus-figure evidence for mechanistic improvement claims.
- `GE02` `GE02_optimized_prime_editing_cells.pdf` from `gkab792.pdf` — Selected to add a compact Oxford journal layout, direct nickase-versus-nuclease comparison, and concise assay reporting that still exposes baseline selection and representative efficiency choices.
- `GE03` `GE03_hifi_mitochondrial_ddcbe.pdf` from `41587_2022_Article_1486.pdf` — Selected because mitochondrial DdCBE engineering introduces a distinct editor architecture, TALE-based design components, and figure-driven off-target versus fidelity tradeoffs.
- `GE04` `GE04_base_editor_purity_mu_gam.pdf` from `aao4774.pdf` — Selected to preserve an older AAAS layout with short but information-dense base-editing optimization, making it useful for efficiency, purity, and comparator extraction.
- `GE05` `GE05_bridge_rna_recombination.pdf` from `GE05_Durrant_2024_bridge_RNA_recombination_bioRxiv.pdf` — Selected to add a visually rich preprint layout and a noncanonical genome engineering modality with strong schematic content for architecture extraction and mechanistic claim synthesis.

## Excluded PDFs and why they were excluded

- `41587_2023_Article_2106.pdf` — Excluded to reduce prime-editing and Nature Biotechnology redundancy after keeping broader layout diversity elsewhere.
- `41587_2025_Article_2641.pdf` — Excluded because the selected set already covers editor-purity optimization and this would add another Nature Biotechnology brief-communication template.
- `GE03_Doll_2023_temperature_tolerant_base_editor.pdf` — Excluded because it overlaps the selected base-editor optimization coverage and adds a second very similar AAAS-style layout.
- `nihms-1541141.pdf` — Excluded because the curated set already retains two prime-editing papers and this foundational manuscript would overweight that modality.
- `nihms969743.pdf` — Excluded because its editor-optimization targets and Broad-style manuscript layout are already represented by stronger diversity picks.

## App-facing input design notes

- `table_template.csv` now mirrors a realistic user spreadsheet with 17 columns and no internal traceability fields.
- Metadata columns are shared with the main app style: Authors, Publication Year, Title, Journal, and DOI.
- Extraction-target columns stay blank in `table_template.csv`; only metadata is prefilled when confidently recoverable from the provided PDFs.
- `schema.csv` is the normal app-facing schema input and uses exactly `column_name,description`.
- `schema.json` and `schema.md` remain richer gold-annotation guides so evaluator-facing difficulty, evidence, and scoring notes stay available without polluting the main-app input surface.

## Difficulty and review notes

- Hard columns: Best or selected variant, Representative editing efficiency (%), Calculated improvement over comparator, Main or best editor architecture, Main improvement claim
- Vision-dependent columns: Representative editing efficiency (%), Calculated improvement over comparator, Main or best editor architecture, Architecture source figure, Number of bar-chart panels in Figure 1
- Calculation-style columns: Calculated improvement over comparator
- Protocol/kit/reagent columns: DNA extraction or genotyping method
- Columns likely to need human review: Best or selected variant, Representative editing efficiency (%), Calculated improvement over comparator, Main or best editor architecture, Main improvement claim

## Traceability notes

- `source_log.csv` retains paper_id, active/excluded status, original filename, curated filename, venue metadata, selection rationale, and key figures to inspect.
- `rename_map.csv` keeps the original-to-curated filename mapping so the app-facing table does not need internal identifiers.
- Excluded PDFs stay under `backup_excluded_papers/` for future swaps or ablation studies without changing the active benchmark.

## Metadata uncertainty

- GE05_bridge_rna_recombination.pdf does not expose a confidently recoverable DOI or posted year in the provided PDF text, so those metadata cells remain blank in the app-facing table and source log pending future manual confirmation.
