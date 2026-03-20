from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from .models import ProviderLocality, ProviderSettings


class ProviderError(RuntimeError):
    pass


@dataclass
class ProviderResponse:
    payload: dict
    provider_name: str
    provider_model: str
    locality: ProviderLocality


class BaseProvider:
    def __init__(self, settings: ProviderSettings):
        self.settings = settings

    def invoke(self, payload: dict) -> ProviderResponse:  # pragma: no cover - overridden
        raise NotImplementedError


class StubLMStudioProvider(BaseProvider):
    def invoke(self, payload: dict) -> ProviderResponse:
        context_text = " ".join(item.get("display_text", "") for item in payload.get("retrieval_context", []))
        lowered = context_text.lower()
        value = None
        state = "unclear"
        support = "weak"
        rationale = "No sufficiently specific evidence was retrieved."
        calculation = ""
        for line in context_text.split("\n"):
            if payload["column_name"].lower() in line.lower() and ":" in line:
                value = line.split(":", 1)[1].strip()
                state = "found"
                support = "direct"
                rationale = "The retrieved passage explicitly stated the requested field."
                break
        if value is None and "figure" in lowered and payload["column_name"].lower() in {"assay readout", "result summary", "figure finding"}:
            value = "Figure indicates positive signal"
            state = "inferred"
            support = "inferred"
            rationale = "The best support came from figure-oriented context rather than prose."
        if value is None and payload["retrieval_context"]:
            snippet = payload["retrieval_context"][0].get("display_text", "")
            if snippet:
                value = snippet[:120].strip()
                state = "inferred"
                support = "weak"
                rationale = "A concise value was synthesized from the highest-ranked retrieved text."
        if payload.get("current_value") and payload.get("verify_mode") and payload["current_value"].strip():
            value = payload["current_value"].strip()
            state = "found"
            support = "direct"
            rationale = "Verify mode mirrored the existing value so the reviewer can confirm or edit it."
        response = {
            "proposal_state": state,
            "proposed_value": value,
            "rationale": rationale,
            "calculation": calculation,
            "evidence_quote": payload["retrieval_context"][0]["display_text"][:240] if payload.get("retrieval_context") else "",
            "page": payload["retrieval_context"][0].get("page", 1) if payload.get("retrieval_context") else 1,
            "support": support,
        }
        return ProviderResponse(response, "stub-lmstudio", self.settings.model, ProviderLocality.LOCAL)


class LMStudioProvider(BaseProvider):
    def invoke(self, payload: dict) -> ProviderResponse:
        request_body = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": "Return only JSON matching the requested schema."},
                {"role": "user", "content": json.dumps(payload)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            with httpx.Client(timeout=self.settings.timeout_seconds) as client:
                response = client.post(f"{self.settings.base_url}/chat/completions", json=request_body)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise ProviderError("LM Studio request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"LM Studio request failed: {exc}") from exc
        try:
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content)
        except Exception as exc:  # noqa: BLE001
            raise ProviderError("LM Studio returned malformed structured output") from exc
        return ProviderResponse(parsed, "lmstudio", self.settings.model, ProviderLocality.LOCAL)


def get_provider(settings: ProviderSettings) -> BaseProvider:
    if settings.provider == "lmstudio":
        return LMStudioProvider(settings)
    return StubLMStudioProvider(settings)
