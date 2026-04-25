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


def _fallback_modes_for(structured_mode: str) -> list[str]:
    if structured_mode == "json_schema":
        return ["json_schema", "json_object", "none"]
    if structured_mode == "json_object":
        return ["json_object", "none"]
    return ["none"]


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _parse_judge_json(content: str) -> dict[str, Any]:
    cleaned = _strip_json_fence(content)
    candidates = [cleaned]
    balanced = _extract_balanced_json_object(cleaned)
    if balanced and balanced not in candidates:
        candidates.append(balanced)
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise EvaluationError("Judge returned non-JSON output after fallback parsing attempts.")


def _response_format_for(mode: str) -> dict[str, Any] | None:
    if mode == "json_schema":
        return {
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
        }
    if mode == "json_object":
        return {"type": "json_object"}
    return None


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
        judge_label=judge_config.label,
        judge_provider=judge_config.provider,
        judge_configured_model_id=judge_config.model_id,
        judge_resolved_model_id=resolved_model_id,
        judge_model_id=judge_config.model_id,
        judge_response_mode=(judge_response.metadata.get("judge_response_mode") if isinstance(judge_response.metadata, dict) else None),
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
        self._ensure_model_loaded(self._judge_config.model_id)
        endpoint = (self._judge_config.api_base or DEFAULT_LM_STUDIO_API_BASE).rstrip("/") + "/chat/completions"
        modes = _fallback_modes_for(self._judge_config.structured_output_mode)
        failures: list[str] = []
        for index, mode in enumerate(modes):
            payload = {
                "model": self._judge_config.model_id,
                "temperature": self._judge_config.temperature,
                "max_tokens": self._judge_config.max_output_tokens,
                "messages": [
                    {"role": "system", "content": _PROMPT_TEMPLATE},
                    {"role": "user", "content": _user_prompt(judge_request)},
                ],
            }
            response_format = _response_format_for(mode)
            if response_format is not None:
                payload["response_format"] = response_format
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
                if exc.code == 400 and index < len(modes) - 1:
                    failures.append(f"{mode}: HTTP {exc.code}: {detail[:200]}")
                    continue
                raise EvaluationError(f"LM Studio judge request failed with HTTP {exc.code}: {detail}") from exc
            except error.URLError as exc:  # pragma: no cover - exercised by integration environments
                raise EvaluationError(f"LM Studio judge request failed at {endpoint}: {exc.reason}") from exc

            choice = ((response_payload.get("choices") or [{}])[0]).get("message") or {}
            content = choice.get("content")
            if isinstance(content, list):
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            try:
                parsed = _parse_judge_json(content or "")
            except EvaluationError as exc:
                if index < len(modes) - 1:
                    failures.append(f"{mode}: {exc}")
                    continue
                if failures:
                    failure_summary = "; ".join(failures)
                    raise EvaluationError(
                        f"{exc} Fallback attempts: {failure_summary}."
                    ) from exc
                raise
            verdict = parsed.get("verdict")
            if verdict not in {"correct", "incorrect", "unclear"}:
                invalid_verdict = EvaluationError("Judge returned an invalid verdict label.")
                if index < len(modes) - 1:
                    failures.append(f"{mode}: {invalid_verdict}")
                    continue
                if failures:
                    failure_summary = "; ".join(failures)
                    raise EvaluationError(f"Judge returned an invalid verdict label. Fallback attempts: {failure_summary}.")
                raise invalid_verdict
            rationale_label = parsed.get("rationale_label")
            return JudgeResponse(
                verdict=verdict,
                rationale_label=rationale_label,
                metadata={
                    "provider": self._judge_config.provider,
                    "configured_model_id": self._judge_config.model_id,
                    "resolved_model_id": response_payload.get("model"),
                    "usage": response_payload.get("usage", {}),
                    "judge_response_mode": mode,
                    "structured_output_fallback_used": mode != modes[0],
                },
            )

        raise EvaluationError("Judge fallback ladder exhausted without a valid response.")

    def _ensure_model_loaded(self, model_id: str) -> None:
        models_payload = self._list_rest_models()
        unload_plan = self._plan_model_unloads(models_payload, model_id)
        for unload_item in unload_plan:
            try:
                self._unload_model_via_rest(instance_id=unload_item["instance_id"])
            except EvaluationError:
                continue

        if self._is_model_loaded(model_id):
            return

        self._load_model(model_id)
        if not self._is_model_loaded(model_id):
            raise EvaluationError(
                f"LM Studio reported a successful load request for judge model '{model_id}', but the model is still not listed at the OpenAI-compatible models endpoint."
            )

    def cleanup_model_residency(self) -> None:
        models_payload = self._list_rest_models()
        unload_plan = self._plan_model_unloads(models_payload, "")
        for unload_item in unload_plan:
            try:
                self._unload_model_via_rest(instance_id=unload_item["instance_id"])
            except EvaluationError:
                continue

    @staticmethod
    def _model_matches_requested_id(model_entry: dict[str, Any], model_id: str) -> bool:
        if str(model_entry.get("key") or "") == model_id:
            return True
        loaded_instances = model_entry.get("loaded_instances") or []
        return any(
            isinstance(instance, dict) and str(instance.get("id") or "") == model_id
            for instance in loaded_instances
        )

    @classmethod
    def _find_requested_model(cls, models_payload: dict[str, Any], model_id: str) -> dict[str, Any] | None:
        models = models_payload.get("models") or []
        for model_entry in models:
            if isinstance(model_entry, dict) and cls._model_matches_requested_id(model_entry, model_id):
                return model_entry
        return None

    @classmethod
    def _loaded_instance_ids(cls, model_entry: dict[str, Any]) -> list[str]:
        loaded_instances = model_entry.get("loaded_instances") or []
        instance_ids: list[str] = []
        for instance in loaded_instances:
            if not isinstance(instance, dict):
                continue
            instance_id = str(instance.get("id") or "").strip()
            if instance_id:
                instance_ids.append(instance_id)
        return instance_ids

    @classmethod
    def _plan_model_unloads(cls, models_payload: dict[str, Any], model_id: str) -> list[dict[str, Any]]:
        keep_instance_id = None
        requested_model = cls._find_requested_model(models_payload, model_id)
        if requested_model is not None:
            loaded_instance_ids = cls._loaded_instance_ids(requested_model)
            if loaded_instance_ids:
                keep_instance_id = loaded_instance_ids[0]

        unloads: list[dict[str, Any]] = []
        for model_entry in models_payload.get("models") or []:
            if not isinstance(model_entry, dict):
                continue
            model_key = str(model_entry.get("key") or "")
            for instance_id in cls._loaded_instance_ids(model_entry):
                if instance_id == keep_instance_id:
                    continue
                unloads.append(
                    {
                        "instance_id": instance_id,
                        "model_id": model_key,
                    }
                )
        return unloads

    def _list_rest_models(self) -> dict[str, Any]:
        endpoint = self._rest_api_base().rstrip("/") + "/api/v1/models"
        http_request = request.Request(endpoint, headers=self._build_headers(), method="GET")
        try:
            with request.urlopen(http_request) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - exercised by integration environments
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvaluationError(
                f"LM Studio judge request failed during model probe with HTTP {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:  # pragma: no cover - exercised by integration environments
            raise EvaluationError(
                f"LM Studio judge request failed during model probe at {endpoint}: {exc.reason}"
            ) from exc

    def _is_model_loaded(self, model_id: str) -> bool:
        endpoint = (self._judge_config.api_base or DEFAULT_LM_STUDIO_API_BASE).rstrip("/") + "/models"
        http_request = request.Request(endpoint, headers=self._build_headers(), method="GET")
        try:
            with request.urlopen(http_request) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:  # pragma: no cover - exercised by integration environments
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvaluationError(
                f"LM Studio judge request failed during model probe with HTTP {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:  # pragma: no cover - exercised by integration environments
            raise EvaluationError(
                f"LM Studio judge request failed during model probe at {endpoint}: {exc.reason}"
            ) from exc

        models = response_payload.get("data")
        if not isinstance(models, list):
            return False
        for entry in models:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id") or "").strip() == model_id:
                return True
        return False

    def _unload_model_via_rest(self, *, instance_id: str) -> None:
        endpoint = self._rest_api_base().rstrip("/") + "/api/v1/models/unload"
        payload = {"instance_id": instance_id}
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(content_type=True),
            method="POST",
        )
        try:
            with request.urlopen(http_request) as response:
                response.read()
        except error.HTTPError as exc:  # pragma: no cover - exercised by integration environments
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvaluationError(
                f"LM Studio judge request failed during model unload with HTTP {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:  # pragma: no cover - exercised by integration environments
            raise EvaluationError(
                f"LM Studio judge request failed during model unload at {endpoint}: {exc.reason}"
            ) from exc

    def _load_model(self, model_id: str) -> None:
        endpoint = self._rest_api_base().rstrip("/") + "/api/v1/models/load"
        payload = {
            "model": model_id,
            "echo_load_config": True,
        }
        http_request = request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._build_headers(content_type=True),
            method="POST",
        )
        try:
            with request.urlopen(http_request) as response:
                response.read()
        except error.HTTPError as exc:  # pragma: no cover - exercised by integration environments
            detail = exc.read().decode("utf-8", errors="replace")
            raise EvaluationError(
                f"LM Studio judge request failed during model load with HTTP {exc.code}: {detail}"
            ) from exc
        except error.URLError as exc:  # pragma: no cover - exercised by integration environments
            raise EvaluationError(
                f"LM Studio judge request failed during model load at {endpoint}: {exc.reason}"
            ) from exc

    def _rest_api_base(self) -> str:
        api_base = (self._judge_config.api_base or DEFAULT_LM_STUDIO_API_BASE).rstrip("/")
        if api_base.endswith("/v1"):
            return api_base[: -len("/v1")]
        return api_base

    def _build_headers(self, *, content_type: bool = False) -> dict[str, str]:
        headers: dict[str, str] = {}
        if content_type:
            headers["Content-Type"] = "application/json"
        if self._judge_config.api_key:
            headers["Authorization"] = f"Bearer {self._judge_config.api_key}"
        return headers

# Backward-compatible alias for existing imports; prefer LMStudioTextJudge in new code and remove this alias if the old name is no longer needed.
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
