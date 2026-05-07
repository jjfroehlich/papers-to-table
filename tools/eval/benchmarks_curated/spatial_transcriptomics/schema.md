# Spatial transcriptomics schema

This file is the human-readable annotation guide for the curated benchmark schema.

## paper_id

- **What to extract:** Stable benchmark row identifier for the active spatial-transcriptomics paper.
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

- **What to extract:** Paper title exactly as shown in the PDF title page or metadata, normalized only for spacing.
- **Expected answer style:** Full title sentence case.
- **What counts as correct:** Correct when it captures the published title.
- **Allowed aliases or variants:** Minor punctuation and spacing normalization only.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not replace the title with highlights or summary bullets.

## doi

- **What to extract:** Canonical DOI for the paper when confidently visible in the PDF; otherwise leave blank.
- **Expected answer style:** Bare DOI string without doi: prefix.
- **What counts as correct:** Correct when the DOI is copied exactly or left blank for uncertain cases.
- **Allowed aliases or variants:** Accept doi.org URL forms only after normalization to bare DOI.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not copy cited-reference DOIs or malformed trailing text.

## year

- **What to extract:** Publication or posted year visible in the PDF front matter.
- **Expected answer style:** Four-digit year.
- **What counts as correct:** Correct when it matches the visible publication year.
- **Allowed aliases or variants:** No aliases.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not infer the year only from repository naming if the PDF itself is unclear.

## journal

- **What to extract:** Journal or preprint venue name shown by the PDF.
- **Expected answer style:** Concise venue name.
- **What counts as correct:** Correct when it names the actual venue for the supplied PDF.
- **Allowed aliases or variants:** Common abbreviations only if they unambiguously resolve to the same venue.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not substitute publisher family for journal name.

## publisher_family

- **What to extract:** High-level publisher family when clear from the venue; otherwise leave blank.
- **Expected answer style:** Controlled category.
- **What counts as correct:** Correct when the journal or venue clearly belongs to that publisher family.
- **Allowed aliases or variants:** No aliases beyond exact curated family names.
- **Evidence expected:** Text evidence.
- **Difficulty:** easy
- **Common pitfalls:** Do not guess when the venue identity is uncertain.

## spatial_platform_or_method

- **What to extract:** Primary spatial platform, protocol, or named method developed or used centrally in the paper.
- **Expected answer style:** Short platform or method label.
- **What counts as correct:** Correct when it captures the central experimental or computational method the paper is about.
- **Allowed aliases or variants:** Named commercial or method aliases are acceptable if they are author-preferred.
- **Evidence expected:** Mostly text evidence.
- **Difficulty:** medium
- **Common pitfalls:** Do not answer with a downstream analysis package unless the paper itself is method-focused on that package.

## tissue_or_disease_context

- **What to extract:** Biological tissue, organ, developmental context, or disease setting that anchors the main spatial analysis.
- **Expected answer style:** Short noun phrase.
- **What counts as correct:** Correct when it identifies the primary biological context for the headline spatial result.
- **Allowed aliases or variants:** Common anatomical synonyms are acceptable when unambiguous.
- **Evidence expected:** Mostly text evidence.
- **Difficulty:** medium
- **Common pitfalls:** Do not switch to a follow-up validation tissue if another sample drives the main findings.

## sample_or_section_type

- **What to extract:** Sample unit or preparation type used for the main spatial assay, such as fresh frozen tissue section, FFPE section, organoid, or intact tissue block.
- **Expected answer style:** Short descriptive phrase.
- **What counts as correct:** Correct when it names the actual section or sample type used for the representative analysis.
- **Allowed aliases or variants:** FF and fresh frozen are equivalent when the paper uses both.
- **Evidence expected:** Mostly text evidence.
- **Difficulty:** medium
- **Common pitfalls:** Do not answer only with the tissue name when the question asks for preparation type.

## spatial_resolution_or_capture_unit

- **What to extract:** Resolution or capture-unit description used for the central assay. This can be a spot size, bead size, pixel size, single-cell or single-nucleus resolution claim, or another concise capture-unit description. If the paper reports heterogeneous resolutions, record the main headline resolution used in the principal result figure.
- **Expected answer style:** Compact numeric-plus-unit phrase or capture-unit phrase.
- **What counts as correct:** Correct when it captures the main resolution language a reader would use to compare methods.
- **Allowed aliases or variants:** Micro sign normalization (um vs μm) is acceptable.
- **Evidence expected:** Mostly text evidence, sometimes figure-supported.
- **Difficulty:** hard
- **Common pitfalls:** Do not confuse sequencing read depth or field of view with spatial resolution.

## main_analysis_output

- **What to extract:** Central downstream analysis output emphasized in the paper, such as spatial domains, cell-type maps, clone maps, ligand-receptor interactions, spatial factors, or tissue architecture.
- **Expected answer style:** Short controlled phrase.
- **What counts as correct:** Correct when it reflects the main type of spatial analysis product the paper foregrounds.
- **Allowed aliases or variants:** Equivalent phrasing such as spatial domains versus tissue domains is acceptable when the figure semantics match.
- **Evidence expected:** Both text and figure evidence can help.
- **Difficulty:** medium
- **Common pitfalls:** Do not list every analysis performed; pick the central output type.

## key_spatial_domain_or_cell_type_finding

- **What to extract:** Concise biological or spatial finding derived from the core results and representative maps.
- **Expected answer style:** Concise explanatory sentence fragment.
- **What counts as correct:** Correct when it captures a central spatial or cell-type finding supported by the paper's core maps.
- **Allowed aliases or variants:** Equivalent biological paraphrases are acceptable if they preserve the same finding.
- **Evidence expected:** Both text and figure evidence.
- **Difficulty:** hard
- **Common pitfalls:** Do not report a purely technical performance claim when a biological finding is requested.

## representative_spatial_figure_panel

- **What to extract:** Figure or panel that best represents the main spatial map, tissue image, or domain visualization supporting the key finding.
- **Expected answer style:** Short figure-panel citation.
- **What counts as correct:** Correct when it points to the representative spatial visualization used for the main finding.
- **Allowed aliases or variants:** Fig. 2A and Figure 2A are equivalent.
- **Evidence expected:** Figure evidence.
- **Difficulty:** medium
- **Common pitfalls:** Do not cite a workflow cartoon if the question asks for the main mapped biological result.

## validation_or_followup_method

- **What to extract:** Main validation or orthogonal follow-up method used to support the spatial findings, if present.
- **Expected answer style:** One or a few short method labels.
- **What counts as correct:** Correct when it names the follow-up assay or validation approach explicitly used to support the spatial interpretation.
- **Allowed aliases or variants:** Common method abbreviations such as IF, smFISH, or RNAscope are acceptable.
- **Evidence expected:** Mostly text evidence, sometimes figure-supported.
- **Difficulty:** medium
- **Common pitfalls:** Do not mistake the primary spatial platform itself for the validation method.
