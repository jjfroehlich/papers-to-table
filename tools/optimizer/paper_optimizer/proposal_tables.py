from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .reporting import load_csv_rows, model_nickname
from .utils import write_json


PROPOSAL_FIELDS = [
    "candidate_id",
    "candidate_label",
    "text_model_id",
    "benchmark_id",
    "suite_id",
    "replicate_index",
    "replicate_id",
    "run_id",
    "pdf_id",
    "row_id",
    "column_name",
    "cell_id",
    "proposal_id",
    "proposed_value",
    "state",
    "support",
    "rationale",
    "calculation",
    "primary_evidence_id",
    "evidence_ids",
    "warning_flags",
    "needs_more_evidence",
    "field_type",
    "allowed_values",
    "recall_rescue_used",
    "whole_document_used",
    "provider_mode",
    "parser_identity",
    "text_model_recorded_by_app",
    "vision_model_id",
    "extraction_lane",
    "failure_attribution",
    "fallback_reasons",
    "metadata_candidate_count",
    "metadata_candidate_values",
    "proposal_source_path",
    "main_app_run_path",
    "raw_proposal_json",
]

SCORED_CELL_FIELDS = [
    "candidate_id",
    "candidate_label",
    "text_model_id",
    "benchmark_id",
    "suite_id",
    "replicate_index",
    "replicate_id",
    "run_id",
    "row_id",
    "row_index",
    "column_name",
    "cell_id",
    "gold_value",
    "proposed_value",
    "normalized_gold",
    "normalized_proposed",
    "is_gold_present",
    "is_gold_empty",
    "was_scored",
    "is_correct",
    "join_status",
    "comparison_kind",
    "proposal_count",
    "selected_proposal_state",
    "scoring_policy",
    "field_type",
    "evidence_outcome",
    "evidence_present_but_unvalidated",
    "diagnostic_flags",
    "judge_verdict",
    "judge_score_mean",
    "judge_model_id",
    "judge_provider",
    "failure_attribution",
    "extraction_lane",
    "scored_cell_source_path",
    "eval_summary_path",
]

DIFFICULTY_FIELDS = [
    "benchmark_id",
    "column_name",
    "candidate_id",
    "candidate_label",
    "text_model_id",
    "gold_present_cell_count",
    "scored_cell_count",
    "correct_cell_count",
    "incorrect_cell_count",
    "unscored_cell_count",
    "missing_proposal_cell_count",
    "duplicate_proposal_cell_count",
    "unclear_proposal_cell_count",
    "judge_cell_count",
    "judge_unclear_cell_count",
    "correctness_gold_present_mean",
    "correctness_scored_mean",
    "mean_proposal_count",
    "replicate_count",
]

METADATA_SCORE_EXCLUDED_COLUMNS = {"Title", "Authors", "Publication Year", "DOI", "Journal"}


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def _json_compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                payload = json.loads(line)
                if isinstance(payload, dict):
                    rows.append(payload)
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _stringify(row.get(field)) for field in fieldnames})


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(_json_compact(row) + "\n")


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return stem.strip("._") or "unknown"


def _replicate_context(row: dict[str, str]) -> dict[str, Any]:
    text_model_id = row.get("text_model_id") or row.get("model_id") or ""
    candidate_id = row.get("candidate_id") or ""
    nickname = model_nickname(text_model_id) if text_model_id else ""
    return {
        "candidate_id": candidate_id,
        "candidate_label": f"{nickname} ({candidate_id})" if nickname and candidate_id else nickname or candidate_id,
        "text_model_id": text_model_id,
        "benchmark_id": row.get("benchmark_id") or "",
        "suite_id": row.get("suite_id") or "",
        "replicate_index": row.get("replicate_index") or "",
        "replicate_id": row.get("replicate_id") or "",
    }


def _proposal_row(context: dict[str, Any], proposal: dict[str, Any], source_path: Path, app_run_path: Path) -> dict[str, Any]:
    metadata = proposal.get("metadata_diagnostics") if isinstance(proposal.get("metadata_diagnostics"), dict) else {}
    return {
        **context,
        "run_id": proposal.get("run_id"),
        "pdf_id": proposal.get("pdf_id"),
        "row_id": proposal.get("row_id"),
        "column_name": proposal.get("column_name"),
        "cell_id": proposal.get("cell_id"),
        "proposal_id": proposal.get("proposal_id"),
        "proposed_value": proposal.get("proposed_value"),
        "state": proposal.get("state"),
        "support": proposal.get("support"),
        "rationale": proposal.get("rationale"),
        "calculation": proposal.get("calculation"),
        "primary_evidence_id": proposal.get("primary_evidence_id"),
        "evidence_ids": proposal.get("evidence_ids") or proposal.get("ordered_supporting_evidence_ids"),
        "warning_flags": proposal.get("warning_flags"),
        "needs_more_evidence": proposal.get("needs_more_evidence"),
        "field_type": proposal.get("field_type"),
        "allowed_values": proposal.get("allowed_values"),
        "recall_rescue_used": proposal.get("recall_rescue_used"),
        "whole_document_used": proposal.get("whole_document_used"),
        "provider_mode": proposal.get("provider_mode"),
        "parser_identity": proposal.get("parser_identity"),
        "text_model_recorded_by_app": proposal.get("text_model_id"),
        "vision_model_id": proposal.get("vision_model_id"),
        "extraction_lane": proposal.get("extraction_lane"),
        "failure_attribution": proposal.get("failure_attribution"),
        "fallback_reasons": proposal.get("fallback_reasons"),
        "metadata_candidate_count": metadata.get("candidate_count"),
        "metadata_candidate_values": metadata.get("candidate_values"),
        "proposal_source_path": str(source_path),
        "main_app_run_path": str(app_run_path),
        "raw_proposal_json": _json_compact(proposal),
    }


def _scored_cell_row(context: dict[str, Any], cell: dict[str, Any], source_path: Path, eval_summary_path: str) -> dict[str, Any]:
    return {
        **context,
        "run_id": cell.get("run_id"),
        "row_id": cell.get("row_id"),
        "row_index": cell.get("row_index"),
        "column_name": cell.get("column_name"),
        "cell_id": cell.get("cell_id"),
        "gold_value": cell.get("gold_value"),
        "proposed_value": cell.get("proposed_value"),
        "normalized_gold": cell.get("normalized_gold"),
        "normalized_proposed": cell.get("normalized_proposed"),
        "is_gold_present": cell.get("is_gold_present"),
        "is_gold_empty": cell.get("is_gold_empty"),
        "was_scored": cell.get("was_scored"),
        "is_correct": cell.get("is_correct"),
        "join_status": cell.get("join_status"),
        "comparison_kind": cell.get("comparison_kind"),
        "proposal_count": cell.get("proposal_count"),
        "selected_proposal_state": cell.get("selected_proposal_state"),
        "scoring_policy": cell.get("scoring_policy"),
        "field_type": cell.get("field_type"),
        "evidence_outcome": cell.get("evidence_outcome"),
        "evidence_present_but_unvalidated": cell.get("evidence_present_but_unvalidated"),
        "diagnostic_flags": cell.get("diagnostic_flags"),
        "judge_verdict": cell.get("judge_verdict"),
        "judge_score_mean": cell.get("judge_score_mean"),
        "judge_model_id": cell.get("judge_model_id"),
        "judge_provider": cell.get("judge_provider"),
        "failure_attribution": cell.get("failure_attribution"),
        "extraction_lane": cell.get("extraction_lane"),
        "scored_cell_source_path": str(source_path),
        "eval_summary_path": eval_summary_path,
    }


def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


def _float_value(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _diagnostic_flags(row: dict[str, Any]) -> set[str]:
    raw = row.get("diagnostic_flags")
    if isinstance(raw, list):
        return {str(item) for item in raw}
    if not raw:
        return set()
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {raw}
        if isinstance(parsed, list):
            return {str(item) for item in parsed}
    return set()


def _difficulty_rows(scored_rows: list[dict[str, Any]], *, by_candidate: bool) -> list[dict[str, Any]]:
    groups: dict[tuple[str, ...], dict[str, Any]] = {}
    for row in scored_rows:
        if str(row.get("column_name") or "") in METADATA_SCORE_EXCLUDED_COLUMNS:
            continue
        key_parts = [str(row.get("benchmark_id") or ""), str(row.get("column_name") or "")]
        if by_candidate:
            key_parts.extend(
                [
                    str(row.get("candidate_id") or ""),
                    str(row.get("candidate_label") or ""),
                    str(row.get("text_model_id") or ""),
                ]
            )
        key = tuple(key_parts)
        group = groups.setdefault(
            key,
            {
                "benchmark_id": row.get("benchmark_id") or "",
                "column_name": row.get("column_name") or "",
                "candidate_id": row.get("candidate_id") if by_candidate else "",
                "candidate_label": row.get("candidate_label") if by_candidate else "",
                "text_model_id": row.get("text_model_id") if by_candidate else "",
                "gold_present_cell_count": 0,
                "scored_cell_count": 0,
                "correct_cell_count": 0,
                "incorrect_cell_count": 0,
                "unscored_cell_count": 0,
                "missing_proposal_cell_count": 0,
                "duplicate_proposal_cell_count": 0,
                "unclear_proposal_cell_count": 0,
                "judge_cell_count": 0,
                "judge_unclear_cell_count": 0,
                "_proposal_counts": [],
                "_replicates": set(),
            },
        )
        if _bool_value(row.get("is_gold_present")) is True:
            group["gold_present_cell_count"] += 1
        if _bool_value(row.get("was_scored")) is True:
            group["scored_cell_count"] += 1
        else:
            group["unscored_cell_count"] += 1
        if _bool_value(row.get("is_correct")) is True:
            group["correct_cell_count"] += 1
        elif _bool_value(row.get("is_correct")) is False:
            group["incorrect_cell_count"] += 1
        flags = _diagnostic_flags(row)
        if row.get("join_status") == "missing_proposal" or "missing_proposal_for_gold_present" in flags:
            group["missing_proposal_cell_count"] += 1
        if row.get("join_status") == "duplicate_proposal" or "duplicate_proposals_for_gold_cell" in flags:
            group["duplicate_proposal_cell_count"] += 1
        if row.get("selected_proposal_state") == "unclear":
            group["unclear_proposal_cell_count"] += 1
        if row.get("judge_model_id") or row.get("judge_verdict"):
            group["judge_cell_count"] += 1
        if str(row.get("judge_verdict") or "").lower() == "unclear":
            group["judge_unclear_cell_count"] += 1
        proposal_count = _float_value(row.get("proposal_count"))
        if proposal_count is not None:
            group["_proposal_counts"].append(proposal_count)
        replicate_key = f"{row.get('candidate_id')}::{row.get('benchmark_id')}::{row.get('replicate_index')}"
        group["_replicates"].add(replicate_key)

    out: list[dict[str, Any]] = []
    for group in groups.values():
        gold_present = group["gold_present_cell_count"]
        scored = group["scored_cell_count"]
        correct = group["correct_cell_count"]
        proposal_counts = group.pop("_proposal_counts")
        replicates = group.pop("_replicates")
        group["correctness_gold_present_mean"] = (correct / gold_present) if gold_present else ""
        group["correctness_scored_mean"] = (correct / scored) if scored else ""
        group["mean_proposal_count"] = (sum(proposal_counts) / len(proposal_counts)) if proposal_counts else ""
        group["replicate_count"] = len(replicates)
        out.append(group)
    def sort_score(item: dict[str, Any]) -> float:
        value = item.get("correctness_gold_present_mean")
        if value in (None, ""):
            return 2.0
        return float(value)

    return sorted(
        out,
        key=lambda item: (
            str(item.get("benchmark_id") or ""),
            sort_score(item),
            -int(item.get("missing_proposal_cell_count") or 0),
            str(item.get("column_name") or ""),
            str(item.get("candidate_label") or ""),
        ),
    )


def write_proposal_tables(experiment_dir: Path) -> dict[str, Any]:
    """Export flattened proposal and scored-cell inspection tables for an optimizer experiment."""

    experiment_dir = Path(experiment_dir)
    replicate_rows = load_csv_rows(experiment_dir / "results" / "replicate_results.csv")
    output_dir = experiment_dir / "results" / "proposal_tables"
    proposal_rows: list[dict[str, Any]] = []
    scored_rows: list[dict[str, Any]] = []

    for replicate in replicate_rows:
        context = _replicate_context(replicate)
        app_run_path_raw = replicate.get("main_app_run_path") or ""
        app_run_path = Path(app_run_path_raw) if app_run_path_raw else Path()
        proposals_path = app_run_path / "proposals" / "proposals.jsonl" if app_run_path_raw else Path()
        for proposal in _jsonl_rows(proposals_path):
            proposal_rows.append(_proposal_row(context, proposal, proposals_path, app_run_path))

        eval_summary_path = replicate.get("eval_summary_path") or ""
        scored_path = Path(eval_summary_path).parent / "scored_cells.jsonl" if eval_summary_path else Path()
        for cell in _jsonl_rows(scored_path):
            scored_rows.append(_scored_cell_row(context, cell, scored_path, eval_summary_path))

    _write_csv(output_dir / "all_proposals.csv", proposal_rows, PROPOSAL_FIELDS)
    _write_jsonl(output_dir / "all_proposals.jsonl", proposal_rows)
    _write_csv(output_dir / "all_scored_cells.csv", scored_rows, SCORED_CELL_FIELDS)
    _write_jsonl(output_dir / "all_scored_cells.jsonl", scored_rows)

    difficulty_rows = _difficulty_rows(scored_rows, by_candidate=False)
    difficulty_by_candidate_rows = _difficulty_rows(scored_rows, by_candidate=True)
    _write_csv(output_dir / "column_difficulty.csv", difficulty_rows, DIFFICULTY_FIELDS)
    _write_csv(output_dir / "column_difficulty_by_candidate.csv", difficulty_by_candidate_rows, DIFFICULTY_FIELDS)

    by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scored_by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    difficulty_by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    difficulty_by_candidate_by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in proposal_rows:
        by_benchmark[str(row.get("benchmark_id") or "unknown")].append(row)
    for row in scored_rows:
        scored_by_benchmark[str(row.get("benchmark_id") or "unknown")].append(row)
    for row in difficulty_rows:
        difficulty_by_benchmark[str(row.get("benchmark_id") or "unknown")].append(row)
    for row in difficulty_by_candidate_rows:
        difficulty_by_candidate_by_benchmark[str(row.get("benchmark_id") or "unknown")].append(row)

    for benchmark_id, rows in by_benchmark.items():
        _write_csv(output_dir / "by_benchmark" / f"{_safe_stem(benchmark_id)}_proposals.csv", rows, PROPOSAL_FIELDS)
    for benchmark_id, rows in scored_by_benchmark.items():
        _write_csv(output_dir / "by_benchmark" / f"{_safe_stem(benchmark_id)}_scored_cells.csv", rows, SCORED_CELL_FIELDS)
    for benchmark_id, rows in difficulty_by_benchmark.items():
        _write_csv(output_dir / "by_benchmark" / f"{_safe_stem(benchmark_id)}_column_difficulty.csv", rows, DIFFICULTY_FIELDS)
    for benchmark_id, rows in difficulty_by_candidate_by_benchmark.items():
        _write_csv(
            output_dir / "by_benchmark" / f"{_safe_stem(benchmark_id)}_column_difficulty_by_candidate.csv",
            rows,
            DIFFICULTY_FIELDS,
        )

    by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scored_by_candidate: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in proposal_rows:
        by_candidate[str(row.get("candidate_id") or "unknown")].append(row)
    for row in scored_rows:
        scored_by_candidate[str(row.get("candidate_id") or "unknown")].append(row)
    for candidate_id, rows in by_candidate.items():
        _write_csv(output_dir / "by_candidate" / f"{_safe_stem(candidate_id)}_proposals.csv", rows, PROPOSAL_FIELDS)
    for candidate_id, rows in scored_by_candidate.items():
        _write_csv(output_dir / "by_candidate" / f"{_safe_stem(candidate_id)}_scored_cells.csv", rows, SCORED_CELL_FIELDS)

    manifest = {
        "proposal_row_count": len(proposal_rows),
        "scored_cell_row_count": len(scored_rows),
        "column_difficulty_row_count": len(difficulty_rows),
        "replicate_row_count": len(replicate_rows),
        "output_dir": str(output_dir),
        "primary_files": [
            "all_proposals.csv",
            "all_scored_cells.csv",
            "column_difficulty.csv",
            "column_difficulty_by_candidate.csv",
        ],
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest
