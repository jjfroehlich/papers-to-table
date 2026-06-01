from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVIEW_INPUT_SCHEMA_VERSION = "papers_to_table.review_input.v1"
REVIEW_PACKAGE_SCHEMA_VERSION = "papers_to_table.review_package.v1"
NORMALIZED_PROPOSAL_SCHEMA_VERSION = "papers_to_table.agent_normalized_proposal.v1"
MAIN_EVIDENCE_SCHEMA_VERSION = "main_evidence"
MAIN_COMPAT_SOURCE_TYPES = {
    "direct_quote",
    "inferred_reasoning",
    "calculation",
    "approximate_highlight",
    "quote_plus_page",
    "caption_grounded_figure_evidence",
    "visual_interpretation_figure_evidence",
}

DECISIONS = {"accepted", "accepted_with_edit", "rejected", "confirmed_no_data"}
ACCEPTED_DECISIONS = {"accepted", "accepted_with_edit"}

PROPOSAL_STATUSES = {
    "value_proposed",
    "no_data",
    "unresolved",
    "not_applicable",
    "not_attempted",
    "error",
}
EVIDENCE_STATUSES = {
    "direct_strong",
    "direct_weak",
    "inferred_strong",
    "inferred_weak",
    "no_evidence",
    "not_applicable",
}
REVIEW_BUCKETS = {"review", "attention", "diagnostic"}

TEXT_EVIDENCE_KEYS = ("quote_text", "table_text", "evidence_text", "caption_text")
DIRECT_TEXT_SOURCE_TYPES = {
    "direct_quote",
    "quote_plus_page",
    "caption_grounded_figure_evidence",
    "visual_interpretation_figure_evidence",
}
KIT_TEXT_SOURCE_TYPE_MAP = {
    "quote_text": "direct_quote",
    "table_text": "direct_quote",
    "caption_text": "direct_quote",
    "evidence_text": "direct_quote",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_id(prefix: str, *parts: object) -> str:
    raw = "::".join(_stable_part(part) for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def _stable_part(part: object) -> str:
    if isinstance(part, (dict, list)):
        return json.dumps(part, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(part or "")


def is_non_empty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in {path} line {line_number}: {exc.msg}") from exc
        if isinstance(value, dict):
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [{key: (value or "") for key, value in row.items()} for row in reader], list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def safe_filename(value: str, fallback: str = "asset") -> str:
    stem = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("._")
    return stem or fallback


def load_review_input(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "review_input.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing required authoring file: {path}")
    payload = read_json(path)
    if not isinstance(payload, dict):
        raise ValueError("review_input.json must contain a JSON object.")
    return payload


def text_evidence_value(evidence: dict[str, Any]) -> str:
    for key in TEXT_EVIDENCE_KEYS:
        value = evidence.get(key)
        if is_non_empty(value):
            return str(value).strip()
    return ""


def authored_evidence_kind(evidence: dict[str, Any]) -> str | None:
    source_type = str(evidence.get("source_type") or "").strip()
    if source_type:
        return source_type
    for key in TEXT_EVIDENCE_KEYS:
        if is_non_empty(evidence.get(key)):
            return key
    if evidence.get("exact_highlight_regions"):
        return "exact_highlight_regions"
    if evidence.get("approximate_highlight_regions"):
        return "approximate_highlight_regions"
    if evidence.get("bbox"):
        return "bbox"
    if is_non_empty(evidence.get("reasoning")):
        return "reasoning"
    return None


def infer_source_type(evidence: dict[str, Any]) -> str:
    source_type = str(evidence.get("source_type") or "").strip()
    if source_type:
        return KIT_TEXT_SOURCE_TYPE_MAP.get(source_type, source_type)
    if is_non_empty(evidence.get("figure_ref")) and is_non_empty(evidence.get("caption_text")):
        return "caption_grounded_figure_evidence"
    if any(is_non_empty(evidence.get(key)) for key in TEXT_EVIDENCE_KEYS):
        return "direct_quote"
    if evidence.get("exact_highlight_regions") or evidence.get("approximate_highlight_regions") or evidence.get("bbox"):
        return "approximate_highlight"
    if is_non_empty(evidence.get("reasoning")) or is_non_empty(evidence.get("source_location")):
        return "inferred_reasoning"
    return "inferred_reasoning"


def normalized_regions(value: Any, *, default_page: int | None = None) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        value = [value]
    if isinstance(value, list) and len(value) == 4 and all(isinstance(item, (int, float)) for item in value):
        return [{"x0": value[0], "y0": value[1], "x1": value[2], "y1": value[3], "page": default_page}]
    if not isinstance(value, list):
        return []
    regions: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        region = {
            "x0": item.get("x0"),
            "y0": item.get("y0"),
            "x1": item.get("x1"),
            "y1": item.get("y1"),
            "page": item.get("page", default_page),
        }
        regions.append(region)
    return regions


def is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def evidence_tier(evidence: dict[str, Any], *, inherited_pdf_id: str | None = None) -> dict[str, Any]:
    pdf_id = str(evidence.get("pdf_id") or inherited_pdf_id or "").strip()
    page_number = evidence.get("page_number")
    page_ok = isinstance(page_number, int) and page_number > 0
    if isinstance(page_number, str) and page_number.strip().isdigit():
        page_ok = int(page_number.strip()) > 0
    source_type = infer_source_type(evidence)
    text_value = text_evidence_value(evidence)
    exact_regions = normalized_regions(evidence.get("exact_highlight_regions"), default_page=_page_int(page_number))
    approximate_regions = normalized_regions(
        evidence.get("approximate_highlight_regions") or evidence.get("bbox"),
        default_page=_page_int(page_number),
    )
    has_regions = bool(exact_regions or approximate_regions)
    has_figure_caption = is_non_empty(evidence.get("figure_ref")) and is_non_empty(evidence.get("caption_text"))

    if pdf_id and page_ok and (text_value or has_figure_caption):
        return {
            "tier": "A",
            "evidence_status": "direct_strong",
            "review_bucket": "review",
            "reason_codes": [],
            "source_type": source_type if source_type in DIRECT_TEXT_SOURCE_TYPES else "direct_quote",
            "label": "Text evidence",
        }
    if pdf_id and page_ok and has_regions:
        status = "direct_weak" if approximate_regions and not exact_regions else "direct_strong"
        return {
            "tier": "B",
            "evidence_status": status,
            "review_bucket": "attention" if status == "direct_weak" else "review",
            "reason_codes": ["approximate_anchor"] if status == "direct_weak" else [],
            "source_type": source_type,
            "label": "Region evidence",
        }
    if pdf_id and page_ok and (is_non_empty(evidence.get("source_location")) or is_non_empty(evidence.get("reasoning"))):
        return {
            "tier": "C",
            "evidence_status": "inferred_weak",
            "review_bucket": "attention",
            "reason_codes": ["page_only_evidence"],
            "source_type": "inferred_reasoning",
            "label": "Weak page evidence",
        }
    return {
        "tier": "D",
        "evidence_status": "no_evidence",
        "review_bucket": "attention",
        "reason_codes": ["missing_structured_evidence"],
        "source_type": source_type,
        "label": "No structured evidence",
    }


def _page_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def merged_evidence_semantics(tiers: list[dict[str, Any]], proposal_status: str) -> dict[str, Any]:
    if proposal_status in {"not_applicable", "not_attempted"}:
        return {"evidence_status": "not_applicable", "review_bucket": "diagnostic", "reason_codes": []}
    if proposal_status in {"unresolved", "error"}:
        return {"evidence_status": "no_evidence", "review_bucket": "attention", "reason_codes": ["unresolved"]}
    if not tiers:
        return {"evidence_status": "no_evidence", "review_bucket": "attention", "reason_codes": ["missing_structured_evidence"]}

    reason_codes: list[str] = []
    for tier in tiers:
        for code in tier.get("reason_codes", []) or []:
            if code not in reason_codes:
                reason_codes.append(code)

    statuses = [str(tier.get("evidence_status") or "no_evidence") for tier in tiers]
    if "direct_strong" in statuses:
        evidence_status = "direct_strong"
    elif "direct_weak" in statuses:
        evidence_status = "direct_weak"
    elif "inferred_strong" in statuses:
        evidence_status = "inferred_strong"
    elif "inferred_weak" in statuses:
        evidence_status = "inferred_weak"
    else:
        evidence_status = "no_evidence"

    review_bucket = "review" if evidence_status in {"direct_strong", "inferred_strong"} else "attention"
    if proposal_status == "no_data" and evidence_status == "no_evidence":
        review_bucket = "attention"
    return {"evidence_status": evidence_status, "review_bucket": review_bucket, "reason_codes": reason_codes}


def latest_decisions(decisions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for decision in decisions:
        proposal_id = str(decision.get("proposal_id") or "")
        if proposal_id:
            latest[proposal_id] = decision
    return latest
