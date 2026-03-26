"""
Batch 3 — Style profiles.

Implements:
- T041: StyleProfile JSON schema
- T042: Per-column preprocessing LLM step for style profiles
- T043: Persist style profiles under style_profiles/
- T044: No-leakage baseline (raw filled cells are NOT passed to extraction as exemplars)
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .artifacts import RunArtifacts

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# T041 — StyleProfile schema
# ---------------------------------------------------------------------------


class StyleProfile(BaseModel):
    """
    Per-column style/format guidance derived from existing filled cells.

    Guides output *form* only — never semantic content.
    """

    column_name: str
    field_type_guess: str = "text"
    """Coarse type guess: 'text', 'numeric', 'year', 'list', 'categorical', 'boolean', 'url'."""
    expected_length: str = "short"
    """Coarse length: 'short' (<10 words), 'medium' (1–3 sentences), 'long' (>3 sentences)."""
    tone: str = "neutral"
    """Writing register: 'neutral', 'formal', 'technical', 'terse'."""
    detail_level: str = "concise"
    """Level of elaboration: 'concise', 'moderate', 'detailed'."""
    value_shape: str = ""
    """Template/pattern hint, e.g. 'YYYY' for years or 'Author, A. B.' for names."""
    unit_style: str = ""
    """Unit convention hint when numeric, e.g. '% w/v', 'mg/kg bw'."""
    format_notes: str = ""
    """Free-form additional format guidance."""
    example_risk: bool = False
    """True when the column appeared to have high semantic diversity — higher leakage risk."""


# ---------------------------------------------------------------------------
# T044 — Leakage-safe style-analysis helpers (no raw exemplar injection)
# ---------------------------------------------------------------------------

_NUMERIC_RE = re.compile(r"^\s*[-+]?\d[\d,. ]*(%|[a-zA-Z/]+)?\s*$")
_YEAR_RE = re.compile(r"^\s*(19|20)\d{2}\s*$")
_URL_RE = re.compile(r"https?://")
_LIST_SEPS = re.compile(r"[;,/]")


def _infer_field_type(samples: list[str]) -> str:
    """Infer a coarse field type from a sample of filled values."""
    if not samples:
        return "text"
    year_count = sum(1 for s in samples if _YEAR_RE.match(s))
    if year_count / len(samples) > 0.6:
        return "year"
    numeric_count = sum(1 for s in samples if _NUMERIC_RE.match(s))
    if numeric_count / len(samples) > 0.6:
        return "numeric"
    url_count = sum(1 for s in samples if _URL_RE.search(s))
    if url_count / len(samples) > 0.5:
        return "url"
    list_count = sum(1 for s in samples if _LIST_SEPS.search(s) and len(s) > 10)
    if list_count / len(samples) > 0.5:
        return "list"
    # Categorical: very few distinct values vs sample size
    distinct = len(set(s.lower().strip() for s in samples))
    if distinct <= max(3, len(samples) // 4):
        return "categorical"
    return "text"


def _infer_length(samples: list[str]) -> str:
    if not samples:
        return "short"
    avg_words = sum(len(s.split()) for s in samples) / len(samples)
    if avg_words < 8:
        return "short"
    if avg_words < 40:
        return "medium"
    return "long"


def _infer_tone(samples: list[str]) -> str:
    if not samples:
        return "neutral"
    has_technical = any(
        any(kw in s.lower() for kw in ["p<", "p =", "n=", "mg/", "kg/", "mm ", "ci", "±", "%"])
        for s in samples
    )
    if has_technical:
        return "technical"
    avg_words = sum(len(s.split()) for s in samples) / len(samples)
    if avg_words < 4:
        return "terse"
    return "neutral"


def _infer_unit_style(samples: list[str]) -> str:
    unit_counts: dict[str, int] = {}
    unit_re = re.compile(r"\b(\d[\d,. ]*)\s*([a-zA-Z/%]+)\b")
    for s in samples:
        for m in unit_re.finditer(s):
            u = m.group(2).lower()
            unit_counts[u] = unit_counts.get(u, 0) + 1
    if not unit_counts:
        return ""
    top_unit = max(unit_counts, key=unit_counts.__getitem__)
    return top_unit if unit_counts[top_unit] >= max(2, len(samples) // 4) else ""


def _infer_value_shape(field_type: str, samples: list[str]) -> str:
    if field_type == "year":
        return "YYYY"
    if field_type == "numeric":
        return "number [unit]"
    if field_type == "categorical" and samples:
        distinct = sorted(set(s.lower().strip() for s in samples))[:5]
        return " | ".join(distinct)
    return ""


def _assess_semantic_leakage_risk(samples: list[str]) -> bool:
    """
    Return True when the sample values are semantically diverse, indicating higher
    risk of leaking semantic content if used as stylistic examples.
    """
    if len(samples) < 3:
        return False
    distinct_ratio = len(set(s.lower()[:20] for s in samples)) / len(samples)
    return distinct_ratio > 0.8 and sum(len(s.split()) for s in samples) / len(samples) > 6


# ---------------------------------------------------------------------------
# T042 — Per-column style-profile generation (deterministic heuristics + optional LLM)
# ---------------------------------------------------------------------------


def _extract_style_signals_from_cells(
    filled_cells: list[str],
) -> dict[str, Any]:
    """
    T044 leakage enforcement: extract ONLY format/style signals from filled cells.

    The returned dict is safe to pass downstream — it never contains raw cell values.
    """
    samples = [c.strip() for c in filled_cells if c.strip()][:20]  # cap at 20
    field_type = _infer_field_type(samples)
    return {
        "sample_count": len(samples),
        "field_type_guess": field_type,
        "expected_length": _infer_length(samples),
        "tone": _infer_tone(samples),
        "detail_level": "concise" if _infer_length(samples) == "short" else "moderate",
        "unit_style": _infer_unit_style(samples),
        "value_shape": _infer_value_shape(field_type, samples),
        "example_risk": _assess_semantic_leakage_risk(samples),
    }


def generate_style_profile_for_column(
    column_name: str,
    column_description: str,
    filled_cells: list[str],
    provider: Any | None = None,
) -> StyleProfile:
    """
    T042: Generate a per-column style profile.

    Always uses deterministic heuristics for baseline signals.
    When a provider is supplied, tries a lightweight LLM refinement step.
    Raw filled cells are NEVER passed to the provider (T044).
    """
    signals = _extract_style_signals_from_cells(filled_cells)

    format_notes = ""

    # Optional LLM refinement (T042): passes only style signals, not raw cells
    if provider is not None and not signals["example_risk"]:
        try:
            format_notes = _llm_refine_format_notes(
                column_name=column_name,
                column_description=column_description,
                signals=signals,
                provider=provider,
            )
        except Exception as exc:
            logger.warning("LLM style-profile refinement failed for %r: %s", column_name, exc)

    return StyleProfile(
        column_name=column_name,
        field_type_guess=signals["field_type_guess"],
        expected_length=signals["expected_length"],
        tone=signals["tone"],
        detail_level=signals["detail_level"],
        value_shape=signals["value_shape"],
        unit_style=signals["unit_style"],
        format_notes=format_notes,
        example_risk=signals["example_risk"],
    )


def _llm_refine_format_notes(
    column_name: str,
    column_description: str,
    signals: dict[str, Any],
    provider: Any,
) -> str:
    """
    Ask the LLM for additional format guidance.

    T044: Only passes style *signals* (type, length, tone, units) — never raw cell text.
    """
    prompt = (
        f"You are a style guide assistant for a scientific literature extraction tool.\n"
        f"Column: {column_name!r}\n"
        f"Description: {column_description!r}\n"
        f"Observed style signals: type={signals['field_type_guess']}, "
        f"length={signals['expected_length']}, tone={signals['tone']}, "
        f"units={signals['unit_style'] or 'none'}.\n\n"
        "Provide one concise sentence of additional format guidance for the column "
        "(output form only — not content predictions). "
        "If you have no useful guidance, reply with an empty string."
    )
    from .provider import ProviderAdapter

    if not isinstance(provider, ProviderAdapter):
        return ""
    result = provider.complete_text(prompt, max_tokens=80)
    return result.strip()[:300]


# ---------------------------------------------------------------------------
# T043 — Persist style profiles
# ---------------------------------------------------------------------------


def generate_and_persist_style_profiles(
    artifacts: RunArtifacts,
    schema_rows: list[dict[str, Any]],
    table_rows: list[dict[str, Any]],
    provider: Any | None = None,
) -> dict[str, StyleProfile]:
    """
    T042+T043: Generate one StyleProfile per schema column and persist them.

    Returns a mapping {column_name: StyleProfile}.
    """
    profiles: dict[str, StyleProfile] = {}

    for schema_row in schema_rows:
        column_name = str(schema_row.get("column_name", ""))
        column_description = str(schema_row.get("description", ""))
        if not column_name:
            continue

        # Collect non-empty filled values from the table (T044: raw values are used only here)
        filled_cells = [
            str(row[column_name])
            for row in table_rows
            if column_name in row and str(row.get(column_name, "")).strip()
        ]

        profile = generate_style_profile_for_column(
            column_name=column_name,
            column_description=column_description,
            filled_cells=filled_cells,
            provider=provider,
        )
        profiles[column_name] = profile

        # Persist individual profile
        artifacts.write_json(
            f"style_profiles/{_safe_filename(column_name)}.json",
            profile.model_dump(mode="json"),
        )

    # Persist combined index
    artifacts.write_json(
        "style_profiles/index.json",
        {k: v.model_dump(mode="json") for k, v in profiles.items()},
    )

    logger.info("Generated %d style profile(s)", len(profiles))
    return profiles


def load_style_profiles(artifacts: RunArtifacts) -> dict[str, StyleProfile]:
    """Load style profiles from artifact index."""
    try:
        index = artifacts.read_json("style_profiles/index.json")
        return {k: StyleProfile.model_validate(v) for k, v in index.items()}
    except FileNotFoundError:
        return {}


def _safe_filename(name: str) -> str:
    return re.sub(r"[^\w\-]", "_", name)[:80]
