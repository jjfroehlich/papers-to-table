from __future__ import annotations

from paper_table_agent.graph.extraction import GroupContext, build_extract_prompt
from paper_table_agent.llm.client import LlmClient, LlmConfig, estimate_tokens


def _make_group() -> GroupContext:
    return GroupContext(
        name="all_columns",
        columns=["Column A"],
        schema={"Column A": "Example column"},
        examples={},
        columns_payload=[{"col_id": 1, "name": "Column A", "description": "Example column"}],
        column_id_map={1: "Column A"},
        column_key_map={"column a": "Column A"},
    )


def _make_chunks(count: int) -> dict[str, list[dict[str, object]]]:
    chunks = []
    for idx in range(count):
        chunks.append(
            {
                "chunk_id": f"chunk-{idx}",
                "chunk_idx": idx,
                "chunk_pk": f"pk-{idx}",
                "page_start": 1,
                "page_end": 1,
                "text": "Lorem ipsum " * 40,
            }
        )
    return {"Column A": chunks}


def test_extract_prompt_respects_token_budget() -> None:
    client = LlmClient(
        LlmConfig(
            mode="stub",
            base_url="http://localhost:1234/v1",
            api_key=None,
            model="local-test",
            max_prompt_tokens=1200,
            max_prompt_chars=10000,
        )
    )
    prompt_meta: dict[str, object] = {}
    prompt, trimmed_chunks = build_extract_prompt(
        client,
        row_context={"row_id": "1", "Column A": "value"},
        group=_make_group(),
        chunks_by_column=_make_chunks(15),
        pdf_id="pdf-1",
        prompt_meta=prompt_meta,
    )
    assert estimate_tokens(prompt) <= client.config.max_prompt_tokens
    assert len(trimmed_chunks) < 15
    assert prompt_meta.get("prompt_trimmed") is True
