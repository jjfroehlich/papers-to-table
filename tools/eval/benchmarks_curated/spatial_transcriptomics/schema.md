# Spatial transcriptomics curated benchmark schema

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
- **Example answer:** `Marie Schott; Daniel León-Periñán; Elena Splendiani`
- **Scoring notes:** Minor punctuation or whitespace normalization is acceptable if author order and identity are preserved.
- **Gold-annotation notes:** Prefer the author line from the paper over inferred bibliographic exports.

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
- **Example answer:** `Open-ST: High-resolution spatial transcriptomics in 3D`
- **Scoring notes:** Minor spacing normalization is acceptable.
- **Gold-annotation notes:** Do not substitute a running head or graphical abstract caption.

## Journal

- **What to extract:** Extract the journal, venue, or preprint server shown by the PDF. Use the visible publication venue rather than the publisher family.
- **Expected answer style:** Venue name
- **Difficulty:** easy
- **Evidence expected:** Text evidence from the journal masthead, venue line, or PDF metadata.
- **Requires vision:** no
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Nature`
- **Scoring notes:** Standard journal-name normalization is acceptable.
- **Gold-annotation notes:** Do not substitute publisher family labels.

## DOI

- **What to extract:** Extract the canonical DOI when it is confidently visible in the provided PDF. Store the bare DOI string without a doi: prefix or URL wrapper. Leave blank if the DOI is not confidently recoverable from the PDF.
- **Expected answer style:** 10.xxxx/...
- **Difficulty:** easy
- **Evidence expected:** Text evidence from the title page, header, footer, or DOI line.
- **Requires vision:** no
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `10.1038/s41586-023-06837-4`
- **Scoring notes:** Normalize doi.org URLs to the bare DOI string.
- **Gold-annotation notes:** Do not copy cited-reference DOIs.

## Spatial platform or method

- **What to extract:** Extract the platform or named method used or introduced by the paper, such as Open-ST, Slide-tags, HDST, Slide-seq, SpaceBar, Visium, MERFISH, seqFISH, or Stereo-seq. Use the method name the paper foregrounds.
- **Expected answer style:** Named platform or method label
- **Difficulty:** medium
- **Evidence expected:** Primarily text evidence from the title, abstract, and early results.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `Open-ST`
- **Scoring notes:** Prefer the named platform over a generic umbrella label.
- **Gold-annotation notes:** If the paper profiles a commercial platform but foregrounds a new derivative name, keep the derivative name.

## Species

- **What to extract:** Extract the biological species of the main experimental sample, not every species mentioned in the paper. Use the species that anchors the main analysis output.
- **Expected answer style:** Short species label
- **Difficulty:** medium
- **Evidence expected:** Text evidence from sample descriptions, abstract, and methods.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `human`
- **Scoring notes:** Use the species tied to the principal spatial analysis.
- **Gold-annotation notes:** For multi-sample papers, choose the species emphasized in the representative figure and main finding.

## Tissue or disease context

- **What to extract:** Extract the organ, tissue, disease, developmental stage, or biological setting of the main analysis. Use the context that anchors the main spatial result rather than every sample mentioned.
- **Expected answer style:** Concise tissue or disease phrase
- **Difficulty:** medium
- **Evidence expected:** Text evidence from the abstract, sample description, and early results.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `mouse hippocampus`
- **Scoring notes:** Prefer the primary analysis context over follow-up validation samples.
- **Gold-annotation notes:** Human review is useful when the paper rotates across several tissues or disease states.

## Sample or section type

- **What to extract:** Extract the physical sample type, such as fresh frozen tissue section, FFPE section, embryo, tumor section, brain section, organoid, or dissociated nuclei with spatial barcoding. Use NOT_FOUND if the paper does not state a recoverable sample type in the main PDF.
- **Expected answer style:** Concise sample-type phrase
- **Difficulty:** medium
- **Evidence expected:** Text evidence from methods summaries or sample descriptions.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `fresh frozen tissue section`
- **Scoring notes:** Capture the specimen format, not just the tissue name.
- **Gold-annotation notes:** This field is expected to be absent or implicit in some methods papers.

## Spatial resolution or capture unit

- **What to extract:** Extract the paper's own headline resolution or capture-unit phrase, such as bead diameter, spot size, single-nucleus level, subcellular, pixel, capture area, or 3D voxel description. Preserve the paper's phrasing rather than forcing a numeric normalization. Use NOT_FOUND if the main PDF does not provide a clear representative phrase.
- **Expected answer style:** Resolution or capture-unit phrase
- **Difficulty:** hard
- **Evidence expected:** Usually text evidence from the abstract or methods, optionally confirmed by figures.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `less than 10 μm spatial resolution`
- **Scoring notes:** Choose the main headline resolution, not every bin size or downstream computational setting.
- **Gold-annotation notes:** This field is intentionally hard because papers mix spot, bead, cell, and subcellular descriptions.

## Calculated capture area from diameter

- **What to extract:** Calculate the approximate area of a circular capture unit from the reported diameter using pi times radius squared. Report square micrometers as a number rounded to one decimal place. Use NOT_APPLICABLE if the platform does not have a meaningful circular capture diameter. Use NOT_FOUND if the needed diameter is not reported in the main PDF.
- **Expected answer style:** Square micrometers rounded to one decimal place
- **Difficulty:** hard
- **Evidence expected:** Text evidence for the representative circular diameter; figures can help confirm the representative capture unit.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** yes
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `78.5`
- **Scoring notes:** Use the same representative diameter referenced by the spatial-resolution field when possible.
- **Gold-annotation notes:** Document the source diameter during gold annotation because this field is calculation-heavy.

## Main analysis output

- **What to extract:** Extract the main output type emphasized by the paper, such as spatial domains, cell-type maps, clone tracing, 3D reconstruction, multimodal cell-state maps, spatial factors, tissue architecture, or differential spatial expression.
- **Expected answer style:** Short output-type phrase
- **Difficulty:** medium
- **Evidence expected:** Synthesis across result headings and the dominant mapped output shown in figures.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `3D reconstruction`
- **Scoring notes:** Choose the dominant analysis product, not every downstream analysis in the paper.
- **Gold-annotation notes:** Keep this distinct from the biological finding field.

## Key spatial domain or cell-type finding

- **What to extract:** Extract one concise biological or spatial finding supported by the representative map, tissue image, or cell-type/domain visualization. Do not answer with a generic statement such as clusters were identified.
- **Expected answer style:** One concise phrase or sentence
- **Difficulty:** hard
- **Evidence expected:** Usually both the representative spatial figure and the corresponding results text.
- **Requires vision:** yes
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Expected to be answerable from the main PDF unless the description explicitly allows NOT_FOUND/NOT_APPLICABLE.
- **Example answer:** `Distinct cell states organize around tumor-lymph node boundary hotspots that are not obvious in 2D alone.`
- **Scoring notes:** Reward concise biological interpretation tied to the main map.
- **Gold-annotation notes:** This field usually needs human review because multiple plausible findings may appear in the paper.

## Representative spatial figure

- **What to extract:** Identify a main figure or panel showing a spatial map, tissue image, cluster map, spatial factor, or cell-type/domain visualization that supports the key finding. Use NOT_FOUND if the main PDF lacks a clear representative spatial figure.
- **Expected answer style:** Fig. 2a
- **Difficulty:** medium
- **Evidence expected:** Figure evidence from the panel that most clearly shows the main spatial map, tissue image, or domain visualization.
- **Requires vision:** yes
- **Requires reasoning:** no
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Fig. 2a`
- **Scoring notes:** Equivalent figure formatting such as Figure 2A is acceptable.
- **Gold-annotation notes:** Prefer a figure with the actual spatial result rather than a workflow cartoon.

## Number of bar-chart panels in Figure 1

- **What to extract:** Count the Figure 1 panels that are bar charts or grouped bar charts only. Do not count schematics, tissue images, scatter plots, line plots, heatmaps, or microscopy panels. Use 0 when Figure 1 has no qualifying bar charts. Use NOT_APPLICABLE only if the paper has no Figure 1.
- **Expected answer style:** Non-negative integer
- **Difficulty:** medium
- **Evidence expected:** Figure evidence from Figure 1 only.
- **Requires vision:** yes
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `2`
- **Scoring notes:** Scope this count to Figure 1 only.
- **Gold-annotation notes:** This is a scoped vision diagnostic field.

## Library preparation or chemistry

- **What to extract:** Extract the named kit, sequencing chemistry, capture chemistry, or library preparation workflow if stated in the main PDF. Use NOT_FOUND if the paper does not provide a recoverable chemistry or library-prep name.
- **Expected answer style:** Short chemistry or protocol phrase
- **Difficulty:** medium
- **Evidence expected:** Text evidence from methods or figure captions; figure evidence is optional.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Illumina flow-cell-derived capture chemistry`
- **Scoring notes:** Prefer the actual library-preparation or capture chemistry description over a generic sequencing-platform mention.
- **Gold-annotation notes:** This protocol field is expected to be absent in some papers.

## Validation or follow-up method

- **What to extract:** Extract the main validation or orthogonal follow-up method used to support the spatial findings, such as immunofluorescence, smFISH, RNAscope, histology, independent dataset validation, targeted sequencing, perturbation, or imaging validation. Use NOT_FOUND if no clear validation method is stated.
- **Expected answer style:** Short validation-method phrase
- **Difficulty:** medium
- **Evidence expected:** Text evidence from results or methods, with figure captions sometimes clarifying the validation method.
- **Requires vision:** no
- **Requires reasoning:** yes
- **Requires calculation:** no
- **Null/placeholder policy:** Blank allowed
- **Example answer:** `Imaging-based spatial transcriptomics validation`
- **Scoring notes:** Do not mistake the primary spatial platform itself for the validation method.
- **Gold-annotation notes:** Some papers validate computationally rather than with wet-lab imaging; capture the actual follow-up used.
