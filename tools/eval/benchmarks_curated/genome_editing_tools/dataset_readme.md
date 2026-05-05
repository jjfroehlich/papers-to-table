# Genome Editing Tools Benchmark

## Dataset purpose
Benchmark extraction from primary papers that introduce or optimize CRISPR-derived editor systems, especially base-editing and multiplex base/prime-editing architectures.

## Why this topic is useful for benchmarking PDF-to-table extraction
The papers use consistent scientific objects but require different evidence paths: metadata, method names, biological systems, quantitative result extraction, and figure/caption interpretation.

## Summary of papers included
GE01-GE05 are open-access Nature Communications primary research articles focused on editor architecture, targeting scope, specificity, or guide-array architecture.

## Intended extraction challenges
Easy: title, DOI, year, modality. Medium: named editor/system and primary assay system. Hard: best variant, highest efficiency, construct architecture, and architecture figure panel.

## Known limitations
This set substitutes directly downloadable open-access editor papers for several classic PMC author manuscripts because PMC PDF endpoints returned JavaScript placeholders in this environment. Classic prime/base editing papers remain good future additions if PDFs are obtained through a browser or institutional route.

## Manual gold-standard annotation instructions
Open each PDF and fill only values directly supported by the main article PDF. Prefer short normalized answers, keep units with quantitative values where the schema asks for them, and record figure-panel evidence for every vision-dependent field. Leave a cell blank when the main PDF does not support a value clearly.
