# Outputs And Artifacts

The main-app writes bundles under `app/runs/{run_id}/` by default, unless `output_dir` is overridden.

## Main Directories and Files

- `run.json`: current run status and high-level provenance.
- `config.snapshot.json`: config that was used for the run.
- `inputs/`
- `style_profiles/`
- `parsed/`
- `matching/`
- `retrieval/`
- `retrieval/_indexes/`: generated prepared retrieval indexes keyed by PDF, retrieval mode, caption/table policy, and typed scoring context.
- `proposals/`
- `proposals/proposals.jsonl`: persisted proposals.
- `evidence/`
- `review/`
- `review/decisions.jsonl`: append-only review decisions.
- `summaries/`
- `summaries/run_summary.json`: run-level status and warning summary.
- `summaries/reviewer_summary.json`: review queue and decision summary. Records whether automation review was applied and how many proposals were auto-accepted.
- `diagnostics/`
- `exports/`
- `exports/workbook_*.xlsx`: exported workbook copy.
- `exports/audit_log_*.json`: export audit log.
- `exports/diagnostics_*.json`: export diagnostics.

## Proposal Records

Each proposal record keeps one target-cell outcome using canonical fields from `specs/contracts.md`: `proposal_status`, `evidence_status`, derived/validated `review_bucket`, and `reason_codes`. Records also keep evidence ids and optional diagnostics used by eval, optimizer, and review tooling:

- `candidate_answers`: generic candidates considered before the final value was selected. Sources are `first_pass_text`, `rescued_text`, `evidence_recovery`, and `figure_review`.
- `selection_diagnostics`: selector outcome, selected/rejected candidate ids, rationale, and whether additional evidence was requested.
- `figure_planner_diagnostics`: whether the text-only figure planner ran, skipped vision, selected figures, requested crops or full-page images, or fell back to heuristic shortlisting.
- `figure_review_diagnostics`: figure-review trigger, planner/attempt state, success, failure, suppression, image-source, fallback, retry, repair, dropped/no-hit reasons, accepted-hit count, and useful-evidence details.

## Run Stats

Run summaries and diagnostics include counters that roll up capability use:

- text and vision model call counts.
- prepared retrieval index source counts (`built`, `disk`, `memory`) and retrieval build/load overhead.
- figure planner attempts, successes, skips, and heuristic fallbacks.
- figure review triggered, attempted, succeeded, failed, suppressed, and actual vision-call counts.
- figure-derived evidence counts, accepted-hit counts, dropped/no-hit reasons, and `figure_review_succeeded_without_hit_count`, which counts successful vision calls that did not produce usable figure evidence.
- candidate-selection attempts and value changes.
- recall-rescue and whole-document eligibility, use, and skip reasons.

## Review Records

- Only explicitly accepted proposals become export candidates.
- Decision sources are recorded: `human_individual`, `human_bulk_accept`, and `automation_accept_all`.
- Headless auto-accept also adds a reviewer note stating that `--accept-all` was used.
