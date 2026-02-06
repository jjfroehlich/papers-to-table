from __future__ import annotations

from paper_table_agent.graph.extraction import GroupContext, build_extract_prompt, build_extract_prompt_batches
from paper_table_agent.llm.client import LlmClient, LlmConfig, estimate_tokens


def _make_group() -> GroupContext:
    return GroupContext(
        name="all_columns",
        columns=["Column A", "Column B", "Column C"],
        schema={"Column A": "Example column", "Column B": "Example column", "Column C": "Example column"},
        examples={},
        columns_payload=[
            {"col_id": 1, "name": "Column A", "description": "Example column"},
            {"col_id": 2, "name": "Column B", "description": "Example column"},
            {"col_id": 3, "name": "Column C", "description": "Example column"},
        ],
        column_id_map={1: "Column A", 2: "Column B", 3: "Column C"},
        column_key_map={"column a": "Column A", "column b": "Column B", "column c": "Column C"},
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
    return {"Column A": chunks, "Column B": chunks, "Column C": chunks}


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


def test_extract_prompt_batches_keep_chunks_and_cover_columns() -> None:
    client = LlmClient(
        LlmConfig(
            mode="stub",
            base_url="http://localhost:1234/v1",
            api_key=None,
            model="local-test",
            max_prompt_tokens=250,
            max_prompt_chars=1500,
        )
    )
    batches = build_extract_prompt_batches(
        client,
        row_context={"row_id": "1", "Column A": "value"},
        group=_make_group(),
        merged_chunks=[chunk for chunk in _make_chunks(6)["Column A"]],
        pdf_id="pdf-1",
    )
    assert len(batches) >= 2
    all_col_ids = [col_id for batch in batches for col_id in batch.col_ids]
    assert sorted(all_col_ids) == [1, 2, 3]
    for batch in batches:
        assert "Context payload" in batch.prompt
        assert "\"chunk_id\"" in batch.prompt
        assert batch.prompt_meta.get("prompt_has_chunks") is True
