# Extract Structured Info from Papers Eval Task Tracker

This file is the canonical implementation-status tracker for the repo.

Keep status here only. Do not duplicate implementation status in `spec.md`, `plan.md`, or `research.md`.

Working rules:

- Keep each task listed exactly once.
- Preserve stable section structure when updating this file.
- Reclassify a task only after checking code, tests, and operator-facing docs.
- Keep completed tasks visible.
- Put temporary historical notes in the appendix rather than inside the canonical checklist.

## Foundation / CLI / Contracts

- [x] E001 Create the base package layout for the evaluator CLI and supporting modules.
- [x] E002 Implement CLI argument parsing for `evaluate` with `--run`, `--runs-root`, repeated `--run`, `--gold`, optional `--gold-sheet`, optional `--schema`, and `--out`.
- [x] E003 Implement output-directory creation and run-level output path helpers.
- [x] E004 Define evaluator-owned typed contracts for loaded run metadata, proposal records, evidence records, gold cells, scored cells, and run summaries.
- [x] E006 Implement contract validation for required main-app artifact files and the published stable eval join fields.
- [x] E010 Implement explicit contract errors for missing required scoring fields, especially missing stable join identifiers such as `row_id`, `column_name`, and `cell_id`.
- [x] E048 Fail fast when the published stable join contract is missing or inconsistent, and document the contract gap clearly.
- [x] E048a Fail fast on unsupported main-app artifact schema versions while preserving bounded backward compatibility for known versions.

## Run Bundle Loading and Gold Loading

- [x] E005 Implement main-app run bundle discovery for one run, a runs root, and an explicit run list.
- [x] E007 Implement proposal loading from `proposals/proposals.jsonl`.
- [x] E008 Implement loading of run metadata from `run.json`, `config.snapshot.json`, `inputs/input_summary.json`, and `summaries/run_summary.json` when present.
- [x] E009 Implement a loader or adapter path for evidence data when proposals do not already carry enough evidence detail.
- [x] E009a Load canonical main-app per-evidence JSON artifacts when sidecar evidence files are absent.
- [x] E009b Reconstruct page-text-compatible source text from persisted parsed-document artifacts when page-text sidecars are absent.
- [x] E011 Implement gold CSV loading.
- [x] E012 Implement gold XLSX loading with single-sheet selection per invocation and a documented default first-sheet behavior when no sheet is specified.
- [x] E013 Implement consistent gold-present versus gold-empty detection.

## Join-Key and Contract Validation

- [x] E047 Add contract validation for eval-mode provenance fields such as gold and masked table hashes and snapshot paths when runs are marked as eval runs.
- [x] E053 Implement contract tests for required main-app artifact fields, worksheet selection behavior, and failure messages.
- [x] E060 Keep an explicit visible note in docs about the required stable join-key contract between the main app and the eval repo, with `row_index` treated only as fallback or debug context.

## Structured Scoring

- [x] E014 Implement field-type resolution precedence across proposal metadata, schema metadata, and evaluator fallbacks, including field or column scoring-policy overrides for text fields.
- [x] E015 Implement boolean normalization.
- [x] E016 Implement categorical normalization with alias mapping and `allowed_values` support.
- [x] E017 Implement numeric normalization for exact, range, and approximate forms, plus numeric tolerance resolution with per-column override and global defaults.
- [x] E018 Implement deterministic boolean comparison.
- [x] E019 Implement deterministic categorical comparison.
- [x] E020 Implement deterministic numeric comparison with binary headline correctness under the resolved tolerance policy plus diagnostic error fields.
- [x] E021 Implement per-cell scoring orchestration for structured fields on gold-present cells only, consuming stable main-app identifiers rather than derived row-index joins.
- [x] E022 Write per-cell outputs for one run in JSONL and CSV.
- [x] E023 Implement per-run aggregation for structured metrics and diagnostic counts.
- [x] E024 Write per-run `run_summary.json` and `run_summary.csv`.

## Evidence Validation

- [x] E028 Implement the minimal evidence anchor contract check using page plus quote text, and quote locatability when persisted page text or equivalent text evidence is available.
- [x] E028a Add bounded normalized-text fallback so parsed-document text can validate anchors without overstating confidence.
- [x] E029 Implement `anchor_valid_rate`, counting only fully validated anchors and distinguishing evidence-present-but-unvalidated as a separate diagnostic state.
- [x] E030 Implement `correct_and_anchored_rate`.
- [x] E031 Implement optional structured-field support proxy evaluation behind a narrow internal interface.
- [x] E032 Implement diagnostic counting for gold-empty proposals, including `filled_on_gold_empty_count`.

## Batch Comparison Outputs

- [x] E025 Implement batch evaluation over a runs root and repeated explicit run paths.
- [x] E026 Normalize run metadata into one flat comparison row schema.
- [x] E033 Implement batch comparison row generation with one row per run.
- [x] E034 Write the canonical batch comparison CSV.
- [x] E035 Write batch comparison XLSX from the same normalized rows.
- [x] E036 Write batch comparison Parquet from the same normalized rows.
- [x] E037 Implement `compare` command support for rebuilding comparison artifacts from per-run summaries.

## Text Judge Integration

- [x] E038 Define the judge request and response schema for text-field scoring under a judge-by-default policy for text fields.
- [x] E039 Implement judge prompt construction with bounded field context only.
- [x] E040 Implement a judge adapter with fixed model configuration, temperature 0, and bounded fallback from `json_schema` to `json_object` to prompt-only JSON mode.
- [x] E041 Implement text-field normalization helpers needed before judge invocation and deterministic override support for highly standardized text columns.
- [x] E042 Implement `text_accuracy` under the configured text scoring policy, with judge-backed scoring by default and deterministic override where configured.
- [x] E043 Persist judge metadata per scored text cell, including judge model id, prompt version or hash, and temperature.
- [x] E044 Write judge records to a separate inspectable artifact such as `judge_records.jsonl`.
- [x] E045 Ensure judge use is limited to text fields by default, while allowing explicit field or column deterministic override for standardized text fields.
- [x] E046 Add CLI flags or config inputs for fixed judge model selection without widening the tool into a broad config framework.
- [x] E061 Make LM Studio the default local-first judge provider through its OpenAI-compatible API, with `qwen/qwen3.5-35b-a3b` as the default configured judge model for MVP.
- [x] E062 Persist full judge provenance for judge-backed cells and judge records, including provider, configured judge model, resolved runtime judge model, prompt version or hash, verdict, and input hash.

## Reproducibility Metadata

- [x] E027 Include core run metadata columns such as run id, mode, text model id, vision model id, parser identity or version, prompt version or hash, schema hash or version, and config hash.

## Tests / Contract Hardening

- [x] E049 Implement unit tests for boolean, categorical, and numeric normalization.
- [x] E050 Implement unit tests for deterministic comparators.
- [x] E051 Implement unit tests for gold-present and gold-empty detection.
- [x] E052 Implement unit tests for evidence anchor validation, including locatable versus present-but-unvalidated quote cases.
- [x] E052a Add tests for canonical main-app evidence-directory loading and parsed-document page-text fallback.
- [x] E054 Implement end-to-end tests for scoring one run.
- [x] E055 Implement end-to-end tests for scoring multiple runs and writing batch comparison outputs.
- [x] E055a Add contract tests proving a main-app-style eval-mode run bundle remains loadable and anchor-validatable.
- [x] E056 Implement mocked judge tests for text scoring under judge-by-default behavior and deterministic text override behavior.
- [x] E059 Review the spec set together for consistency after material changes.

## Verification / CI

- [x] E068 Add minimal CI coverage for loader, scorer, and contract-regression tests.

## Docs / Operator Guidance / Stdout JSON Mode

- [x] E057 Write the initial `README.md` or operator documentation once actual commands, output paths, and examples exist.
- [x] E058 Document the published input artifact contract expected from the main app in operator-facing docs, including stable join identifiers and single-sheet XLSX behavior.
- [x] E063 Tighten `README.md` and operator docs so they clearly explain what the eval repo does, expected main-app inputs, one-run and many-run evaluation workflows, headline metrics, diagnostic metrics, and current limitations.
- [x] E064 Add explicit operator guidance and examples for the LM Studio judge path, including configuration, the default judge model `qwen/qwen3.5-35b-a3b`, and how persisted judge metadata should be interpreted.
- [x] E067 Document judge fallback behavior and the additional judge-failure and judge-response-mode diagnostic metrics exposed in run summaries.
- [x] E065 Add optional machine-readable JSON stdout completion mode for `evaluate` and `compare`, while keeping file artifacts canonical.
- [x] E066 Add tests and docs for JSON stdout mode, including payload schema tagging and key produced artifact paths.

## Appendix: Retired Batch Framing

Earlier versions of this file grouped work into numbered batches. That framing is retired.

If historical implementation order matters for discussion, refer to version control rather than reintroducing batch sections into the canonical checklist.
