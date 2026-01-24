from paper_table_agent.llm.client import LlmClient, LlmConfig
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
