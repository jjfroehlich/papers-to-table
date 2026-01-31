# Spec compliance report — Paper Table Agent

Date: 2026-01-31

## Executive summary

The current implementation broadly matches `specs/spec.md`. Core pipeline stages (parsing, matching, retrieval, extraction, evidence validation, review UX, and export) are implemented and covered by the integration and unit test suite. The main discrepancies found during the audit were documentation-level: exports are produced via the explicit `paper-table-agent export` command rather than automatically during the run, and capability probe results were not surfaced in the run report. Both gaps have been addressed in this revision (spec update + run report enhancement).

## Spec compliance checklist

### Product summary
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Local-first PDF→table pipeline with Run/Review UI | Yes | `paper_table_agent/cli.py`, `paper_table_agent/ui/app.py`, `paper_table_agent/graph/runner.py` | CLI + Streamlit run/review flow verified via tests. |

### Proposal model behavior (inference-first)
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Inference-first extraction with anchored evidence | Yes | `paper_table_agent/prompts/extract_group.md`, `paper_table_agent/graph/extraction.py` | Evidence rules preserve values; evidence quality treated as metadata. |
| Evidence strength grading + rationale | Yes | `paper_table_agent/graph/extraction.py`, `paper_table_agent/llm/models.py` | Rationale stored in `reasoning`; evidence quality flags tracked. |

### Golden path
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Table+schema load, PDF parse, header extraction, matching, retrieval, extraction, evidence finder, persist, review, export | Yes | `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/workflow.py`, `paper_table_agent/graph/exporter.py` | End-to-end CLI tests confirm proposals, evidence, and export outputs. |

### Inputs
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| CSV/XLSX table + schema, PDF folder, run_config.json | Yes | `paper_table_agent/config.py`, `paper_table_agent/cli.py` | RunConfig validation enforces paths. |

### Outputs
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| run_config.json, proposals.sqlite, run_report.json, logs/run.log, checkpoints.sqlite | Yes | `paper_table_agent/graph/workflow.py`, `paper_table_agent/graph/reporting.py`, `paper_table_agent/utils/logging.py` | Verified in stub run. |
| Exports written after `paper-table-agent export` | Yes | `paper_table_agent/graph/exporter.py`, `paper_table_agent/cli.py` | Export invoked in integration test. |
| Debug reports gated by `output.debug_reports` | Yes | `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/exporter.py` | Mapping report and proposals.jsonl are gated. |
| LLM records/payloads recorded when enabled | Yes | `paper_table_agent/llm/client.py`, `paper_table_agent/graph/runner.py` | Paths are set based on provider config. |

### Guardrails
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Locked cells not overwritten; single-space treated as empty | Yes | `paper_table_agent/io/locks.py`, `paper_table_agent/config.py` | Lock map built from table data. |
| Verify mode produces verify-only items | Yes | `paper_table_agent/graph/extraction.py`, `paper_table_agent/graph/runner.py` | Verify records stored without overwriting. |
| Evidence validation annotates flags without suppressing values | Yes | `paper_table_agent/graph/extraction.py` | Evidence validation errors added to flags. |
| Evidence finder for weak/none evidence | Yes | `paper_table_agent/graph/evidence_finder.py` | Runs after extraction when evidence is weak/missing. |

### Matching behavior
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Deterministic matching with title/author/year/DOI features | Yes | `paper_table_agent/graph/matching.py` | DOI bonus + year tolerance implemented. |
| LLM adjudication fallback for plausible candidates | Yes | `paper_table_agent/graph/matching.py`, `paper_table_agent/graph/runner.py` | Adjudication invoked when scores exceed fallback thresholds. |
| Duplicates handled with highest confidence | Yes | `paper_table_agent/graph/runner.py` | Duplicate matches are marked and deconflicted. |

### Extraction behavior
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Column grouping, context summaries, ID-based extraction | Yes | `paper_table_agent/graph/extraction.py`, `paper_table_agent/llm/models.py` | `col_id` mapping and grouped prompts. |
| Evidence validation uses chunk refs and substring checks | Yes | `paper_table_agent/graph/extraction.py` | Normalized matching + validation errors captured. |
| Unclear/error records preserved | Yes | `paper_table_agent/graph/extraction.py` | Error/unclear records stored with flags. |

### Whole-text + paper memory (feature-flagged)
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Whole-text when within budget; paper memory fallback | Yes | `paper_table_agent/graph/runner.py` | Document anchors and paper memory summaries implemented. |
| Evidence anchors include page/anchor_id for highlights | Yes | `paper_table_agent/llm/models.py`, `paper_table_agent/pdf/highlight.py` | Evidence items contain page + anchor references. |

### Retrieval behavior
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Sparse+dense retrieval + reranking with fallback | Yes | `paper_table_agent/retrieval/pipeline.py`, `paper_table_agent/retrieval/index.py` | TF-IDF fallback logged on failure. |
| Query expansion/HyDE optional; context window expansion | Yes | `paper_table_agent/retrieval/pipeline.py` | Query variants and neighbor expansion implemented. |
| Deterministic hash backends for offline tests | Yes | `paper_table_agent/llm/embeddings.py`, `tests/test_retrieval.py` | Hash backend tested. |

### Review UX
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| Run tab + Review tab with Accept/Reject/Edit | Yes | `paper_table_agent/ui/app.py`, `paper_table_agent/ui/review_queue.py` | UI tests import app module successfully. |
| Highlighted evidence with re-locate action | Yes | `paper_table_agent/pdf/highlight.py`, `paper_table_agent/ui/app.py` | Highlight locator + UI actions implemented. |

### Operational defaults
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| No UI tuning knobs; config via run_config.json | Yes | `paper_table_agent/ui/app.py`, `paper_table_agent/config.py` | UI exposes only run paths. |
| Health checks + run report logging | Yes | `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/reporting.py` | Health check events surface in run report. |
| Capability probes cached and summarized in run report | Yes | `paper_table_agent/llm/client.py`, `paper_table_agent/graph/runner.py`, `paper_table_agent/graph/reporting.py` | Capability events recorded + surfaced. |
| CLI entrypoint + UI smoke mode | Yes | `paper_table_agent/cli.py`, `tests/test_cli_entrypoint.py`, `tests/test_ui_smoke.py` | CI smoke path covered. |
| Stub run fixture yields evidence + highlight | Yes | `tests/test_stub_run_cli.py`, `tests/test_integration.py` | Evidence/highlight assertions exist. |

### Failure semantics
| Requirement | Implemented? | Evidence | Notes |
| --- | --- | --- | --- |
| matched PDFs > 0 and proposals == 0 ⇒ completed_with_warnings + why_no_values | Yes | `paper_table_agent/graph/reporting.py` | Run report includes `why_no_values` diagnostics. |
| Health check failures mark run failed | Yes | `paper_table_agent/graph/reporting.py`, `paper_table_agent/graph/runner.py` | FAIL files written when health checks fail. |

## Priority gaps

No remaining P0/P1 gaps identified after updates. The only changes required to align spec and implementation were:

1. Documenting that exports are produced by the explicit `paper-table-agent export` command.
2. Surfacing LLM capability probe summaries in `run_report.json`.

## Spec ambiguities or contradictions

- None outstanding after updating output semantics in the spec to match the actual run/export flow.

## Verification evidence

- `pytest -q` (full test suite)
- `python -m paper_table_agent.cli run --config tests/fixtures/stub_run_config.json` (stub run output verification)
