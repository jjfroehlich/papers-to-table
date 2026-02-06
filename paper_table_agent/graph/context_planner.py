from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paper_table_agent.config import ExtractionConfig
from paper_table_agent.llm.client import LlmClient, LlmJsonError, estimate_tokens
from paper_table_agent.llm.models import PaperMemoryResult
from paper_table_agent.llm.prompts import render_prompt


_PROMPT_TOKEN_CACHE: dict[tuple[str, str], int] = {}


@dataclass
class ContextPlan:
    pdf_id: str
    mode: str
    included_sections: list[str]
    page_marked_text_path: Path | None
    token_estimate: int
    ctx_window_tokens: int
    column_batches: list[list[str]]
    memory_stats: dict[str, Any] | None = None


def plan_context(
    pdf_id: str,
    page_text: list[str],
    column_payloads: list[dict[str, Any]],
    row_context: dict[str, Any],
    extract_client: LlmClient,
    helper_client: LlmClient,
    extraction_config: ExtractionConfig,
    run_dir: Path,
) -> tuple[ContextPlan, str]:
    ctx_window = extract_client.config.max_prompt_tokens or 0
    thinking_mode = _is_thinking_model(extract_client.config.model, extraction_config)
    column_batches = _build_column_batches(column_payloads, extraction_config.column_batch_size)
    fulltext = _assemble_page_marked_text(page_text)
    trimmed_text, included_sections, trim_steps = _trim_fulltext(fulltext, extraction_config)
    prompt_tokens = _estimate_prompt_tokens(
        pdf_id,
        "fulltext",
        _render_prompt_for_estimate(row_context, column_payloads, trimmed_text, "fulltext"),
        extract_client,
    )
    fulltext_path = None
    if trimmed_text:
        fulltext_path = run_dir / "artifacts" / "parsed" / f"{pdf_id}_context_fulltext.txt"
        fulltext_path.parent.mkdir(parents=True, exist_ok=True)
        fulltext_path.write_text(trimmed_text, encoding="utf-8")
    if (
        extraction_config.whole_text_enabled
        and thinking_mode
        and ctx_window
        and prompt_tokens <= int(ctx_window * extraction_config.fulltext_target_ratio)
    ):
        plan = ContextPlan(
            pdf_id=pdf_id,
            mode="fulltext",
            included_sections=included_sections,
            page_marked_text_path=fulltext_path,
            token_estimate=prompt_tokens,
            ctx_window_tokens=ctx_window,
            column_batches=column_batches,
        )
        return plan, trimmed_text
    if thinking_mode and extraction_config.paper_memory_enabled:
        memory_payload, memory_stats, memory_path = _build_memory_payload(
            pdf_id,
            page_text,
            extraction_config,
            helper_client,
            run_dir,
        )
        if memory_payload:
            prompt_tokens = _estimate_prompt_tokens(
                pdf_id,
                "memory",
                _render_prompt_for_estimate(row_context, column_payloads, memory_payload, "memory"),
                extract_client,
            )
            plan = ContextPlan(
                pdf_id=pdf_id,
                mode="memory",
                included_sections=included_sections,
                page_marked_text_path=memory_path,
                token_estimate=prompt_tokens,
                ctx_window_tokens=ctx_window,
                column_batches=column_batches,
                memory_stats=memory_stats,
            )
            return plan, memory_payload
    plan = ContextPlan(
        pdf_id=pdf_id,
        mode="retrieval",
        included_sections=included_sections,
        page_marked_text_path=None,
        token_estimate=prompt_tokens,
        ctx_window_tokens=ctx_window,
        column_batches=column_batches,
        memory_stats={"trim_steps": trim_steps},
    )
    return plan, ""


def _is_thinking_model(model_name: str, extraction_config: ExtractionConfig) -> bool:
    tokens = [token.lower() for token in extraction_config.thinking_models]
    model_lower = (model_name or "").lower()
    return any(token in model_lower for token in tokens)


def _build_column_batches(column_payloads: list[dict[str, Any]], batch_size: int) -> list[list[str]]:
    names = [payload.get("name") for payload in column_payloads if payload.get("name")]
    if batch_size <= 1:
        return [[name] for name in names]
    batches: list[list[str]] = []
    for idx in range(0, len(names), batch_size):
        batches.append(names[idx : idx + batch_size])
    return batches


def _assemble_page_marked_text(page_text: list[str]) -> str:
    parts: list[str] = []
    for idx, text in enumerate(page_text, start=1):
        if not text.strip():
            continue
        parts.append(f"## Page {idx}")
        parts.append(text.strip())
    return "\n\n".join(parts).strip()


def _trim_fulltext(text: str, extraction_config: ExtractionConfig) -> tuple[str, list[str], list[str]]:
    if not text:
        return "", [], []
    included_sections = _detect_sections(text)
    trimmed = text
    trim_steps: list[str] = []
    trimmed, dropped = _drop_section(trimmed, ["references", "bibliography"])
    if dropped:
        trim_steps.append("drop_references")
    trimmed, dropped = _drop_section(trimmed, ["acknowledgements", "acknowledgments"])
    if dropped:
        trim_steps.append("drop_acknowledgements")
    if trim_steps or len(trimmed) > 0:
        trimmed = _trim_captions(trimmed, extraction_config.fulltext_caption_max_chars)
        trim_steps.append("trim_captions")
    trimmed, dropped = _drop_section(trimmed, ["appendix", "supplementary", "supplement"])
    if dropped:
        trim_steps.append("drop_appendix")
    trimmed = _strip_table_like_blocks(trimmed)
    trim_steps.append("strip_table_blocks")
    return trimmed.strip(), included_sections, trim_steps


def _detect_sections(text: str) -> list[str]:
    sections = [
        "abstract",
        "introduction",
        "methods",
        "results",
        "discussion",
        "conclusion",
        "references",
    ]
    found: list[str] = []
    for section in sections:
        pattern = re.compile(rf"(?im)^\\s*{re.escape(section)}\\b")
        if pattern.search(text):
            found.append(section.capitalize())
    return found


def _drop_section(text: str, headers: list[str]) -> tuple[str, bool]:
    header_set = {header.lower() for header in headers}
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if line.strip().lower() in header_set:
            return "\n".join(lines[:idx]).rstrip(), True
    return text, False


def _trim_captions(text: str, max_chars: int) -> str:
    lines = text.splitlines()
    trimmed: list[str] = []
    for line in lines:
        if re.match(r"(?i)^\\s*(figure|fig\\.|table)\\s+\\d+", line.strip()):
            trimmed.append(line.strip()[:max_chars])
        else:
            trimmed.append(line)
    return "\n".join(trimmed)


def _strip_table_like_blocks(text: str) -> str:
    cleaned: list[str] = []
    for line in text.splitlines():
        if len(line) > 200 and sum(char.isdigit() for char in line) / max(len(line), 1) > 0.35:
            continue
        if re.match(r"^[\\s\\d\\|\\-\\+\\.]{20,}$", line):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _build_memory_payload(
    pdf_id: str,
    page_text: list[str],
    extraction_config: ExtractionConfig,
    helper_client: LlmClient,
    run_dir: Path,
) -> tuple[str, dict[str, Any], Path | None]:
    anchors: list[dict[str, Any]] = []
    total_tokens = 0
    for page_idx, text in enumerate(page_text, start=1):
        if not text.strip():
            continue
        tokens = estimate_tokens(text)
        if total_tokens + tokens > extraction_config.paper_memory_max_tokens:
            break
        anchors.append({"anchor_id": f"page-{page_idx}", "page": page_idx, "text": text})
        total_tokens += tokens
    if not anchors:
        return "", {"pages": 0, "anchors": 0, "notes": 0}, None
    prompt = render_prompt(
        "paper_memory.md",
        _prompt_meta={"pdf_id": pdf_id, "prompt_name": "paper_memory"},
        document_anchors=json.dumps(anchors, indent=2),
    )
    try:
        result = helper_client.complete_json(prompt, PaperMemoryResult)
    except LlmJsonError:
        return "", {"pages": len(anchors), "anchors": len(anchors), "notes": 0, "failed": True}, None
    payload = {
        "summary": result.summary,
        "notes": result.notes,
    }
    memory_path = run_dir / "artifacts" / "parsed" / f"{pdf_id}_context_memory.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    stats = {"pages": len(anchors), "anchors": len(anchors), "notes": len(result.notes)}
    return json.dumps(payload, indent=2), stats, memory_path


def _estimate_prompt_tokens(
    pdf_id: str,
    mode: str,
    prompt: str,
    client: LlmClient,
) -> int:
    cache_key = (pdf_id, mode)
    if cache_key in _PROMPT_TOKEN_CACHE:
        return _PROMPT_TOKEN_CACHE[cache_key]
    estimate = estimate_tokens(prompt)
    if client.config.measure_prompt_tokens:
        measured = client.measure_prompt_tokens(prompt)
        if measured:
            estimate = measured
    _PROMPT_TOKEN_CACHE[cache_key] = estimate
    return estimate


def _render_prompt_for_estimate(
    row_context: dict[str, Any],
    column_payloads: list[dict[str, Any]],
    context_payload: str,
    context_mode: str,
) -> str:
    column_payload = column_payloads[:1] if column_payloads else []
    return render_prompt(
        "extract_column.md",
        _prompt_meta={"prompt_name": "extract_column_estimate"},
        row_context=json.dumps(row_context, indent=2),
        columns=json.dumps(column_payload, indent=2),
        context_mode=context_mode,
        context_payload=context_payload,
    )
