"""
Batch 3 — Provider abstraction and LM Studio integration.

Implements:
- T050: Provider abstraction and capability-probe model
- T051: LM Studio localhost API as initial MVP provider
- T052: Provider error handling and structured-output failure policy
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# T050 — Provider abstraction
# ---------------------------------------------------------------------------


class ProviderCapabilities(BaseModel):
    provider_name: str
    model_name: str
    locality: str = "local"  # "local" | "cloud"
    supports_structured_output: bool = False
    supports_vision: bool = False
    available: bool = True


class ProviderError(RuntimeError):
    """Raised when the provider call fails unrecoverably."""


class StructuredOutputError(ProviderError):
    """Raised when the provider cannot produce valid structured output."""


class ProviderAdapter(ABC):
    """Abstract base for all LLM provider adapters."""

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Return cached or freshly probed capabilities."""

    @abstractmethod
    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Request a structured JSON completion.

        Returns the parsed JSON dict.
        Raises StructuredOutputError if the response cannot be parsed.
        """

    @abstractmethod
    def complete_text(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """Request a plain-text completion."""

    def complete_vision_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str,
        json_schema: dict[str, Any],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """
        Request a structured JSON completion with an attached image.

        Default implementation raises NotImplementedError; override in vision-capable providers.
        """
        raise NotImplementedError("Vision not supported by this provider")


# ---------------------------------------------------------------------------
# T051 — LM Studio localhost API
# ---------------------------------------------------------------------------

_LM_STUDIO_DEFAULT_BASE = "http://localhost:1234/v1"
_DEFAULT_TIMEOUT = 60  # seconds
_DEFAULT_RETRIES = 2


class LMStudioProvider(ProviderAdapter):
    """
    T051: LM Studio localhost API provider.

    Uses the OpenAI-compatible chat/completions endpoint.
    Attempts structured JSON output via json_object response format or schema injection.
    """

    def __init__(
        self,
        base_url: str = _LM_STUDIO_DEFAULT_BASE,
        model_name: str = "local-model",
        timeout: int = _DEFAULT_TIMEOUT,
        max_retries: int = _DEFAULT_RETRIES,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model_name = model_name
        self._timeout = timeout
        self._max_retries = max_retries
        self._capabilities: ProviderCapabilities | None = None

    @property
    def capabilities(self) -> ProviderCapabilities:
        if self._capabilities is None:
            self._capabilities = self._probe_capabilities()
        return self._capabilities

    def _probe_capabilities(self) -> ProviderCapabilities:
        """T050: Probe whether the LM Studio endpoint is reachable and what it supports."""
        try:
            resp = self._raw_request(
                "GET",
                "/models",
                body=None,
                timeout=10,
            )
            model_ids = [m.get("id", "") for m in resp.get("data", [])]
            # Check if the configured model name appears in the model list
            available = any(self._model_name in mid for mid in model_ids) or bool(model_ids)
            # Vision capability probe: check model name for vision keywords
            supports_vision = any(
                kw in self._model_name.lower() for kw in ("vision", "vl", "llava", "qwen-vl")
            )
            logger.info(
                "LM Studio probe: available=%s models=%s supports_vision=%s",
                available,
                model_ids[:3],
                supports_vision,
            )
            return ProviderCapabilities(
                provider_name="lmstudio",
                model_name=self._model_name,
                locality="local",
                supports_structured_output=True,
                supports_vision=supports_vision,
                available=available,
            )
        except Exception as exc:
            logger.warning("LM Studio capability probe failed: %s", exc)
            return ProviderCapabilities(
                provider_name="lmstudio",
                model_name=self._model_name,
                locality="local",
                supports_structured_output=False,
                supports_vision=False,
                available=False,
            )

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict[str, Any],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """T052: Structured-output request with retry and JSON validation."""
        schema_hint = json.dumps(json_schema, indent=2)
        augmented_system = (
            f"{system_prompt}\n\n"
            "You MUST respond with a single valid JSON object matching this schema:\n"
            f"{schema_hint}\n"
            "Do not include any text before or after the JSON object."
        )
        messages = [
            {"role": "system", "content": augmented_system},
            {"role": "user", "content": user_prompt},
        ]
        body = {
            "model": self._model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }

        raw_text = self._chat_with_retry(body)
        return self._parse_json_response(raw_text, json_schema)

    def complete_text(
        self,
        prompt: str,
        max_tokens: int = 256,
        temperature: float = 0.0,
    ) -> str:
        """T051: Plain-text completion via chat endpoint."""
        messages = [{"role": "user", "content": prompt}]
        body = {
            "model": self._model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        return self._chat_with_retry(body)

    def complete_vision_json(
        self,
        system_prompt: str,
        user_prompt: str,
        image_b64: str,
        json_schema: dict[str, Any],
        max_tokens: int = 512,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        """T055: Vision-capable structured request."""
        schema_hint = json.dumps(json_schema, indent=2)
        augmented_system = (
            f"{system_prompt}\n\n"
            "You MUST respond with a single valid JSON object matching this schema:\n"
            f"{schema_hint}\n"
            "Do not include any text before or after the JSON object."
        )
        messages = [
            {"role": "system", "content": augmented_system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            },
        ]
        body = {
            "model": self._model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        raw_text = self._chat_with_retry(body)
        return self._parse_json_response(raw_text, json_schema)

    # ------------------------------------------------------------------
    # T052 — Error handling helpers
    # ------------------------------------------------------------------

    def _chat_with_retry(self, body: dict[str, Any]) -> str:
        """Execute a chat completions request with retry on transient errors."""
        last_exc: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                resp = self._raw_request("POST", "/chat/completions", body)
                choices = resp.get("choices", [])
                if not choices:
                    raise ProviderError("LM Studio returned empty choices list")
                content = choices[0].get("message", {}).get("content", "")
                logger.debug("LM Studio response (attempt %d): %s…", attempt + 1, content[:120])
                return content
            except (ProviderError, urllib.error.URLError, TimeoutError) as exc:
                last_exc = exc
                if attempt < self._max_retries:
                    wait = 2 ** attempt
                    logger.warning("LM Studio attempt %d failed: %s — retrying in %ds", attempt + 1, exc, wait)
                    time.sleep(wait)
                else:
                    break
            except Exception as exc:
                last_exc = exc
                break

        raise ProviderError(f"LM Studio request failed after {self._max_retries + 1} attempt(s): {last_exc}") from last_exc

    def _parse_json_response(self, raw_text: str, schema: dict[str, Any]) -> dict[str, Any]:
        """T052: Parse and validate a JSON response. Raises StructuredOutputError on failure."""
        text = raw_text.strip()
        # Try to extract JSON block if model added surrounding text
        if not text.startswith("{"):
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                text = text[start:end]
            else:
                raise StructuredOutputError(f"Model response does not contain a JSON object: {raw_text[:200]!r}")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(f"Model response is not valid JSON: {exc}. Raw: {raw_text[:200]!r}") from exc
        if not isinstance(parsed, dict):
            raise StructuredOutputError(f"Expected JSON object, got: {type(parsed)}")
        return parsed

    def _raw_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Make a raw HTTP request to the LM Studio API."""
        url = f"{self._base_url}{path}"
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        data = json.dumps(body).encode("utf-8") if body is not None else None
        timeout_val = timeout or self._timeout

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout_val) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")[:300]
            raise ProviderError(f"HTTP {exc.code} from LM Studio: {body_text}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"Could not reach LM Studio at {url}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ProviderError(f"LM Studio request timed out after {timeout_val}s") from exc


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------


def build_provider_from_config(provider_config: dict[str, Any]) -> ProviderAdapter | None:
    """
    Build a ProviderAdapter from a provider config dict.

    Returns None when the provider config is empty (no provider configured).
    """
    provider_name = (
        provider_config.get("provider_name")
        or provider_config.get("name")
        or ""
    ).lower()

    if not provider_name or provider_name in ("none", "stub", "disabled"):
        return None

    if provider_name == "lmstudio":
        return LMStudioProvider(
            base_url=provider_config.get("base_url", _LM_STUDIO_DEFAULT_BASE),
            model_name=provider_config.get("model_name") or provider_config.get("model") or "local-model",
            timeout=int(provider_config.get("timeout", _DEFAULT_TIMEOUT)),
            max_retries=int(provider_config.get("max_retries", _DEFAULT_RETRIES)),
        )

    logger.warning("Unknown provider name %r — no provider will be used", provider_name)
    return None
