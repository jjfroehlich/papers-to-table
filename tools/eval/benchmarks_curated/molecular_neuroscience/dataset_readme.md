# Molecular Neuroscience Benchmark

## Dataset purpose
Benchmark extraction from molecular and cellular neuroscience papers with perturbations, cell types, assays, quantitative readouts, and mechanism claims.

## Why this topic is useful for benchmarking PDF-to-table extraction
The papers use consistent scientific objects but require different evidence paths: metadata, method names, biological systems, quantitative result extraction, and figure/caption interpretation.

## Summary of papers included
MN01-MN05 are eLife primary research articles spanning synaptic plasticity, reporter imaging, microglia-synapse remodeling, synapse formation signaling, and astrocyte receptor control of CA1 synaptic strength.

## Intended extraction challenges
Easy: article metadata and species. Medium: region/cell type, perturbation, assay. Hard: quantitative result and mechanistic conclusion, with figure-panel anchoring.

## Known limitations
The papers are not all from one organism or brain region, so normalization should preserve the stated biological system instead of forcing a shared vocabulary.

## Manual gold-standard annotation instructions
Open each PDF and fill only values directly supported by the main article PDF. Prefer short normalized answers, keep units with quantitative values where the schema asks for them, and record figure-panel evidence for every vision-dependent field. Leave a cell blank when the main PDF does not support a value clearly.
