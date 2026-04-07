from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
import respx
from unittest.mock import AsyncMock, patch

from backend.app.provider import LMStudioProvider, ProviderCapabilities, ProviderError, initialize_provider


def _provider_config(*, working_context_budget: int = 25000, load_context_length: int | None = 32000):
    return SimpleNamespace(
        token="lm_studio",
        base_url="http://localhost:1234",
        text_model=SimpleNamespace(
            working_context_budget=working_context_budget,
            required_load_context_length=load_context_length or working_context_budget,
            load_context_is_derived=load_context_length is None,
        ),
        vision_model=None,
    )


def _models_payload(*, loaded_instances: list[dict] | None = None, max_context_length: int = 65536) -> dict:
    return {
        "models": [
            {
                "type": "llm",
                "key": "text-model",
                "max_context_length": max_context_length,
                "loaded_instances": loaded_instances or [],
            },
            {
                "type": "llm",
                "key": "other-model",
                "max_context_length": 32768,
                "loaded_instances": [
                    {"id": "other-instance", "config": {"context_length": 8192}}
                ],
            },
        ]
    }


@pytest.mark.asyncio
@respx.mock
async def test_reuses_loaded_model_with_sufficient_context():
    provider = LMStudioProvider(base_url="http://localhost:1234")
    respx.get("http://localhost:1234/api/v1/models").mock(
        return_value=httpx.Response(
            200,
            json=_models_payload(
                loaded_instances=[
                    {"id": "text-instance", "config": {"context_length": 32000}}
                ]
            ),
        )
    )

    report = await provider.ensure_model_availability(
        text_model_id="text-model",
        text_working_context_budget=25000,
        text_load_context_length=32000,
        text_load_context_is_derived=False,
    )

    text_report = report["text_model"]
    assert text_report["reused_loaded_model"] is True
    assert text_report["load_requested"] is False
    assert text_report["loaded_instance_id"] == "text-instance"
    assert text_report["requested_load_context"] == 32000
    assert text_report["actual_load_config"]["context_length"] == 32000


@pytest.mark.asyncio
@respx.mock
async def test_loads_model_when_requested_model_is_not_currently_loaded():
    provider = LMStudioProvider(base_url="http://localhost:1234")
    respx.get("http://localhost:1234/api/v1/models").mock(
        return_value=httpx.Response(200, json=_models_payload(loaded_instances=[]))
    )
    respx.post("http://localhost:1234/api/v1/models/load").mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "llm",
                "instance_id": "text-model",
                "load_time_seconds": 4.2,
                "status": "loaded",
                "load_config": {"context_length": 32000},
            },
        )
    )

    report = await provider.ensure_model_availability(
        text_model_id="text-model",
        text_working_context_budget=25000,
        text_load_context_length=32000,
        text_load_context_is_derived=False,
    )

    text_report = report["text_model"]
    assert text_report["reused_loaded_model"] is False
    assert text_report["load_requested"] is True
    assert text_report["status"] == "loaded_via_api"
    assert text_report["loaded_instance_context_length"] == 32000
    assert text_report["load_time_seconds"] == 4.2


@pytest.mark.asyncio
@respx.mock
async def test_loads_model_when_loaded_context_is_insufficient():
    provider = LMStudioProvider(base_url="http://localhost:1234")
    respx.get("http://localhost:1234/api/v1/models").mock(
        return_value=httpx.Response(
            200,
            json=_models_payload(
                loaded_instances=[
                    {"id": "text-instance-small", "config": {"context_length": 16000}}
                ]
            ),
        )
    )
    respx.post("http://localhost:1234/api/v1/models/load").mock(
        return_value=httpx.Response(
            200,
            json={
                "type": "llm",
                "instance_id": "text-model",
                "load_time_seconds": 5.8,
                "status": "loaded",
                "load_config": {"context_length": 32000},
            },
        )
    )

    report = await provider.ensure_model_availability(
        text_model_id="text-model",
        text_working_context_budget=25000,
        text_load_context_length=32000,
        text_load_context_is_derived=False,
    )

    text_report = report["text_model"]
    assert text_report["load_requested"] is True
    assert text_report["reused_loaded_model"] is False
    assert text_report["existing_loaded_instances"][0]["context_length"] == 16000
    assert text_report["loaded_instance_context_length"] == 32000


@pytest.mark.asyncio
@respx.mock
async def test_load_failure_is_reported_honestly():
    provider = LMStudioProvider(base_url="http://localhost:1234")
    respx.get("http://localhost:1234/api/v1/models").mock(
        return_value=httpx.Response(200, json=_models_payload(loaded_instances=[]))
    )
    respx.post("http://localhost:1234/api/v1/models/load").mock(
        return_value=httpx.Response(500, text="load failed")
    )

    with pytest.raises(ProviderError) as exc:
        await provider.ensure_model_availability(
            text_model_id="text-model",
            text_working_context_budget=25000,
            text_load_context_length=32000,
            text_load_context_is_derived=False,
        )

    assert exc.value.reason == "model_load_failed"
    details = exc.value.details or {}
    text_report = details["model_management"]["text_model"]
    assert text_report["load_requested"] is True
    assert text_report["status"] == "failed"
    assert text_report["failure"]["reason"] == "model_load_failed"


@pytest.mark.asyncio
async def test_initialize_provider_exposes_model_management_in_provider_mode():
    config = _provider_config()
    model_management = {
        "provider": "lm_studio",
        "base_url": "http://localhost:1234",
        "text_model": {
            "model_id": "text-model",
            "requested_load_context": 32000,
            "load_requested": False,
            "reused_loaded_model": True,
            "loaded_instance_context_length": 32000,
            "status": "reused_loaded_instance",
        },
        "vision_model": None,
        "recorded_at": "2026-04-07T00:00:00+00:00",
    }
    caps = ProviderCapabilities(
        supports_structured_output=True,
        structured_output_mode="json_schema",
        model_id="text-model",
        vision_capable=False,
    )

    with patch.object(
        LMStudioProvider,
        "ensure_model_availability",
        new=AsyncMock(return_value=model_management),
    ), patch.object(
        LMStudioProvider,
        "probe_capabilities",
        new=AsyncMock(return_value=caps),
    ):
        provider, mode = await initialize_provider(
            config,
            text_model_id="text-model",
            vision_model_id=None,
        )

    assert isinstance(provider, LMStudioProvider)
    assert mode.model_management is not None
    assert mode.model_management["text_model"]["reused_loaded_model"] is True
    assert mode.model_management["text_model"]["requested_load_context"] == 32000