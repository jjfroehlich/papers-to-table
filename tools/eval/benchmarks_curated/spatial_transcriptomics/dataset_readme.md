# Spatial Transcriptomics Benchmark

## Dataset purpose
Benchmark extraction from spatial transcriptomics and spatial omics papers with tissue sections, spatial platforms, clustering/cell-type annotation, and figure-derived spatial maps.

## Why this topic is useful for benchmarking PDF-to-table extraction
The papers use consistent scientific objects but require different evidence paths: metadata, method names, biological systems, quantitative result extraction, and figure/caption interpretation.

## Summary of papers included
ST01-ST05 are open-access Nature Communications primary articles covering automated spatial multi-omics, multiplexed deterministic barcoding, transfer-learning cell typing, multi-scale clustering, and segmentation-free cell-type inference.

## Intended extraction challenges
Easy: metadata, platform, species. Medium: tissue context and analysis output. Hard: spatial resolution/capture unit and spatial-domain/cell-type finding from maps and captions.

## Known limitations
The set emphasizes open-access downloadable PDFs and method/application papers rather than every historically foundational platform paper. Some papers are computational methods applied to spatial data rather than wet-lab platform introductions.

## Manual gold-standard annotation instructions
Open each PDF and fill only values directly supported by the main article PDF. Prefer short normalized answers, keep units with quantitative values where the schema asks for them, and record figure-panel evidence for every vision-dependent field. Leave a cell blank when the main PDF does not support a value clearly.
