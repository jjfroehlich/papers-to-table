# Schema

## paper_id
- Description: Stable row identifier assigned during curation.
- Expected answer style: GE##
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Use the table row metadata.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: GE01

## pdf_filename
- Description: Exact PDF filename in the dataset pdfs folder.
- Expected answer style: Filename ending in .pdf
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Use the local file name.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: GE01_Tan_2019_high_precision_base_editors.pdf

## paper_title
- Description: Full article title.
- Expected answer style: Title case as printed by source; minor punctuation variants acceptable.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Title page or article metadata.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: Engineering of high-precision base editors for site-specific single nucleotide replacement

## doi
- Description: Digital Object Identifier for the article.
- Expected answer style: DOI without URL prefix.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Article metadata, title page, or source log.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: 10.1038/s41467-018-08034-8

## year
- Description: Publication year.
- Expected answer style: YYYY
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Article metadata.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: 2019

## editing_modality
- Description: Genome-editing modality emphasized by the paper.
- Expected answer style: Short label such as cytosine_base_editing, C_to_G_base_editing, prime_editing, multiplex_base_prime_editing.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Abstract plus introduction/results.
- Difficulty: easy; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: cytosine_base_editing

## main_editor_or_system_name
- Description: Primary named editor or platform introduced, optimized, or benchmarked.
- Expected answer style: Canonical paper terminology; separate multiple names with semicolons.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Abstract, main results, and figure legends.
- Difficulty: medium; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: Target-AID-NG; DAP array

## best_or_selected_variant
- Description: Best-performing or selected variant highlighted by the authors for the main assay.
- Expected answer style: Variant name exactly or compactly as reported.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Results text and plots comparing variants.
- Difficulty: hard; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: YE1-BE3-FNLS

## primary_assay_system
- Description: Main cell type, organism, or experimental system used to establish the editing result.
- Expected answer style: Concise biological system; include cell line or organism when available.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Methods/results around the primary editing assay.
- Difficulty: medium; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: rice protoplasts

## highest_reported_editing_efficiency_percent
- Description: Highest reported on-target editing efficiency relevant to the main editor claim.
- Expected answer style: Percent as number only; use the paper-reported denominator and note exact target during annotation if needed.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Quantitative result text, figure axes, or source data table in the main PDF.
- Difficulty: hard; requires vision: false; requires reasoning: true; requires calculation: true
- Example answer: 42.5

## construct_or_editor_architecture_compact
- Description: Compact architecture of the editor, construct, or guide array. Use underscore-separated modules in observed order.
- Expected answer style: Promoter_or_expression_context_domain1_domain2_domainN; no spaces; use unknown only when main PDF lacks a schematic.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Figure schematic plus caption and construct description. Vision evidence is expected when a schematic is present.
- Difficulty: hard; requires vision: true; requires reasoning: true; requires calculation: false
- Example answer: nCas9_APOBEC1_UGI

## architecture_source_figure
- Description: Main figure panel containing the construct, editor, or array architecture schematic.
- Expected answer style: Figure panel label such as Fig. 1a or Extended Data Fig. 2b.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Figure panel or caption evidence.
- Difficulty: hard; requires vision: true; requires reasoning: true; requires calculation: false
- Example answer: Fig. 1a
