from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from paper_table_agent.config import ExtractionConfig
from paper_table_agent.llm.client import LlmClient, LlmJsonError, estimate_tokens, get_capability_cache
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
    ctx_window_chars: int
    column_batches: list[list[str]]
    ctx_window_source: str | None = None
    ctx_window_reason: list[str] | None = None
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
    call_recorder: Callable[[str, dict[str, Any]], None] | None = None,
) -> tuple[ContextPlan, str]:
    ctx_window, ctx_window_chars, cap_meta = _effective_prompt_caps(extract_client)
    thinking_mode = _is_thinking_model(extract_client.config.model, extraction_config)
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
        batch_size = _resolve_batch_size(
            column_payloads,
            extraction_config,
            row_context,
            trimmed_text,
            "fulltext",
            ctx_window,
            extract_client,
            pdf_id,
        )
        column_batches = _build_column_batches(column_payloads, batch_size)
        plan = ContextPlan(
            pdf_id=pdf_id,
            mode="fulltext",
            included_sections=included_sections,
            page_marked_text_path=fulltext_path,
            token_estimate=prompt_tokens,
            ctx_window_tokens=ctx_window,
            ctx_window_chars=ctx_window_chars,
            ctx_window_source=cap_meta.get("source"),
            ctx_window_reason=cap_meta.get("reasons"),
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
            call_recorder=call_recorder,
        )
        if memory_payload:
            prompt_tokens = _estimate_prompt_tokens(
                pdf_id,
                "memory",
                _render_prompt_for_estimate(row_context, column_payloads, memory_payload, "memory"),
                extract_client,
            )
            batch_size = _resolve_batch_size(
                column_payloads,
                extraction_config,
                row_context,
                memory_payload,
                "memory",
                ctx_window,
                extract_client,
                pdf_id,
            )
            column_batches = _build_column_batches(column_payloads, batch_size)
            plan = ContextPlan(
                pdf_id=pdf_id,
                mode="memory",
                included_sections=included_sections,
                page_marked_text_path=memory_path,
                token_estimate=prompt_tokens,
                ctx_window_tokens=ctx_window,
                ctx_window_chars=ctx_window_chars,
                ctx_window_source=cap_meta.get("source"),
                ctx_window_reason=cap_meta.get("reasons"),
                column_batches=column_batches,
                memory_stats=memory_stats,
            )
            return plan, memory_payload
    batch_size = _resolve_batch_size(
        column_payloads,
        extraction_config,
        row_context,
        "",
        "retrieval",
        ctx_window,
        extract_client,
        pdf_id,
    )
    column_batches = _build_column_batches(column_payloads, batch_size)
    plan = ContextPlan(
        pdf_id=pdf_id,
        mode="retrieval",
        included_sections=included_sections,
        page_marked_text_path=None,
        token_estimate=prompt_tokens,
        ctx_window_tokens=ctx_window,
        ctx_window_chars=ctx_window_chars,
        ctx_window_source=cap_meta.get("source"),
        ctx_window_reason=cap_meta.get("reasons"),
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


def _effective_prompt_caps(client: LlmClient) -> tuple[int, int, dict[str, Any]]:
    max_tokens = client.config.max_prompt_tokens
    override_tokens = client.config.ctx_window_tokens_override
    max_chars = client.config.max_prompt_chars
    char_tokens = estimate_tokens("x" * max_chars) if max_chars else 0
    capabilities = get_capability_cache(client.config)
    probed_tokens = capabilities.get("ctx_window_tokens") if capabilities else None

    ctx_window = None
    source = None
    reasons: list[str] = []
    if override_tokens:
        ctx_window = int(override_tokens)
        source = "override"
        reasons.append("ctx_window_override")
    elif max_tokens:
        ctx_window = int(max_tokens)
        source = "max_prompt_tokens"
        reasons.append("max_prompt_tokens")
    elif isinstance(probed_tokens, int) and probed_tokens > 0:
        ctx_window = int(probed_tokens)
        source = "model_probe"
        reasons.append("ctx_window_probe")

    if char_tokens:
        if ctx_window:
            if char_tokens < ctx_window:
                reasons.append("max_prompt_chars")
            ctx_window = min(ctx_window, char_tokens)
        else:
            ctx_window = char_tokens
            source = "max_prompt_chars"
            reasons.append("max_prompt_chars")

    if not ctx_window:
        ctx_window = 0
        source = source or "unknown"

    meta = {
        "source": source,
        "reasons": reasons,
        "probe_tokens": probed_tokens,
        "max_prompt_tokens": max_tokens,
        "override_tokens": override_tokens,
        "char_tokens": char_tokens,
    }
    return int(ctx_window), max_chars, meta


def _resolve_batch_size(
    column_payloads: list[dict[str, Any]],
    extraction_config: ExtractionConfig,
    row_context: dict[str, Any],
    context_payload: str,
    context_mode: str,
    ctx_window: int,
    extract_client: LlmClient,
    pdf_id: str,
) -> int:
    base = max(1, extraction_config.column_batch_size)
    if base > 1 or not column_payloads:
        return base
    if not ctx_window:
        return base
    for candidate in (2, 3):
        if len(column_payloads) < candidate:
            break
        estimate = _estimate_prompt_tokens(
            pdf_id,
            f"{context_mode}_{candidate}",
            _render_prompt_for_estimate(row_context, column_payloads[:candidate], context_payload, context_mode),
            extract_client,
        )
        if estimate <= int(ctx_window * extraction_config.fulltext_target_ratio):
            return candidate
    return base


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
    call_recorder: Callable[[str, dict[str, Any]], None] | None = None,
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
        if call_recorder:
            call_recorder(
                "paper_memory",
                {
                    "pdf_id": pdf_id,
                    "anchor_count": len(anchors),
                },
            )
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
    extraction_payload = {"notes": result.notes}
    return json.dumps(extraction_payload, indent=2), stats, memory_path


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
