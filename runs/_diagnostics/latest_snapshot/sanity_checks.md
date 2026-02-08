# Sanity checks

- `paper_table_agent/graph/runner.py::_run_health_checks`: probes model endpoint availability, runs a
  small `query_expand.md` completion, and validates embedding/reranker backends. Logs health_check events
  and applies fallbacks if needed.
- `paper_table_agent/graph/reporting.py::_run_sanity_check`: fails the run report if matched PDFs exist
  but zero proposals were stored; captures diagnostics like schema column count, missing cell count,
  extraction invocation count, and evidence validation drops.
