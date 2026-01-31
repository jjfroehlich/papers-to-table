from __future__ import annotations

from paper_table_agent.llm.client import LlmClient, LlmConfig


def _client() -> LlmClient:
    return LlmClient(
        LlmConfig(
            mode="openai",
            base_url="https://example.com/v1",
            api_key=None,
            model="test-model",
        )
    )


def test_parse_json_with_leading_text() -> None:
    client = _client()
    content = "Here is the result:\nSure, here's the JSON.\n\n{\"foo\": 1, \"bar\": \"ok\"}"
    assert client._parse_json(content) == {"foo": 1, "bar": "ok"}


def test_parse_json_last_fenced_block() -> None:
    client = _client()
    content = """
Some text
```json
{\"a\": 1}
```
More analysis
```json
{\"b\": 2}
```
"""
    assert client._parse_json(content) == {"b": 2}


def test_parse_json_array_span() -> None:
    client = _client()
    content = "Output follows: [1, 2, 3]\nTrailing notes."
    assert client._parse_json(content) == [1, 2, 3]


def test_parse_json_with_think_block() -> None:
    client = _client()
    content = "<think>Reasoning\nMore reasoning</think>\n{\"ok\": true}"
    assert client._parse_json(content) == {"ok": True}


def test_parse_json_with_think_and_fence() -> None:
    client = _client()
    content = "<think>analysis</think>\n```json\n{\"title\": \"Paper\"}\n```"
    assert client._parse_json(content) == {"title": "Paper"}
