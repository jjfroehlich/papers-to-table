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
import json
import re
import textwrap
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from pydantic import BaseModel

from .schemas import ProviderLocality


def _has_explicit_model_id(model_id: Optional[str]) -> bool:
    if model_id is None:
        return False
    normalized = model_id.strip()
    return bool(normalized) and normalized != "default"


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
    probed_at: Optional[str] = None


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
    structured_output_fallback_used: bool = False
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
        temperature: float = 0.0,
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
        temperature: float = 0.0,
    ) -> dict:
        """Vision-capable structured completion. Returns parsed dict."""
        ...

    def get_provider_mode(
        self,
        text_model_id: Optional[str],
        vision_model_id: Optional[str],
        capabilities: Optional[ProviderCapabilities] = None,
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
        fallback_used = structured_output_mode in ("json_object", "none")
        return ProviderMode(
            token=self.token,
            locality=self.locality.value,
            mode=mode,
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            capabilities=capabilities,
            structured_output_mode=structured_output_mode,
            structured_output_fallback_used=fallback_used,
            readiness_error=readiness_error,
            readiness_reason=readiness_reason,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )

    def get_request_counts(self) -> dict[str, int]:
        """Return provider request counters for run artifacts."""
        return {}


# ---------------------------------------------------------------------------
# Provider errors (T052)
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Hard provider error that should record an error proposal outcome."""
    def __init__(self, message: str, recoverable: bool = False, reason: Optional[str] = None):
        super().__init__(message)
        self.recoverable = recoverable
        self.reason = reason


class StructuredOutputError(ProviderError):
    """Structured output contract failure."""
    pass


class ModelUnavailableError(ProviderError):
    """Model is not loaded or available."""

    def __init__(self, message: str, recoverable: bool = False, reason: Optional[str] = None):
        super().__init__(message, recoverable=recoverable, reason=reason or "model_unavailable")


class ProviderTimeoutError(ProviderError):
    """Request timed out."""

    def __init__(self, message: str, recoverable: bool = False, reason: Optional[str] = None):
        super().__init__(message, recoverable=recoverable, reason=reason or "provider_unreachable")


# ---------------------------------------------------------------------------
# JSON repair helper (T052)
# ---------------------------------------------------------------------------

def _try_repair_json(raw: str) -> Optional[dict]:
    """Bounded JSON repair attempt for common LLM output artifacts.

    Handles:
    - markdown code fences
    - wrapper tags such as <think>...</think>
    - balanced-object extraction from mixed output
    - trailing commas
    - truncated output (best-effort)
    """
    cleaned = _strip_json_wrappers(raw)
    for candidate in (cleaned, _extract_balanced_json_object(cleaned)):
        parsed = _parse_json_candidate(candidate)
        if isinstance(parsed, dict):
            return parsed
    return None


def _strip_json_wrappers(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"<(think|analysis)[^>]*>.*?</\1>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    if "```" in cleaned:
        lines = cleaned.splitlines()
        cleaned = "\n".join(line for line in lines if not line.strip().startswith("```"))
    return cleaned.strip()


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


def _parse_json_candidate(candidate: Optional[str]) -> Optional[object]:
    if not candidate:
        return None
    for raw_candidate in (candidate, re.sub(r",\s*([}\]])", r"\1", candidate)):
        try:
            return json.loads(raw_candidate)
        except json.JSONDecodeError:
            continue
    return None


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


def _parse_and_validate_response(raw: str, response_schema: dict) -> dict:
    parsed = _try_repair_json(raw)
    if not isinstance(parsed, dict):
        raise StructuredOutputError(f"LM Studio returned malformed JSON after bounded recovery: {raw[:200]}")
    _validate_against_schema(parsed, response_schema)
    return parsed


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


# ---------------------------------------------------------------------------
# LM Studio provider (T051)
# ---------------------------------------------------------------------------

DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 1  # bounded: one retry


class LMStudioProvider(ProviderAdapter):
    """LM Studio localhost API integration.

    T051: implements the MVP local-first provider path.
    Uses the OpenAI-compatible /v1/chat/completions endpoint.
    """

    def __init__(self, base_url: str = "http://localhost:1234"):
        self._base_url = base_url.rstrip("/")
        self._capabilities: Optional[ProviderCapabilities] = None
        self._request_counts: dict[str, int] = {
            "http_total": 0,
            "models_list": 0,
            "completions_total": 0,
            "completions_text_raw": 0,
            "completions_text_structured": 0,
            "completions_vision_structured": 0,
            "completions_probe_structured": 0,
            "completion_retry_attempts": 0,
        }

    def _bump(self, key: str, amount: int = 1) -> None:
        self._request_counts[key] = self._request_counts.get(key, 0) + amount

    def get_request_counts(self) -> dict[str, int]:
        return dict(self._request_counts)

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

        # Probe structured-output support (T050)
        # Try json_schema first (stricter), then json_object
        effective_model = text_model_id
        structured_mode, structured_reason, structured_error = await self._probe_structured_output_mode(effective_model)

        return ProviderCapabilities(
            supports_structured_output=structured_mode != "none",
            structured_output_mode=structured_mode,
            structured_output_reason=structured_reason,
            structured_output_error=structured_error,
            model_id=effective_model,
            vision_capable=vision_model_id is not None,
            probed_at=now,
        )

    async def _probe_structured_output_mode(self, model_id: str) -> tuple[str, Optional[str], Optional[str]]:
        """Probe best supported structured mode for the live extraction path."""
        structured_reason: Optional[str] = None
        structured_error: Optional[str] = None
        try:
            test_schema = {
                "type": "object",
                "properties": {"test": {"type": "string"}},
                "required": ["test"],
            }
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "Reply with {\"test\": \"ok\"}"}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "test", "schema": test_schema},
                },
                "max_tokens": 32,
                "temperature": 0.0,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                self._bump("http_total")
                self._bump("completions_total")
                self._bump("completions_probe_structured")
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload
                )
                if resp.status_code == 200:
                    content = _coerce_message_content(resp.json()["choices"][0]["message"]["content"])
                    _parse_and_validate_response(content, test_schema)
                    return "json_schema", None, None
                reason, message = _classify_lm_studio_response_error(resp.status_code, resp.text)
                if reason:
                    structured_reason = reason
                    structured_error = message
        except Exception:
            pass

        # Some model/runtime pairs reject json_schema but still support json_object.
        try:
            payload = {
                "model": model_id,
                "messages": [{"role": "user", "content": "Reply with {\"test\": \"ok\"}"}],
                "response_format": {"type": "json_object"},
                "max_tokens": 32,
                "temperature": 0.0,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                self._bump("http_total")
                self._bump("completions_total")
                self._bump("completions_probe_structured")
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload
                )
                if resp.status_code == 200:
                    content = _coerce_message_content(resp.json()["choices"][0]["message"]["content"])
                    _parse_and_validate_response(content, test_schema)
                    return "json_object", structured_reason, structured_error
                reason, message = _classify_lm_studio_response_error(resp.status_code, resp.text)
                if reason and not structured_reason:
                    structured_reason = reason
                    structured_error = message
        except Exception:
            pass
        return "none", structured_reason, structured_error

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
            "max_tokens": max_tokens,
            "temperature": 0.0,
        }
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
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
        temperature: float = 0.0,
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
            for mode in _fallback_modes_for(structured_mode):
                try:
                    return await self._complete_structured_with_mode(
                        messages=messages,
                        response_schema=response_schema,
                        model_id=model_id,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        structured_mode=mode,
                        post_method=self._post_structured_payload,
                    )
                except StructuredOutputError as e:
                    last_error = e
                    if getattr(e, "reason", None) == "structured_backend_incompatible":
                        self._record_structured_backend_incompatibility(e, mode)
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
        temperature: float,
        structured_mode: str,
        post_method,
    ) -> dict:
        payload = self._build_payload(
            messages, model_id, max_tokens, temperature, response_schema, structured_mode
        )
        try:
            first_raw = await post_method(payload, model_id)
            return _parse_and_validate_response(first_raw, response_schema)
        except StructuredOutputError as first_error:
            if getattr(first_error, "reason", None) == "structured_backend_incompatible":
                raise
            self._bump("completion_retry_attempts")
            retry_payload = self._build_payload(
                list(messages) + [
                    {
                        "role": "user",
                        "content": (
                            "Your previous response did not satisfy the required JSON contract. "
                            "Return ONLY one JSON object with no prose, no code fences, and no wrapper text. "
                            f"Schema: {json.dumps(response_schema)}. Validation issue: {str(first_error)}"
                        ),
                    }
                ],
                model_id,
                min(max_tokens, 1024),
                temperature,
                response_schema,
                structured_mode,
            )
            retry_raw = await post_method(retry_payload, model_id)
            return _parse_and_validate_response(retry_raw, response_schema)

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
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            self._bump("http_total")
            self._bump("completions_total")
            self._bump("completions_text_structured")
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions", json=payload
            )
        if resp.status_code == 404:
            raise ModelUnavailableError(
                f"Model '{model_id}' not found at LM Studio. Ensure the model is loaded."
            )
        if resp.status_code == 503:
            raise ModelUnavailableError("LM Studio is busy or model is not loaded.")
        if resp.status_code != 200:
            reason, message = _classify_lm_studio_response_error(resp.status_code, resp.text)
            if reason:
                raise StructuredOutputError(message or resp.text[:300], reason=reason)
            raise ProviderError(
                f"LM Studio returned HTTP {resp.status_code}: {resp.text[:300]}"
            )
        return _coerce_message_content(resp.json()["choices"][0]["message"]["content"])

    def _build_payload(
        self,
        messages: list[dict],
        model_id: str,
        max_tokens: int,
        temperature: float,
        response_schema: dict,
        structured_mode: str,
    ) -> dict:
        """Build the request payload based on negotiated structured output mode."""
        base: dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
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
        temperature: float = 0.0,
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
        structured_mode = caps.structured_output_mode if caps else "none"
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
                        post_method=self._post_vision_payload,
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
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT * 2) as client:
            self._bump("http_total")
            self._bump("completions_total")
            self._bump("completions_vision_structured")
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions", json=payload
            )
        if resp.status_code == 404:
            raise ModelUnavailableError(
                f"Vision model '{model_id}' not found at LM Studio. Ensure the model is loaded."
            )
        if resp.status_code == 503:
            raise ModelUnavailableError("LM Studio is busy or vision model is not loaded.")
        if resp.status_code != 200:
            reason, message = _classify_lm_studio_response_error(resp.status_code, resp.text)
            if reason:
                raise StructuredOutputError(message or resp.text[:200], reason=reason)
            raise ProviderError(
                f"Vision completion failed HTTP {resp.status_code}: {resp.text[:200]}"
            )
        return _coerce_message_content(resp.json()["choices"][0]["message"]["content"])

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

    async def vision_complete_structured(self, messages, response_schema, model_id, image_b64, max_tokens=2048, temperature=0.0) -> dict:
        raise NotImplementedError("Cloud provider vision completion not implemented in MVP.")


# ---------------------------------------------------------------------------
# Provider factory (T050)
# ---------------------------------------------------------------------------

def build_provider(config: object) -> ProviderAdapter:
    """Build the appropriate ProviderAdapter from RunConfig.provider.

    T050: one typed interface, LM Studio as default local-first path.
    T052a: no silent fallback to stub/degraded mode.
    """
    from .config import CANONICAL_PROVIDERS

    token = config.token  # type: ignore[attr-defined]
    if token == "lm_studio":
        return LMStudioProvider(base_url=config.base_url)  # type: ignore[attr-defined]

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
) -> tuple[ProviderAdapter, ProviderMode]:
    """Build provider, probe capabilities, return (adapter, mode).

    T052a: mode is recorded truthfully; never returns a degraded mode silently.
    """
    try:
        provider = build_provider(config)
        caps = await provider.probe_capabilities(text_model_id, vision_model_id)
        if isinstance(provider, LMStudioProvider):
            provider.set_capabilities(caps)
        mode = provider.get_provider_mode(
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            capabilities=caps,
            readiness_error=None,
            readiness_reason=caps.structured_output_reason,
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
        raise ProviderError(str(e), reason=reason) from e
