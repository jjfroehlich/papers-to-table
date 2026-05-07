# Genome editing tools schema

This file is the human-readable annotation guide for the curated benchmark schema.

## paper_id

- **What to extract:** Stable benchmark row identifier for the active genome-editing paper.
- **Expected answer style:** Exact short identifier.
- **What counts as correct:** Correct when it matches the assigned paper row id.
- **Allowed aliases or variants:** No aliases.
- **Evidence expected:** Neither; benchmark metadata lane.
- **Difficulty:** easy
- **Common pitfalls:** Do not substitute filename text for the curated id.

## pdf_filename

- **What to extract:** Renamed active PDF filename stored in the dataset pdfs directory.
- **Expected answer style:** Exact filename with .pdf extension.
- **What counts as correct:** Correct when the filename matches the curated active PDF in /pdfs.
- **Allowed aliases or variants:** No aliases.
- **Evidence expected:** Neither; benchmark metadata lane.
- **Difficulty:** easy
- **Common pitfalls:** Do not use the original source filename once the curated rename is applied.

## paper_title

- **What to extract:** Paper title exactly as it appears in the PDF front matter, normalized only for spacing.
- **Expected answer style:** Full title sentence case.
- **What counts as correct:** Correct when it captures the published title without invented abbreviations.
- **Allowed aliases or variants:** Minor punctuation and spacing normalization only.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not replace the title with article highlights or graphical abstract captions.

## doi

- **What to extract:** Canonical DOI for the paper when confidently visible in the PDF; otherwise leave blank.
- **Expected answer style:** Bare DOI string without doi: prefix.
- **What counts as correct:** Correct when the DOI is copied exactly or left blank for uncertain cases.
- **Allowed aliases or variants:** Accept doi.org URL forms only after normalization to bare DOI.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not copy cited-reference DOIs or malformed trailing punctuation.

## year

- **What to extract:** Publication or posted year visible in the PDF front matter. Leave blank if the year is not confidently recoverable from the PDF itself.
- **Expected answer style:** Four-digit year.
- **What counts as correct:** Correct when it matches the visible publication year.
- **Allowed aliases or variants:** No aliases.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not infer the year only from filename conventions when the PDF is ambiguous.

## journal

- **What to extract:** Journal or preprint venue name shown by the PDF.
- **Expected answer style:** Concise venue name.
- **What counts as correct:** Correct when it names the actual venue for the supplied PDF.
- **Allowed aliases or variants:** Common abbreviations only if they unambiguously resolve to the same venue.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not substitute publisher family for journal name.

## publisher_family

- **What to extract:** High-level publisher family when it is clear from the venue; otherwise leave blank.
- **Expected answer style:** Controlled category.
- **What counts as correct:** Correct when the journal or venue clearly belongs to that publisher family.
- **Allowed aliases or variants:** No aliases beyond exact curated family names.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not guess when the venue identity is uncertain.

## editing_modality

- **What to extract:** Main genome-editing modality emphasized by the paper. Use one controlled category: prime editing, adenine base editing, cytosine base editing, dual base editing, CRISPR nuclease editing, RNA editing, delivery/system engineering, or other.
- **Expected answer style:** Lowercase controlled category.
- **What counts as correct:** Correct when it reflects the primary editor class or engineering focus tested in the core results.
- **Allowed aliases or variants:** Prime editor -> prime editing; CBE -> cytosine base editing; DdCBE can remain cytosine base editing if the mitochondrial context is central in other fields.
- **Evidence expected:** Mostly text evidence.
- **Difficulty:** medium
- **Common pitfalls:** Do not label a paper as delivery/system engineering when it clearly introduces a new editor chemistry.

## main_editor_or_system_name

- **What to extract:** Main named editor, editor family, or engineered system introduced, optimized, or benchmarked in the paper.
- **Expected answer style:** Concise named system or family label.
- **What counts as correct:** Correct when it captures the main editor brand or system name used as the paper center of gravity.
- **Allowed aliases or variants:** Widely used abbreviations are acceptable when they are the author-preferred names.
- **Evidence expected:** Text evidence, occasionally reinforced by figure labels.
- **Difficulty:** medium
- **Common pitfalls:** Do not answer with a generic modality if the paper names a specific editor system.

## best_or_selected_variant

- **What to extract:** Specific editor variant, architecture variant, or carry-forward construct highlighted by the authors as best, preferred, or taken forward into later assays.
- **Expected answer style:** Short named variant.
- **What counts as correct:** Correct when it matches the paper's preferred or selected variant in the core assay narrative.
- **Allowed aliases or variants:** Accept exact variant aliases used interchangeably by the authors.
- **Evidence expected:** Both text and figure evidence are often needed.
- **Difficulty:** hard
- **Common pitfalls:** Do not pick an isolated supplementary maximum that the authors never prioritize.

## primary_assay_system

- **What to extract:** Main organism, cell type, tissue, or experimental system used for the central editing assay that anchors the paper's headline result.
- **Expected answer style:** Short noun phrase.
- **What counts as correct:** Correct when it identifies the main experimental system that supports the representative performance figure.
- **Allowed aliases or variants:** Common cell-line spellings are acceptable.
- **Evidence expected:** Mostly text evidence.
- **Difficulty:** medium
- **Common pitfalls:** Do not switch to a follow-up in vivo validation system if the core optimization happened elsewhere.

## representative_editing_efficiency_percent

- **What to extract:** Representative editing efficiency percent from the primary assay. Use the best or central reported value from the main assay figure or headline result, not a buried supplementary global maximum.
- **Expected answer style:** Bare number representing a percent.
- **What counts as correct:** Correct when the chosen value is representative of the central assay and matches the stated convention.
- **Allowed aliases or variants:** Equivalent decimal-percent transcription may be normalized when unambiguous.
- **Evidence expected:** Both text and figure evidence.
- **Difficulty:** hard
- **Common pitfalls:** Do not copy multiple percentages or averages across incompatible assays.

## construct_or_editor_architecture_compact

- **What to extract:** Compact underscore-separated architecture string that captures the main editor or construct components visible in text or a schematic figure.
- **Expected answer style:** Underscore-separated compact string.
- **What counts as correct:** Correct when the architecture string includes the core functional components the paper highlights.
- **Allowed aliases or variants:** Standard abbreviations such as RT, UGI, or pegRNA are allowed.
- **Evidence expected:** Both text and figure evidence.
- **Difficulty:** hard
- **Common pitfalls:** Do not turn narrative sentences into the compact string or omit the main effector module.

## architecture_source_figure

- **What to extract:** Main figure or panel that best supports the editor architecture answer.
- **Expected answer style:** Short figure-panel citation.
- **What counts as correct:** Correct when it points to the main architecture schematic or closely adjacent labeled panel.
- **Allowed aliases or variants:** Fig. 1A and Figure 1A are equivalent.
- **Evidence expected:** Figure evidence.
- **Difficulty:** medium
- **Common pitfalls:** Do not cite a performance panel unless it also contains the architecture schematic.

## main_improvement_claim

- **What to extract:** Concise claim of what the paper improved, such as higher editing efficiency, improved purity, reduced off-target editing, altered targeting scope, or better delivery/system behavior.
- **Expected answer style:** Concise explanatory sentence fragment.
- **What counts as correct:** Correct when it captures the principal improvement the authors ask readers to remember.
- **Allowed aliases or variants:** Equivalent phrasing is acceptable if the biological meaning is preserved.
- **Evidence expected:** Mostly text evidence, optionally supported by figures.
- **Difficulty:** hard
- **Common pitfalls:** Do not mix several unrelated claims into one unfocused summary.
