from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class ModelRequestPolicy:
    family: str = "generic"
    preferred_structured_mode: str = "json_schema"
    require_json_keyword: bool = False
    disable_thinking_reminder: bool = False
    omit_max_tokens_for_structured: bool = False
    fast_abort_malformed_json_attempts: int | None = None
    retry_malformed_structured_response: bool = True
    request_defaults: dict[str, Any] | None = None
    extra_body_defaults: dict[str, Any] | None = None
    chat_template_kwargs_defaults: dict[str, Any] | None = None

    def ordered_structured_modes(self, negotiated_mode: str) -> list[str]:
        supported = _fallback_modes_for(negotiated_mode)
        if self.preferred_structured_mode in supported:
            supported.remove(self.preferred_structured_mode)
            return [self.preferred_structured_mode, *supported]
        return supported

    def apply_messages(self, messages: list[dict[str, Any]], structured_mode: str) -> list[dict[str, Any]]:
        normalized = list(messages)
        if self.require_json_keyword or structured_mode in {"json_object", "none"}:
            normalized = _ensure_json_keyword(normalized)
        if self.disable_thinking_reminder:
            normalized = _append_system_reminder(
                normalized,
                "Use non-thinking mode. Return only the requested JSON object.",
            )
        return normalized


DEFAULT_MODEL_REQUEST_POLICY = ModelRequestPolicy()

DEFAULT_MODEL_PROFILES_PATH = Path(__file__).with_name("model_profiles") / "default_profiles.json"


def resolve_model_request_policy(model_id: str | None) -> ModelRequestPolicy:
    normalized = (model_id or "").casefold()
    for predicate, policy in _load_model_policy_overrides():
        if predicate(normalized):
            return policy
    return DEFAULT_MODEL_REQUEST_POLICY


@lru_cache(maxsize=1)
def _load_model_policy_overrides() -> tuple[tuple[Callable[[str], bool], ModelRequestPolicy], ...]:
    path = Path(os.environ.get("PAPERS_TO_TABLE_MODEL_PROFILES") or DEFAULT_MODEL_PROFILES_PATH)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return ()
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        return ()
    overrides: list[tuple[Callable[[str], bool], ModelRequestPolicy]] = []
    for item in profiles:
        if not isinstance(item, dict):
            continue
        match = item.get("match")
        policy_payload = item.get("policy")
        if not isinstance(match, dict) or not isinstance(policy_payload, dict):
            continue
        predicate = _compile_matcher(match)
        if predicate is None:
            continue
        try:
            policy = ModelRequestPolicy(**policy_payload)
        except TypeError:
            continue
        overrides.append((predicate, policy))
    return tuple(overrides)


def _compile_matcher(match: dict[str, Any]) -> Callable[[str], bool] | None:
    exact = match.get("exact")
    contains = match.get("contains")
    all_contains = match.get("all_contains")
    if isinstance(exact, str) and exact.strip():
        expected = exact.casefold()
        return lambda model_id: model_id == expected
    if isinstance(contains, str) and contains.strip():
        needle = contains.casefold()
        return lambda model_id: needle in model_id
    if isinstance(all_contains, list) and all(isinstance(item, str) and item.strip() for item in all_contains):
        needles = [item.casefold() for item in all_contains]
        return lambda model_id: all(needle in model_id for needle in needles)
    return None


def _fallback_modes_for(structured_mode: str) -> list[str]:
    if structured_mode == "json_schema":
        return ["json_schema", "json_object", "none"]
    if structured_mode == "json_object":
        return ["json_object", "none"]
    return ["none"]


def _ensure_json_keyword(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if any("json" in str(message.get("content", "")).casefold() for message in messages):
        return messages
    normalized = list(messages)
    normalized.append({"role": "system", "content": "Respond with valid JSON only."})
    return normalized


def _append_system_reminder(messages: list[dict[str, Any]], reminder: str) -> list[dict[str, Any]]:
    normalized = list(messages)
    normalized.append({"role": "system", "content": reminder})
    return normalized
