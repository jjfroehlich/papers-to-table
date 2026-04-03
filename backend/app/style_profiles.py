"""Batch 3: Style profiles — per-column output-shape guidance for extraction.

T041 – StyleProfile JSON schema
T042 – Per-column preprocessing LLM step
T043 – Persist style profiles under style_profiles/
T044 – No-leakage baseline

Style profiles guide OUTPUT FORM only (length, tone, format, units).
They do NOT inject raw filled cells as semantic exemplars.
Proposal content must remain grounded in the current PDF evidence.
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


def _safe_filename(name: str, max_len: int = 64) -> str:
    """Return a filename-safe version of *name* for all platforms."""
    safe = _INVALID_FILENAME_CHARS.sub("_", name)
    safe = safe.replace(" ", "_")
    return safe[:max_len]

from .artifacts import write_json


# ---------------------------------------------------------------------------
# StyleProfile schema (T041)
# ---------------------------------------------------------------------------

class StyleProfile(BaseModel):
    """Output-shape guidance derived from existing filled cells for a schema column.

    All fields guide format and presentation only.
    Raw cell values are NOT stored here (no-leakage baseline, T044).
    """

    column_name: str

    # Core shape signals
    field_type_guess: str
    """Best guess at the field type: 'numeric', 'text', 'categorical', 'boolean',
    'range', 'date', 'percentage', 'mixed', 'unknown'."""

    expected_length: str
    """Typical output length: 'single_value', 'short' (<10 words),
    'medium' (10-50 words), 'long' (>50 words)."""

    tone: str
    """Register: 'technical', 'formal', 'neutral', 'informal'."""

    detail_level: str
    """Granularity: 'high', 'medium', 'low'."""

    value_shape: str
    """Structural pattern, e.g. 'single number with unit', 'year (YYYY)',
    'percentage with symbol', 'free text', 'comma-separated list', 'range X–Y'."""

    unit_style: Optional[str] = None
    """Unit convention if applicable, e.g. 'SI units', 'imperial', '%'."""

    format_notes: Optional[str] = None
    """Any additional format observations, e.g. '2 decimal places', 'abbreviated author names'."""

    example_risk: str = "none"
    """Risk level if raw values were used as exemplars.
    'none' | 'low' | 'medium' | 'high'.
    Logged for diagnostics; raw values are NOT included."""

    generated_at: str
    source_column_count: int
    """Number of non-empty cells analyzed when producing this profile."""

    provider_mode: str = "unavailable"
    """How the profile was produced: 'live_llm', 'heuristic', 'unavailable'."""


# ---------------------------------------------------------------------------
# Default / heuristic profile (used when LLM is unavailable)
# ---------------------------------------------------------------------------

def _heuristic_profile(column_name: str, filled_values: list[str]) -> StyleProfile:
    """Build a safe heuristic profile without LLM calls."""
    now = datetime.now(timezone.utc).isoformat()
    n = len(filled_values)

    # Basic heuristic type detection
    numeric_count = sum(
        1 for v in filled_values
        if v.strip().lstrip("-+").replace(".", "", 1).replace(",", "", 1).isdigit()
    )
    is_mostly_numeric = n > 0 and numeric_count / n >= 0.6

    avg_len = sum(len(v) for v in filled_values) / max(n, 1)
    if avg_len < 20:
        expected_length = "single_value"
    elif avg_len < 100:
        expected_length = "short"
    elif avg_len < 300:
        expected_length = "medium"
    else:
        expected_length = "long"

    field_type_guess = "numeric" if is_mostly_numeric else "text"
    if n == 0:
        field_type_guess = "unknown"

    return StyleProfile(
        column_name=column_name,
        field_type_guess=field_type_guess,
        expected_length=expected_length,
        tone="technical",
        detail_level="medium",
        value_shape="single value" if is_mostly_numeric else "free text",
        unit_style=None,
        format_notes=None,
        example_risk="none",
        generated_at=now,
        source_column_count=n,
        provider_mode="heuristic",
    )


# ---------------------------------------------------------------------------
# LLM-assisted profile generation (T042)
# ---------------------------------------------------------------------------

_STYLE_SYSTEM_PROMPT = (
    "You are an expert scientific data curator analyzing a spreadsheet column. "
    "Your job is to describe the OUTPUT FORMAT and STYLE of a spreadsheet column, "
    "NOT to interpret the content. "
    "Respond ONLY with a JSON object matching the required schema."
)


def _build_style_prompt(column_name: str, description: str, filled_values: list[str]) -> str:
    # Limit to avoid bloating the context; T044: never include more values than needed
    sample = filled_values[:10]
    sample_text = "\n".join(f"  - {v}" for v in sample)
    return (
        f"Column: {column_name}\n"
        f"Description: {description}\n\n"
        f"Sample existing values (for FORMAT ANALYSIS ONLY — do not use as semantic answers):\n"
        f"{sample_text}\n\n"
        "Analyse the FORMAT, LENGTH, TONE, UNITS, and VALUE SHAPE of the sample values. "
        "Return ONLY a JSON object with these fields:\n"
        '  "field_type_guess": one of numeric/text/categorical/boolean/range/date/percentage/mixed/unknown\n'
        '  "expected_length": one of single_value/short/medium/long\n'
        '  "tone": one of technical/formal/neutral/informal\n'
        '  "detail_level": one of high/medium/low\n'
        '  "value_shape": brief string describing structural pattern (e.g. "single number with unit")\n'
        '  "unit_style": unit convention or null\n'
        '  "format_notes": any extra format notes or null\n'
        '  "example_risk": one of none/low/medium/high (risk if raw values were used as semantic answers)\n'
        "Return only the JSON object, no other text."
    )


async def generate_style_profile(
    column_name: str,
    description: str,
    filled_values: list[str],
    provider: Optional[object] = None,  # ProviderAdapter from provider.py
    model_id: Optional[str] = None,
) -> StyleProfile:
    """Generate a style profile for a column.

    When a live provider is available, uses the LLM for richer analysis.
    Falls back to heuristic analysis when provider is None or unavailable.

    T044: raw filled_values are passed to the LLM for FORMAT analysis only.
    They are NOT included in the persisted StyleProfile (no-leakage).
    """
    now = datetime.now(timezone.utc).isoformat()
    n = len([v for v in filled_values if v.strip()])

    # Only pass non-empty values to the LLM
    nonempty = [v.strip() for v in filled_values if v.strip()]

    if provider is not None and model_id and nonempty:
        try:
            import json

            prompt = _build_style_prompt(column_name, description, nonempty)
            response_text = await provider.text_complete_raw(
                system=_STYLE_SYSTEM_PROMPT,
                user=prompt,
                max_tokens=512,
                model_id=model_id,
            )
            # Parse the JSON response
            # Strip markdown code fences if present
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                cleaned = "\n".join(lines).strip()
            data = json.loads(cleaned)

            return StyleProfile(
                column_name=column_name,
                field_type_guess=str(data.get("field_type_guess", "unknown")),
                expected_length=str(data.get("expected_length", "short")),
                tone=str(data.get("tone", "neutral")),
                detail_level=str(data.get("detail_level", "medium")),
                value_shape=str(data.get("value_shape", "free text")),
                unit_style=data.get("unit_style") or None,
                format_notes=data.get("format_notes") or None,
                example_risk=str(data.get("example_risk", "none")),
                generated_at=now,
                source_column_count=n,
                provider_mode="live_llm",
            )
        except Exception:
            # Fall through to heuristic
            pass

    return _heuristic_profile(column_name, nonempty)


# ---------------------------------------------------------------------------
# Persistence helpers (T043)
# ---------------------------------------------------------------------------

def get_style_profiles_dir(run_dir: pathlib.Path) -> pathlib.Path:
    return run_dir / "style_profiles"


def persist_style_profile(run_dir: pathlib.Path, profile: StyleProfile) -> pathlib.Path:
    """Persist a style profile as JSON under style_profiles/<column>.json.

    T043: Stored profiles contain ONLY shape/format signals, no raw cell values.
    """
    profiles_dir = get_style_profiles_dir(run_dir)
    profiles_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(profile.column_name)
    path = profiles_dir / f"{safe_name}.json"
    write_json(path, profile.model_dump())
    return path


def load_style_profile(run_dir: pathlib.Path, column_name: str) -> Optional[StyleProfile]:
    """Load a persisted style profile for a column."""
    safe_name = _safe_filename(column_name)
    path = get_style_profiles_dir(run_dir) / f"{safe_name}.json"
    if path.exists():
        from .artifacts import read_json
        try:
            data = read_json(path)
            return StyleProfile.model_validate(data)
        except Exception:
            return None
    return None


def load_all_style_profiles(run_dir: pathlib.Path) -> dict[str, StyleProfile]:
    """Load all persisted style profiles for a run."""
    profiles_dir = get_style_profiles_dir(run_dir)
    if not profiles_dir.exists():
        return {}
    result = {}
    from .artifacts import read_json
    for p in profiles_dir.glob("*.json"):
        try:
            data = read_json(p)
            sp = StyleProfile.model_validate(data)
            result[sp.column_name] = sp
        except Exception:
            pass
    return result


# ---------------------------------------------------------------------------
# Run-level style-profile generation (T042)
# ---------------------------------------------------------------------------

async def run_style_profiles_stage(
    run_dir: pathlib.Path,
    df,   # pd.DataFrame
    schema: list[dict],
    provider: Optional[object] = None,
    model_id: Optional[str] = None,
) -> dict[str, StyleProfile]:
    """Generate and persist style profiles for all schema columns.

    Returns a mapping of column_name -> StyleProfile.
    Called from the runner before extraction.
    """
    profiles: dict[str, StyleProfile] = {}
    for col_def in schema:
        col_name = col_def.get("column_name", "")
        description = col_def.get("description", "")
        if not col_name:
            continue

        # Gather existing filled values for this column (T044: format analysis only)
        if col_name in df.columns:
            filled = [
                str(v).strip()
                for v in df[col_name].tolist()
                if str(v).strip() and str(v).strip().lower() not in {"nan", "none", ""}
            ]
        else:
            filled = []

        profile = await generate_style_profile(
            col_name,
            description,
            filled,
            provider,
            model_id,
        )
        persist_style_profile(run_dir, profile)
        profiles[col_name] = profile

    return profiles
