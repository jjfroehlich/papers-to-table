from __future__ import annotations

import re

_LIGATURES = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\ufb05": "ft",
    "\ufb06": "st",
}


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
