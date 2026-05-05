# Schema

## paper_id
- Description: Stable row identifier assigned during curation.
- Expected answer style: MN##
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Use the table row metadata.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: MN01

## pdf_filename
- Description: Exact PDF filename in the dataset pdfs folder.
- Expected answer style: Filename ending in .pdf
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Use the local file name.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: MN01_Ortega_2018_presynaptic_homeostatic_plasticity.pdf

## paper_title
- Description: Full article title.
- Expected answer style: Title as printed by source.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Title page or article metadata.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: Imaging neuropeptide release at synapses with a genetically engineered reporter

## doi
- Description: Digital Object Identifier for the article.
- Expected answer style: DOI without URL prefix.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Article metadata.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: 10.7554/eLife.46421

## year
- Description: Publication year.
- Expected answer style: YYYY
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Article metadata.
- Difficulty: easy; requires vision: false; requires reasoning: false; requires calculation: false
- Example answer: 2019

## species
- Description: Species used for the primary biological experiment.
- Expected answer style: Common or Latin species name; include multiple species only if primary assays require both.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Methods, abstract, or organism metadata.
- Difficulty: easy; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: mouse

## brain_region_or_neural_cell_type
- Description: Brain region, neural preparation, or principal neural/glial cell type assayed.
- Expected answer style: Concise region/cell type phrase.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Abstract/results/methods and figure labels.
- Difficulty: medium; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: hippocampal CA1 pyramidal neurons

## perturbation_or_condition
- Description: Experimental perturbation, genotype, stimulation, drug, or condition central to the main result.
- Expected answer style: Concise intervention phrase; include control comparison if needed.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Results text and methods.
- Difficulty: medium; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: astrocyte-specific GluN2C deletion

## primary_assay_or_readout
- Description: Main assay or readout used to support the primary conclusion.
- Expected answer style: Technique plus readout, not a full sentence.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Results section, figure legend, and methods.
- Difficulty: medium; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: whole-cell patch clamp EPSC amplitude

## key_quantitative_result
- Description: Main numerical result tied to the primary readout.
- Expected answer style: Short result with value, unit, direction, and comparator when available.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Result paragraph or figure/legend; may require reading graph axes.
- Difficulty: hard; requires vision: false; requires reasoning: true; requires calculation: true
- Example answer: EPSC amplitude decreased by 35% versus control

## main_mechanistic_conclusion
- Description: Primary mechanistic interpretation supported by the paper.
- Expected answer style: One concise sentence or clause.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Discussion plus primary results; avoid overclaiming beyond the paper.
- Difficulty: hard; requires vision: false; requires reasoning: true; requires calculation: false
- Example answer: Latrophilin signaling promotes synapse formation through a GPCR-dependent pathway.

## figure_panel_for_primary_result
- Description: Figure panel that best supports the key quantitative result or mechanism.
- Expected answer style: Figure panel label such as Fig. 3c.
- Correctness: The value should match the paper evidence at the requested granularity; aliases are acceptable when they name the same scientific entity.
- Evidence: Figure/caption evidence plus result text.
- Difficulty: medium; requires vision: true; requires reasoning: true; requires calculation: false
- Example answer: Fig. 4d
