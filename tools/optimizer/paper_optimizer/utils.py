from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def stable_json_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


EXTERNAL_CANDIDATE_ID_MAX_LENGTH = 40
SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def slugify_identifier(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("_")
    return slug or "external"


def shorten_identifier(value: str, *, max_length: int = EXTERNAL_CANDIDATE_ID_MAX_LENGTH) -> str:
    slug = slugify_identifier(value)
    if len(slug) <= max_length:
        return slug
    digest = sha256_text(slug)[:8]
    prefix_length = max(1, max_length - len(digest) - 1)
    prefix = slug[:prefix_length].rstrip("_.-") or "external"
    return f"{prefix}_{digest}"


def external_candidate_id(external_result: dict[str, Any]) -> str:
    explicit = external_result.get("candidate_id")
    if isinstance(explicit, str) and explicit.strip():
        return shorten_identifier(explicit)
    label = str(external_result.get("label") or external_result.get("system") or "external")
    return shorten_identifier(f"external_{label}")


def flatten_dict(source: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in source.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten_dict(value, full_key))
        else:
            out[full_key] = value
    return out


def deep_merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def set_nested_value(target: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = [part for part in dotted_path.split(".") if part]
    if not parts:
        raise ValueError("dotted_path must not be empty")

    cursor = target
    for part in parts[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, dict):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[parts[-1]] = value


def resolve_path_fields(payload: Any, *, base_dir: Path, field_names: set[str]) -> Any:
    if isinstance(payload, dict):
        resolved: dict[str, Any] = {}
        for key, value in payload.items():
            if key in field_names and isinstance(value, str) and value.strip():
                candidate = Path(value)
                resolved[key] = str(candidate.resolve()) if candidate.is_absolute() else str((base_dir / candidate).resolve())
            else:
                resolved[key] = resolve_path_fields(value, base_dir=base_dir, field_names=field_names)
        return resolved
    if isinstance(payload, list):
        return [resolve_path_fields(item, base_dir=base_dir, field_names=field_names) for item in payload]
    return payload


def normalize_python_command_prefix(command_prefix: list[str]) -> list[str]:
    if not command_prefix:
        return []
    executable = Path(command_prefix[0]).name.lower()
    if executable in {"python", "python.exe", "python3", "python3.exe", "py"}:
        return [sys.executable, *command_prefix[1:]]
    return list(command_prefix)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
