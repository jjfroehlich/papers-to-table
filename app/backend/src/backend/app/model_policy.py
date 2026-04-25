from __future__ import annotations

from dataclasses import dataclass
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

_MODEL_POLICY_OVERRIDES: tuple[tuple[Callable[[str], bool], ModelRequestPolicy], ...] = (
    (
        lambda model_id: "qwen" in model_id,
        ModelRequestPolicy(
            family="qwen",
            preferred_structured_mode="json_object",
            require_json_keyword=True,
            disable_thinking_reminder=True,
            omit_max_tokens_for_structured=True,
            fast_abort_malformed_json_attempts=1,
            retry_malformed_structured_response=False,
        ),
    ),
    (
        lambda model_id: "gpt-oss" in model_id,
        ModelRequestPolicy(family="gpt_oss", preferred_structured_mode="json_schema"),
    ),
    (
        lambda model_id: "gemma" in model_id,
        ModelRequestPolicy(family="gemma", preferred_structured_mode="json_schema"),
    ),
)


def resolve_model_request_policy(model_id: str | None) -> ModelRequestPolicy:
    normalized = (model_id or "").casefold()
    for predicate, policy in _MODEL_POLICY_OVERRIDES:
        if predicate(normalized):
            return policy
    return DEFAULT_MODEL_REQUEST_POLICY


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
