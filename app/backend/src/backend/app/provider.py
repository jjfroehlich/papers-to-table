"""Batch 3: Provider abstraction, LM Studio integration, and structured-output negotiation.

T050 – Provider abstraction + capability-probe model
T051 – LM Studio localhost API integration
T051a – Optional cloud-provider adapter slots
T052 – Provider error handling + structured-output failure policy
T052a – Provider-mode truth explicit in artifacts

The canonical provider token is 'lm_studio'.
The canonical operator-visible label is 'LM Studio'.
No silent fallback from a live path to stub or degraded mode.
"""

from __future__ import annotations

import abc
import hashlib
import json
import os
import re
import tempfile
import textwrap
import time
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from .model_policy import resolve_model_request_policy
from .schemas import ProviderLocality


def _has_explicit_model_id(model_id: Optional[str]) -> bool:
    if model_id is None:
        return False
    normalized = model_id.strip()
    return bool(normalized) and normalized != "default"


def _messages_contain_json_keyword(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = message.get("content")
        if isinstance(content, str) and re.search(r"json", content, flags=re.IGNORECASE):
            return True
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and re.search(r"json", text, flags=re.IGNORECASE):
                    return True
    return False


def _ensure_json_keyword_in_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if _messages_contain_json_keyword(messages):
        return messages
    return [
        {
            "role": "system",
            "content": "Return JSON only. Output exactly one JSON object and no prose.",
        },
        *messages,
    ]


# ---------------------------------------------------------------------------
# Provider capability contract (T050)
# ---------------------------------------------------------------------------

class ProviderCapabilities(BaseModel):
    """Detected capabilities of a provider/model pair."""
    supports_structured_output: bool = False
    structured_output_mode: str = "none"
    """One of: 'json_schema', 'json_object', or 'none'."""
    structured_output_reason: Optional[str] = None
    structured_output_error: Optional[str] = None
    model_id: Optional[str] = None
    vision_capable: bool = False
    vision_structured_output_mode: Optional[str] = None
    vision_structured_output_reason: Optional[str] = None
    vision_structured_output_error: Optional[str] = None
    probed_at: Optional[str] = None


def _canonical_structured_output_reason(
    structured_output_mode: Optional[str],
    structured_output_reason: Optional[str],
) -> Optional[str]:
    if structured_output_mode == "json_schema":
        return None
    if structured_output_reason == "structured_backend_incompatible":
        return structured_output_reason
    if structured_output_mode == "json_object":
        return "json_schema_unsupported"
    if structured_output_mode == "none":
        return "structured_modes_unavailable"
    return structured_output_reason


class ProviderMode(BaseModel):
    """Runtime provider mode — persisted in run artifacts (T052a)."""
    token: str
    locality: str   # 'local' | 'cloud'
    mode: str
    """One of: 'live_local', 'live_cloud', 'unavailable', 'disabled', 'stub'."""
    text_model_id: Optional[str] = None
    vision_model_id: Optional[str] = None
    capabilities: Optional[ProviderCapabilities] = None
    structured_output_mode: Optional[str] = None
    structured_output_reason: Optional[str] = None
    structured_output_fallback_used: bool = False
    vision_structured_output_mode: Optional[str] = None
    vision_structured_output_reason: Optional[str] = None
    model_management: Optional[dict[str, Any]] = None
    readiness_error: Optional[str] = None
    readiness_reason: Optional[str] = None
    recorded_at: str = ""

    def is_live(self) -> bool:
        return self.mode in ("live_local", "live_cloud")

    def display_label(self) -> str:
        from .config import PROVIDER_DISPLAY_NAMES
        base = PROVIDER_DISPLAY_NAMES.get(self.token, self.token)
        suffix = {
            "live_local": "(live local)",
            "live_cloud": "(live cloud)",
            "unavailable": "(unavailable)",
            "disabled": "(disabled)",
            "stub": "(stub/demo)",
        }.get(self.mode, "")
        return f"{base} {suffix}".strip()


# ---------------------------------------------------------------------------
# Abstract provider interface (T050)
# ---------------------------------------------------------------------------

class ProviderAdapter(abc.ABC):
    """Abstract base class for all provider adapters.

    T050: one typed interface for LM Studio (default) and optional cloud providers.
    """

    @property
    @abc.abstractmethod
    def token(self) -> str:
        """Canonical provider token (e.g. 'lm_studio')."""
        ...

    @property
    @abc.abstractmethod
    def locality(self) -> ProviderLocality:
        ...

    @abc.abstractmethod
    async def probe_capabilities(
        self,
        text_model_id: str,
        vision_model_id: Optional[str] = None,
    ) -> ProviderCapabilities:
        """Check model availability and structured-output support."""
        ...

    @abc.abstractmethod
    async def text_complete_raw(
        self,
        system: str,
        user: str,
        max_tokens: int = 512,
    ) -> str:
        """Raw text completion, returns the assistant message content as a string."""
        ...

    @abc.abstractmethod
    async def chat_complete_structured(
        self,
        messages: list[dict],
        response_schema: dict,
        model_id: str,
        max_tokens: int = 2048,
        temperature: Optional[float] = None,
    ) -> dict:
        """Structured-output completion. Returns parsed dict.

        Negotiates structured output mode based on probed capabilities.
        Raises ProviderError on hard failure after bounded recovery.
        """
        ...

    @abc.abstractmethod
    async def vision_complete_structured(
        self,
        messages: list[dict],
        response_schema: dict,
        model_id: str,
        image_b64: str,
        max_tokens: int = 2048,
        temperature: Optional[float] = None,
        retry_malformed_structured_response: bool = True,
    ) -> dict:
        """Vision-capable structured completion. Returns parsed dict."""
        ...

    def get_provider_mode(
        self,
        text_model_id: Optional[str],
        vision_model_id: Optional[str],
        capabilities: Optional[ProviderCapabilities] = None,
        model_management: Optional[dict[str, Any]] = None,
        readiness_error: Optional[str] = None,
        readiness_reason: Optional[str] = None,
    ) -> ProviderMode:
        if readiness_error:
            mode = "unavailable"
        elif self.locality == ProviderLocality.cloud:
            mode = "live_cloud"
        else:
            mode = "live_local"
        structured_output_mode = capabilities.structured_output_mode if capabilities else None
        structured_output_reason = _canonical_structured_output_reason(
            structured_output_mode,
            capabilities.structured_output_reason if capabilities else None,
        )
        fallback_used = structured_output_mode in ("json_object", "none")
        return ProviderMode(
            token=self.token,
            locality=self.locality.value,
            mode=mode,
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            capabilities=capabilities,
            structured_output_mode=structured_output_mode,
            structured_output_reason=structured_output_reason,
            structured_output_fallback_used=fallback_used,
            vision_structured_output_mode=(
                capabilities.vision_structured_output_mode if capabilities else None
            ),
            vision_structured_output_reason=(
                _canonical_structured_output_reason(
                    capabilities.vision_structured_output_mode if capabilities else None,
                    capabilities.vision_structured_output_reason if capabilities else None,
                )
                if capabilities
                else None
            ),
            model_management=model_management,
            readiness_error=readiness_error,
            readiness_reason=readiness_reason,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_request_counts(self) -> dict[str, int]:
        """Return provider request counters for run artifacts."""
        return {}

    def get_diagnostics(self) -> dict[str, Any]:
        """Return provider attempt diagnostics for run artifacts."""
        return {}

    def get_diagnostics_cursor(self) -> int:
        """Return an opaque cursor for later incremental diagnostic reads."""
        return 0

    def get_diagnostics_since(self, cursor: int) -> list[dict[str, Any]]:
        """Return provider attempt diagnostics recorded after the given cursor."""
        return []

    def get_probe_report(self) -> dict[str, Any]:
        """Return capability-probe details suitable for diagnostics artifacts."""
        return {}

    def get_model_request_profile_report(self) -> dict[str, Any]:
        """Return effective model request settings suitable for run artifacts."""
        return {}

    def get_model_management_report(self) -> dict[str, Any]:
        """Return model-management details suitable for diagnostics artifacts."""
        return {}

    def get_trace_records(self) -> list[dict[str, Any]]:
        """Return verbose provider trace records when enabled."""
        return []


# ---------------------------------------------------------------------------
# Provider errors (T052)
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Hard provider error that should record an error proposal outcome."""
    def __init__(
        self,
        message: str,
        recoverable: bool = False,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.recoverable = recoverable
        self.reason = reason
        self.details = details


class StructuredOutputError(ProviderError):
    """Structured output contract failure."""
    pass


class ModelUnavailableError(ProviderError):
    """Model is not loaded or available."""

    def __init__(
        self,
        message: str,
        recoverable: bool = False,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            recoverable=recoverable,
            reason=reason or "model_unavailable",
            details=details,
        )


class ProviderTimeoutError(ProviderError):
    """Request timed out."""

    def __init__(
        self,
        message: str,
        recoverable: bool = False,
        reason: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ):
        super().__init__(
            message,
            recoverable=recoverable,
            reason=reason or "provider_unreachable",
            details=details,
        )


# ---------------------------------------------------------------------------
# JSON repair helper (T052)
# ---------------------------------------------------------------------------

def _try_repair_json(raw: str) -> Optional[dict]:
    parsed, _meta = _try_repair_json_with_metadata(raw)
    return parsed


def _try_repair_json_with_metadata(raw: str) -> tuple[Optional[dict], dict[str, Any]]:
    """Bounded JSON repair attempt for common LLM output artifacts."""
    cleaned, wrapper_meta = _strip_json_wrappers(raw)
    metadata: dict[str, Any] = {
        **wrapper_meta,
        "balanced_object_extracted": False,
        "parsed_from": None,
        "trailing_comma_repaired": False,
        "failure_stage": None,
        "validation_error": None,
    }
    parsed, trailing_comma_fixed = _parse_json_candidate(cleaned)
    if isinstance(parsed, dict):
        metadata["parsed_from"] = "cleaned"
        metadata["trailing_comma_repaired"] = trailing_comma_fixed
        return parsed, metadata

    balanced = _extract_balanced_json_object(cleaned)
    if balanced is not None:
        metadata["balanced_object_extracted"] = True
        parsed, trailing_comma_fixed = _parse_json_candidate(balanced)
        if isinstance(parsed, dict):
            metadata["parsed_from"] = "balanced_object"
            metadata["trailing_comma_repaired"] = trailing_comma_fixed
            return parsed, metadata

    metadata["failure_stage"] = "malformed_json"
    return None, metadata


def _strip_json_wrappers(raw: str) -> tuple[str, dict[str, Any]]:
    cleaned = raw.strip()
    wrappers_removed = False
    fences_removed = False
    without_wrappers = re.sub(r"<(think|analysis)[^>]*>.*?</\1>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if without_wrappers != cleaned:
        wrappers_removed = True
        cleaned = without_wrappers
    if "```" in cleaned:
        lines = cleaned.splitlines()
        next_cleaned = "\n".join(line for line in lines if not line.strip().startswith("```"))
        if next_cleaned != cleaned:
            fences_removed = True
            cleaned = next_cleaned
    return cleaned.strip(), {
        "wrapper_tags_removed": wrappers_removed,
        "code_fences_removed": fences_removed,
    }


def _extract_balanced_json_object(text: str) -> Optional[str]:
    for start_index, char in enumerate(text):
        if char != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for index in range(start_index, len(text)):
            current = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    return text[start_index:index + 1]
    return None


def _parse_json_candidate(candidate: Optional[str]) -> tuple[Optional[object], bool]:
    if not candidate:
        return None, False
    repaired_candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
    for index, raw_candidate in enumerate((candidate, repaired_candidate)):
        try:
            return json.loads(raw_candidate), index == 1 and repaired_candidate != candidate
        except json.JSONDecodeError:
            continue
    return None, False


def _schema_allows_type(schema: dict[str, Any], expected_type: str) -> bool:
    allowed_types = schema.get("type")
    if allowed_types is None:
        return False
    if isinstance(allowed_types, list):
        return expected_type in [str(item) for item in allowed_types]
    return str(allowed_types) == expected_type


def _coerce_schema_text_value(value: object) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        text = value
    elif isinstance(value, list):
        parts = [part for item in value if (part := _coerce_schema_text_value(item))]
        text = "\n".join(parts)
    elif isinstance(value, dict):
        if "text" in value:
            return _coerce_schema_text_value(value.get("text"))
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    stripped = text.strip()
    return stripped or None


def _is_extraction_state_schema(schema: dict[str, Any]) -> bool:
    enum_values = schema.get("enum")
    if not isinstance(enum_values, list):
        return False
    return {"found", "inferred", "unclear"}.issubset({str(item) for item in enum_values})


def _normalize_extraction_state_value(value: object, proposed_value: object = None) -> object:
    if value is None:
        return "found" if _coerce_schema_text_value(proposed_value) else "unclear"
    if not isinstance(value, str):
        return value
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    if normalized in {"found", "inferred", "unclear"}:
        return normalized
    if normalized in {"yes", "present", "visible", "clear", "success", "succeeded"}:
        return "found"
    if normalized == "possible":
        return "inferred"
    if normalized in {"propose", "proposed", "propose_value", "proposed_value"}:
        return "found" if _coerce_schema_text_value(proposed_value) else "unclear"
    return value


def _describe_schema_repairs(original: object, normalized: object, schema: dict[str, Any]) -> list[str]:
    repairs: list[str] = []
    if not isinstance(original, dict) or not isinstance(normalized, dict):
        return repairs
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    state_schema = properties.get("state")
    if (
        isinstance(state_schema, dict)
        and _is_extraction_state_schema(state_schema)
        and original.get("state") != normalized.get("state")
    ):
        repairs.append("state_synonym_normalized")
    numeric_schema = properties.get("numeric_value_form")
    if (
        isinstance(numeric_schema, dict)
        and original.get("numeric_value_form") != normalized.get("numeric_value_form")
    ):
        repairs.append("numeric_value_form_normalized")
    for field_name in schema.get("required", []):
        if field_name not in original and field_name in normalized:
            repairs.append(f"missing_{field_name}_defaulted")
    return repairs


def _normalize_value_for_schema(value: object, schema: dict[str, Any]) -> object:
    if value is None:
        return None

    if "enum" in schema and None in schema["enum"] and isinstance(value, str):
        stripped = value.strip().lower()
        if stripped in {"", "n/a", "na", "none", "null", "not applicable", "not_applicable"}:
            return None

    if _schema_allows_type(schema, "integer") and isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return int(stripped)

    if _schema_allows_type(schema, "string") and not isinstance(value, str):
        coerced = _coerce_schema_text_value(value)
        if coerced is not None:
            return coerced

    if isinstance(value, dict):
        properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        normalized = dict(value)
        for field_name, field_schema in properties.items():
            if field_name in normalized:
                normalized[field_name] = _normalize_value_for_schema(normalized[field_name], field_schema)
        state_schema = properties.get("state")
        if isinstance(state_schema, dict) and _is_extraction_state_schema(state_schema):
            normalized["state"] = _normalize_extraction_state_value(
                normalized.get("state"),
                normalized.get("proposed_value"),
            )
        for field_name in schema.get("required", []):
            if field_name in normalized:
                continue
            field_schema = properties.get(field_name)
            if not isinstance(field_schema, dict):
                continue
            if _schema_allows_type(field_schema, "null"):
                normalized[field_name] = None
            elif _schema_allows_type(field_schema, "array"):
                normalized[field_name] = []
            elif _schema_allows_type(field_schema, "boolean"):
                normalized[field_name] = False
        return normalized

    if isinstance(value, list) and _schema_allows_type(schema, "array"):
        item_schema = schema.get("items") if isinstance(schema.get("items"), dict) else {}
        return [_normalize_value_for_schema(item, item_schema) for item in value]

    return value


def _value_matches_json_type(value: object, expected_type: str) -> bool:
    if expected_type == "null":
        return value is None
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return (isinstance(value, int) or isinstance(value, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    return True


def _validate_against_schema(value: object, schema: dict, path: str = "$") -> None:
    allowed_types = schema.get("type")
    if allowed_types is not None:
        type_options = allowed_types if isinstance(allowed_types, list) else [allowed_types]
        if not any(_value_matches_json_type(value, str(option)) for option in type_options):
            expected = ", ".join(str(option) for option in type_options)
            actual = type(value).__name__
            raise StructuredOutputError(f"Schema validation failed at {path}: expected {expected}, got {actual}.")

    if "enum" in schema and value not in schema["enum"]:
        raise StructuredOutputError(f"Schema validation failed at {path}: value {value!r} is not in enum {schema['enum']!r}.")

    if value is None:
        return

    if isinstance(value, dict):
        required = schema.get("required", [])
        for field_name in required:
            if field_name not in value:
                raise StructuredOutputError(f"Schema validation failed at {path}: missing required field '{field_name}'.")
        for field_name, field_schema in schema.get("properties", {}).items():
            if field_name in value:
                _validate_against_schema(value[field_name], field_schema, f"{path}.{field_name}")
        return

    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            _validate_against_schema(item, schema["items"], f"{path}[{index}]")


def _parse_and_validate_response_with_details(
    raw: str,
    response_schema: dict,
    *,
    allow_degraded_normalization: bool = False,
) -> tuple[dict, dict[str, Any]]:
    parsed, details = _try_repair_json_with_metadata(raw)
    if allow_degraded_normalization and isinstance(parsed, dict):
        original_parsed = parsed
        normalized = _normalize_value_for_schema(parsed, response_schema)
        if isinstance(normalized, dict):
            parsed = normalized
            details["degraded_normalization_used"] = normalized != original_parsed
            repairs = _describe_schema_repairs(original_parsed, normalized, response_schema)
            if repairs:
                details["degraded_normalization_repairs"] = repairs
    if not isinstance(parsed, dict):
        error = StructuredOutputError(f"LM Studio returned malformed JSON after bounded recovery: {raw[:200]}")
        error.details = details
        raise error
    try:
        _validate_against_schema(parsed, response_schema)
    except StructuredOutputError as error:
        details["failure_stage"] = "schema_validation"
        details["validation_error"] = str(error)
        error.details = details
        raise
    details["failure_stage"] = "ok"
    return parsed, details


def _parse_and_validate_response(raw: str, response_schema: dict) -> dict:
    parsed, _details = _parse_and_validate_response_with_details(raw, response_schema)
    return parsed


def _should_retry_structured_output_error(error: StructuredOutputError) -> bool:
    details = getattr(error, "details", None)
    if isinstance(details, dict) and details.get("failure_stage") == "schema_validation":
        return False
    return getattr(error, "reason", None) != "structured_backend_incompatible"


def _classify_lm_studio_response_error(status_code: int, body_text: str) -> tuple[Optional[str], Optional[str]]:
    body_preview = body_text[:300]
    if status_code == 400 and re.search(r"failed to process regex|regex|grammar", body_text, flags=re.IGNORECASE):
        return (
            "structured_backend_incompatible",
            f"LM Studio rejected structured-output grammar/regex constraints: {body_preview}",
        )
    return None, None


def _fallback_modes_for(structured_mode: str) -> list[str]:
    if structured_mode == "json_schema":
        return ["json_schema", "json_object", "none"]
    if structured_mode == "json_object":
        return ["json_object", "none"]
    return ["none"]


def _coerce_message_content(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            coerced = _coerce_message_content(item)
            if coerced:
                parts.append(coerced)
        return "\n".join(parts).strip()
    if isinstance(raw, dict):
        if "text" in raw:
            return _coerce_message_content(raw.get("text"))
        return json.dumps(raw, ensure_ascii=False, sort_keys=True)
    return str(raw)


def _structured_message_content(message: dict[str, Any]) -> tuple[str, str]:
    """Return structured-output text from LM Studio message payloads.

    Some reasoning models can place the final JSON in `reasoning_content` while
    leaving the normal assistant `content` empty even when thinking is disabled.
    Treat that as a recoverable transport quirk instead of rejecting the model.
    """

    raw_content = message.get("content")
    content = _coerce_message_content(raw_content) if raw_content is not None else ""
    if content.strip():
        return content, "content"
    raw_reasoning_content = message.get("reasoning_content")
    reasoning_content = _coerce_message_content(raw_reasoning_content) if raw_reasoning_content is not None else ""
    if reasoning_content.strip():
        return reasoning_content, "reasoning_content"
    return content, "content"


_PROBE_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "proposed_value": {"type": ["string", "null"]},
        "state": {"type": "string", "enum": ["found", "unclear"]},
        "numeric_value_form": {"type": ["string", "null"], "enum": ["exact", "range", "approximate", None]},
        "primary_quote": {"type": ["string", "null"]},
        "primary_quote_page": {"type": ["integer", "null"]},
        "evidence_kind": {"type": "string", "enum": ["direct_quote", "inferred_reasoning", "calculation", "none"]},
    },
    "required": [
        "proposed_value",
        "state",
        "numeric_value_form",
        "primary_quote",
        "primary_quote_page",
        "evidence_kind",
    ],
}

_PROBE_TEXT = (
    "Return ONLY one JSON object with keys proposed_value, state, numeric_value_form, "
    "primary_quote, primary_quote_page, and evidence_kind. "
    "Use state='found', proposed_value='ok', numeric_value_form=null, primary_quote='ok', "
    "primary_quote_page=1, evidence_kind='direct_quote'."
)

_MINIMAL_PNG_DATA_URL = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sWcN4sAAAAASUVORK5CYII="
)


# ---------------------------------------------------------------------------
# LM Studio provider (T051)
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 300.0
DEFAULT_VISION_TIMEOUT = 420.0
DEFAULT_MODEL_LOAD_TIMEOUT = 600.0
DEFAULT_MODEL_UNLOAD_TIMEOUT = 180.0
DEFAULT_LOCK_TIMEOUT = 900.0
DEFAULT_RETRIES = 1  # bounded: one retry


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _default_lm_studio_lock_path(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        normalized = normalized[: -len("/v1")]
    normalized = normalized.replace("://localhost", "://127.0.0.1")
    key = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return str(os.path.join(tempfile.gettempdir(), f"papers_to_table_lm_studio_{key}.lock"))


class _LMStudioFileLock:
    def __init__(
        self,
        *,
        path: str,
        timeout_seconds: float,
        enabled: bool,
        owner: str,
        record_event: Any,
    ) -> None:
        self.path = path
        self.timeout_seconds = max(1.0, float(timeout_seconds or DEFAULT_LOCK_TIMEOUT))
        self.enabled = enabled
        self.owner = owner
        self.record_event = record_event
        self.acquired = False
        self.wait_ms = 0.0

    def __enter__(self) -> "_LMStudioFileLock":
        if not self.enabled:
            self.record_event("skipped", 0.0, None)
            return self

        start = perf_counter()
        deadline = time.monotonic() + self.timeout_seconds
        stale_seconds = max(self.timeout_seconds * 4.0, 3600.0)
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        last_error: Optional[Exception] = None
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    payload = {
                        "owner": self.owner,
                        "pid": os.getpid(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    json.dump(payload, handle, sort_keys=True)
                self.acquired = True
                self.wait_ms = round((perf_counter() - start) * 1000.0, 3)
                self.record_event("acquired", self.wait_ms, None)
                return self
            except FileExistsError as exc:
                last_error = exc
                try:
                    age = time.time() - os.path.getmtime(self.path)
                    if age > stale_seconds:
                        os.remove(self.path)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    self.wait_ms = round((perf_counter() - start) * 1000.0, 3)
                    self.record_event("timeout", self.wait_ms, str(last_error))
                    raise ProviderTimeoutError(
                        f"Timed out waiting {self.timeout_seconds:.1f}s for LM Studio lock {self.path}",
                        reason="lm_studio_lock_timeout",
                        details={"lock_path": self.path, "owner": self.owner, "wait_ms": self.wait_ms},
                    ) from last_error
                time.sleep(0.2)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.acquired:
            try:
                os.remove(self.path)
                self.record_event("released", self.wait_ms, None)
            except OSError as error:
                self.record_event("release_failed", self.wait_ms, str(error))


class LMStudioProvider(ProviderAdapter):
    """LM Studio localhost API integration.

    T051: implements the MVP local-first provider path.
    Uses the OpenAI-compatible /v1/chat/completions endpoint.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:1234",
        *,
        verbose_logging: bool = False,
        preview_limit: int = 240,
        text_model_config: Optional[object] = None,
        vision_model_config: Optional[object] = None,
        request_timeout_seconds: float = DEFAULT_TIMEOUT,
        vision_request_timeout_seconds: float = DEFAULT_VISION_TIMEOUT,
        model_load_timeout_seconds: float = DEFAULT_MODEL_LOAD_TIMEOUT,
        model_unload_timeout_seconds: float = DEFAULT_MODEL_UNLOAD_TIMEOUT,
        lock_enabled: bool = True,
        lock_timeout_seconds: float = DEFAULT_LOCK_TIMEOUT,
        lock_path: Optional[str] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._capabilities: Optional[ProviderCapabilities] = None
        self._verbose_logging = verbose_logging
        self._preview_limit = max(80, int(preview_limit or 240))
        self._request_timeout_seconds = float(request_timeout_seconds or DEFAULT_TIMEOUT)
        self._vision_request_timeout_seconds = float(vision_request_timeout_seconds or DEFAULT_VISION_TIMEOUT)
        self._model_load_timeout_seconds = float(model_load_timeout_seconds or DEFAULT_MODEL_LOAD_TIMEOUT)
        self._model_unload_timeout_seconds = float(model_unload_timeout_seconds or DEFAULT_MODEL_UNLOAD_TIMEOUT)
        self._lock_enabled = _env_bool("PAPER_TO_TABLE_LM_STUDIO_LOCK_ENABLED", bool(lock_enabled))
        self._lock_timeout_seconds = float(lock_timeout_seconds or DEFAULT_LOCK_TIMEOUT)
        self._lock_path = (
            os.environ.get("PAPER_TO_TABLE_LM_STUDIO_LOCK_PATH")
            or lock_path
            or _default_lm_studio_lock_path(self._base_url)
        )
        self._model_configs: dict[str, object] = {}
        for model_config in (text_model_config, vision_model_config):
            model_id = getattr(model_config, "model_id", None)
            if _has_explicit_model_id(model_id):
                self._model_configs[str(model_id)] = model_config
        self._request_counts: dict[str, int] = {
            "http_total": 0,
            "models_list": 0,
            "model_management_list": 0,
            "model_management_load": 0,
            "model_management_unload": 0,
            "completions_total": 0,
            "completions_text_raw": 0,
            "completions_text_structured": 0,
            "completions_vision_structured": 0,
            "completions_probe_structured": 0,
            "completion_retry_attempts": 0,
        }
        self._diagnostic_attempts: list[dict[str, Any]] = []
        self._probe_report: dict[str, Any] = {
            "provider": "lm_studio",
            "base_url": self._base_url,
            "logging_mode": "verbose" if self._verbose_logging else "standard",
            "text": None,
            "vision": None,
            "recorded_at": None,
        }
        self._trace_records: list[dict[str, Any]] = []
        self._pending_transport_metadata: Optional[dict[str, Any]] = None
        self._model_management_events: list[dict[str, Any]] = []
        self._model_management_counters: dict[str, int] = {
            "load_attempts": 0,
            "load_successes": 0,
            "load_failures": 0,
            "unload_attempts": 0,
            "unload_successes": 0,
            "unload_failures": 0,
            "model_switch_count": 0,
            "same_model_multi_instance_detected": 0,
            "channel_error_count": 0,
            "client_disconnected_count": 0,
            "model_load_canceled_count": 0,
            "generation_canceled_count": 0,
            "transition_conflict_count": 0,
            "lock_acquire_count": 0,
            "lock_timeout_count": 0,
            "lock_wait_ms_total": 0,
        }
        self._peak_loaded_llm_count = 0
        self._model_management_report: dict[str, Any] = {
            "provider": "lm_studio",
            "base_url": self._base_url,
            "timeouts": self._timeout_report(),
            "lock": self._lock_report(),
            "text_model": None,
            "vision_model": None,
            "recorded_at": None,
        }

    def _bump(self, key: str, amount: int = 1) -> None:
        self._request_counts[key] = self._request_counts.get(key, 0) + amount

    def get_request_counts(self) -> dict[str, int]:
        return dict(self._request_counts)

    def _timeout_report(self) -> dict[str, float]:
        return {
            "request_timeout_seconds": self._request_timeout_seconds,
            "vision_request_timeout_seconds": self._vision_request_timeout_seconds,
            "model_load_timeout_seconds": self._model_load_timeout_seconds,
            "model_unload_timeout_seconds": self._model_unload_timeout_seconds,
            "lm_studio_lock_timeout_seconds": self._lock_timeout_seconds,
        }

    def _lock_report(self) -> dict[str, Any]:
        return {
            "enabled": self._lock_enabled,
            "path": self._lock_path,
            "env_override_path": bool(os.environ.get("PAPER_TO_TABLE_LM_STUDIO_LOCK_PATH")),
        }

    def _record_lock_event(self, *, owner: str, status: str, wait_ms: float, error: Optional[str]) -> None:
        if status == "acquired":
            self._model_management_counters["lock_acquire_count"] += 1
            self._model_management_counters["lock_wait_ms_total"] += int(round(wait_ms))
        elif status == "timeout":
            self._model_management_counters["lock_timeout_count"] += 1
            self._model_management_counters["transition_conflict_count"] += 1
        self._record_model_management_event(
            phase="lm_studio_lock",
            action=owner,
            status=status,
            details={"lock_path": self._lock_path, "wait_ms": wait_ms, "error": error},
        )

    def _lm_studio_lock(self, owner: str) -> _LMStudioFileLock:
        return _LMStudioFileLock(
            path=self._lock_path,
            timeout_seconds=self._lock_timeout_seconds,
            enabled=self._lock_enabled,
            owner=owner,
            record_event=lambda status, wait_ms, error: self._record_lock_event(
                owner=owner,
                status=status,
                wait_ms=wait_ms,
                error=error,
            ),
        )

    def get_diagnostics(self) -> dict[str, Any]:
        attempts = list(self._diagnostic_attempts)
        by_outcome: dict[str, int] = {}
        by_request_kind: dict[str, int] = {}
        total_duration_ms = 0.0
        last_error: Optional[dict[str, Any]] = None
        for attempt in attempts:
            outcome = str(attempt.get("outcome") or "unknown")
            request_kind = str(attempt.get("request_kind") or "unknown")
            by_outcome[outcome] = by_outcome.get(outcome, 0) + 1
            by_request_kind[request_kind] = by_request_kind.get(request_kind, 0) + 1
            total_duration_ms += float(attempt.get("duration_ms", 0.0) or 0.0)
            if outcome != "success":
                last_error = {
                    "request_kind": request_kind,
                    "structured_mode": attempt.get("structured_mode"),
                    "error_reason": attempt.get("error_reason"),
                    "error_message": attempt.get("error_message"),
                    "http_status": attempt.get("http_status"),
                    "recorded_at": attempt.get("recorded_at"),
                }
        return {
            "logging_mode": "verbose" if self._verbose_logging else "standard",
            "attempt_count": len(attempts),
            "total_duration_ms": round(total_duration_ms, 3),
            "by_outcome": by_outcome,
            "by_request_kind": by_request_kind,
            "last_error": last_error,
            "attempts": attempts,
            "timeouts": self._timeout_report(),
            "lock": self._lock_report(),
            "model_management_counters": dict(self._model_management_counters),
        }

    def get_diagnostics_cursor(self) -> int:
        return len(self._diagnostic_attempts)

    def get_diagnostics_since(self, cursor: int) -> list[dict[str, Any]]:
        safe_cursor = max(0, int(cursor or 0))
        return [dict(item) for item in self._diagnostic_attempts[safe_cursor:]]

    def get_probe_report(self) -> dict[str, Any]:
        return dict(self._probe_report)

    def get_model_request_profile_report(self) -> dict[str, Any]:
        profiles: dict[str, Any] = {}
        for model_id in sorted(self._model_configs):
            policy = resolve_model_request_policy(model_id)
            profiles[model_id] = {
                "family": policy.family,
                "preferred_structured_mode": policy.preferred_structured_mode,
                "require_json_keyword": policy.require_json_keyword,
                "disable_thinking_reminder": policy.disable_thinking_reminder,
                "omit_max_tokens_for_structured": policy.omit_max_tokens_for_structured,
                "fast_abort_malformed_json_attempts": policy.fast_abort_malformed_json_attempts,
                "retry_malformed_structured_response": policy.retry_malformed_structured_response,
                "request_settings": self._effective_request_settings(
                    model_id=model_id,
                    max_tokens=None,
                    temperature=None,
                ),
            }
        return {
            "provider": "lm_studio",
            "base_url": self._base_url,
            "models": profiles,
        }

    def get_trace_records(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._trace_records]

    def get_model_management_report(self) -> dict[str, Any]:
        return dict(self._model_management_report)

    def _classify_operational_error(self, error_message: Optional[str]) -> Optional[str]:
        text = str(error_message or "").lower()
        if not text:
            return None
        if "channel error" in text:
            return "channel_error"
        if "client disconnected" in text:
            return "client_disconnected"
        if "operation canceled" in text and "load" in text:
            return "model_load_canceled"
        if "operation canceled" in text or "generation canceled" in text or "stopping generation" in text:
            return "generation_canceled"
        return None

    def _record_model_management_event(
        self,
        *,
        phase: str,
        action: str,
        status: str,
        model_id: Optional[str] = None,
        instance_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        event = {
            "sequence": len(self._model_management_events) + 1,
            "phase": phase,
            "action": action,
            "status": status,
            "model_id": model_id,
            "instance_id": instance_id,
            "details": details or {},
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._model_management_events.append(event)

    def _update_loaded_model_observability(self, models_payload: dict[str, Any]) -> dict[str, Any]:
        llm_loaded_count = 0
        same_model_multi_instance: list[dict[str, Any]] = []
        for model_entry in models_payload.get("models") or []:
            if not isinstance(model_entry, dict):
                continue
            loaded_instances = self._loaded_instance_summaries(model_entry)
            if str(model_entry.get("type") or "").lower() == "llm":
                llm_loaded_count += len(loaded_instances)
            if len(loaded_instances) > 1:
                same_model_multi_instance.append(
                    {
                        "model_id": str(model_entry.get("key") or ""),
                        "loaded_instances": loaded_instances,
                    }
                )
        self._peak_loaded_llm_count = max(self._peak_loaded_llm_count, llm_loaded_count)
        if same_model_multi_instance:
            self._model_management_counters["same_model_multi_instance_detected"] += len(same_model_multi_instance)
        return {
            "loaded_llm_instance_count": llm_loaded_count,
            "peak_loaded_llm_instance_count": self._peak_loaded_llm_count,
            "same_model_multi_instance": same_model_multi_instance,
        }

    def _truncate_preview(self, value: Optional[str], limit: int = 240) -> Optional[str]:
        if value is None:
            return None
        collapsed = re.sub(r"\s+", " ", value).strip()
        if not collapsed:
            return None
        effective_limit = max(40, int(limit or self._preview_limit))
        if len(collapsed) <= effective_limit:
            return collapsed
        return collapsed[: effective_limit - 3] + "..."

    def _preview_for_logging(self, value: Optional[str]) -> Optional[str]:
        if not self._verbose_logging:
            return None
        return self._truncate_preview(value, self._preview_limit)

    def _summarize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        response_format = payload.get("response_format")
        messages = payload.get("messages") or []
        sampling_keys = [
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "presence_penalty",
            "repetition_penalty",
        ]
        request_settings = {
            key: payload.get(key)
            for key in ["max_tokens", *sampling_keys]
            if key in payload
        }
        if isinstance(payload.get("chat_template_kwargs"), dict):
            request_settings["chat_template_kwargs"] = dict(payload["chat_template_kwargs"])
        passthrough_keys = sorted(
            key
            for key in payload
            if key
            not in {
                "model",
                "messages",
                "max_tokens",
                "response_format",
                *sampling_keys,
                "chat_template_kwargs",
            }
        )
        summary: dict[str, Any] = {
            "model": payload.get("model"),
            "max_tokens": payload.get("max_tokens"),
            "temperature": payload.get("temperature"),
            "request_settings": request_settings,
            "extra_body_keys": passthrough_keys,
            "response_format_type": response_format.get("type") if isinstance(response_format, dict) else None,
            "message_count": len(messages),
            "message_roles": [msg.get("role") for msg in messages if isinstance(msg, dict)],
        }
        if not self._verbose_logging:
            return summary
        message_summaries: list[dict[str, Any]] = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                message_summaries.append(
                    {
                        "role": msg.get("role"),
                        "content_type": "text",
                        "char_count": len(content),
                        "preview": self._preview_for_logging(content),
                    }
                )
            elif isinstance(content, list):
                text_parts = [
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                ]
                image_count = sum(
                    1
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "image_url"
                )
                joined_text = "\n".join(part for part in text_parts if part)
                message_summaries.append(
                    {
                        "role": msg.get("role"),
                        "content_type": "multimodal",
                        "text_char_count": len(joined_text),
                        "text_preview": self._preview_for_logging(joined_text),
                        "image_count": image_count,
                    }
                )
        if message_summaries:
            summary["messages"] = message_summaries
        if isinstance(response_format, dict):
            response_summary = {"type": response_format.get("type")}
            if response_format.get("type") == "json_schema":
                json_schema = response_format.get("json_schema") or {}
                schema = json_schema.get("schema") or {}
                response_summary["schema_name"] = json_schema.get("name")
                response_summary["strict"] = json_schema.get("strict")
                response_summary["schema_required"] = schema.get("required", [])
                response_summary["schema_property_count"] = len(schema.get("properties", {}))
            summary["response_format"] = response_summary
        return summary

    def _config_field_was_set(self, model_config: Optional[object], field_name: str) -> bool:
        if model_config is None:
            return False
        fields_set = getattr(model_config, "model_fields_set", set())
        return field_name in fields_set

    def _dict_from_model_config(self, model_config: Optional[object], field_name: str) -> dict[str, Any]:
        value = getattr(model_config, field_name, None) if model_config is not None else None
        return dict(value) if isinstance(value, dict) else {}

    def _effective_request_settings(
        self,
        *,
        model_id: str,
        max_tokens: Optional[int],
        temperature: Optional[float],
        structured: bool = True,
    ) -> dict[str, Any]:
        policy = resolve_model_request_policy(model_id)
        model_config = self._model_configs.get(model_id)
        payload: dict[str, Any] = dict(policy.request_defaults or {})

        for field_name in [
            "temperature",
            "top_p",
            "top_k",
            "min_p",
            "presence_penalty",
            "repetition_penalty",
        ]:
            value = getattr(model_config, field_name, None) if model_config is not None else None
            if value is not None and (field_name != "temperature" or self._config_field_was_set(model_config, field_name)):
                payload[field_name] = value

        if temperature is not None:
            payload["temperature"] = temperature
        if "temperature" not in payload:
            payload["temperature"] = 0.0

        if max_tokens is not None and (not structured or not policy.omit_max_tokens_for_structured):
            payload["max_tokens"] = max_tokens

        chat_template_kwargs = {
            **dict(policy.chat_template_kwargs_defaults or {}),
            **self._dict_from_model_config(model_config, "chat_template_kwargs"),
        }
        extra_body = {
            **dict(policy.extra_body_defaults or {}),
            **self._dict_from_model_config(model_config, "extra_body"),
        }
        if chat_template_kwargs:
            payload["chat_template_kwargs"] = chat_template_kwargs
        payload.update(extra_body)
        return payload

    def _append_trace_record(self, record: dict[str, Any]) -> None:
        if not self._verbose_logging:
            return
        enriched = dict(record)
        enriched["sequence"] = len(self._trace_records) + 1
        enriched["recorded_at"] = datetime.now(timezone.utc).isoformat()
        self._trace_records.append(enriched)

    def _set_pending_transport_metadata(
        self,
        *,
        request_kind: str,
        structured_mode: Optional[str],
        model_id: str,
        duration_ms: float,
        http_status: Optional[int],
        raw_preview: Optional[str] = None,
        payload_summary: Optional[dict[str, Any]] = None,
    ) -> None:
        self._pending_transport_metadata = {
            "request_kind": request_kind,
            "structured_mode": structured_mode,
            "model_id": model_id,
            "duration_ms": round(duration_ms, 3),
            "http_status": http_status,
            "raw_preview": self._preview_for_logging(raw_preview),
            "payload_summary": payload_summary,
        }

    def _consume_pending_transport_metadata(
        self,
        *,
        request_kind: str,
        structured_mode: Optional[str],
        model_id: str,
        fallback_duration_ms: float,
        raw_preview: Optional[str] = None,
        payload_summary: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        pending = self._pending_transport_metadata or {
            "request_kind": request_kind,
            "structured_mode": structured_mode,
            "model_id": model_id,
            "duration_ms": round(fallback_duration_ms, 3),
            "http_status": None,
            "raw_preview": self._preview_for_logging(raw_preview),
            "payload_summary": payload_summary,
        }
        self._pending_transport_metadata = None
        if raw_preview and not pending.get("raw_preview"):
            pending["raw_preview"] = self._preview_for_logging(raw_preview)
        if payload_summary and not pending.get("payload_summary"):
            pending["payload_summary"] = payload_summary
        return pending

    def _record_attempt(
        self,
        *,
        request_kind: str,
        structured_mode: Optional[str],
        model_id: str,
        outcome: str,
        duration_ms: float,
        http_status: Optional[int] = None,
        error_reason: Optional[str] = None,
        error_message: Optional[str] = None,
        raw_preview: Optional[str] = None,
        phase: str = "request",
        error_details: Optional[dict[str, Any]] = None,
        payload_summary: Optional[dict[str, Any]] = None,
    ) -> None:
        self._diagnostic_attempts.append(
            {
                "sequence": len(self._diagnostic_attempts) + 1,
                "phase": phase,
                "request_kind": request_kind,
                "structured_mode": structured_mode,
                "model_id": model_id,
                "outcome": outcome,
                "duration_ms": round(duration_ms, 3),
                "http_status": http_status,
                "error_reason": error_reason,
                "error_message": self._truncate_preview(error_message),
                "error_details": error_details,
                "raw_preview": self._preview_for_logging(raw_preview),
                "payload_summary": payload_summary if self._verbose_logging else None,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    def _record_exception_attempt(
        self,
        *,
        request_kind: str,
        structured_mode: Optional[str],
        model_id: str,
        duration_ms: float,
        error: Exception,
    ) -> None:
        if isinstance(error, ModelUnavailableError):
            outcome = "model_unavailable"
        elif getattr(error, "reason", None) == "model_load_failed":
            outcome = "model_load_failed"
        elif isinstance(error, ProviderTimeoutError):
            outcome = "timeout"
        elif isinstance(error, StructuredOutputError):
            reason = getattr(error, "reason", None)
            outcome = "structured_backend_incompatible" if reason == "structured_backend_incompatible" else "structured_output_error"
        else:
            outcome = "provider_error"
        error_classification = self._classify_operational_error(str(error))
        if error_classification == "channel_error":
            self._model_management_counters["channel_error_count"] += 1
        elif error_classification == "client_disconnected":
            self._model_management_counters["client_disconnected_count"] += 1
        elif error_classification == "model_load_canceled":
            self._model_management_counters["model_load_canceled_count"] += 1
        elif error_classification == "generation_canceled":
            self._model_management_counters["generation_canceled_count"] += 1
        self._record_attempt(
            request_kind=request_kind,
            structured_mode=structured_mode,
            model_id=model_id,
            outcome=outcome,
            duration_ms=duration_ms,
            error_reason=getattr(error, "reason", None),
            error_message=str(error),
            error_details={
                **(getattr(error, "details", None) or {}),
                "operational_error_classification": error_classification,
            },
        )

    def _rest_url(self, path: str) -> str:
        return f"{self._base_url}{path}"

    @staticmethod
    def _coerce_positive_int(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    @classmethod
    def _loaded_instance_context_length(cls, instance: dict[str, Any]) -> Optional[int]:
        config = instance.get("config") or {}
        return cls._coerce_positive_int(config.get("context_length"))

    @staticmethod
    def _model_matches_requested_id(model_entry: dict[str, Any], model_id: str) -> bool:
        if str(model_entry.get("key") or "") == model_id:
            return True
        loaded_instances = model_entry.get("loaded_instances") or []
        return any(str(instance.get("id") or "") == model_id for instance in loaded_instances)

    @classmethod
    def _find_requested_model(cls, models_payload: dict[str, Any], model_id: str) -> Optional[dict[str, Any]]:
        models = models_payload.get("models") or []
        for model_entry in models:
            if isinstance(model_entry, dict) and cls._model_matches_requested_id(model_entry, model_id):
                return model_entry
        return None

    @classmethod
    def _find_compatible_loaded_instance(
        cls,
        model_entry: dict[str, Any],
        required_load_context: Optional[int],
    ) -> Optional[dict[str, Any]]:
        loaded_instances = model_entry.get("loaded_instances") or []
        compatible: list[tuple[int, dict[str, Any]]] = []
        for instance in loaded_instances:
            if not isinstance(instance, dict):
                continue
            context_length = cls._loaded_instance_context_length(instance)
            if required_load_context is None:
                compatible.append((context_length or 0, instance))
                continue
            if context_length is not None and context_length >= required_load_context:
                compatible.append((context_length, instance))
        if not compatible:
            return None
        compatible.sort(key=lambda item: item[0])
        return compatible[0][1]

    @classmethod
    def _loaded_instance_summaries(cls, model_entry: dict[str, Any]) -> list[dict[str, Any]]:
        loaded_instances = model_entry.get("loaded_instances") or []
        summaries: list[dict[str, Any]] = []
        for instance in loaded_instances:
            if not isinstance(instance, dict):
                continue
            summaries.append(
                {
                    "instance_id": instance.get("id"),
                    "context_length": cls._loaded_instance_context_length(instance),
                    "config": instance.get("config") or {},
                }
            )
        return summaries

    @classmethod
    def _loaded_instances_for_model_ids(
        cls,
        models_payload: dict[str, Any],
        requested_model_ids: dict[str, Optional[int]],
    ) -> set[str]:
        keep_instance_ids: set[str] = set()
        for model_id, required_load_context in requested_model_ids.items():
            if not _has_explicit_model_id(model_id):
                continue
            model_entry = cls._find_requested_model(models_payload, model_id)
            if model_entry is None:
                continue
            compatible = cls._find_compatible_loaded_instance(model_entry, required_load_context)
            if compatible is None:
                continue
            instance_id = str(compatible.get("id") or "")
            if instance_id:
                keep_instance_ids.add(instance_id)
        return keep_instance_ids

    @classmethod
    def _plan_model_unloads(
        cls,
        models_payload: dict[str, Any],
        requested_model_ids: dict[str, Optional[int]],
    ) -> list[dict[str, Any]]:
        keep_instance_ids = cls._loaded_instances_for_model_ids(models_payload, requested_model_ids)
        unloads: list[dict[str, Any]] = []
        for model_entry in models_payload.get("models") or []:
            if not isinstance(model_entry, dict):
                continue
            model_key = str(model_entry.get("key") or "")
            for instance in model_entry.get("loaded_instances") or []:
                if not isinstance(instance, dict):
                    continue
                instance_id = str(instance.get("id") or "")
                if not instance_id or instance_id in keep_instance_ids:
                    continue
                unloads.append(
                    {
                        "instance_id": instance_id,
                        "model_id": model_key,
                        "context_length": cls._loaded_instance_context_length(instance),
                    }
                )
        return unloads

    async def _list_rest_models(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                self._bump("http_total")
                self._bump("model_management_list")
                resp = await client.get(self._rest_url("/api/v1/models"))
            if resp.status_code != 200:
                raise ProviderError(
                    f"LM Studio model-management API at {self._rest_url('/api/v1/models')} returned HTTP {resp.status_code}.",
                    reason="provider_unreachable",
                )
            return resp.json()
        except ProviderError:
            raise
        except Exception as error:
            raise ProviderError(
                f"Cannot reach LM Studio model-management API at {self._rest_url('/api/v1/models')}: {error}",
                reason="provider_unreachable",
            ) from error

    async def _load_model_via_rest(
        self,
        *,
        role: str,
        model_id: str,
        required_load_context: Optional[int],
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model_id,
            "echo_load_config": True,
        }
        if required_load_context is not None:
            payload["context_length"] = required_load_context

        load_started = perf_counter()
        try:
            self._model_management_counters["load_attempts"] += 1
            with self._lm_studio_lock(f"load:{role}:{model_id}"):
                async with httpx.AsyncClient(timeout=self._model_load_timeout_seconds) as client:
                    self._bump("http_total")
                    self._bump("model_management_load")
                    resp = await client.post(self._rest_url("/api/v1/models/load"), json=payload)
            duration_ms = (perf_counter() - load_started) * 1000.0
            if resp.status_code != 200:
                message = (
                    f"LM Studio failed to load {role} model '{model_id}' via /api/v1/models/load "
                    f"(HTTP {resp.status_code}): {resp.text[:300]}"
                )
                error = ProviderError(message, reason="model_load_failed")
                self._record_exception_attempt(
                    request_kind=f"{role}_model_load",
                    structured_mode=None,
                    model_id=model_id,
                    duration_ms=duration_ms,
                    error=error,
                )
                raise error

            response_data = resp.json()
            self._record_attempt(
                request_kind=f"{role}_model_load",
                structured_mode=None,
                model_id=model_id,
                outcome="success",
                duration_ms=duration_ms,
                http_status=resp.status_code,
                raw_preview=resp.text,
                phase="model_management",
                payload_summary=self._summarize_payload(payload),
            )
            self._model_management_counters["load_successes"] += 1
            self._record_model_management_event(
                phase="model_management",
                action="load",
                status="success",
                model_id=model_id,
                instance_id=response_data.get("instance_id"),
                details={"role": role, "required_load_context": required_load_context},
            )
            return response_data
        except ProviderError:
            self._model_management_counters["load_failures"] += 1
            raise
        except Exception as error:
            duration_ms = (perf_counter() - load_started) * 1000.0
            wrapped = ProviderError(
                f"LM Studio model load request failed for {role} model '{model_id}': {error}",
                reason="model_load_failed",
            )
            self._record_exception_attempt(
                request_kind=f"{role}_model_load",
                structured_mode=None,
                model_id=model_id,
                duration_ms=duration_ms,
                error=wrapped,
            )
            self._model_management_counters["load_failures"] += 1
            self._record_model_management_event(
                phase="model_management",
                action="load",
                status="failed",
                model_id=model_id,
                details={"role": role, "required_load_context": required_load_context},
            )
            raise wrapped from error

    async def _unload_model_via_rest(self, *, instance_id: str) -> dict[str, Any]:
        payload = {"instance_id": instance_id}
        load_started = perf_counter()
        try:
            self._model_management_counters["unload_attempts"] += 1
            with self._lm_studio_lock(f"unload:{instance_id}"):
                async with httpx.AsyncClient(timeout=self._model_unload_timeout_seconds) as client:
                    self._bump("http_total")
                    self._bump("model_management_unload")
                    resp = await client.post(self._rest_url("/api/v1/models/unload"), json=payload)
            duration_ms = (perf_counter() - load_started) * 1000.0
            if resp.status_code != 200:
                message = (
                    f"LM Studio failed to unload model instance '{instance_id}' via /api/v1/models/unload "
                    f"(HTTP {resp.status_code}): {resp.text[:300]}"
                )
                error = ProviderError(message, reason="model_unload_failed")
                self._record_exception_attempt(
                    request_kind="model_unload",
                    structured_mode=None,
                    model_id=instance_id,
                    duration_ms=duration_ms,
                    error=error,
                )
                raise error
            response_data = resp.json()
            self._record_attempt(
                request_kind="model_unload",
                structured_mode=None,
                model_id=instance_id,
                outcome="success",
                duration_ms=duration_ms,
                http_status=resp.status_code,
                raw_preview=resp.text,
                phase="model_management",
                payload_summary=self._summarize_payload(payload),
            )
            self._model_management_counters["unload_successes"] += 1
            self._record_model_management_event(
                phase="model_management",
                action="unload",
                status="success",
                instance_id=instance_id,
            )
            return response_data
        except ProviderError:
            self._model_management_counters["unload_failures"] += 1
            raise
        except Exception as error:
            duration_ms = (perf_counter() - load_started) * 1000.0
            wrapped = ProviderError(
                f"LM Studio model unload request failed for instance '{instance_id}': {error}",
                reason="model_unload_failed",
            )
            self._record_exception_attempt(
                request_kind="model_unload",
                structured_mode=None,
                model_id=instance_id,
                duration_ms=duration_ms,
                error=wrapped,
            )
            self._model_management_counters["unload_failures"] += 1
            self._record_model_management_event(
                phase="model_management",
                action="unload",
                status="failed",
                instance_id=instance_id,
            )
            raise wrapped from error

    async def _ensure_role_model_ready(
        self,
        *,
        role: str,
        model_id: str,
        required_load_context: Optional[int],
        working_context_budget: Optional[int] = None,
        load_context_is_derived: Optional[bool] = None,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "model_id": model_id,
            "working_context_budget": working_context_budget,
            "configured_load_context": None if load_context_is_derived else required_load_context,
            "requested_load_context": required_load_context,
            "load_context_is_derived": bool(load_context_is_derived),
            "load_requested": False,
            "reused_loaded_model": False,
            "loaded_instance_id": None,
            "loaded_instance_context_length": None,
            "existing_loaded_instances": [],
            "max_context_length": None,
            "actual_load_config": None,
            "load_time_seconds": None,
            "status": "pending",
            "failure": None,
        }

        models_payload = await self._list_rest_models()
        model_entry = self._find_requested_model(models_payload, model_id)
        if model_entry is None:
            message = (
                f"Configured {role} model '{model_id}' is not available in LM Studio. "
                "Download it in LM Studio or update the configured model id."
            )
            report["status"] = "failed"
            report["failure"] = {"reason": "model_unavailable", "message": message}
            raise ModelUnavailableError(
                message,
                details={"model_management": report},
            )

        report["existing_loaded_instances"] = self._loaded_instance_summaries(model_entry)
        report["max_context_length"] = self._coerce_positive_int(model_entry.get("max_context_length"))

        if (
            required_load_context is not None
            and report["max_context_length"] is not None
            and required_load_context > report["max_context_length"]
        ):
            message = (
                f"Configured {role} model '{model_id}' cannot satisfy requested load context "
                f"{required_load_context}; LM Studio reports max_context_length={report['max_context_length']}."
            )
            report["status"] = "failed"
            report["failure"] = {"reason": "model_load_failed", "message": message}
            raise ProviderError(
                message,
                reason="model_load_failed",
                details={"model_management": report},
            )

        compatible_instance = self._find_compatible_loaded_instance(model_entry, required_load_context)
        if compatible_instance is not None:
            report["reused_loaded_model"] = True
            report["loaded_instance_id"] = compatible_instance.get("id")
            report["loaded_instance_context_length"] = self._loaded_instance_context_length(compatible_instance)
            report["actual_load_config"] = compatible_instance.get("config") or {}
            report["status"] = "reused_loaded_instance"
            return report

        try:
            load_result = await self._load_model_via_rest(
                role=role,
                model_id=model_id,
                required_load_context=required_load_context,
            )
        except ProviderError as error:
            report["status"] = "failed"
            report["load_requested"] = True
            report["failure"] = {
                "reason": getattr(error, "reason", None) or "model_load_failed",
                "message": str(error),
            }
            raise ProviderError(
                str(error),
                recoverable=getattr(error, "recoverable", False),
                reason=getattr(error, "reason", None) or "model_load_failed",
                details={"model_management": report},
            ) from error
        report["load_requested"] = True
        report["loaded_instance_id"] = load_result.get("instance_id")
        report["load_time_seconds"] = load_result.get("load_time_seconds")
        report["actual_load_config"] = load_result.get("load_config")
        report["loaded_instance_context_length"] = self._coerce_positive_int(
            (load_result.get("load_config") or {}).get("context_length")
        )
        report["status"] = "loaded_via_api"
        return report

    async def ensure_model_availability(
        self,
        *,
        text_model_id: str,
        text_working_context_budget: Optional[int] = None,
        text_load_context_length: Optional[int] = None,
        text_load_context_is_derived: bool = False,
        vision_model_id: Optional[str] = None,
        vision_load_context_length: Optional[int] = None,
    ) -> dict[str, Any]:
        report: dict[str, Any] = {
            "provider": "lm_studio",
            "base_url": self._base_url,
            "timeouts": self._timeout_report(),
            "lock": self._lock_report(),
            "text_model": None,
            "vision_model": None,
            "unloads": {
                "attempted": [],
                "succeeded": [],
                "failed": [],
            },
            "residency_policy": {
                "target_loaded_llm_instances": 1,
                "max_loaded_llm_instances": 2,
            },
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            requested_model_ids = {
                text_model_id: text_load_context_length,
            }
            if vision_model_id is not None and _has_explicit_model_id(vision_model_id):
                requested_model_ids[vision_model_id] = vision_load_context_length

            preflight_models = await self._list_rest_models()
            report["preflight_state"] = self._update_loaded_model_observability(preflight_models)
            keep_instance_ids = self._loaded_instances_for_model_ids(preflight_models, requested_model_ids)
            unload_plan = self._plan_model_unloads(preflight_models, requested_model_ids)
            if unload_plan:
                report["unloads"]["attempted"] = unload_plan
                for unload_item in unload_plan:
                    try:
                        response = await self._unload_model_via_rest(instance_id=unload_item["instance_id"])
                        report["unloads"]["succeeded"].append(
                            {
                                **unload_item,
                                "response_instance_id": response.get("instance_id"),
                            }
                        )
                    except ProviderError as error:
                        report["unloads"]["failed"].append(
                            {
                                **unload_item,
                                "reason": getattr(error, "reason", None),
                                "message": str(error),
                            }
                        )

            text_report = await self._ensure_role_model_ready(
                role="text",
                model_id=text_model_id,
                required_load_context=text_load_context_length,
                working_context_budget=text_working_context_budget,
                load_context_is_derived=text_load_context_is_derived,
            )
            report["text_model"] = text_report

            if vision_model_id is not None and _has_explicit_model_id(vision_model_id):
                vision_report = await self._ensure_role_model_ready(
                    role="vision",
                    model_id=vision_model_id,
                    required_load_context=vision_load_context_length,
                )
                report["vision_model"] = vision_report
            postflight_models = await self._list_rest_models()
            report["postflight_state"] = self._update_loaded_model_observability(postflight_models)
            report["timeline"] = list(self._model_management_events)
            report["counters"] = dict(self._model_management_counters)
            report["switch_required"] = bool(report["unloads"]["attempted"] or (text_report or {}).get("load_requested"))
            if report["switch_required"]:
                self._model_management_counters["model_switch_count"] += 1
                report["counters"] = dict(self._model_management_counters)
            self._model_management_report = report
            return report
        except ProviderError as error:
            details = dict(getattr(error, "details", None) or {})
            role_report = details.get("model_management")
            if isinstance(role_report, dict):
                failed_model_id = role_report.get("model_id")
                if failed_model_id == vision_model_id:
                    report["vision_model"] = role_report
                else:
                    report["text_model"] = role_report
            self._model_management_report = report
            raise ProviderError(
                str(error),
                recoverable=getattr(error, "recoverable", False),
                reason=getattr(error, "reason", None),
                details={"model_management": report},
            ) from error

    async def cleanup_model_residency(
        self,
        *,
        keep_model_ids: list[str] | None = None,
        phase_label: str = "phase_cleanup",
    ) -> dict[str, Any]:
        keep_requested = {
            model_id: None
            for model_id in (keep_model_ids or [])
            if _has_explicit_model_id(model_id)
        }
        before = await self._list_rest_models()
        before_state = self._update_loaded_model_observability(before)
        unload_plan = self._plan_model_unloads(before, keep_requested)
        report = {
            "phase_label": phase_label,
            "keep_model_ids": sorted(keep_requested.keys()),
            "before_state": before_state,
            "attempted": list(unload_plan),
            "succeeded": [],
            "failed": [],
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._record_model_management_event(
            phase=phase_label,
            action="cleanup_begin",
            status="started",
            details={"keep_model_ids": report["keep_model_ids"]},
        )
        for unload_item in unload_plan:
            try:
                response = await self._unload_model_via_rest(instance_id=unload_item["instance_id"])
                report["succeeded"].append(
                    {**unload_item, "response_instance_id": response.get("instance_id")}
                )
            except ProviderError as error:
                report["failed"].append(
                    {
                        **unload_item,
                        "reason": getattr(error, "reason", None),
                        "message": str(error),
                    }
                )
        after = await self._list_rest_models()
        report["after_state"] = self._update_loaded_model_observability(after)
        self._record_model_management_event(
            phase=phase_label,
            action="cleanup_end",
            status="completed" if not report["failed"] else "completed_with_failures",
            details={
                "attempted": len(report["attempted"]),
                "succeeded": len(report["succeeded"]),
                "failed": len(report["failed"]),
            },
        )
        self._model_management_report = {
            **dict(self._model_management_report),
            "last_cleanup": report,
            "timeouts": self._timeout_report(),
            "lock": self._lock_report(),
            "timeline": list(self._model_management_events),
            "counters": dict(self._model_management_counters),
        }
        return report

    @property
    def token(self) -> str:
        return "lm_studio"

    @property
    def locality(self) -> ProviderLocality:
        return ProviderLocality.local

    # --- Capability probing (T050) ---

    async def probe_capabilities(
        self,
        text_model_id: str,
        vision_model_id: Optional[str] = None,
    ) -> ProviderCapabilities:
        """Check model availability and structured-output capability.

        Probes /v1/models to verify the model is loaded,
        then makes a minimal structured-output test request.
        T052: capability mismatch for one model must not poison other requests.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                self._bump("http_total")
                self._bump("models_list")
                resp = await client.get(f"{self._base_url}/v1/models")
                if resp.status_code != 200:
                    raise ProviderError(
                        f"LM Studio at {self._base_url} returned HTTP {resp.status_code}.",
                        reason="provider_unreachable",
                    )
                models_data = resp.json()
                available_ids = {
                    m.get("id", "") for m in models_data.get("data", [])
                }
        except ProviderError:
            raise
        except Exception as e:
            raise ProviderError(
                f"Cannot reach LM Studio at {self._base_url}: {e}",
                reason="provider_unreachable",
            ) from e

        if not _has_explicit_model_id(text_model_id):
            raise ProviderError(
                "provider.text_model.model_id must be set to a real LM Studio model id; "
                '"default" is not allowed.'
            )

        if text_model_id not in available_ids:
            raise ModelUnavailableError(
                f"Configured text model '{text_model_id}' is not loaded in LM Studio. "
                "Load that model or update provider.text_model.model_id."
            )

        if vision_model_id is not None and _has_explicit_model_id(vision_model_id):
            if vision_model_id not in available_ids:
                raise ModelUnavailableError(
                    f"Configured vision model '{vision_model_id}' is not loaded in LM Studio. "
                    "Load that model or update provider.vision_model.model_id."
                )

        effective_model = text_model_id
        structured_mode, structured_reason, structured_error, text_probe = await self._probe_structured_output_mode(
            effective_model,
            modality="text",
        )

        vision_structured_mode: Optional[str] = None
        vision_structured_reason: Optional[str] = None
        vision_structured_error: Optional[str] = None
        vision_probe: Optional[dict[str, Any]] = None
        if vision_model_id is not None and _has_explicit_model_id(vision_model_id):
            (
                vision_structured_mode,
                vision_structured_reason,
                vision_structured_error,
                vision_probe,
            ) = await self._probe_structured_output_mode(
                vision_model_id,
                modality="vision",
            )

        self._probe_report = {
            "provider": "lm_studio",
            "base_url": self._base_url,
            "logging_mode": "verbose" if self._verbose_logging else "standard",
            "text": text_probe,
            "vision": vision_probe,
            "recorded_at": now,
        }

        return ProviderCapabilities(
            supports_structured_output=structured_mode != "none",
            structured_output_mode=structured_mode,
            structured_output_reason=structured_reason,
            structured_output_error=structured_error,
            model_id=effective_model,
            vision_capable=vision_model_id is not None,
            vision_structured_output_mode=vision_structured_mode,
            vision_structured_output_reason=vision_structured_reason,
            vision_structured_output_error=vision_structured_error,
            probed_at=now,
        )

    def _build_probe_messages(self, modality: str) -> list[dict[str, Any]]:
        if modality == "vision":
            return [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROBE_TEXT},
                        {"type": "image_url", "image_url": {"url": _MINIMAL_PNG_DATA_URL}},
                    ],
                }
            ]
        return [{"role": "user", "content": _PROBE_TEXT}]

    async def _probe_structured_output_mode(
        self,
        model_id: str,
        *,
        modality: str,
    ) -> tuple[str, Optional[str], Optional[str], dict[str, Any]]:
        """Probe best supported structured mode for a text or vision request shape."""

        async def _run_probe(mode: str) -> tuple[bool, Optional[str], Optional[str], dict[str, Any]]:
            policy = resolve_model_request_policy(model_id)
            payload: dict[str, Any] = {
                "model": model_id,
                "messages": policy.apply_messages(self._build_probe_messages(modality), mode),
                **self._effective_request_settings(
                    model_id=model_id,
                    max_tokens=96,
                    temperature=None,
                ),
            }
            if mode == "json_schema":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": f"{modality}_probe", "schema": _PROBE_RESPONSE_SCHEMA},
                }
            elif mode == "json_object":
                payload["response_format"] = {"type": "json_object"}

            payload_summary = self._summarize_payload(payload)
            started = perf_counter()
            record: dict[str, Any] = {
                "modality": modality,
                "model_id": model_id,
                "structured_mode": mode,
                "supported": False,
                "payload_summary": payload_summary if self._verbose_logging else None,
            }
            try:
                with self._lm_studio_lock(f"probe:{modality}:{model_id}:{mode}"):
                    async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                        self._bump("http_total")
                        self._bump("completions_total")
                        self._bump("completions_probe_structured")
                        resp = await client.post(
                            f"{self._base_url}/v1/chat/completions", json=payload
                        )
                duration_ms = round((perf_counter() - started) * 1000.0, 3)
                record["duration_ms"] = duration_ms
                record["http_status"] = resp.status_code
                if resp.status_code == 200:
                    content, content_source = _structured_message_content(resp.json()["choices"][0]["message"])
                    try:
                        _parsed, parse_details = _parse_and_validate_response_with_details(content, _PROBE_RESPONSE_SCHEMA)
                        record["supported"] = True
                        record["parse_details"] = parse_details
                        record["response_preview"] = self._preview_for_logging(content)
                        record["message_content_source"] = content_source
                        self._append_trace_record(
                            {
                                "phase": "probe",
                                "request_kind": f"{modality}_probe",
                                "structured_mode": mode,
                                "model_id": model_id,
                                "outcome": "success",
                                "duration_ms": duration_ms,
                                "http_status": resp.status_code,
                                "payload_summary": payload_summary,
                                "response_preview": self._preview_for_logging(content),
                                "message_content_source": content_source,
                                "parse_details": parse_details,
                            }
                        )
                        return True, None, None, record
                    except StructuredOutputError as error:
                        details = getattr(error, "details", None)
                        record["error_reason"] = getattr(error, "reason", None)
                        record["error_message"] = str(error)
                        record["parse_details"] = details
                        record["response_preview"] = self._preview_for_logging(content)
                        record["message_content_source"] = content_source
                        self._append_trace_record(
                            {
                                "phase": "probe",
                                "request_kind": f"{modality}_probe",
                                "structured_mode": mode,
                                "model_id": model_id,
                                "outcome": "structured_output_error",
                                "duration_ms": duration_ms,
                                "http_status": resp.status_code,
                                "payload_summary": payload_summary,
                                "response_preview": self._preview_for_logging(content),
                                "message_content_source": content_source,
                                "parse_details": details,
                                "error_message": str(error),
                            }
                        )
                        return False, getattr(error, "reason", None), str(error), record

                reason, message = _classify_lm_studio_response_error(resp.status_code, resp.text)
                record["error_reason"] = reason
                record["error_message"] = message or self._truncate_preview(resp.text, 300)
                record["response_preview"] = self._preview_for_logging(resp.text)
                self._append_trace_record(
                    {
                        "phase": "probe",
                        "request_kind": f"{modality}_probe",
                        "structured_mode": mode,
                        "model_id": model_id,
                        "outcome": "structured_backend_incompatible" if reason == "structured_backend_incompatible" else "provider_error",
                        "duration_ms": duration_ms,
                        "http_status": resp.status_code,
                        "payload_summary": payload_summary,
                        "response_preview": self._preview_for_logging(resp.text),
                        "error_reason": reason,
                        "error_message": message or self._truncate_preview(resp.text, 300),
                    }
                )
                return False, reason, message or self._truncate_preview(resp.text, 300), record
            except Exception as error:
                duration_ms = round((perf_counter() - started) * 1000.0, 3)
                record["duration_ms"] = duration_ms
                record["error_reason"] = "probe_exception"
                record["error_message"] = self._truncate_preview(str(error), 300)
                self._append_trace_record(
                    {
                        "phase": "probe",
                        "request_kind": f"{modality}_probe",
                        "structured_mode": mode,
                        "model_id": model_id,
                        "outcome": "provider_error",
                        "duration_ms": duration_ms,
                        "payload_summary": payload_summary,
                        "error_reason": "probe_exception",
                        "error_message": self._truncate_preview(str(error), 300),
                    }
                )
                return False, "probe_exception", self._truncate_preview(str(error), 300), record

        policy = resolve_model_request_policy(model_id)
        structured_reason: Optional[str] = None
        structured_error: Optional[str] = None
        probe_records: dict[str, dict[str, Any] | None] = {"json_schema": None, "json_object": None}
        for mode in policy.ordered_structured_modes("json_schema"):
            if mode == "none":
                continue
            ok, reason, error, record = await _run_probe(mode)
            probe_records[mode] = record
            if ok:
                report: dict[str, Any] = {
                    "modality": modality,
                    "model_id": model_id,
                    "best_mode": mode,
                    "json_schema": probe_records.get("json_schema"),
                    "json_object": probe_records.get("json_object"),
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
                fallback_reason = None if mode == "json_schema" else _canonical_structured_output_reason(mode, structured_reason)
                fallback_error = None if mode == "json_schema" else structured_error
                if fallback_reason == "json_schema_unsupported" and not fallback_error:
                    fallback_error = (
                        "LM Studio did not provide json_schema support for this model/runtime combination."
                    )
                return mode, fallback_reason, fallback_error, report
            if not structured_reason:
                structured_reason = reason
                structured_error = error

        report: dict[str, Any] = {
            "modality": modality,
            "model_id": model_id,
            "best_mode": None,
            "json_schema": probe_records.get("json_schema"),
            "json_object": probe_records.get("json_object"),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        report["best_mode"] = "none"
        structured_reason = _canonical_structured_output_reason("none", structured_reason)
        if structured_reason == "structured_modes_unavailable" and not structured_error:
            structured_error = (
                "LM Studio did not provide a compatible structured-output mode for this model/runtime combination."
            )
        return "none", structured_reason, structured_error, report

    # --- Text completion ---

    async def text_complete_raw(
        self,
        system: str,
        user: str,
        max_tokens: int = 512,
        model_id: str = "",
    ) -> str:
        """Simple text completion, returns assistant content as string."""
        if not _has_explicit_model_id(model_id):
            raise ProviderError(
                "LM Studio text completion requires an explicit model_id; "
                '"default" is not allowed.'
            )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            **self._effective_request_settings(
                model_id=model_id,
                max_tokens=max_tokens,
                temperature=None,
                structured=False,
            ),
        }
        try:
            with self._lm_studio_lock(f"text_raw:{model_id}"):
                async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                    self._bump("http_total")
                    self._bump("completions_total")
                    self._bump("completions_text_raw")
                    resp = await client.post(
                        f"{self._base_url}/v1/chat/completions", json=payload
                    )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                raise ProviderError(
                    f"LM Studio returned HTTP {resp.status_code}: {resp.text[:200]}"
                )
        except ProviderError:
            raise
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(f"Request timed out: {e}") from e
        except Exception as e:
            raise ProviderError(f"LM Studio request failed: {e}") from e

    # --- Structured completion (T052) ---

    async def chat_complete_structured(
        self,
        messages: list[dict],
        response_schema: dict,
        model_id: str,
        max_tokens: int = 2048,
        temperature: Optional[float] = None,
    ) -> dict:
        """Structured-output chat completion with one bounded recovery ladder.

        Ladder:
        1) json_schema if supported
        2) json_object if supported
        3) prompt-only JSON mode (no response_format), still parsed and bounded-recovered
        """
        caps = self._capabilities
        structured_mode = caps.structured_output_mode if caps else "none"
        if structured_mode not in ("json_schema", "json_object", "none"):
            structured_mode = "none"

        last_error: Optional[Exception] = None
        try:
            policy = resolve_model_request_policy(model_id)
            malformed_failures = 0
            for mode in policy.ordered_structured_modes(structured_mode):
                try:
                    return await self._complete_structured_with_mode(
                        messages=messages,
                        response_schema=response_schema,
                        model_id=model_id,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        structured_mode=mode,
                        request_kind="text_structured",
                        post_method=self._post_structured_payload,
                        retry_malformed_structured_response=policy.retry_malformed_structured_response,
                    )
                except StructuredOutputError as e:
                    last_error = e
                    malformed_failures += 1
                    if getattr(e, "reason", None) == "structured_backend_incompatible":
                        self._record_structured_backend_incompatibility(e, mode)
                        continue
                    if (
                        policy.fast_abort_malformed_json_attempts is not None
                        and malformed_failures >= policy.fast_abort_malformed_json_attempts
                        and mode != "none"
                    ):
                        continue
                    raise
            if last_error is not None:
                raise last_error
            raise StructuredOutputError("Structured completion failed without a recorded error.")
        except (ProviderError, StructuredOutputError, ModelUnavailableError, ProviderTimeoutError):
            raise
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(f"Request timed out: {e}") from e
        except Exception as e:
            raise ProviderError(f"LM Studio request failed: {e}") from e

    async def _complete_structured_with_mode(
        self,
        messages: list[dict],
        response_schema: dict,
        model_id: str,
        max_tokens: int,
        temperature: Optional[float],
        structured_mode: str,
        request_kind: str,
        post_method,
        retry_malformed_structured_response: bool = True,
    ) -> dict:
        payload = self._build_payload(
            messages, model_id, max_tokens, temperature, response_schema, structured_mode
        )
        allow_degraded_normalization = structured_mode in ("json_object", "none")
        payload_summary = self._summarize_payload(payload)
        call_started = perf_counter()
        try:
            first_raw = await post_method(payload, model_id)
            metadata = self._consume_pending_transport_metadata(
                request_kind=request_kind,
                structured_mode=structured_mode,
                model_id=model_id,
                fallback_duration_ms=(perf_counter() - call_started) * 1000.0,
                raw_preview=first_raw,
                payload_summary=payload_summary,
            )
            parsed, parse_details = _parse_and_validate_response_with_details(
                first_raw,
                response_schema,
                allow_degraded_normalization=allow_degraded_normalization,
            )
            self._record_attempt(
                request_kind=request_kind,
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="success",
                duration_ms=float(metadata.get("duration_ms", 0.0) or 0.0),
                http_status=metadata.get("http_status"),
                raw_preview=metadata.get("raw_preview"),
                phase="initial",
                error_details=(
                    parse_details
                    if self._verbose_logging or parse_details.get("degraded_normalization_used")
                    else None
                ),
                payload_summary=metadata.get("payload_summary"),
            )
            self._append_trace_record(
                {
                    "phase": "initial",
                    "request_kind": request_kind,
                    "structured_mode": structured_mode,
                    "model_id": model_id,
                    "outcome": "success",
                    "duration_ms": float(metadata.get("duration_ms", 0.0) or 0.0),
                    "http_status": metadata.get("http_status"),
                    "payload_summary": metadata.get("payload_summary"),
                    "response_preview": metadata.get("raw_preview"),
                    "parse_details": parse_details,
                }
            )
            return parsed
        except StructuredOutputError as first_error:
            if self._pending_transport_metadata is not None:
                metadata = self._consume_pending_transport_metadata(
                    request_kind=request_kind,
                    structured_mode=structured_mode,
                    model_id=model_id,
                    fallback_duration_ms=(perf_counter() - call_started) * 1000.0,
                    payload_summary=payload_summary,
                )
                reason = getattr(first_error, "reason", None)
                outcome = "structured_backend_incompatible" if reason == "structured_backend_incompatible" else "structured_output_error"
                self._record_attempt(
                    request_kind=request_kind,
                    structured_mode=structured_mode,
                    model_id=model_id,
                    outcome=outcome,
                    duration_ms=float(metadata.get("duration_ms", 0.0) or 0.0),
                    http_status=metadata.get("http_status"),
                    error_reason=reason,
                    error_message=str(first_error),
                    raw_preview=metadata.get("raw_preview"),
                    phase="initial",
                    error_details=getattr(first_error, "details", None),
                    payload_summary=metadata.get("payload_summary"),
                )
                self._append_trace_record(
                    {
                        "phase": "initial",
                        "request_kind": request_kind,
                        "structured_mode": structured_mode,
                        "model_id": model_id,
                        "outcome": outcome,
                        "duration_ms": float(metadata.get("duration_ms", 0.0) or 0.0),
                        "http_status": metadata.get("http_status"),
                        "payload_summary": metadata.get("payload_summary"),
                        "response_preview": metadata.get("raw_preview"),
                        "error_reason": reason,
                        "error_message": str(first_error),
                        "parse_details": getattr(first_error, "details", None),
                    }
                )
            else:
                self._record_exception_attempt(
                    request_kind=request_kind,
                    structured_mode=structured_mode,
                    model_id=model_id,
                    duration_ms=(perf_counter() - call_started) * 1000.0,
                    error=first_error,
                )
            if getattr(first_error, "reason", None) == "structured_backend_incompatible":
                raise
            if not retry_malformed_structured_response or not _should_retry_structured_output_error(first_error):
                raise
            self._bump("completion_retry_attempts")
            retry_instruction = self._build_retry_instruction(
                response_schema=response_schema,
                validation_issue=str(first_error),
                structured_mode=structured_mode,
            )
            retry_payload = self._build_payload(
                list(messages) + [
                    {
                        "role": "user",
                        "content": retry_instruction,
                    }
                ],
                model_id,
                max_tokens,
                temperature,
                response_schema,
                structured_mode,
            )
            retry_payload_summary = self._summarize_payload(retry_payload)
            retry_started = perf_counter()
            retry_raw = await post_method(retry_payload, model_id)
            metadata = self._consume_pending_transport_metadata(
                request_kind=request_kind,
                structured_mode=structured_mode,
                model_id=model_id,
                fallback_duration_ms=(perf_counter() - retry_started) * 1000.0,
                raw_preview=retry_raw,
                payload_summary=retry_payload_summary,
            )
            parsed, parse_details = _parse_and_validate_response_with_details(
                retry_raw,
                response_schema,
                allow_degraded_normalization=allow_degraded_normalization,
            )
            self._record_attempt(
                request_kind=request_kind,
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="success",
                duration_ms=float(metadata.get("duration_ms", 0.0) or 0.0),
                http_status=metadata.get("http_status"),
                raw_preview=metadata.get("raw_preview"),
                phase="retry",
                error_details=(
                    parse_details
                    if self._verbose_logging or parse_details.get("degraded_normalization_used")
                    else None
                ),
                payload_summary=metadata.get("payload_summary"),
            )
            self._append_trace_record(
                {
                    "phase": "retry",
                    "request_kind": request_kind,
                    "structured_mode": structured_mode,
                    "model_id": model_id,
                    "outcome": "success",
                    "duration_ms": float(metadata.get("duration_ms", 0.0) or 0.0),
                    "http_status": metadata.get("http_status"),
                    "payload_summary": metadata.get("payload_summary"),
                    "response_preview": metadata.get("raw_preview"),
                    "parse_details": parse_details,
                }
            )
            return parsed
        except (ProviderError, ModelUnavailableError, ProviderTimeoutError) as provider_error:
            if self._pending_transport_metadata is None:
                self._record_exception_attempt(
                    request_kind=request_kind,
                    structured_mode=structured_mode,
                    model_id=model_id,
                    duration_ms=(perf_counter() - call_started) * 1000.0,
                    error=provider_error,
                )
            else:
                self._pending_transport_metadata = None
            raise

    def _build_retry_instruction(
        self,
        *,
        response_schema: dict[str, Any],
        validation_issue: str,
        structured_mode: str,
    ) -> str:
        if structured_mode == "json_schema":
            return (
                "Your previous response did not satisfy the required JSON contract. "
                "Return ONLY one JSON object with no prose, no code fences, and no wrapper text. "
                f"Schema: {json.dumps(response_schema)}. Validation issue: {validation_issue}"
            )
        example = json.dumps(self._build_schema_example(response_schema), ensure_ascii=False)
        return (
            "Your previous response did not satisfy the required JSON contract. "
            "Return ONLY one JSON object with exactly the required keys. "
            "Use null for unknown scalar fields and [] for unknown arrays. "
            "Do not add prose, code fences, comments, or wrapper text. "
            f"Use this response shape: {example}. Validation issue: {validation_issue}"
        )

    def _build_schema_example(self, schema: dict[str, Any]) -> object:
        enum_values = schema.get("enum")
        if isinstance(enum_values, list) and enum_values:
            for value in enum_values:
                if value is not None:
                    return value
            return None

        allowed_types = schema.get("type")
        type_options = allowed_types if isinstance(allowed_types, list) else [allowed_types]
        normalized_types = [str(option) for option in type_options if option is not None]

        if "object" in normalized_types:
            properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
            required = schema.get("required", [])
            return {
                field_name: self._build_schema_example(properties.get(field_name, {}))
                for field_name in required
            }
        if "array" in normalized_types:
            return []
        if "integer" in normalized_types:
            return 1
        if "number" in normalized_types:
            return 1
        if "boolean" in normalized_types:
            return False
        if "string" in normalized_types:
            return "value"
        if "null" in normalized_types:
            return None
        return None

    def _record_structured_backend_incompatibility(self, error: StructuredOutputError, attempted_mode: str) -> None:
        caps = self._capabilities
        if caps is None:
            return
        remaining_modes = _fallback_modes_for(attempted_mode)
        next_mode = remaining_modes[1] if len(remaining_modes) > 1 else "none"
        caps.structured_output_mode = next_mode
        caps.structured_output_reason = getattr(error, "reason", None) or "structured_backend_incompatible"
        caps.structured_output_error = str(error)

    async def _post_structured_payload(self, payload: dict, model_id: str) -> str:
        started = perf_counter()
        payload_summary = self._summarize_payload(payload)
        with self._lm_studio_lock(f"text_structured:{model_id}"):
            async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
                self._bump("http_total")
                self._bump("completions_total")
                self._bump("completions_text_structured")
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload
                )
        duration_ms = (perf_counter() - started) * 1000.0
        structured_mode = payload.get("response_format", {}).get("type") if isinstance(payload.get("response_format"), dict) else "none"
        if resp.status_code == 404:
            self._record_attempt(
                request_kind="text_structured",
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="model_unavailable",
                duration_ms=duration_ms,
                http_status=404,
                error_message=f"Model '{model_id}' not found at LM Studio. Ensure the model is loaded.",
                payload_summary=payload_summary,
            )
            raise ModelUnavailableError(
                f"Model '{model_id}' not found at LM Studio. Ensure the model is loaded."
            )
        if resp.status_code == 503:
            self._record_attempt(
                request_kind="text_structured",
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="model_unavailable",
                duration_ms=duration_ms,
                http_status=503,
                error_message="LM Studio is busy or model is not loaded.",
                payload_summary=payload_summary,
            )
            raise ModelUnavailableError("LM Studio is busy or model is not loaded.")
        if resp.status_code != 200:
            reason, message = _classify_lm_studio_response_error(resp.status_code, resp.text)
            if reason:
                self._record_attempt(
                    request_kind="text_structured",
                    structured_mode=structured_mode,
                    model_id=model_id,
                    outcome="structured_backend_incompatible",
                    duration_ms=duration_ms,
                    http_status=resp.status_code,
                    error_reason=reason,
                    error_message=message or resp.text[:300],
                    raw_preview=resp.text,
                    payload_summary=payload_summary,
                )
                raise StructuredOutputError(message or resp.text[:300], reason=reason)
            self._record_attempt(
                request_kind="text_structured",
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="provider_error",
                duration_ms=duration_ms,
                http_status=resp.status_code,
                error_message=f"LM Studio returned HTTP {resp.status_code}: {resp.text[:300]}",
                raw_preview=resp.text,
                payload_summary=payload_summary,
            )
            raise ProviderError(
                f"LM Studio returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
        raw, content_source = _structured_message_content(resp.json()["choices"][0]["message"])
        self._set_pending_transport_metadata(
            request_kind="text_structured",
            structured_mode=structured_mode,
            model_id=model_id,
            duration_ms=duration_ms,
            http_status=resp.status_code,
            raw_preview=raw,
            payload_summary={**payload_summary, "message_content_source": content_source},
        )
        return raw

    def _build_payload(
        self,
        messages: list[dict],
        model_id: str,
        max_tokens: int,
        temperature: Optional[float],
        response_schema: dict,
        structured_mode: str,
    ) -> dict:
        """Build the request payload based on negotiated structured output mode."""
        policy = resolve_model_request_policy(model_id)
        normalized_messages = policy.apply_messages(list(messages), structured_mode)
        base: dict[str, Any] = {
            "model": model_id,
            "messages": normalized_messages,
            **self._effective_request_settings(
                model_id=model_id,
                max_tokens=max_tokens,
                temperature=temperature,
            ),
        }
        if structured_mode == "json_schema":
            base["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "extraction_response",
                    "schema": response_schema,
                    "strict": True,
                },
            }
        elif structured_mode == "json_object":
            base["response_format"] = {"type": "json_object"}
        # else: text_fallback — system prompt instructs JSON
        return base

    async def vision_complete_structured(
        self,
        messages: list[dict],
        response_schema: dict,
        model_id: str,
        image_b64: str,
        max_tokens: int = 2048,
        temperature: Optional[float] = None,
        retry_malformed_structured_response: bool = True,
    ) -> dict:
        """Vision-capable structured completion (T055).

        Sends an image + text prompt to a vision-capable model.
        """
        # Build vision message with base64 image
        vision_messages = list(messages)
        # Inject image into the last user message
        last_user = None
        for i in range(len(vision_messages) - 1, -1, -1):
            if vision_messages[i]["role"] == "user":
                last_user = i
                break

        if last_user is not None:
            old_content = vision_messages[last_user]["content"]
            vision_messages[last_user] = {
                "role": "user",
                "content": [
                    {"type": "text", "text": old_content},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }

        caps = self._capabilities
        structured_mode = caps.vision_structured_output_mode if caps else "none"
        if structured_mode not in ("json_schema", "json_object", "none"):
            structured_mode = "none"

        last_error: Optional[Exception] = None
        try:
            for mode in _fallback_modes_for(structured_mode):
                try:
                    return await self._complete_structured_with_mode(
                        messages=vision_messages,
                        response_schema=response_schema,
                        model_id=model_id,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        structured_mode=mode,
                        request_kind="vision_structured",
                        post_method=self._post_vision_payload,
                        retry_malformed_structured_response=retry_malformed_structured_response,
                    )
                except StructuredOutputError as e:
                    last_error = e
                    if getattr(e, "reason", None) == "structured_backend_incompatible":
                        self._record_structured_backend_incompatibility(e, mode)
                        continue
                    raise
            if last_error is not None:
                raise last_error
            raise StructuredOutputError("Vision structured completion failed without a recorded error.")
        except (ProviderError, StructuredOutputError):
            raise
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(f"Vision request timed out: {e}") from e
        except Exception as e:
            raise ProviderError(f"Vision request failed: {e}") from e

    async def _post_vision_payload(self, payload: dict, model_id: str) -> str:
        started = perf_counter()
        payload_summary = self._summarize_payload(payload)
        with self._lm_studio_lock(f"vision_structured:{model_id}"):
            async with httpx.AsyncClient(timeout=self._vision_request_timeout_seconds) as client:
                self._bump("http_total")
                self._bump("completions_total")
                self._bump("completions_vision_structured")
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload
                )
        duration_ms = (perf_counter() - started) * 1000.0
        structured_mode = payload.get("response_format", {}).get("type") if isinstance(payload.get("response_format"), dict) else "none"
        if resp.status_code == 404:
            self._record_attempt(
                request_kind="vision_structured",
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="model_unavailable",
                duration_ms=duration_ms,
                http_status=404,
                error_message=f"Vision model '{model_id}' not found at LM Studio. Ensure the model is loaded.",
                payload_summary=payload_summary,
            )
            raise ModelUnavailableError(
                f"Vision model '{model_id}' not found at LM Studio. Ensure the model is loaded."
            )
        if resp.status_code == 503:
            self._record_attempt(
                request_kind="vision_structured",
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="model_unavailable",
                duration_ms=duration_ms,
                http_status=503,
                error_message="LM Studio is busy or vision model is not loaded.",
                payload_summary=payload_summary,
            )
            raise ModelUnavailableError("LM Studio is busy or vision model is not loaded.")
        if resp.status_code != 200:
            reason, message = _classify_lm_studio_response_error(resp.status_code, resp.text)
            if reason:
                self._record_attempt(
                    request_kind="vision_structured",
                    structured_mode=structured_mode,
                    model_id=model_id,
                    outcome="structured_backend_incompatible",
                    duration_ms=duration_ms,
                    http_status=resp.status_code,
                    error_reason=reason,
                    error_message=message or resp.text[:200],
                    raw_preview=resp.text,
                    payload_summary=payload_summary,
                )
                raise StructuredOutputError(message or resp.text[:200], reason=reason)
            self._record_attempt(
                request_kind="vision_structured",
                structured_mode=structured_mode,
                model_id=model_id,
                outcome="provider_error",
                duration_ms=duration_ms,
                http_status=resp.status_code,
                error_message=f"Vision completion failed HTTP {resp.status_code}: {resp.text[:200]}",
                raw_preview=resp.text,
                payload_summary=payload_summary,
            )
            raise ProviderError(
                f"Vision completion failed HTTP {resp.status_code}: {resp.text[:200]}"
            )
        raw, content_source = _structured_message_content(resp.json()["choices"][0]["message"])
        self._set_pending_transport_metadata(
            request_kind="vision_structured",
            structured_mode=structured_mode,
            model_id=model_id,
            duration_ms=duration_ms,
            http_status=resp.status_code,
            raw_preview=raw,
            payload_summary={**payload_summary, "message_content_source": content_source},
        )
        return raw

    def set_capabilities(self, caps: ProviderCapabilities) -> None:
        """Set probed capabilities so they are reused across requests."""
        self._capabilities = caps


# ---------------------------------------------------------------------------
# Optional cloud-provider slot (T051a)
# ---------------------------------------------------------------------------

class CloudProviderAdapter(ProviderAdapter):
    """Stub base for optional cloud providers.

    T051a: cloud providers stay behind the same typed interface.
    Credentials must come from environment variables, not hardcoded config.
    """

    def __init__(self, token: str, base_url: str, api_key_env: str = "CLOUD_API_KEY"):
        self._token = token
        self._base_url = base_url
        self._api_key_env = api_key_env

    @property
    def token(self) -> str:
        return self._token

    @property
    def locality(self) -> ProviderLocality:
        return ProviderLocality.cloud

    def _get_api_key(self) -> str:
        import os
        key = os.environ.get(self._api_key_env, "")
        if not key:
            raise ProviderError(
                f"Cloud provider '{self._token}' requires env var {self._api_key_env} to be set."
            )
        return key

    async def probe_capabilities(self, text_model_id: str, vision_model_id: Optional[str] = None) -> ProviderCapabilities:
        raise NotImplementedError("Cloud provider probe not implemented in MVP.")

    async def text_complete_raw(self, system: str, user: str, max_tokens: int = 512, model_id: str = "") -> str:
        raise NotImplementedError("Cloud provider text completion not implemented in MVP.")

    async def chat_complete_structured(self, messages, response_schema, model_id, max_tokens=2048, temperature=0.0) -> dict:
        raise NotImplementedError("Cloud provider structured completion not implemented in MVP.")

    async def vision_complete_structured(
        self,
        messages,
        response_schema,
        model_id,
        image_b64,
        max_tokens=2048,
        temperature=0.0,
        retry_malformed_structured_response=True,
    ) -> dict:
        raise NotImplementedError("Cloud provider vision completion not implemented in MVP.")


# ---------------------------------------------------------------------------
# Provider factory (T050)
# ---------------------------------------------------------------------------

def build_provider(config: object, diagnostics_config: Optional[object] = None) -> ProviderAdapter:
    """Build the appropriate ProviderAdapter from RunConfig.provider.

    T050: one typed interface, LM Studio as default local-first path.
    T052a: no silent fallback to stub/degraded mode.
    """
    from .config import CANONICAL_PROVIDERS

    token = config.token  # type: ignore[attr-defined]
    if token == "lm_studio":
        verbose_logging = bool(getattr(diagnostics_config, "verbose_provider_logging", False))
        preview_limit = int(getattr(diagnostics_config, "provider_preview_chars", 240) or 240)
        return LMStudioProvider(  # type: ignore[attr-defined]
            base_url=config.base_url,
            verbose_logging=verbose_logging,
            preview_limit=preview_limit,
            text_model_config=getattr(config, "text_model", None),
            vision_model_config=getattr(config, "vision_model", None),
            request_timeout_seconds=getattr(config, "request_timeout_seconds", DEFAULT_TIMEOUT),
            vision_request_timeout_seconds=getattr(config, "vision_request_timeout_seconds", DEFAULT_VISION_TIMEOUT),
            model_load_timeout_seconds=getattr(config, "model_load_timeout_seconds", DEFAULT_MODEL_LOAD_TIMEOUT),
            model_unload_timeout_seconds=getattr(config, "model_unload_timeout_seconds", DEFAULT_MODEL_UNLOAD_TIMEOUT),
            lock_enabled=getattr(config, "lm_studio_lock_enabled", True),
            lock_timeout_seconds=getattr(config, "lm_studio_lock_timeout_seconds", DEFAULT_LOCK_TIMEOUT),
            lock_path=getattr(config, "lm_studio_lock_path", None),
        )

    # Cloud provider slot (T051a)
    # If custom registry entries are added later, map them here.
    raise ProviderError(
        f"Unknown provider token '{token}'. "
        f"Supported providers: {sorted(CANONICAL_PROVIDERS)}. "
        "For LM Studio, use 'lm_studio'."
    )


async def initialize_provider(
    config: object,  # RunConfig.provider
    text_model_id: str,
    vision_model_id: Optional[str],
    diagnostics_config: Optional[object] = None,
) -> tuple[ProviderAdapter, ProviderMode]:
    """Build provider, probe capabilities, return (adapter, mode).

    T052a: mode is recorded truthfully; never returns a degraded mode silently.
    """
    provider: Optional[ProviderAdapter] = None
    try:
        provider = build_provider(config, diagnostics_config=diagnostics_config)
        model_management: Optional[dict[str, Any]] = None
        ensure_models = getattr(provider, "ensure_model_availability", None)
        text_model_config = getattr(config, "text_model", None)
        vision_model_config = getattr(config, "vision_model", None)
        if callable(ensure_models) and (text_model_config is not None or vision_model_config is not None):
            model_management = await ensure_models(
                text_model_id=text_model_id,
                text_working_context_budget=getattr(text_model_config, "working_context_budget", None),
                text_load_context_length=getattr(text_model_config, "required_load_context_length", None),
                text_load_context_is_derived=bool(
                    getattr(text_model_config, "load_context_is_derived", False)
                ),
                vision_model_id=vision_model_id,
                vision_load_context_length=getattr(vision_model_config, "load_context_length", None),
            )
        caps = await provider.probe_capabilities(text_model_id, vision_model_id)
        if isinstance(provider, LMStudioProvider):
            provider.set_capabilities(caps)
        mode = provider.get_provider_mode(
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            capabilities=caps,
            model_management=model_management,
            readiness_error=None,
            readiness_reason=None,
        )
        return provider, mode
    except ProviderError as e:
        # T052a: propagate reason-classified provider failures for truthful warnings.
        reason = getattr(e, "reason", None)
        if not reason:
            if isinstance(e, ModelUnavailableError):
                reason = "model_unavailable"
            elif isinstance(e, StructuredOutputError):
                reason = "no_compatible_structured_mode"
            else:
                reason = "provider_unreachable"
        details = dict(getattr(e, "details", None) or {})
        if provider is not None and not details.get("model_management"):
            get_model_management = getattr(provider, "get_model_management_report", None)
            if callable(get_model_management):
                model_management = get_model_management() or {}
                if model_management:
                    details["model_management"] = model_management
        raise ProviderError(str(e), reason=reason, details=details or None) from e
