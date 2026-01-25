from __future__ import annotations

import math
import re
import unicodedata

_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "ft",
    "\ufb06": "st",
}

_DASH_VARIANTS = "\u2010\u2011\u2012\u2013\u2014\u2212\u2015"
_EMPTY_SENTINELS = {"", "nan", "na", "n/a", "null", "none", "-"}


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = normalize_unicode(text)
    normalized = normalized.translate(str.maketrans(_LIGATURES))
    normalized = re.sub(r"-\s*\n\s*", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_for_matching(text: str) -> str:
    normalized = normalize_text(text).casefold()
    normalized = re.sub(r"[^0-9a-z]+", "", normalized)
    return normalized


def normalize_key(text: str) -> str:
    if not text:
        return ""
    normalized = normalize_unicode(text)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_unicode(text: str) -> str:
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.translate(str.maketrans({dash: "-" for dash in _DASH_VARIANTS}))
    return normalized


def normalize_chunk_id(text: str) -> str:
    if not text:
        return ""
    normalized = normalize_unicode(text)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def normalize_str_for_prompt(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    text = normalize_unicode(str(value))
    stripped = text.strip()
    if not stripped:
        return ""
    lowered = stripped.casefold()
    if lowered in _EMPTY_SENTINELS:
        return ""
    return stripped
