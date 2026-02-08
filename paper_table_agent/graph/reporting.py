from __future__ import annotations

import csv
import json
import logging
import zipfile
from pathlib import Path

from jinja2 import Template

from paper_table_agent.io.schema import load_schema
from paper_table_agent.store.db import Store
from paper_table_agent.llm.client import estimate_tokens

LOGGER = logging.getLogger(__name__)


_REPORT_TEMPLATE = Template(
    """
<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>Mapping Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 24px; }
    th, td { border: 1px solid #ddd; padding: 8px; }
    th { background-color: #f4f4f4; }
    .candidates { margin-left: 16px; }
  </style>
  </head>
<body>
  <h1>Mapping Report</h1>
  <p>
    Matched: {{ matched }} |
    Ambiguous: {{ ambiguous }} |
    Unmatched: {{ unmatched }} |
    Duplicates: {{ duplicates }}
  </p>
  <table>
    <thead>
      <tr>
        <th>PDF ID</th>
        <th>Row ID</th>
        <th>Status</th>
        <th>Confidence</th>
        <th>PDF Title</th>
        <th>PDF Authors</th>
        <th>PDF Year</th>
        <th>Row Title</th>
        <th>Row Authors</th>
        <th>Row Year</th>
        <th>LLM Adjudication</th>
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        <td>{{ row.pdf_id }}</td>
        <td>{{ row.row_id }}</td>
        <td>{{ row.status }}</td>
        <td>{{ row.confidence }}</td>
        <td>{{ row.pdf_title }}</td>
        <td>{{ row.pdf_authors }}</td>
        <td>{{ row.pdf_year }}</td>
        <td>{{ row.row_title }}</td>
        <td>{{ row.row_authors }}</td>
        <td>{{ row.row_year }}</td>
        <td>{{ row.llm_adjudication }}</td>
      </tr>
      {% if row.candidates %}
      <tr>
        <td colspan=\"10\">
          <div class=\"candidates\">
            <strong>Top candidates</strong>
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Row ID</th>
                  <th>Score</th>
                  <th>Title</th>
                  <th>Authors</th>
                  <th>Year</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {% for candidate in row.candidates %}
                <tr>
                  <td>{{ candidate.rank }}</td>
                  <td>{{ candidate.row_id }}</td>
                  <td>{{ candidate.score }}</td>
                  <td>{{ candidate.title }}</td>
                  <td>{{ candidate.authors }}</td>
                  <td>{{ candidate.year }}</td>
                  <td>{{ candidate.source }}</td>
                </tr>
                {% endfor %}
              </tbody>
            </table>
          </div>
        </td>
      </tr>
      {% endif %}
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
"""
)


def write_mapping_report(store: Store, output_dir: Path, write_reports: bool = False) -> None:
    if not write_reports:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    matches = store.fetch_matches()
    rows = {row["row_id"]: dict(row) for row in store.fetch_rows()}
    pdf_metadata = {row["pdf_id"]: dict(row) for row in store.fetch_pdf_metadata()}
    candidates = store.fetch_match_candidates()
    events = [
        dict(row)
        for row in store.conn.execute("SELECT event_type, payload_json FROM events")
    ]
    adjudication_by_pdf: dict[str, str] = {}
    for event in events:
        event_type = event.get("event_type")
        if event_type not in {"match_adjudication_attempted", "match_adjudication_skipped"}:
            continue
        payload = json.loads(event.get("payload_json") or "{}")
        pdf_id = payload.get("pdf_id")
        if not pdf_id:
            continue
        if event_type == "match_adjudication_attempted":
            adjudication_by_pdf[pdf_id] = "Attempted"
        else:
            reason = payload.get("reason", "skipped")
            adjudication_by_pdf[pdf_id] = f"Skipped ({reason})"
    candidates_by_pdf: dict[str, list[dict[str, object]]] = {}
    for candidate in candidates:
        candidates_by_pdf.setdefault(candidate["pdf_id"], []).append(dict(candidate))
    for pdf_id, items in candidates_by_pdf.items():
        items.sort(key=lambda item: (item.get("rank") or 0, item.get("source") or ""))
        candidates_by_pdf[pdf_id] = items[:5]
    report_rows = []
    for match in matches:
        row = rows.get(match["row_id"], {})
        pdf_meta = pdf_metadata.get(match["pdf_id"], {})
        report_rows.append(
            {
                "pdf_id": match["pdf_id"],
                "row_id": match["row_id"],
                "status": match["status"],
                "confidence": match["confidence"],
                "pdf_title": pdf_meta.get("title", ""),
                "pdf_authors": pdf_meta.get("authors", ""),
                "pdf_year": pdf_meta.get("year", ""),
                "row_title": row.get("title", ""),
                "row_authors": row.get("authors", ""),
                "row_year": row.get("year", ""),
                "candidates": candidates_by_pdf.get(match["pdf_id"], []),
                "llm_adjudication": adjudication_by_pdf.get(match["pdf_id"], "Not attempted"),
            }
        )

    summary = {
        "matched": sum(1 for match in matches if match["status"] == "matched"),
        "ambiguous": sum(1 for match in matches if match["status"] == "ambiguous"),
        "unmatched": sum(1 for match in matches if match["status"] == "unmatched"),
        "duplicates": sum(1 for match in matches if match["status"] == "duplicate"),
    }

    html = _REPORT_TEMPLATE.render(rows=report_rows, **summary)
    (output_dir / "mapping_report.html").write_text(html, encoding="utf-8")

    with (output_dir / "pdf_row_matches.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "pdf_id",
                "row_id",
                "status",
                "confidence",
                "pdf_title",
                "pdf_authors",
                "pdf_year",
                "row_title",
                "row_authors",
                "row_year",
            ]
        )
        for row in report_rows:
            writer.writerow(
                [
                    row["pdf_id"],
                    row["row_id"],
                    row["status"],
                    row["confidence"],
                    row["pdf_title"],
                    row["pdf_authors"],
                    row["pdf_year"],
                    row["row_title"],
                    row["row_authors"],
                    row["row_year"],
                ]
            )


def write_run_report(store: Store, run_paths: Path | object) -> str:
    run_dir = run_paths.run_dir if hasattr(run_paths, "run_dir") else Path(run_paths)
    config_path = run_dir / "run_config.json"
    config_payload = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    matches = [dict(row) for row in store.fetch_matches()]
    proposals = [
        dict(row)
        for row in store.conn.execute(
            "SELECT column, status, proposed_value, flags_json, evidence_json FROM proposals"
        )
    ]
    events = [
        dict(row)
        for row in store.conn.execute("SELECT level, event_type, payload_json FROM events")
    ]
    matched = sum(1 for row in matches if row.get("status") == "matched")
    ambiguous = sum(1 for row in matches if row.get("status") == "ambiguous")
    unmatched = sum(1 for row in matches if row.get("status") in {"unmatched", "duplicate"})
    proposal_counts = _proposal_counts(proposals)
    evidence_quality = _evidence_quality_breakdown(proposals)
    evidence_coverage = _evidence_coverage_metrics(proposals)
    highlight_stats = _highlight_stats(proposals)
    evidence_finder_stats = _evidence_finder_stats(proposals)
    extraction_batch_stats = _extract_group_batch_stats(events)
    found_unanchored_downgraded = _found_unanchored_downgraded(proposals)
    context_plan_summary = _context_plan_summary(events)
    column_completion = _column_completion_stats(proposals, extraction_batch_stats)
    extractable_columns = _count_extractable_columns(store, config_payload, matched_rows=matches)
    llm_capabilities = [
        json.loads(event.get("payload_json") or "{}")
        for event in events
        if event.get("event_type") == "llm_capabilities"
    ]
    prompt_limits = _prompt_limit_summary(config_payload, llm_capabilities)
    llm_call_summary = _llm_call_summary(events)
    sanity_check = _run_sanity_check(
        matched,
        extractable_columns,
        proposal_counts.get("total", 0),
        store,
        config_payload,
        matches,
        proposals,
    )
    health_events = [event for event in events if event.get("event_type") == "health_check_failed"]
    parse_events = [event for event in events if event.get("event_type") == "parse_sanity"]
    audit_events = [
        json.loads(event.get("payload_json") or "{}")
        for event in events
        if event.get("event_type") == "audit_plan"
    ]
    audit_summary = audit_events[-1] if audit_events else {}
    eval_summary = {}
    eval_path = run_dir / "exports" / "proposal_eval.json"
    if eval_path.exists():
        eval_payload = json.loads(eval_path.read_text(encoding="utf-8"))
        eval_summary = eval_payload.get("summary", {})
    run_status = "failed" if sanity_check.get("failed") or health_events else "completed"
    if sanity_check.get("warning") and run_status != "failed":
        run_status = "completed_with_warnings"
    if run_status not in {"failed", "completed_with_warnings"}:
        error_events = [event for event in events if event.get("level") == "error"]
        if error_events:
            run_status = "completed_with_errors"
    if run_status == "failed":
        (run_dir / "FAILED").write_text("failed", encoding="utf-8")
        if sanity_check.get("failed"):
            LOGGER.error("Run failed sanity check: %s", sanity_check)
        elif health_events:
            LOGGER.error("Run failed health check: %s", health_events)
    elif run_status == "completed_with_warnings":
        (run_dir / "COMPLETED_WITH_WARNINGS").write_text("done", encoding="utf-8")
    retrieval_backend = next(
        (
            json.loads(event.get("payload_json") or "{}")
            for event in reversed(events)
            if event.get("event_type") == "retrieval_backend"
        ),
        {},
    )
    fallback_events = {
        "embedding_fallback": [],
        "reranker_fallback": [],
        "retrieval_fallback": [],
        "llm_backend_incompatible": [],
        "llm_fallback_applied": [],
    }
    for event in events:
        event_type = event.get("event_type")
        if event_type in fallback_events:
            fallback_events[event_type].append(json.loads(event.get("payload_json") or "{}"))
    debug_extraction = []
    for row in store.fetch_debug_extraction():
        payload_json = row["payload_json"]
        payload = json.loads(payload_json) if payload_json else {}
        debug_extraction.append(payload)
    payload = {
        "run_id": run_dir.name,
        "status": run_status,
        "inputs": {
            "table_path": config_payload.get("table_path"),
            "pdf_folder": config_payload.get("pdf_folder"),
        },
        "summary": {
            "mapping": {
                "matched": matched,
                "ambiguous": ambiguous,
                "unmatched": unmatched,
                "total": len(matches),
            },
            "proposals": proposal_counts,
            "evidence_quality": evidence_quality,
            "evidence_coverage": evidence_coverage,
            "highlighting": highlight_stats,
            "evidence_finder": evidence_finder_stats,
            "extraction_batches": extraction_batch_stats,
            "extraction_diagnostics": {
                "evidence_coverage_rate": evidence_coverage.get("coverage_rate", 0),
                "highlight_success_rate": highlight_stats.get("ok_rate", 0),
                "found_unanchored_downgraded": found_unanchored_downgraded,
                "columns_missing": column_completion.get("columns_missing"),
                "columns_attempted": column_completion.get("columns_attempted"),
                "columns_completed": column_completion.get("columns_completed"),
            },
            "audit": {
                "enabled": bool((config_payload.get("audit") or {}).get("use_filled_cells_as_gold")),
                "audited_cells_count": audit_summary.get("audited_cells_count", 0),
                "audited_columns_count": audit_summary.get("audited_columns_count", 0),
                "audited_rows_count": audit_summary.get("audited_rows_count", 0),
                "audited_match_rate": eval_summary.get("match_rate", 0),
            },
            "evaluation": eval_summary,
            "errors": {
                "total_events": len(events),
                "error_events": sum(1 for row in events if row.get("level") == "error"),
            },
            "health_check": {
                "failed": bool(health_events),
                "errors": [json.loads(event.get("payload_json") or "{}") for event in health_events],
            },
            "llm_capabilities": llm_capabilities,
            "llm": {
                "mode": (config_payload.get("provider") or {}).get("mode"),
                "base_url": (config_payload.get("provider") or {}).get("base_url"),
                "models": {
                    "header": (config_payload.get("provider") or {}).get("model_header"),
                    "match": (config_payload.get("provider") or {}).get("model_match"),
                    "extract": (config_payload.get("provider") or {}).get("model_extract"),
                    "query_helper": (config_payload.get("provider") or {}).get("model_query_helper"),
                },
                "live_llm": not (
                    (config_payload.get("provider") or {}).get("mock_mode")
                    or (config_payload.get("provider") or {}).get("mode") in {"stub", "mock"}
                ),
                "prompt_limits": prompt_limits,
            },
            "llm_calls": llm_call_summary,
            "context_plan": context_plan_summary,
            "parsing": [json.loads(event.get("payload_json") or "{}") for event in parse_events],
            "retrieval": retrieval_backend,
            "fallbacks": {
                "embedding": fallback_events["embedding_fallback"],
                "reranker": fallback_events["reranker_fallback"],
                "retrieval": fallback_events["retrieval_fallback"],
                "llm_backend_incompatible": fallback_events["llm_backend_incompatible"],
                "llm_fallback_applied": fallback_events["llm_fallback_applied"],
            },
            "sanity_check": sanity_check,
        },
        "debug_extraction": debug_extraction,
    }
    (run_dir / "run_report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return run_status


def _count_extractable_columns(
    store: Store,
    config_payload: dict[str, object],
    matched_rows: list[dict[str, object]],
) -> int:
    try:
        table_path = Path(str(config_payload.get("table_path", "")))
        schema_source = table_path
        if config_payload.get("schema_mode") == "separate" and config_payload.get("schema_path"):
            schema_source = Path(str(config_payload["schema_path"]))
        specs = load_schema(schema_source, str(config_payload.get("schema_sheet_name", "schema")))
    except Exception:
        return 0
    schema_columns = [spec.column_name for spec in specs]
    if not schema_columns:
        return 0
    matched_row_ids = {
        str(row.get("row_id"))
        for row in matched_rows
        if row.get("status") == "matched" and row.get("row_id") is not None
    }
    if not matched_row_ids:
        return 0
    locked_rows = store.list_locks()
    locked_map: dict[str, set[str]] = {}
    for lock in locked_rows:
        if str(lock["row_id"]) in matched_row_ids:
            locked_map.setdefault(str(lock["row_id"]), set()).add(str(lock["column"]))
    extractable: set[str] = set()
    for row_id in matched_row_ids:
        locked = locked_map.get(row_id, set())
        for column in schema_columns:
            if column not in locked:
                extractable.add(column)
    return len(extractable)


def _proposal_counts(proposals: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {"total": len(proposals)}
    for row in proposals:
        status = str(row.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
        proposed_value = row.get("proposed_value")
        if proposed_value is not None and str(proposed_value).strip():
            counts["with_value"] = counts.get("with_value", 0) + 1
        else:
            counts["without_value"] = counts.get("without_value", 0) + 1
    return counts


def _evidence_quality_breakdown(proposals: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {"strong": 0, "weak": 0, "none": 0}
    for row in proposals:
        flags = json.loads(row.get("flags_json") or "{}")
        quality = flags.get("evidence_quality") or "none"
        if quality not in counts:
            counts[quality] = 0
        counts[quality] += 1
    return counts


def _highlight_stats(proposals: list[dict[str, object]]) -> dict[str, int]:
    total = 0
    highlighted = 0
    failed = 0
    for row in proposals:
        evidence = json.loads(row.get("evidence_json") or "[]")
        for item in evidence:
            total += 1
            if item.get("highlight_status") == "highlighted":
                highlighted += 1
            if item.get("highlight_status") == "failed":
                failed += 1
    ok_rate = (highlighted / total) if total else 0
    failed_rate = (failed / total) if total else 0
    return {
        "total_evidence_items": total,
        "highlighted": highlighted,
        "failed": failed,
        "ok_rate": ok_rate,
        "failed_rate": failed_rate,
    }


def _evidence_coverage_metrics(proposals: list[dict[str, object]]) -> dict[str, float | int]:
    total_with_value = 0
    with_evidence = 0
    weak_count = 0
    needs_more = 0
    for row in proposals:
        proposed_value = row.get("proposed_value")
        has_value = proposed_value is not None and str(proposed_value).strip() != ""
        flags = json.loads(row.get("flags_json") or "{}")
        evidence_items = json.loads(row.get("evidence_json") or "[]")
        if has_value:
            total_with_value += 1
            if evidence_items:
                with_evidence += 1
        if flags.get("evidence_quality") == "weak":
            weak_count += 1
        if flags.get("needs_more_evidence"):
            needs_more += 1
    coverage_rate = (with_evidence / total_with_value) if total_with_value else 0
    return {
        "proposals_with_value": total_with_value,
        "proposals_with_evidence": with_evidence,
        "coverage_rate": coverage_rate,
        "weak_evidence_count": weak_count,
        "needs_more_evidence_count": needs_more,
    }


def _evidence_finder_stats(proposals: list[dict[str, object]]) -> dict[str, float | int]:
    attempted = 0
    succeeded = 0
    backfilled = 0
    for row in proposals:
        flags = json.loads(row.get("flags_json") or "{}")
        if flags.get("evidence_finder_attempted"):
            attempted += 1
        if flags.get("evidence_finder_succeeded"):
            succeeded += 1
        backfilled += int(flags.get("evidence_backfilled_count") or 0)
    attempted_rate = (attempted / len(proposals)) if proposals else 0
    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "backfilled_count": backfilled,
        "attempted_rate": attempted_rate,
    }


def _extract_group_batch_stats(events: list[dict[str, object]]) -> dict[str, object]:
    batch_events = [
        json.loads(event.get("payload_json") or "{}")
        for event in events
        if event.get("event_type") == "extract_group_batch"
    ]
    total_batches = len(batch_events)
    prompt_trims = sum(1 for event in batch_events if event.get("prompt_trimmed"))
    columns_attempted = sum(len(event.get("columns", []) or []) for event in batch_events)
    missing_by_row: dict[tuple[str, str, str], int] = {}
    for event in batch_events:
        key = (
            str(event.get("pdf_id") or ""),
            str(event.get("row_id") or ""),
            str(event.get("group") or ""),
        )
        missing_by_row[key] = max(int(event.get("total_missing_columns") or 0), missing_by_row.get(key, 0))
    total_missing_columns = sum(missing_by_row.values()) if missing_by_row else 0
    chunks_present = sum(1 for event in batch_events if event.get("batch_has_chunks"))
    chunks_missing = total_batches - chunks_present
    return {
        "total_batches": total_batches,
        "columns_attempted": columns_attempted,
        "total_missing_columns": total_missing_columns,
        "prompt_trims": prompt_trims,
        "chunks_present_batches": chunks_present,
        "chunks_missing_batches": chunks_missing,
        "batch_details": batch_events,
    }


def _found_unanchored_downgraded(proposals: list[dict[str, object]]) -> int:
    count = 0
    for row in proposals:
        flags = json.loads(row.get("flags_json") or "{}")
        if flags.get("found_unanchored_downgraded"):
            count += 1
    return count


def _context_plan_summary(events: list[dict[str, object]]) -> dict[str, object]:
    plans = [
        json.loads(event.get("payload_json") or "{}")
        for event in events
        if event.get("event_type") == "context_plan"
    ]
    by_pdf: dict[str, dict[str, object]] = {}
    for plan in plans:
        pdf_id = str(plan.get("pdf_id") or "")
        if not pdf_id:
            continue
        by_pdf[pdf_id] = plan
    return {
        "total": len(by_pdf),
        "modes": {pdf_id: payload.get("mode") for pdf_id, payload in by_pdf.items()},
        "plans": list(by_pdf.values()),
    }


def _column_completion_stats(
    proposals: list[dict[str, object]],
    extraction_batch_stats: dict[str, object],
) -> dict[str, int]:
    columns_missing = int(extraction_batch_stats.get("total_missing_columns") or 0)
    columns_attempted = int(extraction_batch_stats.get("columns_attempted") or 0)
    columns_completed = 0
    for row in proposals:
        value = row.get("proposed_value")
        if value is not None and str(value).strip():
            columns_completed += 1
    return {
        "columns_missing": columns_missing,
        "columns_attempted": columns_attempted,
        "columns_completed": columns_completed,
    }


def _run_sanity_check(
    matched: int,
    extractable_columns: int,
    proposals_count: int,
    store: Store,
    config_payload: dict[str, object],
    matches: list[dict[str, object]],
    proposals: list[dict[str, object]],
) -> dict[str, object]:
    warning = matched > 0 and proposals_count == 0
    if not warning:
        return {"failed": False, "warning": False}
    schema_columns = _load_schema_columns(config_payload)
    missing_cell_count = _missing_cell_count(store, schema_columns, matches)
    extraction_events = _event_count(store, "extraction_invoked")
    validation_drop_count = sum(
        1
        for proposal in proposals
        if "evidence_validation_errors" in json.loads(proposal.get("flags_json") or "{}")
    )
    return {
        "failed": False,
        "warning": True,
        "why_no_values": {
            "columns_attempted": schema_columns,
            "schema_column_count": len(schema_columns),
            "extractable_columns": extractable_columns,
            "missing_cell_count": missing_cell_count,
            "retrieval_hit_rate": _retrieval_hit_rate(store),
            "groups_configured": (config_payload.get("extraction", {}) or {}).get("groups", []),
            "llm_calls": {
                "extraction_invoked_count": extraction_events,
            },
            "validation_failure_counts": {
                "evidence_validation_drop_count": validation_drop_count,
            },
        },
    }


def _retrieval_hit_rate(store: Store) -> dict[str, int]:
    rows = store.fetch_debug_extraction()
    totals = {"columns_with_hits": 0, "columns_with_no_hits": 0}
    for row in rows:
        payload = json.loads(row["payload_json"] or "{}") if row else {}
        hits = payload.get("retrieval_hits_per_column", {})
        for count in hits.values():
            if count:
                totals["columns_with_hits"] += 1
            else:
                totals["columns_with_no_hits"] += 1
    return totals


def _prompt_limit_summary(
    config_payload: dict[str, object],
    llm_capabilities: list[dict[str, object]] | None = None,
) -> dict[str, int | None | str | list[str]]:
    provider = config_payload.get("provider") or {}
    max_prompt_tokens = provider.get("max_prompt_tokens")
    max_prompt_chars = provider.get("max_prompt_chars")
    override_tokens = provider.get("ctx_window_tokens_override")
    tokens_cap = None
    if isinstance(max_prompt_tokens, int):
        tokens_cap = max_prompt_tokens
    chars_cap = max_prompt_chars if isinstance(max_prompt_chars, int) else None
    char_tokens = estimate_tokens("x" * chars_cap) if chars_cap else None
    probed_tokens = None
    if llm_capabilities:
        for payload in reversed(llm_capabilities):
            if payload.get("label") == "extract":
                candidate = payload.get("ctx_window_tokens")
                if isinstance(candidate, int) and candidate > 0:
                    probed_tokens = candidate
                    break
    effective_tokens = None
    reasons: list[str] = []
    source = None
    if isinstance(override_tokens, int) and override_tokens > 0:
        effective_tokens = override_tokens
        source = "override"
        reasons.append("ctx_window_override")
    elif tokens_cap:
        effective_tokens = tokens_cap
        source = "max_prompt_tokens"
        reasons.append("max_prompt_tokens")
    elif probed_tokens:
        effective_tokens = probed_tokens
        source = "model_probe"
        reasons.append("ctx_window_probe")
    if char_tokens:
        if effective_tokens:
            if char_tokens < effective_tokens:
                reasons.append("max_prompt_chars")
            effective_tokens = min(effective_tokens, char_tokens)
        else:
            effective_tokens = char_tokens
            source = "max_prompt_chars"
            reasons.append("max_prompt_chars")
    return {
        "max_prompt_tokens": tokens_cap,
        "max_prompt_chars": chars_cap,
        "ctx_window_tokens_override": override_tokens if isinstance(override_tokens, int) else None,
        "ctx_window_tokens_probe": probed_tokens,
        "effective_max_prompt_tokens": effective_tokens,
        "effective_source": source,
        "effective_reason": reasons,
    }


def _llm_call_summary(events: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        if event.get("event_type") != "llm_call":
            continue
        payload = json.loads(event.get("payload_json") or "{}")
        stage = str(payload.get("stage") or "unknown")
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def _event_count(store: Store, event_type: str) -> int:
    row = store.conn.execute(
        "SELECT COUNT(*) as count FROM events WHERE event_type = ?",
        (event_type,),
    ).fetchone()
    return int(row["count"]) if row else 0


def _load_schema_columns(config_payload: dict[str, object]) -> list[str]:
    try:
        table_path = Path(str(config_payload.get("table_path", "")))
        schema_source = table_path
        if config_payload.get("schema_mode") == "separate" and config_payload.get("schema_path"):
            schema_source = Path(str(config_payload["schema_path"]))
        specs = load_schema(schema_source, str(config_payload.get("schema_sheet_name", "schema")))
    except Exception:
        return []
    return [spec.column_name for spec in specs]


def _missing_cell_count(
    store: Store,
    schema_columns: list[str],
    matched_rows: list[dict[str, object]],
) -> int:
    if not schema_columns:
        return 0
    matched_row_ids = {
        str(row.get("row_id"))
        for row in matched_rows
        if row.get("status") == "matched" and row.get("row_id") is not None
    }
    if not matched_row_ids:
        return 0
    locked_rows = store.list_locks()
    locked_map: dict[str, set[str]] = {}
    for lock in locked_rows:
        if str(lock["row_id"]) in matched_row_ids:
            locked_map.setdefault(str(lock["row_id"]), set()).add(str(lock["column"]))
    missing = 0
    for row_id in matched_row_ids:
        locked = locked_map.get(row_id, set())
        for column in schema_columns:
            if column not in locked:
                missing += 1
    return missing


def write_run_bundle(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    bundle_path = run_dir / "run_bundle.zip"
    files = [
        run_dir / "run_config.json",
        run_dir / "run_report.json",
        run_dir / "proposals.sqlite",
        run_dir / "exports" / "mapping_report.html",
        run_dir / "exports" / "pdf_row_matches.csv",
        run_dir / "exports" / "audit_log.csv",
        run_dir / "exports" / "updated_table.xlsx",
    ]
    logs_dir = run_dir / "logs"
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in files:
            if path.exists():
                bundle.write(path, arcname=path.relative_to(run_dir))
        if logs_dir.exists():
            for log_path in logs_dir.glob("**/*"):
                if log_path.is_file():
                    bundle.write(log_path, arcname=log_path.relative_to(run_dir))
    return bundle_path
