from __future__ import annotations

import pathlib
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Optional

from pydantic import BaseModel, Field

from .artifacts import write_json

EXTRACTION_KINDS = {"metadata", "methods", "results", "claims", "visual"}
GROUPS = {"metadata", "methods", "results", "claims", "visual"}
VISUAL_POLICIES = {"never", "fallback_only", "prefer"}
BLANK_POLICIES = {"fill_blank", "preserve_filled"}
RETRIEVAL_PROFILES = {"metadata", "methods", "results", "claims", "visual", "general"}


class ColumnPlanEntry(BaseModel):
    column_name: str
    extraction_kind: str = "results"
    group: str = "results"
    visual_policy: str = "fallback_only"
    allowed_values: Optional[list[str]] = None
    blank_policy: str = "fill_blank"
    retrieval_profile: str = "general"
    retrieval_hints: list[str] = Field(default_factory=list)
    source: str = "deterministic"
    validation_warnings: list[str] = Field(default_factory=list)


class ColumnPlan(BaseModel):
    schema_version: str = "column_plan.v1"
    planner_mode: str = "deterministic"
    entries: list[ColumnPlanEntry]
    generated_at: str
    planner_ms: float = 0.0
    planner_call_count: int = 0
    validation_warning_count: int = 0


COLUMN_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "entries": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "column_name": {"type": "string"},
                    "extraction_kind": {
                        "type": "string",
                        "enum": ["metadata", "methods", "results", "claims", "visual"],
                    },
                    "group": {
                        "type": "string",
                        "enum": ["metadata", "methods", "results", "claims", "visual"],
                    },
                    "visual_policy": {
                        "type": "string",
                        "enum": ["never", "fallback_only", "prefer"],
                    },
                    "blank_policy": {
                        "type": "string",
                        "enum": ["fill_blank", "preserve_filled"],
                    },
                    "retrieval_profile": {
                        "type": "string",
                        "enum": ["metadata", "methods", "results", "claims", "visual", "general"],
                    },
                    "retrieval_hints": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "column_name",
                    "extraction_kind",
                    "group",
                    "visual_policy",
                    "blank_policy",
                    "retrieval_profile",
                    "retrieval_hints",
                ],
            },
        }
    },
    "required": ["entries"],
}


def _terms(*values: object) -> str:
    return " ".join(str(value or "") for value in values).lower()


def _unique(values: list[str], *, limit: int = 12) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(value.strip())
        if len(out) >= limit:
            break
    return out


def _classify_column(column: dict[str, Any]) -> tuple[str, str, str, str, list[str]]:
    name = str(column.get("column_name") or "")
    description = str(column.get("description") or "")
    field_type = str(column.get("field_type") or "")
    text = _terms(name, description, field_type)
    hints: list[str] = []

    if name in {"Title", "Authors", "Publication Year", "DOI"} or re.search(
        r"\b(title|author|doi|publication year|journal|metadata)\b", text
    ):
        hints.extend(["title", "authors", "doi", "published", "journal"])
        return "metadata", "metadata", "never", "metadata", _unique(hints)

    if re.search(r"\b(figure|fig\.|image|graph|plot|panel|microscopy|map|spatial|visual)\b", text):
        hints.extend(["figure", "caption", "graph", "panel"])
        return "visual", "visual", "prefer", "visual", _unique(hints)

    if re.search(r"\b(method|protocol|library|construct|vector|plasmid|assay|cell line|species|system|design|delivery)\b", text):
        hints.extend(["methods", "protocol", "construct", "assay", "library"])
        return "methods", "methods", "fallback_only", "methods", _unique(hints)

    if re.search(r"\b(result|outcome|accuracy|efficiency|rate|count|number|n\s*=|percent|fold|effect|performance)\b", text):
        hints.extend(["results", "measured", "reported", "count", "percent"])
        return "results", "results", "fallback_only", "results", _unique(hints)

    if re.search(r"\b(conclusion|claim|supports|suggests|limitation|novel|finding)\b", text):
        hints.extend(["conclusion", "finding", "suggests"])
        return "claims", "claims", "fallback_only", "claims", _unique(hints)

    return "results", "results", "fallback_only", "general", []


def build_column_plan(
    schema: list[dict[str, Any]],
    *,
    planner_mode: str = "deterministic",
) -> ColumnPlan:
    entries: list[ColumnPlanEntry] = []
    for column in schema:
        column_name = str(column.get("column_name") or "").strip()
        if not column_name:
            continue
        extraction_kind, group, visual_policy, retrieval_profile, hints = _classify_column(column)
        allowed_values = column.get("allowed_values")
        entries.append(
            ColumnPlanEntry(
                column_name=column_name,
                extraction_kind=extraction_kind if extraction_kind in EXTRACTION_KINDS else "results",
                group=group if group in GROUPS else "results",
                visual_policy=visual_policy if visual_policy in VISUAL_POLICIES else "fallback_only",
                allowed_values=list(allowed_values) if isinstance(allowed_values, list) else None,
                blank_policy="fill_blank",
                retrieval_profile=(
                    retrieval_profile if retrieval_profile in RETRIEVAL_PROFILES else "general"
                ),
                retrieval_hints=hints,
            )
        )
    return ColumnPlan(
        planner_mode=planner_mode,
        entries=entries,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _schema_prompt(schema: list[dict[str, Any]]) -> list[dict[str, str]]:
    compact_schema = [
        {
            "column_name": str(column.get("column_name") or ""),
            "description": str(column.get("description") or ""),
            "field_type": str(column.get("field_type") or ""),
            "allowed_values": column.get("allowed_values") if isinstance(column.get("allowed_values"), list) else None,
        }
        for column in schema
        if str(column.get("column_name") or "").strip()
    ]
    return [
        {
            "role": "system",
            "content": (
                "Classify table schema columns for scientific-paper extraction. "
                "Return one entry per input column. Do not infer paper-specific values. "
                "Use metadata only for bibliographic fields; use visual only when figures, panels, plots, "
                "or image interpretation are likely required."
            ),
        },
        {
            "role": "user",
            "content": (
                "Plan extraction groups and retrieval behavior for this schema JSON:\n"
                f"{compact_schema}\n\n"
                "Fields: extraction_kind/group choose metadata, methods, results, claims, or visual. "
                "visual_policy is never, fallback_only, or prefer. retrieval_hints should be short search terms."
            ),
        },
    ]


def _validate_llm_plan(
    schema: list[dict[str, Any]],
    raw_entries: Any,
    deterministic: ColumnPlan,
) -> list[ColumnPlanEntry]:
    deterministic_by_name = {entry.column_name: entry for entry in deterministic.entries}
    raw_by_name: dict[str, dict[str, Any]] = {}
    if isinstance(raw_entries, list):
        for item in raw_entries:
            if isinstance(item, dict):
                name = str(item.get("column_name") or "").strip()
                if name:
                    raw_by_name[name] = item

    entries: list[ColumnPlanEntry] = []
    for column in schema:
        name = str(column.get("column_name") or "").strip()
        if not name:
            continue
        fallback = deterministic_by_name.get(name) or ColumnPlanEntry(column_name=name)
        raw = raw_by_name.get(name, {})
        warnings: list[str] = []

        def choose(key: str, allowed: set[str], default: str) -> str:
            value = str(raw.get(key) or "").strip()
            if value in allowed:
                return value
            if raw:
                warnings.append(f"invalid_{key}")
            return default

        hints = raw.get("retrieval_hints")
        if isinstance(hints, list):
            retrieval_hints = _unique([str(hint) for hint in hints], limit=12)
        else:
            retrieval_hints = list(fallback.retrieval_hints)
            if raw:
                warnings.append("invalid_retrieval_hints")

        allowed_values = column.get("allowed_values")
        extraction_kind = choose("extraction_kind", EXTRACTION_KINDS, fallback.extraction_kind)
        group = choose("group", GROUPS, fallback.group)
        visual_policy = choose("visual_policy", VISUAL_POLICIES, fallback.visual_policy)
        retrieval_profile = choose("retrieval_profile", RETRIEVAL_PROFILES, fallback.retrieval_profile)
        text = _terms(name, column.get("description"), column.get("field_type"))
        name_text = _terms(name)

        if extraction_kind != "metadata" and retrieval_profile == "metadata":
            retrieval_profile = fallback.retrieval_profile if fallback.retrieval_profile != "metadata" else extraction_kind
            warnings.append("metadata_retrieval_for_content_field_corrected")
        if re.search(r"\b(figure|fig\.|panel|bar-chart|bar chart|architecture source)\b", name_text):
            extraction_kind = "visual"
            group = "visual"
            visual_policy = "prefer"
            retrieval_profile = "visual"
            if "figure" not in retrieval_hints:
                retrieval_hints = _unique([*retrieval_hints, "figure", "caption", "panel"], limit=12)
            warnings.append("figure_field_forced_visual")
        elif extraction_kind == "visual":
            group = "visual"
            visual_policy = "prefer"
            retrieval_profile = "visual"
        elif extraction_kind == "methods" and retrieval_profile not in {"methods", "visual"}:
            retrieval_profile = "methods"
            warnings.append("methods_retrieval_profile_corrected")
        elif extraction_kind == "results" and retrieval_profile not in {"results", "visual"}:
            retrieval_profile = "results"
            warnings.append("results_retrieval_profile_corrected")

        entries.append(
            ColumnPlanEntry(
                column_name=name,
                extraction_kind=extraction_kind,
                group=group,
                visual_policy=visual_policy,
                allowed_values=list(allowed_values) if isinstance(allowed_values, list) else None,
                blank_policy=choose("blank_policy", BLANK_POLICIES, fallback.blank_policy),
                retrieval_profile=retrieval_profile,
                retrieval_hints=retrieval_hints or list(fallback.retrieval_hints),
                source="llm_primary" if raw else "deterministic_fallback",
                validation_warnings=warnings,
            )
        )
    return entries


async def plan_columns(
    schema: list[dict[str, Any]],
    *,
    planner_mode: str = "deterministic",
    provider: Any = None,
    model_id: Optional[str] = None,
    max_tokens: int = 4096,
) -> ColumnPlan:
    deterministic = build_column_plan(schema, planner_mode="deterministic")
    if planner_mode == "disabled":
        return ColumnPlan(
            planner_mode="disabled",
            entries=[],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    if planner_mode != "llm_primary" or provider is None or not model_id:
        deterministic.planner_mode = planner_mode
        return deterministic

    started = perf_counter()
    try:
        raw = await provider.chat_complete_structured(
            messages=_schema_prompt(schema),
            response_schema=COLUMN_PLAN_SCHEMA,
            model_id=model_id,
            max_tokens=max_tokens,
        )
        entries = _validate_llm_plan(schema, raw.get("entries") if isinstance(raw, dict) else None, deterministic)
        return ColumnPlan(
            planner_mode="llm_primary",
            entries=entries,
            generated_at=datetime.now(timezone.utc).isoformat(),
            planner_ms=round((perf_counter() - started) * 1000.0, 3),
            planner_call_count=1,
            validation_warning_count=sum(len(entry.validation_warnings) for entry in entries),
        )
    except Exception as exc:
        entries = [
            entry.model_copy(
                update={
                    "source": "deterministic_fallback",
                    "validation_warnings": [f"planner_failed:{type(exc).__name__}"],
                }
            )
            for entry in deterministic.entries
        ]
        return ColumnPlan(
            planner_mode="deterministic_fallback",
            entries=entries,
            generated_at=datetime.now(timezone.utc).isoformat(),
            planner_ms=round((perf_counter() - started) * 1000.0, 3),
            planner_call_count=1,
            validation_warning_count=len(entries),
        )


def get_column_plan_path(run_dir: pathlib.Path) -> pathlib.Path:
    return run_dir / "planning" / "column_plan.json"


def persist_column_plan(run_dir: pathlib.Path, plan: ColumnPlan) -> pathlib.Path:
    path = get_column_plan_path(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json(path, plan.model_dump())
    return path
