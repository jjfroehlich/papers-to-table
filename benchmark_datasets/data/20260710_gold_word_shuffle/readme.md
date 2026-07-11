# Gold word-shuffle negative control

Generated from the active checked-in gold tables by
`python tools/optimizer/scripts/generate_negative_controls.py`.

Whitespace-delimited tokens are shuffled independently within each non-empty target cell. Single-token and otherwise unshufflable cells remain unchanged, making this a weak negative control for word-order sensitivity rather than a guaranteed score floor.

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
