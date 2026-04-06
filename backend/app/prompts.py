from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .artifacts import hash_file

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"

PROMPT_FILES = {
    "text_extraction_system": "text_extraction_system.txt",
    "figure_extraction_system": "figure_extraction_system.txt",
    "style_profile_system": "style_profile_system.txt",
}


def _prompt_path(prompt_key: str) -> Path:
    filename = PROMPT_FILES.get(prompt_key)
    if filename is None:
        raise KeyError(f"Unknown prompt key: {prompt_key}")
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path


def load_prompt_text(prompt_key: str) -> str:
    text = _prompt_path(prompt_key).read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt file is empty: {_prompt_path(prompt_key)}")
    return text


def get_prompt_file_provenance() -> dict[str, dict[str, str]]:
    provenance: dict[str, dict[str, str]] = {}
    for prompt_key, filename in PROMPT_FILES.items():
        path = _prompt_path(prompt_key)
        provenance[prompt_key] = {
            "path": f"backend/app/prompts/{filename}",
            "sha256": hash_file(path),
        }
    return provenance


def get_prompt_bundle() -> dict[str, object]:
    payload = {
        "prompts": {},
        "prompt_files": get_prompt_file_provenance(),
    }
    for prompt_key in PROMPT_FILES:
        payload["prompts"][prompt_key] = load_prompt_text(prompt_key)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    payload["bundle_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload