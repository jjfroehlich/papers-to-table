from __future__ import annotations

import json
import math
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from paper_table_agent.io.xlsx import load_table
from paper_table_agent.text.normalization import normalize_text, normalize_str_for_prompt


def evaluate_run(
    *,
    run_dir: Path | None,
    db_path: Path,
    table_path: Path,
    schema_sheet_name: str | None = None,
    pdf_folder: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    if output_dir is None:
        output_dir = (run_dir / "exports") if run_dir else db_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    run_config = _load_run_config(run_dir) if run_dir else {}
    proposals = _load_proposals(db_path, proposal_kind="audit")
    table = load_table(table_path, sheet_name=schema_sheet_name)
    page_text_by_pdf = _load_page_text(run_dir, pdf_folder)
    eval_config = _eval_settings(run_config)
    if not proposals:
        payload = _empty_eval_payload(
            run_id=run_dir.name if run_dir else None,
            eval_config=eval_config,
            reason="no_audit_proposals",
            note=(
                "No audit proposals found. Set audit.use_filled_cells_as_gold=true and rerun."
            ),
        )
    else:
        payload = _evaluate_proposals(
            proposals,
            table.dataframe,
            eval_config,
            page_text_by_pdf,
            run_id=run_dir.name if run_dir else None,
        )
    output_path = output_dir / "proposal_eval.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path = output_dir / "proposal_eval.md"
    md_path.write_text(_render_eval_md(payload), encoding="utf-8")
    if run_dir:
        update_run_report(run_dir, payload)
    return payload


def _empty_eval_payload(
    *,
    run_id: str | None,
    eval_config: dict[str, Any],
    reason: str,
    note: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {
            "total_cells": 0,
            "matched": 0,
            "match_rate": 0.0,
            "columns_evaluated": 0,
            "proposals_with_value": 0,
            "proposals_with_evidence": 0,
            "evidence_coverage_rate": 0.0,
            "anchorable_quote_rate": 0.0,
            "highlight_ok_rate": 0.0,
            "highlight_failed_rate": 0.0,
            "found_unanchored_downgraded": 0,
            "status": reason,
            "note": note,
        },
        "per_column": {},
        "cells": [],
        "config": {
            "model_extract": eval_config.get("model_extract"),
            "ctx_window": eval_config.get("ctx_window"),
        },
    }


def update_run_report(run_dir: Path, eval_payload: dict[str, Any]) -> None:
    run_report_path = run_dir / "run_report.json"
    if not run_report_path.exists():
        return
    report = json.loads(run_report_path.read_text(encoding="utf-8"))
    summary = report.setdefault("summary", {})
    summary["evaluation"] = eval_payload.get("summary", {})
    summary.setdefault("audit", {})
    summary["audit"].update(
        {
            "audited_cells_count": eval_payload.get("summary", {}).get("total_cells", 0),
            "audited_columns_count": eval_payload.get("summary", {}).get("columns_evaluated", 0),
            "audited_match_rate": eval_payload.get("summary", {}).get("match_rate", 0),
        }
    )
    run_report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _load_run_config(run_dir: Path | None) -> dict[str, Any]:
    if not run_dir:
        return {}
    config_path = run_dir / "run_config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _eval_settings(run_config: dict[str, Any]) -> dict[str, Any]:
    audit = run_config.get("audit", {}) if run_config else {}
    return {
        "numeric_tolerance_by_column": audit.get("numeric_tolerance_by_column", {}),
        "categorical_aliases_by_column": audit.get("categorical_aliases_by_column", {}),
        "text_similarity_threshold": audit.get("text_similarity_threshold", 0.6),
        "model_extract": (run_config.get("provider", {}) or {}).get("model_extract"),
        "ctx_window": (run_config.get("retrieval", {}) or {}).get("max_context_tokens"),
    }


def _load_proposals(db_path: Path, proposal_kind: str | None = None) -> list[dict[str, Any]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = list(
        conn.execute(
            "SELECT proposal_id, pdf_id, row_id, column, proposed_value, status, evidence_json, flags_json FROM proposals"
        )
    )
    conn.close()
    proposals: list[dict[str, Any]] = []
    for row in rows:
        flags = json.loads(row["flags_json"] or "{}")
        if proposal_kind and flags.get("proposal_kind") != proposal_kind:
            continue
        if flags.get("verify_only"):
            continue
        proposals.append(
            {
                "proposal_id": row["proposal_id"],
                "pdf_id": row["pdf_id"],
                "row_id": row["row_id"],
                "column": row["column"],
                "proposed_value": row["proposed_value"],
                "status": row["status"],
                "evidence": json.loads(row["evidence_json"] or "[]"),
                "flags": flags,
            }
        )
    return proposals


def _load_page_text(run_dir: Path | None, pdf_folder: Path | None) -> dict[str, list[str]]:
    page_text_by_pdf: dict[str, list[str]] = {}
    if run_dir:
        parsed_dir = run_dir / "artifacts" / "parsed"
        if parsed_dir.exists():
            for path in parsed_dir.glob("*_pymupdf.json"):
                payload = json.loads(path.read_text(encoding="utf-8"))
                pdf_id = payload.get("pdf_id")
                if pdf_id:
                    page_text_by_pdf[pdf_id] = payload.get("page_text") or []
    if page_text_by_pdf or not pdf_folder:
        return page_text_by_pdf
    from paper_table_agent.pdf.parser import compute_sha1, parse_pdf

    for pdf_path in pdf_folder.glob("*.pdf"):
        parsed = parse_pdf(pdf_path)
        pdf_id = compute_sha1(pdf_path)
        page_text_by_pdf[pdf_id] = parsed.page_text
    return page_text_by_pdf


def _evaluate_proposals(
    proposals: list[dict[str, Any]],
    table_df: Any,
    eval_config: dict[str, Any],
    page_text_by_pdf: dict[str, list[str]],
    *,
    run_id: str | None,
) -> dict[str, Any]:
    per_column: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    total = 0
    matched = 0
    total_evidence_items = 0
    anchorable_items = 0
    highlighted_items = 0
    highlight_failed = 0
    proposals_with_value = 0
    proposals_with_evidence = 0
    found_unanchored = 0

    for proposal in proposals:
        column = proposal["column"]
        row_id = proposal["row_id"]
        gold_value = _get_table_value(table_df, row_id, column)
        gold_norm = normalize_str_for_prompt(gold_value)
        if not gold_norm:
            continue
        proposed_value = proposal.get("proposed_value")
        proposed_norm = normalize_str_for_prompt(proposed_value)
        if proposed_norm:
            proposals_with_value += 1
        evidence = proposal.get("evidence") or []
        if evidence:
            proposals_with_evidence += 1
        evidence_stats = _evidence_stats(evidence, page_text_by_pdf.get(proposal["pdf_id"]))
        total_evidence_items += evidence_stats["total"]
        anchorable_items += evidence_stats["anchorable"]
        highlighted_items += evidence_stats["highlighted"]
        highlight_failed += evidence_stats["failed"]
        if proposal.get("flags", {}).get("found_unanchored_downgraded"):
            found_unanchored += 1

        match_type, match, score = _compare_values(
            gold_norm,
            proposed_norm,
            column,
            eval_config,
        )
        total += 1
        if match:
            matched += 1

        column_metrics = per_column.setdefault(
            column,
            {
                "total": 0,
                "matched": 0,
                "scores": [],
                "evidence_items": 0,
                "anchorable_items": 0,
                "highlighted_items": 0,
                "failed_items": 0,
            },
        )
        column_metrics["total"] += 1
        column_metrics["matched"] += int(match)
        column_metrics["scores"].append(score)
        column_metrics["evidence_items"] += evidence_stats["total"]
        column_metrics["anchorable_items"] += evidence_stats["anchorable"]
        column_metrics["highlighted_items"] += evidence_stats["highlighted"]
        column_metrics["failed_items"] += evidence_stats["failed"]

        if len(records) < 200:
            records.append(
                {
                    "proposal_id": proposal["proposal_id"],
                    "row_id": row_id,
                    "column": column,
                    "gold_value": gold_value,
                    "proposed_value": proposed_value,
                    "match": match,
                    "match_type": match_type,
                    "score": score,
                    "evidence_items": evidence_stats["total"],
                    "anchorable_items": evidence_stats["anchorable"],
                    "highlighted_items": evidence_stats["highlighted"],
                    "failed_items": evidence_stats["failed"],
                }
            )

    per_column_payload = {}
    for column, stats in per_column.items():
        total_col = stats["total"]
        per_column_payload[column] = {
            "total": total_col,
            "matched": stats["matched"],
            "match_rate": _safe_div(stats["matched"], total_col),
            "avg_similarity": _safe_avg(stats["scores"]),
            "anchorable_quote_rate": _safe_div(stats["anchorable_items"], stats["evidence_items"]),
            "highlight_ok_rate": _safe_div(stats["highlighted_items"], stats["evidence_items"]),
            "highlight_failed_rate": _safe_div(stats["failed_items"], stats["evidence_items"]),
        }

    summary = {
        "total_cells": total,
        "matched": matched,
        "match_rate": _safe_div(matched, total),
        "columns_evaluated": len(per_column_payload),
        "proposals_with_value": proposals_with_value,
        "proposals_with_evidence": proposals_with_evidence,
        "evidence_coverage_rate": _safe_div(proposals_with_evidence, proposals_with_value),
        "anchorable_quote_rate": _safe_div(anchorable_items, total_evidence_items),
        "highlight_ok_rate": _safe_div(highlighted_items, total_evidence_items),
        "highlight_failed_rate": _safe_div(highlight_failed, total_evidence_items),
        "found_unanchored_downgraded": found_unanchored,
    }
    if total == 0:
        summary["status"] = "no_audit_cells"
        summary["note"] = "No filled cells were available for audit evaluation."
    payload = {
        "run_id": run_id,
        "generated_at": datetime.utcnow().isoformat(),
        "summary": summary,
        "per_column": per_column_payload,
        "cells": records,
        "config": {
            "model_extract": eval_config.get("model_extract"),
            "ctx_window": eval_config.get("ctx_window"),
        },
    }
    return payload


def _get_table_value(table_df: Any, row_id: str, column: str) -> str | None:
    try:
        row_index = int(row_id)
    except (TypeError, ValueError):
        return None
    if column not in table_df.columns:
        return None
    value = table_df.at[row_index, column]
    if value is None:
        return None
    return str(value)


def _compare_values(
    gold: str,
    proposed: str,
    column: str,
    eval_config: dict[str, Any],
) -> tuple[str, bool, float]:
    if not proposed:
        return "missing", False, 0.0
    gold_num = _parse_numeric(gold)
    proposed_num = _parse_numeric(proposed)
    if gold_num is not None and proposed_num is not None:
        tol = float(eval_config.get("numeric_tolerance_by_column", {}).get(column, 0.0))
        match = math.isclose(gold_num, proposed_num, abs_tol=tol)
        score = 1.0 - min(abs(gold_num - proposed_num), 1.0)
        return "numeric", match, max(score, 0.0)
    alias_map = eval_config.get("categorical_aliases_by_column", {}).get(column, {})
    if alias_map:
        match = _categorical_match(gold, proposed, alias_map)
        return "categorical", match, 1.0 if match else 0.0
    if _normalize_comp(gold) == _normalize_comp(proposed):
        return "categorical", True, 1.0
    similarity = _token_f1(gold, proposed)
    threshold = float(eval_config.get("text_similarity_threshold", 0.6))
    return "text", similarity >= threshold, similarity


def _parse_numeric(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", value)
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


def _categorical_match(gold: str, proposed: str, alias_map: dict[str, list[str]]) -> bool:
    normalized_gold = _normalize_comp(gold)
    normalized_proposed = _normalize_comp(proposed)
    for canonical, aliases in alias_map.items():
        normalized_canonical = _normalize_comp(canonical)
        normalized_aliases = {_normalize_comp(alias) for alias in aliases}
        if normalized_gold in {normalized_canonical} | normalized_aliases:
            return normalized_proposed in {normalized_canonical} | normalized_aliases
    return normalized_gold == normalized_proposed


def _normalize_comp(value: str) -> str:
    return re.sub(r"[^0-9a-z]+", "", normalize_text(value).casefold())


def _token_f1(a: str, b: str) -> float:
    tokens_a = set(re.findall(r"[a-z0-9]+", normalize_text(a).casefold()))
    tokens_b = set(re.findall(r"[a-z0-9]+", normalize_text(b).casefold()))
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a & tokens_b)
    precision = overlap / len(tokens_a)
    recall = overlap / len(tokens_b)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _evidence_stats(evidence: list[dict[str, Any]], page_text: list[str] | None) -> dict[str, int]:
    total = 0
    anchorable = 0
    highlighted = 0
    failed = 0
    for item in evidence:
        total += 1
        quote = str(item.get("quote") or item.get("quote_text") or item.get("quote_raw") or "").strip()
        page = item.get("page")
        if quote and isinstance(page, int) and page_text and 0 < page <= len(page_text):
            if quote in page_text[page - 1]:
                anchorable += 1
        status = item.get("highlight_status")
        if status == "highlighted":
            highlighted += 1
        if status == "failed":
            failed += 1
    return {"total": total, "anchorable": anchorable, "highlighted": highlighted, "failed": failed}


def _safe_div(numerator: float, denominator: float) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


def _safe_avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _render_eval_md(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    status = summary.get("status")
    note = summary.get("note")
    lines = [
        "# Proposal Evaluation",
        "",
        f"Generated at: {payload.get('generated_at')}",
        "",
        "## Summary",
        f"- Status: {status}" if status else "- Status: ok",
        f"- Note: {note}" if note else "- Note: none",
        f"- Total audited cells: {summary.get('total_cells', 0)}",
        f"- Match rate: {summary.get('match_rate', 0):.2%}",
        f"- Evidence coverage rate: {summary.get('evidence_coverage_rate', 0):.2%}",
        f"- Anchorable quote rate: {summary.get('anchorable_quote_rate', 0):.2%}",
        f"- Highlight OK rate: {summary.get('highlight_ok_rate', 0):.2%}",
        f"- Found→inferred downgrades: {summary.get('found_unanchored_downgraded', 0)}",
        "",
        "## Per-column",
    ]
    for column, stats in payload.get("per_column", {}).items():
        lines.append(f"- **{column}**: match_rate={stats.get('match_rate', 0):.2%}")
    return "\n".join(lines) + "\n"
