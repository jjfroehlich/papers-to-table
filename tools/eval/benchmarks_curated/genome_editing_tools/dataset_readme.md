# Genome editing tools curated benchmark

## Dataset purpose
Curated benchmark for extraction tasks centered on genome editing system design, editor architecture, assay context, and headline performance claims.

## Why the selected papers are useful for this benchmark
The selected set balances prime editing, base editing, mitochondrial editing, and bridge-RNA-guided recombination across Cell, Nucleic Acids Research, Nature Biotechnology, Science Advances, and bioRxiv layouts.

## Selected paper summary
- `GE01` `GE01_enhanced_prime_editing.pdf` — Enhanced prime editing systems by manipulating cellular determinants of editing outcomes. Selected for a dense Cell layout, clear prime-editing architecture figures, multiple named editor variants (PE4/PE5/PEmax), and strong text-plus-figure evidence for mechanistic improvement claims.
- `GE02` `GE02_optimized_prime_editing_cells.pdf` — Optimized nickase- and nuclease-based prime editing in human and mouse cells. Selected to add a compact Oxford journal layout, direct nickase-versus-nuclease comparison, and concise assay reporting that still exposes baseline selection and representative efficiency choices.
- `GE03` `GE03_hifi_mitochondrial_ddcbe.pdf` — Precision mitochondrial DNA editing with high-fidelity DddA-derived base editors. Selected because mitochondrial DdCBE engineering introduces a distinct editor architecture, TALE-based design components, and figure-driven off-target versus fidelity tradeoffs.
- `GE04` `GE04_base_editor_purity_mu_gam.pdf` — Improved base excision repair inhibition and bacteriophage Mu Gam protein yields C:G-to-T:A base editors with higher efficiency and product purity. Selected to preserve an older AAAS layout with short but information-dense base-editing optimization, making it useful for efficiency, purity, and comparator extraction.
- `GE05` `GE05_bridge_rna_recombination.pdf` — Bridge RNAs direct modular and programmable recombination of target and donor DNA. Selected to add a visually rich preprint layout and a noncanonical genome engineering modality with strong schematic content for architecture extraction and mechanistic claim synthesis.

## Excluded paper summary
- `41587_2023_Article_2106.pdf` — Efficient prime editing in two-cell mouse embryos using PEmbryo. Excluded to reduce prime-editing and Nature Biotechnology redundancy after keeping broader layout diversity elsewhere.
- `41587_2025_Article_2641.pdf` — QBEmax is a sequence-permuted and internally protected base editor. Excluded because the selected set already covers editor-purity optimization and this would add another Nature Biotechnology brief-communication template.
- `GE03_Doll_2023_temperature_tolerant_base_editor.pdf` — A temperature-tolerant CRISPR base editor mediates highly efficient and precise gene editing in Drosophila. Excluded because it overlaps the selected base-editor optimization coverage and adds a second very similar AAAS-style layout.
- `nihms-1541141.pdf` — Search-and-replace genome editing without double-strand breaks or donor DNA. Excluded because the curated set already retains two prime-editing papers and this foundational manuscript would overweight that modality.
- `nihms969743.pdf` — Improving cytidine and adenine base editors by expression optimization and ancestral reconstruction. Excluded because its editor-optimization targets and Broad-style manuscript layout are already represented by stronger diversity picks.

## Task difficulty mix
- Metadata lanes stay easy so row-to-PDF alignment is deterministic.
- Medium fields emphasize method naming, assay context, and controlled-category extraction.
- Hard fields emphasize representative numeric choice, architecture compression or spatial interpretation, and concise evidence-backed reasoning.
- Hard columns in this dataset: best_or_selected_variant, representative_editing_efficiency_percent, construct_or_editor_architecture_compact, main_improvement_claim.

## Proposal types tested
- Exact metadata transcription
- Controlled-category method labeling
- Short assay or tissue context extraction
- Numeric or capture-unit extraction
- Figure-panel citation
- Concise explanatory summary backed by text and figures

## Vision-dependent columns
representative_editing_efficiency_percent, construct_or_editor_architecture_compact, architecture_source_figure

## Manual gold-standard annotation instructions
1. Work row by row in the renamed `pdfs/` directory so annotations always reference the curated filenames.
2. Keep the metadata fields as already populated unless manual PDF review uncovers a confident correction.
3. For extraction-target columns, use the conventions in `schema.md`, especially the representative-value rules for nontrivial numeric fields.
4. Record only one final gold answer per column; if a paper provides several candidate values, prefer the one tied to the principal figure or headline result.
5. When a target is truly absent or not confidently recoverable from the provided PDF, leave it blank and note the reason in manual annotation notes outside this checked-in template.

## Known limitations
- This pass intentionally leaves all extraction-target cells blank.
- Some papers are author-manuscript or preprint PDFs, so pagination and figure labeling style are not perfectly uniform.
- Manual annotation still needs to confirm ambiguous metadata fields that were left blank for safety.
