import json

import httpx

from paper_table_agent.graph.extraction import GroupContext, build_proposal_records, extract_group
from paper_table_agent.llm.client import LlmClient, LlmConfig, strip_regex_from_json_schema
from paper_table_agent.llm.models import GroupExtractionResult, HeaderExtractionResult


def test_stub_llm_provider_returns_deterministic_json() -> None:
    client = LlmClient(
        LlmConfig(
            mode="stub",
            base_url="http://localhost:1234/v1",
            api_key=None,
            model="stub-model",
        )
    )
    header_prompt = "Text:\nTest Paper\nAda Lovelace\n2024\n"
    header = client.complete_json(header_prompt, HeaderExtractionResult)
    assert header.title == "Test Paper"
    assert header.year == "2024"

    extraction_prompt = (
        "Columns (use col_id in responses):\n"
        "[{\"col_id\": 1, \"name\": \"Method\", \"description\": \"Method used\", \"examples\": []}]\n"
        "Retrieved chunks:\n"
        "[{\"chunk_id\": \"page-1\", \"chunk_idx\": 1, \"text\": \"Method: method X.\", \"page_start\": 1}]"
    )
    extraction = client.complete_json(extraction_prompt, GroupExtractionResult)
    assert extraction.proposals


def test_guided_json_fallback_on_regex_error() -> None:
    calls: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        calls.append(payload)
        if "response_format" in payload:
            return httpx.Response(400, json={"error": "Failed to process regex"})
        content = {
            "proposals": [
                {
                    "column": "Method",
                    "proposed_value": "X",
                    "status": "found",
                    "confidence": 0.9,
                    "evidence": [],
                }
            ]
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(content)}}]})

    client = LlmClient(
        LlmConfig(
            mode="openai",
            base_url="http://example.com/v1",
            api_key=None,
            model="test-model",
            guided_json_mode="on",
        )
    )
    client._client = httpx.Client(transport=httpx.MockTransport(handler))

    group = GroupContext(
        name="test",
        columns=["Method"],
        schema={"Method": "Method description"},
        examples={},
        columns_payload=[{"col_id": 1, "name": "Method", "description": "Method description", "examples": []}],
        column_id_map={1: "Method"},
        column_key_map={"method": "Method"},
    )
    result = extract_group(
        client,
        row_context={"row_id": "1", "title": "Test"},
        group=group,
        chunks_by_column={"Method": []},
        mapping_dependent=False,
        pdf_id="pdf-1",
    )
    proposals = build_proposal_records("pdf-1", "1", result)

    assert calls[0].get("response_format") is not None
    assert "response_format" not in calls[1]
    assert proposals[0]["status"] != "error"
    assert proposals[0]["proposed_value"] == "X"


def test_strip_regex_from_json_schema_removes_pattern_keys() -> None:
    schema = {
        "type": "object",
        "pattern": "^root$",
        "properties": {
            "name": {"type": "string", "pattern": "^[a-z]+$"},
            "meta": {
                "type": "object",
                "patternProperties": {"^x-": {"type": "string"}},
            },
        },
    }
    cleaned = strip_regex_from_json_schema(schema)
    assert "pattern" not in cleaned
    assert "patternProperties" not in cleaned["properties"]["meta"]
    assert "pattern" not in cleaned["properties"]["name"]
