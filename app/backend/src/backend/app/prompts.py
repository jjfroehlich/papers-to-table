from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Optional

from .artifacts import hash_file, hash_json_data

PROMPT_BUNDLES_DIR = Path(__file__).resolve().parent / "prompt_bundles"
DEFAULT_PROMPT_BUNDLE = "default"

REQUIRED_PROMPT_KEYS = {
    "text_extraction_system",
    "text_extraction_user",
    "figure_extraction_system",
    "figure_extraction_user",
    "evidence_recovery_system",
    "evidence_recovery_user",
    "style_profile_system",
}


def _resolve_bundle_root(bundle: Optional[str], bundle_path: Optional[str]) -> Path:
    if bundle_path:
        return Path(bundle_path).resolve()
    selected = (bundle or DEFAULT_PROMPT_BUNDLE).strip() or DEFAULT_PROMPT_BUNDLE
    return (PROMPT_BUNDLES_DIR / selected).resolve()


def _normalize_manifest_file_path(relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").strip()
    if not normalized:
        raise ValueError("Prompt manifest contains an empty file path.")
    path_obj = Path(normalized)
    if path_obj.is_absolute() or ".." in path_obj.parts:
        raise ValueError(f"Prompt manifest file path must be bundle-relative: {relative_path}")
    return normalized


def _load_manifest(bundle_root: Path) -> dict[str, object]:
    manifest_path = bundle_root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Prompt bundle manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Prompt bundle manifest is not valid JSON: {manifest_path}") from exc

    if not isinstance(manifest, dict):
        raise ValueError(f"Prompt bundle manifest must be a JSON object: {manifest_path}")

    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError(f"Prompt bundle manifest must define a non-empty 'files' object: {manifest_path}")

    missing_keys = sorted(REQUIRED_PROMPT_KEYS - set(files.keys()))
    if missing_keys:
        raise ValueError(
            f"Prompt bundle manifest is missing required prompt keys: {', '.join(missing_keys)}"
        )

    if not isinstance(manifest.get("bundle_id"), str) or not str(manifest.get("bundle_id")).strip():
        raise ValueError(f"Prompt bundle manifest must define a non-empty string 'bundle_id': {manifest_path}")

    return manifest


@lru_cache(maxsize=16)
def _load_prompt_bundle_cached(bundle: Optional[str], bundle_path: Optional[str]) -> dict[str, object]:
    bundle_root = _resolve_bundle_root(bundle, bundle_path)
    manifest_path = bundle_root / "manifest.json"
    manifest = _load_manifest(bundle_root)
    file_map = manifest.get("files", {})

    prompt_files: dict[str, dict[str, str]] = {}
    prompt_texts: dict[str, str] = {}

    for prompt_key, relative_path_raw in file_map.items():
        if not isinstance(relative_path_raw, str):
            raise ValueError(f"Prompt manifest path for key '{prompt_key}' must be a string")
        relative_path = _normalize_manifest_file_path(relative_path_raw)
        file_path = (bundle_root / relative_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(
                f"Prompt file for key '{prompt_key}' not found: {file_path}"
            )
        text = file_path.read_text(encoding="utf-8").strip()
        if not text:
            raise ValueError(f"Prompt file for key '{prompt_key}' is empty: {file_path}")
        prompt_texts[prompt_key] = text
        prompt_files[prompt_key] = {
            "logical_key": prompt_key,
            "path": str(file_path),
            "relative_path": relative_path,
            "sha256": hash_file(file_path),
        }

    manifest_hash = hash_json_data(manifest)
    bundle_hash_payload = {
        "bundle_id": manifest.get("bundle_id"),
        "bundle_version": manifest.get("bundle_version"),
        "prompt_texts": prompt_texts,
    }
    bundle_hash = hashlib.sha256(
        json.dumps(bundle_hash_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return {
        "bundle_id": str(manifest.get("bundle_id", "")).strip(),
        "bundle_version": manifest.get("bundle_version"),
        "bundle_path": str(bundle_root),
        "manifest_path": str(manifest_path),
        "manifest_hash": manifest_hash,
        "bundle_hash": bundle_hash,
        "prompt_files": prompt_files,
        "prompt_keys": sorted(prompt_texts.keys()),
        "prompts": prompt_texts,
        "manifest": manifest,
    }


def clear_prompt_bundle_cache() -> None:
    _load_prompt_bundle_cached.cache_clear()


def get_prompt_bundle(
    *,
    bundle: Optional[str] = None,
    bundle_path: Optional[str] = None,
) -> dict[str, object]:
    return copy.deepcopy(_load_prompt_bundle_cached(bundle, bundle_path))


def load_prompt_text(
    prompt_key: str,
    *,
    bundle: Optional[str] = None,
    bundle_path: Optional[str] = None,
) -> str:
    prompt_bundle = get_prompt_bundle(bundle=bundle, bundle_path=bundle_path)
    prompts = prompt_bundle.get("prompts", {})
    if prompt_key not in prompts:
        available = ", ".join(sorted(prompts.keys()))
        raise KeyError(f"Unknown prompt key '{prompt_key}'. Available keys: {available}")
    return str(prompts[prompt_key])


def render_prompt_template(
    prompt_key: str,
    substitutions: dict[str, object],
    *,
    bundle: Optional[str] = None,
    bundle_path: Optional[str] = None,
) -> str:
    template = Template(load_prompt_text(prompt_key, bundle=bundle, bundle_path=bundle_path))
    return template.substitute({k: "" if v is None else str(v) for k, v in substitutions.items()})


def get_prompt_file_provenance(
    *,
    bundle: Optional[str] = None,
    bundle_path: Optional[str] = None,
) -> dict[str, dict[str, str]]:
    prompt_bundle = get_prompt_bundle(bundle=bundle, bundle_path=bundle_path)
    return prompt_bundle["prompt_files"]