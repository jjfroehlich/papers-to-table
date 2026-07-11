# Gold cross-field negative control

Generated from the active checked-in gold tables by
`python tools/optimizer/scripts/generate_negative_controls.py`.

Whole non-empty gold values are reassigned across target rows and columns within each dataset. The generator requires a value-level derangement, so no non-empty target cell retains its original rendered value. This intentionally mixes field types and is a strong score-floor control.

The generator preserves CSV headers, row order, `row_id`, `row_index`, metadata columns, and the
blank/non-empty target-cell mask. It creates three deterministic replicates for every active benchmark
dataset. Exact source hashes, seeds, target columns, and cell counts are recorded in
`generation_manifest.json`.

Verify that the checked-in files still match their sources and algorithm with:

```bash
python tools/optimizer/scripts/generate_negative_controls.py --check
```

These files are Eval inputs and report controls. They are not extraction outputs and must not participate
in optimizer winner or recommended-default selection.
