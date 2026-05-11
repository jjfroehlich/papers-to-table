# Benchmark Datasets

Curated benchmark datasets live at the repository root under `benchmark_datasets/` so they are visible to users and usable by the app, Eval, and Optimizer.

Each dataset has the same basic shape:

- `table_template.csv`: app-facing input table with stable `row_id` / `row_index`, paper metadata, and blank target cells.
- `schema.csv`: extraction schema used by the main app. The descriptions become prompt instructions.
- `table_gold.csv`: human-curated answer table used by Eval.
- `pdfs/`: source PDFs for the benchmark.

Available datasets:

- `massively_parallel_reporter_assays`
- `genome_editing_tools`
- `spatial_transcriptomics`

## Massively Parallel Reporter Assays

This is the default visible benchmark and replaces the older app test fixtures. It covers five MPRA/STARR-seq style papers with target fields for assay design, cloning, species, model systems, reporter integration, sequence/barcode details, RNA-library preparation, and UMI usage.

Use it in the main app:

```json
{
  "table_path": "../benchmark_datasets/massively_parallel_reporter_assays/table_template.csv",
  "schema_path": "../benchmark_datasets/massively_parallel_reporter_assays/schema.csv",
  "pdf_dir": "../benchmark_datasets/massively_parallel_reporter_assays/pdfs"
}
```

Use it with Eval:

```bash
python scripts/papers_to_table.py eval \
  --run /abs/run_bundle \
  --gold /abs/repo/benchmark_datasets/massively_parallel_reporter_assays/table_gold.csv \
  --out /abs/eval_out
```

Score an external filled table:

```bash
cd tools/eval
python -m paper_eval evaluate \
  --external-result /abs/external_filled_table.csv \
  --gold /abs/repo/benchmark_datasets/massively_parallel_reporter_assays/table_gold.csv \
  --out /abs/eval_out
```

## Schema Descriptions

Schema descriptions are crucial because they are converted into model prompts. A good description names the exact field, acceptable evidence, units, scope, and any table convention such as controlled values. A vague description is a vague prompt.

You can use an LLM to draft or improve these descriptions, but review them before running. The final schema should clarify what is being looked for and should not smuggle in default answers.

## Gold Tables

<details>
<summary>Massively parallel reporter assays gold table</summary>

| row_index | Title | Synthetic designs | Cloning | Species | Model system | Episomal vs genomic | Integration method | # Variants tested | length of sequences (bp) | Where is the BC? | BC length (bp) | RNA library | UMI? |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Sequence determinants of human gene regulatory elements | + | restriction | human | HepG2, GP5d, RPE1 | episomal | none | 27,000,000 motif; 2,000,000,000 genomic; 2,000,000,000 random | 49, 500, 150, 170 | no BC | no BC | reporter-specific RT | no |
| 1 | Optimized reporters for multiplexed detection of transcription factor activity | + | restriction | mouse, human | mESC, mNPC, HEK293, K562, HEPG2, U2OS, MCF7, A549, HCT116 | episomal | none | 5,530 | 202 | 5'UTR | 13 | Reverse transcription with gene-specific primer targeting GFP ORF, PCR adding Illumina adapters. | yes |
| 2 | Genome-Wide Quantitative Enhancer Activity Maps Identified by STARR-seq | - | not found | fly, human | S2, OSC, HeLa | episomal | none | 11,300,000 | 600 | no BC | no BC | Poly(A) selection, targeted RT, PCR | no |
| 3 | Predictable Engineering of Signal-Dependent Cis-Regulatory Elements | + | golden gate | mouse | neural tube differentiation from mESCs | genomic | Lenti | 13,991 | 608 | 3'UTR | 24 | none | no |
| 4 | Synthetic and genomic regulatory elements reveal aspects of cis-regulatory grammar in mouse embryonic stem cells | + | restriction | mouse | mESC | episomal | none | 1,438 | 40-80 | 3'UTR | 9 | cDNA synthesis with oligo dT, PCR amplification 13 cycles, XbaI/XhoI digest, ligation to Illumina adapters, enrichment PCR. | no |

</details>

