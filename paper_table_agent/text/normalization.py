from __future__ import annotations

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


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = text.translate(str.maketrans(_LIGATURES))
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
    normalized = unicodedata.normalize("NFKC", text)
    normalized = normalized.replace("\u00a0", " ")
    normalized = normalized.translate(str.maketrans({dash: "-" for dash in _DASH_VARIANTS}))
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()
