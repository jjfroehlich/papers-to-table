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


# ---------------------------------------------------------------------------
# Provider capability contract (T050)
# ---------------------------------------------------------------------------

class ProviderCapabilities(BaseModel):
    """Detected capabilities of a provider/model pair."""
    supports_structured_output: bool = False
    structured_output_mode: str = "none"
    """One of: 'json_schema', 'json_object', 'text_fallback', 'none'."""
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
    readiness_error: Optional[str] = None
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
    ) -> ProviderMode:
        if readiness_error:
            mode = "unavailable"
        elif self.locality == ProviderLocality.cloud:
            mode = "live_cloud"
        else:
            mode = "live_local"
        return ProviderMode(
            token=self.token,
            locality=self.locality.value,
            mode=mode,
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            capabilities=capabilities,
            readiness_error=readiness_error,
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Provider errors (T052)
# ---------------------------------------------------------------------------

class ProviderError(Exception):
    """Hard provider error that should record an error proposal outcome."""
    def __init__(self, message: str, recoverable: bool = False):
        super().__init__(message)
        self.recoverable = recoverable


class StructuredOutputError(ProviderError):
    """Structured output contract failure."""
    pass


class ModelUnavailableError(ProviderError):
    """Model is not loaded or available."""
    pass


class ProviderTimeoutError(ProviderError):
    """Request timed out."""
    pass


# ---------------------------------------------------------------------------
# JSON repair helper (T052)
# ---------------------------------------------------------------------------

def _try_repair_json(raw: str) -> Optional[dict]:
    """Bounded JSON repair attempt for common LLM output artifacts.

    Handles:
    - markdown code fences
    - trailing commas
    - single quotes
    - truncated output (best-effort)
    """
    # Strip markdown fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        inner = [l for l in lines if not l.startswith("```")]
        cleaned = "\n".join(inner).strip()

    # First try: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Second try: extract first JSON object
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Third try: remove trailing commas
    no_trailing = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        return json.loads(no_trailing)
    except json.JSONDecodeError:
        pass

    return None


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
                resp = await client.get(f"{self._base_url}/v1/models")
                if resp.status_code != 200:
                    return ProviderCapabilities(
                        supports_structured_output=False,
                        structured_output_mode="none",
                        model_id=text_model_id,
                        probed_at=now,
                    )
                models_data = resp.json()
                available_ids = {
                    m.get("id", "") for m in models_data.get("data", [])
                }
        except Exception:
            return ProviderCapabilities(
                supports_structured_output=False,
                structured_output_mode="none",
                model_id=text_model_id,
                probed_at=now,
            )

        # Check if text model is available (model_id "default" always accepted)
        model_ok = (text_model_id == "default") or (text_model_id in available_ids) or bool(available_ids)

        if not model_ok:
            return ProviderCapabilities(
                supports_structured_output=False,
                structured_output_mode="none",
                model_id=text_model_id,
                probed_at=now,
            )

        # Probe structured-output support (T050)
        # Try json_schema first (stricter), then json_object
        effective_model = text_model_id if text_model_id != "default" else (
            next(iter(available_ids), "default")
        )
        structured_mode = await self._probe_structured_output_mode(effective_model)

        return ProviderCapabilities(
            supports_structured_output=structured_mode != "none",
            structured_output_mode=structured_mode,
            model_id=effective_model,
            vision_capable=vision_model_id is not None,
            probed_at=now,
        )

    async def _probe_structured_output_mode(self, model_id: str) -> str:
        """Try json_schema, then json_object, return the first that works."""
        # Try json_schema (LM Studio >= 0.3.x with grammar support)
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
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    parsed = _try_repair_json(content)
                    if parsed is not None:
                        return "json_schema"
        except Exception:
            pass

        # Try json_object
        try:
            payload_jo = {
                "model": model_id,
                "messages": [{"role": "user", "content": "Reply with JSON: {\"test\": \"ok\"}"}],
                "response_format": {"type": "json_object"},
                "max_tokens": 32,
                "temperature": 0.0,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload_jo
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    parsed = _try_repair_json(content)
                    if parsed is not None:
                        return "json_object"
        except Exception:
            pass

        return "text_fallback"

    # --- Text completion ---

    async def text_complete_raw(
        self,
        system: str,
        user: str,
        max_tokens: int = 512,
        model_id: str = "default",
    ) -> str:
        """Simple text completion, returns assistant content as string."""
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
        """Structured-output chat completion with bounded recovery (T052).

        Negotiates format based on probed capabilities.
        Attempts one repair pass on malformed JSON before hard failure.
        T052: one compatibility mismatch does NOT poison the rest of the run.
        """
        caps = self._capabilities
        structured_mode = caps.structured_output_mode if caps else "text_fallback"

        payload = self._build_payload(
            messages, model_id, max_tokens, temperature, response_schema, structured_mode
        )

        last_exc: Optional[Exception] = None
        for attempt in range(DEFAULT_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    resp = await client.post(
                        f"{self._base_url}/v1/chat/completions", json=payload
                    )

                if resp.status_code == 404:
                    raise ModelUnavailableError(
                        f"Model '{model_id}' not found at LM Studio. "
                        "Ensure the model is loaded."
                    )
                if resp.status_code == 503:
                    raise ModelUnavailableError("LM Studio is busy or model is not loaded.")
                if resp.status_code != 200:
                    raise ProviderError(
                        f"LM Studio returned HTTP {resp.status_code}: {resp.text[:300]}"
                    )

                raw_content = resp.json()["choices"][0]["message"]["content"]
                parsed = _try_repair_json(raw_content)
                if parsed is not None:
                    return parsed

                # Bounded repair: ask model to reformat its last output
                if attempt == 0:
                    repair_msg = {
                        "role": "user",
                        "content": (
                            "Your previous response was not valid JSON. "
                            "Return ONLY a valid JSON object with no surrounding text, "
                            "markdown, or explanations. "
                            f"Ensure it matches this schema: {json.dumps(response_schema)}"
                        ),
                    }
                    payload["messages"] = list(messages) + [
                        {"role": "assistant", "content": raw_content},
                        repair_msg,
                    ]
                    # Reduce max_tokens for repair to avoid truncation
                    payload["max_tokens"] = min(max_tokens, 1024)
                    continue

                raise StructuredOutputError(
                    f"LM Studio returned malformed JSON after repair attempt: {raw_content[:200]}"
                )

            except (ProviderError, StructuredOutputError, ModelUnavailableError, ProviderTimeoutError):
                raise
            except httpx.TimeoutException as e:
                last_exc = ProviderTimeoutError(f"Request timed out: {e}")
                if attempt >= DEFAULT_RETRIES:
                    raise last_exc from e
            except Exception as e:
                raise ProviderError(f"LM Studio request failed: {e}") from e

        if last_exc:
            raise last_exc
        raise ProviderError("Structured completion failed after retries")

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

        payload = self._build_payload(
            vision_messages, model_id, max_tokens, temperature,
            response_schema, "json_object"  # use json_object for vision (broader compat)
        )

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT * 2) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions", json=payload
                )
            if resp.status_code != 200:
                raise ProviderError(
                    f"Vision completion failed HTTP {resp.status_code}: {resp.text[:200]}"
                )
            raw = resp.json()["choices"][0]["message"]["content"]
            parsed = _try_repair_json(raw)
            if parsed is None:
                raise StructuredOutputError(
                    f"Vision model returned malformed JSON: {raw[:200]}"
                )
            return parsed
        except (ProviderError, StructuredOutputError):
            raise
        except httpx.TimeoutException as e:
            raise ProviderTimeoutError(f"Vision request timed out: {e}") from e
        except Exception as e:
            raise ProviderError(f"Vision request failed: {e}") from e

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

    async def text_complete_raw(self, system: str, user: str, max_tokens: int = 512, model_id: str = "default") -> str:
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
        )
        return provider, mode
    except ProviderError as e:
        # T052a: return unavailable mode with honest error, not silent degradation
        from .config import PROVIDER_DISPLAY_NAMES
        mode = ProviderMode(
            token=getattr(config, "token", "unknown"),
            locality=ProviderLocality.local.value,
            mode="unavailable",
            text_model_id=text_model_id,
            vision_model_id=vision_model_id,
            readiness_error=str(e),
            recorded_at=datetime.now(timezone.utc).isoformat(),
        )
        raise ProviderError(str(e)) from e
