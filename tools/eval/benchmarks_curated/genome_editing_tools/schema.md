# Genome editing tools curated benchmark schema

This file is the human-readable gold-annotation guide for the benchmark columns. `schema.csv` is the normal app-facing schema input; this file adds richer guidance for manual annotation and scoring.

## Authors

- **What to extract:** Extract the full author list in publication order from the paper front matter or PDF metadata. Preserve author names and separate them with semicolons in the stored value. Leave blank only if the full author line is not confidently recoverable from the provided PDF.
- **Expected answer style:** Semicolon-separated author names in publication order
- **Difficulty:** easy
- **Evidence expected:** Text evidence from the author line on the title page or article front matter; PDF metadata can confirm spelling when needed.
- **Requires vision:** no
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Peter J. Chen; Jeffrey A. Hussmann; Jun Yan`
- **Scoring notes:** Minor punctuation or whitespace normalization is acceptable if author order and identity are preserved.
- **Gold-annotation notes:** Prefer the explicit author line in the paper over inferred citation exports.

## Publication Year

- **What to extract:** Extract the 4-digit publication year of this paper. Use the year shown in the PDF metadata or article front matter. Leave the cell blank if the year is not confidently recoverable from the provided PDF.
- **Expected answer style:** YYYY
- **Difficulty:** easy
- **Evidence expected:** Text evidence from the article front matter, DOI line, journal header, or posted-date line.
- **Requires vision:** no
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `2024`
- **Scoring notes:** Use a single 4-digit year only.
- **Gold-annotation notes:** For preprints, use the posted year visible in the PDF if present.

## Title

- **What to extract:** Extract the exact title of the paper from the PDF front matter. Preserve the published wording and normalize only obvious spacing artifacts.
- **Expected answer style:** Full title text
- **Difficulty:** easy
- **Evidence expected:** Text evidence from the article title page or PDF metadata.
- **Requires vision:** no
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `Enhanced prime editing systems by manipulating cellular determinants of editing outcomes`
- **Scoring notes:** Minor spacing normalization is acceptable.
- **Gold-annotation notes:** Do not replace the title with a graphical abstract caption or short running head.

## Journal

- **What to extract:** Extract the journal, venue, or preprint server shown by the PDF. Use the visible publication venue rather than the publisher family.
- **Expected answer style:** Venue name
- **Difficulty:** easy
- **Evidence expected:** Text evidence from the journal masthead, venue line, or PDF metadata.
- **Requires vision:** no
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Cell`
- **Scoring notes:** Standard journal-name normalization is acceptable.
- **Gold-annotation notes:** Do not substitute publisher family labels such as Elsevier or Springer Nature.

## DOI

- **What to extract:** Extract the canonical DOI when it is confidently visible in the provided PDF. Store the bare DOI string without a doi: prefix or URL wrapper. Leave blank if the DOI is not confidently recoverable from the PDF.
- **Expected answer style:** 10.xxxx/...
- **Difficulty:** easy
- **Evidence expected:** Text evidence from the title page, header, footer, or DOI line.
- **Requires vision:** no
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `10.1016/j.cell.2021.09.018`
- **Scoring notes:** Normalize doi.org URLs to the bare DOI string.
- **Gold-annotation notes:** Do not copy cited-reference DOIs.

## Editing modality

- **What to extract:** Extract the main genome-editing modality emphasized by the paper. Use one of these labels: prime editing, adenine base editing, cytosine base editing, mitochondrial base editing, recombination/insertion system, CRISPR nuclease editing, delivery/system engineering, or other.
- **Expected answer style:** Controlled modality label
- **Difficulty:** medium
- **Evidence expected:** Primarily text evidence from the title, abstract, and opening results; figures can help disambiguate.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `prime editing`
- **Scoring notes:** Choose the dominant modality for the core contribution, not every modality mentioned.
- **Gold-annotation notes:** Use mitochondrial base editing when mitochondrial DdCBE-style editing is the central paper focus.

## Main editor or system name

- **What to extract:** Extract the central named tool or system introduced, optimized, or benchmarked in the paper. Prefer the explicit author-facing system name rather than a generic modality label.
- **Expected answer style:** Short system name
- **Difficulty:** medium
- **Evidence expected:** Text evidence from the title, abstract, result headings, or figure labels.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `PEmax`
- **Scoring notes:** Use the name the authors foreground in the main results.
- **Gold-annotation notes:** If multiple families appear, choose the one that anchors the paper title or headline result.

## Best or selected variant

- **What to extract:** Extract the specific variant the authors highlight as best, use for follow-up assays, or present as the final preferred system. Use NOT_FOUND if the paper never makes one preferred variant clear.
- **Expected answer style:** Short variant label
- **Difficulty:** hard
- **Evidence expected:** Synthesis across result text, comparison tables/plots, and statements about which construct is carried forward.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `PEmax`
- **Scoring notes:** Do not select a one-off supplementary maximum that the paper does not carry forward.
- **Gold-annotation notes:** This field often needs human review when several variants perform similarly.

## Primary assay system

- **What to extract:** Extract the main organism, cell line, cell type, embryo, organelle, or experimental system used for the central assay. Choose the system that anchors the representative performance result.
- **Expected answer style:** Concise assay-system phrase
- **Difficulty:** medium
- **Evidence expected:** Text evidence from the abstract, methods summary, and first main results figure.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `HEK293T cells`
- **Scoring notes:** Prefer the core optimization system over later validation models.
- **Gold-annotation notes:** For mitochondrial editors, organelle-qualified human cell contexts are acceptable when central.

## Main comparator or baseline

- **What to extract:** Extract the editor or system used as the key baseline comparison in the main result that supports the representative value. Use NOT_FOUND if no single main comparator is clearly defined.
- **Expected answer style:** Short comparator label
- **Difficulty:** medium
- **Evidence expected:** Text evidence from main results plus the comparison figure that supports the representative value.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `PE2`
- **Scoring notes:** Prefer the baseline shown in the same main assay as the representative editing efficiency.
- **Gold-annotation notes:** This field matters for the calculated-improvement column, so keep the assay pairing consistent.

## Representative editing efficiency (%)

- **What to extract:** Extract the central representative editing efficiency percentage for the main or best editor variant in the primary assay. Do not use an arbitrary supplementary maximum. Use NOT_FOUND if no suitable main-PDF value is available.
- **Expected answer style:** Number without percent sign
- **Difficulty:** hard
- **Evidence expected:** Usually both text and figure evidence from the main figure or headline result.
- **Requires vision:** yes
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `42.3`
- **Scoring notes:** Choose a single representative value tied to the same assay used for the comparator and claim fields.
- **Gold-annotation notes:** Human review is recommended whenever multiple figures offer plausible representative values.

## Calculated improvement over comparator

- **What to extract:** Calculate fold-change by dividing the representative editing efficiency of the main or best variant by the comparator efficiency from the same figure or assay. Report a numeric fold-change rounded to two decimals. Use NOT_FOUND if one or both values are missing from the main PDF. Use NOT_APPLICABLE if the paper has no meaningful same-assay comparator.
- **Expected answer style:** Numeric fold-change rounded to two decimals
- **Difficulty:** hard
- **Evidence expected:** Figure or table evidence for both numerator and denominator, with text evidence helpful for confirming assay pairing.
- **Requires vision:** yes
- **Requires reasoning:** yes
- **Requires calculation:** yes
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `2.35`
- **Scoring notes:** The numerator and denominator must come from the same assay context.
- **Gold-annotation notes:** This field is intentionally calculation-heavy and often benefits from explicit annotation notes during gold creation.

## Main or best editor architecture

- **What to extract:** Extract the architecture of the main or best tool or selected variant, not every architecture tested. Use a compact underscore-separated component string such as CMV_PEmax_P2A_MLH1dn. Use NOT_FOUND if the main-PDF architecture cannot be recovered confidently.
- **Expected answer style:** component_component_component
- **Difficulty:** hard
- **Evidence expected:** Usually both schematic figure evidence and text description of construct components.
- **Requires vision:** yes
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `CMV_PEmax_P2A_MLH1dn`
- **Scoring notes:** Capture the core architecture components in a compact order; omit plasmid boilerplate.
- **Gold-annotation notes:** Keep this tied to the selected variant rather than to the overall family name.

## Architecture source figure

- **What to extract:** Identify the main figure or panel that supports the architecture answer, such as Fig. 1a. Use NOT_FOUND if no clear architecture-supporting figure exists in the main PDF.
- **Expected answer style:** Fig. 1a
- **Difficulty:** medium
- **Evidence expected:** Figure evidence from the panel that explicitly diagrams or labels the architecture.
- **Requires vision:** yes
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Fig. 1a`
- **Scoring notes:** Equivalent figure formatting such as Figure 1A is acceptable.
- **Gold-annotation notes:** Prefer the schematic panel over a performance-only plot.

## Number of bar-chart panels in Figure 1

- **What to extract:** Count the panels in Figure 1 that are bar charts or grouped bar charts. Do not count schematic-only panels, line plots, gels, heatmaps, or microscopy images. Use 0 when Figure 1 contains no qualifying bar charts. Use NOT_APPLICABLE only if the paper has no Figure 1.
- **Expected answer style:** Non-negative integer
- **Difficulty:** medium
- **Evidence expected:** Figure evidence from Figure 1 only.
- **Requires vision:** yes
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `3`
- **Scoring notes:** Scope this count to Figure 1 only.
- **Gold-annotation notes:** This is a vision diagnostic field rather than a biology summary field.

## DNA extraction or genotyping method

- **What to extract:** Extract the named kit, reagent, PCR or amplicon sequencing approach, or genotyping workflow used to measure edits. If only a general method is available, use that. Use NOT_FOUND if the paper does not state a usable method in the provided PDF.
- **Expected answer style:** Short reagent or workflow phrase
- **Difficulty:** medium
- **Evidence expected:** Text evidence from methods or figure captions; figure evidence is optional.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Amplicon sequencing`
- **Scoring notes:** Prefer the actual assay readout workflow over a generic sequencing platform mention.
- **Gold-annotation notes:** This protocol field is expected to be absent in some papers.

## Main improvement claim

- **What to extract:** Extract one concise phrase or sentence summarizing the main improvement claimed by the paper. Keep it focused on the main contribution rather than listing every result.
- **Expected answer style:** One concise phrase or sentence
- **Difficulty:** hard
- **Evidence expected:** Text evidence from the title, abstract, and main results; figures can reinforce the claim.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `Improved prime-editing efficiency and precision by suppressing mismatch repair and optimizing editor expression.`
- **Scoring notes:** Reward faithful compression of the main claim, not a broad abstract paraphrase.
- **Gold-annotation notes:** Human review is useful when the paper mixes mechanistic and performance claims.
