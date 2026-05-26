You are filling scientific extraction benchmark tables.

Benchmark root folder:
C:\Users\jonat\Desktop\20260517_external_codex_gpt-pro-5-5-extra-high\benchmark_datasets

Complete this task for all three benchmark dataset subfolders in that folder, including for example:
C:\Users\jonat\Desktop\20260517_external_codex_gpt-pro-5-5-extra-high\benchmark_datasets\genome_editing_tools
C:\Users\jonat\Desktop\20260517_external_codex_gpt-pro-5-5-extra-high\benchmark_datasets\massively_parallel_reporter_assays
C:\Users\jonat\Desktop\20260517_external_codex_gpt-pro-5-5-extra-high\benchmark_datasets\spatial_transcriptomics

For each benchmark dataset folder, use:
1. The empty table/template file in that benchmark folder.
2. The schema file in that benchmark folder.
3. The PDF files in that benchmark folder.

Task:
Fill in proposed values for every target cell in each benchmark table using only information supported by the provided PDFs.

Rules:
- Preserve the original row order.
- Preserve all original columns exactly, including row_id and row_index if present.
- Do not rename columns.
- Do not remove rows.
- Fill only the target value columns.
- If a value is not available in the PDFs, leave the cell blank.
- Do not guess values that are not supported by the paper.
- Use concise values that match the schema.
- For categorical fields, use only allowed schema values when provided.
- Process all three benchmark datasets independently.
- Return one completed CSV file per benchmark dataset.
- Name each output file clearly with the benchmark folder name, for example:
  genome_editing_tools_filled.csv

Output:
Three completed CSV files, one for each benchmark dataset, with the same headers as their corresponding input table.