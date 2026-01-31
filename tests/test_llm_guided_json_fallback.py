from __future__ import annotations

import httpx

from paper_table_agent.llm.client import LlmClient, LlmConfig
from paper_table_agent.llm.models import QueryExpansionResult


class _FakeClient:
    def __init__(self) -> None:
        self.calls: int = 0
        self.payloads: list[dict[str, object]] = []

    def post(self, url: str, json: dict[str, object], headers: dict[str, str] | None = None) -> httpx.Response:
        self.calls += 1
        self.payloads.append(json)
        request = httpx.Request("POST", url)
        if self.calls == 1:
            return httpx.Response(400, text="Failed to process regex", request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{\"queries\": []}"}}]},
            request=request,
        )


def test_guided_json_fallback_on_regex_error() -> None:
    client = LlmClient(
        LlmConfig(
            mode="openai",
            base_url="https://example.com/v1",
            api_key=None,
            model="test-model",
            guided_json_mode="on",
        )
    )
    fake_client = _FakeClient()
    client._client = fake_client  # type: ignore[assignment]
    result = client.complete_json("PROMPT_META: {}\nReturn JSON", QueryExpansionResult)
    assert isinstance(result, QueryExpansionResult)
    assert fake_client.calls == 2
    assert "response_format" in fake_client.payloads[0]
    assert "response_format" not in fake_client.payloads[1]
    messages = fake_client.payloads[1]["messages"]
    assert messages[0]["content"] == "Return ONLY JSON. No markdown. No preamble."
