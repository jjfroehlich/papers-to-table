from __future__ import annotations

import hashlib
import json
from typing import Any, Protocol
from urllib import error, request

from paper_eval.contracts import (
    DEFAULT_JUDGE_MODEL_ID,
    DEFAULT_JUDGE_PROVIDER,
    DEFAULT_LM_STUDIO_API_BASE,
    JudgeConfig,
    JudgeRecord,
    JudgeRequest,
    JudgeResponse,
)
from paper_eval.errors import EvaluationError
from paper_eval.normalize import normalize_text_for_match, normalize_whitespace

_PROMPT_TEMPLATE = """You are a reproducible evaluator for one text field.
Decide whether the proposed answer is materially equivalent to the gold answer for the named field.
Return JSON only with this schema:
{"verdict":"correct|incorrect|unclear","rationale_label":"short-public-label"}

Rules:
- Use only the provided field name, optional field description, gold answer, proposed answer, and optional evidence excerpt.
- Do not explain chain-of-thought.
- Use verdict "correct" only for materially equivalent answers.
- Use verdict "incorrect" when the answers are materially different.
- Use verdict "unclear" only when the provided bounded context is insufficient.
"""


class TextJudge(Protocol):
    def judge(self, judge_request: JudgeRequest) -> JudgeResponse:
        ...


def prompt_hash_for_version(prompt_version: str) -> str:
    return hashlib.sha256(f"{prompt_version}\n{_PROMPT_TEMPLATE}".encode("utf-8")).hexdigest()


def build_judge_request(
    *,
    judge_config: JudgeConfig,
    run_id: str,
    row_id: str | None,
    column_name: str,
    cell_id: str | None,
    gold_value: Any,
    proposed_value: Any,
    field_description: str | None,
    evidence_excerpt: str | None,
) -> JudgeRequest:
    bounded_field_name, field_name_truncated = _bounded_text(column_name, judge_config.max_field_name_chars)
    bounded_description, description_truncated = _bounded_text(
        field_description, judge_config.max_field_description_chars
    )
    bounded_gold, gold_truncated = _bounded_text(gold_value, judge_config.max_value_chars)
    bounded_proposed, proposed_truncated = _bounded_text(proposed_value, judge_config.max_value_chars)
    bounded_evidence, evidence_truncated = _bounded_text(evidence_excerpt, judge_config.max_evidence_chars)
    normalized_gold = normalize_text_for_match(gold_value) or ""
    normalized_proposed = normalize_text_for_match(proposed_value) or ""
    prompt_hash = prompt_hash_for_version(judge_config.prompt_version)
    request_payload = {
        "field_name": bounded_field_name,
        "field_description": bounded_description,
        "gold_value": bounded_gold,
        "proposed_value": bounded_proposed,
        "normalized_gold": normalized_gold,
        "normalized_proposed": normalized_proposed,
        "evidence_excerpt": bounded_evidence,
        "prompt_version": judge_config.prompt_version,
        "prompt_hash": prompt_hash,
    }
    input_hash = hashlib.sha256(json.dumps(request_payload, sort_keys=True).encode("utf-8")).hexdigest()
    return JudgeRequest(
        run_id=run_id,
        row_id=row_id,
        column_name=bounded_field_name,
        cell_id=cell_id,
        field_description=bounded_description,
        gold_value=bounded_gold,
        proposed_value=bounded_proposed,
        normalized_gold=normalized_gold,
        normalized_proposed=normalized_proposed,
        evidence_excerpt=bounded_evidence,
        prompt_version=judge_config.prompt_version,
        prompt_hash=prompt_hash,
        input_hash=input_hash,
        was_truncated=any(
            (
                field_name_truncated,
                description_truncated,
                gold_truncated,
                proposed_truncated,
                evidence_truncated,
            )
        ),
    )


def judge_record_from_result(
    *,
    judge_config: JudgeConfig,
    judge_request: JudgeRequest,
    judge_response: JudgeResponse,
) -> JudgeRecord:
    usage = judge_response.metadata.get("usage", {}) if isinstance(judge_response.metadata, dict) else {}
    resolved_model_id = judge_response.metadata.get("resolved_model_id")
    return JudgeRecord(
        run_id=judge_request.run_id,
        row_id=judge_request.row_id,
        column_name=judge_request.column_name,
        cell_id=judge_request.cell_id,
        judge_provider=judge_config.provider,
        judge_configured_model_id=judge_config.model_id,
        judge_resolved_model_id=resolved_model_id,
        judge_model_id=judge_config.model_id,
        judge_prompt_version=judge_request.prompt_version,
        judge_prompt_hash=judge_request.prompt_hash,
        judge_temperature=judge_config.temperature,
        judge_verdict=judge_response.verdict,
        judge_input_hash=judge_request.input_hash,
        rationale_label=judge_response.rationale_label,
        request_tokens=usage.get("prompt_tokens"),
        response_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        input_was_truncated=judge_request.was_truncated,
        normalized_gold=judge_request.normalized_gold,
        normalized_proposed=judge_request.normalized_proposed,
        evidence_excerpt=judge_request.evidence_excerpt,
    )


class LMStudioTextJudge:
    def __init__(self, judge_config: JudgeConfig) -> None:
        self._judge_config = judge_config

    def judge(self, judge_request: JudgeRequest) -> JudgeResponse:
        endpoint = (self._judge_config.api_base or DEFAULT_LM_STUDIO_API_BASE).rstrip("/") + "/chat/completions"
        payload = {
            "model": self._judge_config.model_id,
            "temperature": self._judge_config.temperature,
            "max_tokens": self._judge_config.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "paper_eval_text_judge",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "verdict": {
                                "type": "string",
                                "enum": ["correct", "incorrect", "unclear"],
                            },
                            "rationale_label": {"type": ["string", "null"]},
                        },
                        "required": ["verdict", "rationale_label"],
                        "additionalProperties": False,
                    },
                },
            },
            "messages": [
                {"role": "system", "content": _PROMPT_TEMPLATE},
                {"role": "user", "content": _user_prompt(judge_request)},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._judge_config.api_key:
            headers["Authorization"] = f"Bearer {self._judge_config.api_key}"
        http_request = request.Request(endpoint, data=data, headers=headers, method="POST")
        try:
            with request.urlopen(http_request) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - exercised by integration environments
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvaluationError(f"LM Studio judge request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:  # pragma: no cover - exercised by integration environments
            raise EvaluationError(f"LM Studio judge request failed at {endpoint}: {exc.reason}") from exc

        choice = ((response_payload.get("choices") or [{}])[0]).get("message") or {}
        content = choice.get("content")
        if isinstance(content, list):
            content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
        try:
            parsed = json.loads(content or "")
        except json.JSONDecodeError as exc:
            raise EvaluationError("Judge returned non-JSON output despite strict structured-output request.") from exc
        verdict = parsed.get("verdict")
        if verdict not in {"correct", "incorrect", "unclear"}:
            raise EvaluationError("Judge returned an invalid verdict label.")
        rationale_label = parsed.get("rationale_label")
        return JudgeResponse(
            verdict=verdict,
            rationale_label=rationale_label,
            metadata={
                "provider": self._judge_config.provider,
                "configured_model_id": self._judge_config.model_id,
                "resolved_model_id": response_payload.get("model"),
                "usage": response_payload.get("usage", {}),
            },
        )

# Backward-compatible alias for existing tests/imports while LM Studio remains the only concrete judge adapter.
OpenAICompatibleTextJudge = LMStudioTextJudge


def _user_prompt(judge_request: JudgeRequest) -> str:
    payload = {
        "field_name": judge_request.column_name,
        "field_description": judge_request.field_description,
        "gold_value": judge_request.gold_value,
        "proposed_value": judge_request.proposed_value,
        "normalized_gold": judge_request.normalized_gold,
        "normalized_proposed": judge_request.normalized_proposed,
        "evidence_excerpt": judge_request.evidence_excerpt,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _bounded_text(value: Any, limit: int) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    normalized = normalize_whitespace(str(value))
    if normalized == "":
        return None, False
    if len(normalized) <= limit:
        return normalized, False
    clipped = normalized[: max(limit - 1, 0)].rstrip()
    return f"{clipped}…"[:limit], True
