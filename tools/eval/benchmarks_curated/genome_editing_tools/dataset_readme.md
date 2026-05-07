# Genome editing tools curated benchmark

## Dataset purpose

Curated benchmark for realistic app-facing extraction tasks on genome editing papers, emphasizing editor naming, representative performance, comparator reasoning, architecture grounding, and concise evidence-backed claims.

## Active and excluded PDFs

- Active PDFs: 5
- Excluded backup PDFs preserved in `backup_excluded_papers/`: 5

### Active papers

- `GE01` `GE01_enhanced_prime_editing.pdf` — Enhanced prime editing systems by manipulating cellular determinants of editing outcomes. Selected for a dense Cell layout, clear prime-editing architecture figures, multiple named editor variants (PE4/PE5/PEmax), and strong text-plus-figure evidence for mechanistic improvement claims.
- `GE02` `GE02_optimized_prime_editing_cells.pdf` — Optimized nickase- and nuclease-based prime editing in human and mouse cells. Selected to add a compact Oxford journal layout, direct nickase-versus-nuclease comparison, and concise assay reporting that still exposes baseline selection and representative efficiency choices.
- `GE03` `GE03_hifi_mitochondrial_ddcbe.pdf` — Precision mitochondrial DNA editing with high-fidelity DddA-derived base editors. Selected because mitochondrial DdCBE engineering introduces a distinct editor architecture, TALE-based design components, and figure-driven off-target versus fidelity tradeoffs.
- `GE04` `GE04_base_editor_purity_mu_gam.pdf` — Improved base excision repair inhibition and bacteriophage Mu Gam protein yields C:G-to-T:A base editors with higher efficiency and product purity. Selected to preserve an older AAAS layout with short but information-dense base-editing optimization, making it useful for efficiency, purity, and comparator extraction.
- `GE05` `GE05_bridge_rna_recombination.pdf` — Bridge RNAs direct modular and programmable recombination of target and donor DNA. Selected to add a visually rich preprint layout and a noncanonical genome engineering modality with strong schematic content for architecture extraction and mechanistic claim synthesis.

### Excluded backup papers

- `41587_2023_Article_2106.pdf` — Efficient prime editing in two-cell mouse embryos using PEmbryo. Excluded to reduce prime-editing and Nature Biotechnology redundancy after keeping broader layout diversity elsewhere.
- `41587_2025_Article_2641.pdf` — QBEmax is a sequence-permuted and internally protected base editor. Excluded because the selected set already covers editor-purity optimization and this would add another Nature Biotechnology brief-communication template.
- `GE03_Doll_2023_temperature_tolerant_base_editor.pdf` — A temperature-tolerant CRISPR base editor mediates highly efficient and precise gene editing in Drosophila. Excluded because it overlaps the selected base-editor optimization coverage and adds a second very similar AAAS-style layout.
- `nihms-1541141.pdf` — Search-and-replace genome editing without double-strand breaks or donor DNA. Excluded because the curated set already retains two prime-editing papers and this foundational manuscript would overweight that modality.
- `nihms969743.pdf` — Improving cytidine and adenine base editors by expression optimization and ancestral reconstruction. Excluded because its editor-optimization targets and Broad-style manuscript layout are already represented by stronger diversity picks.

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
- `Editing modality` (medium)
- `Main editor or system name` (medium)
- `Best or selected variant` (hard)
- `Primary assay system` (medium)
- `Main comparator or baseline` (medium)
- `Representative editing efficiency (%)` (hard)
- `Calculated improvement over comparator` (hard)
- `Main or best editor architecture` (hard)
- `Architecture source figure` (medium)
- `Number of bar-chart panels in Figure 1` (medium)
- `DNA extraction or genotyping method` (medium)
- `Main improvement claim` (hard)

## Difficulty, vision, calculation, and protocol summary

- Easy columns: Authors, Publication Year, Title, Journal, DOI
- Medium columns: Editing modality, Main editor or system name, Primary assay system, Main comparator or baseline, Architecture source figure, Number of bar-chart panels in Figure 1, DNA extraction or genotyping method
- Hard columns: Best or selected variant, Representative editing efficiency (%), Calculated improvement over comparator, Main or best editor architecture, Main improvement claim
- Vision-dependent columns: Representative editing efficiency (%), Calculated improvement over comparator, Main or best editor architecture, Architecture source figure, Number of bar-chart panels in Figure 1
- Calculation-style columns: Calculated improvement over comparator
- Protocol/kit/reagent columns: DNA extraction or genotyping method
- Columns likely to need human review during gold annotation: Best or selected variant, Representative editing efficiency (%), Calculated improvement over comparator, Main or best editor architecture, Main improvement claim

## Why internal traceability fields are not app-facing columns

- `paper_id`, `pdf_filename`, and `publisher_family` are internal traceability fields, not realistic user extraction targets.
- Keeping those fields out of `table_template.csv` makes the benchmark look like a normal main-app input while preserving row-to-PDF traceability in the helper files.

## Notes for gold annotation

- Keep the comparator, representative efficiency, and calculated improvement fields tied to the same main assay.
- Use the architecture field for the selected best/main system only, not every construct tested.
- Expect human review for papers with several plausible carry-forward variants or multiple candidate representative figures.
