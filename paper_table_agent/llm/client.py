from __future__ import annotations

import ipaddress
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LlmJsonError(RuntimeError):
    def __init__(
        self,
        message: str,
        prompt: str,
        response: str,
        repair_attempted: bool,
        validation_errors: list[dict[str, Any]] | None = None,
        http_status: int | None = None,
        error_substring: str | None = None,
        guided_json_active: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.prompt = prompt
        self.response = response
        self.repair_attempted = repair_attempted
        self.validation_errors = validation_errors or []
        self.http_status = http_status
        self.error_substring = error_substring
        self.guided_json_active = guided_json_active


@dataclass
class LlmConfig:
    mode: str
    base_url: str
    api_key: str | None
    model: str
    timeout_s: float = 60.0
    max_retries: int = 2
    max_prompt_chars: int = 12000
    mock_mode: bool = False
    mock_payloads: dict[str, Any] | None = None
    guided_json_mode: str = "auto"
    record_path: Path | None = None


class LlmClient:
    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        self._client = httpx.Client(timeout=self.config.timeout_s)
        self.last_raw_response: str | None = None
        self.last_guided_json_error: str | None = None
        self.last_guided_json_status: int | None = None
        self.last_guided_json_active: bool | None = None
        if self.config.record_path:
            self.config.record_path.parent.mkdir(parents=True, exist_ok=True)

    def _truncate_prompt(self, prompt: str) -> str:
        max_chars = self.config.max_prompt_chars
        if len(prompt) <= max_chars:
            return prompt
        head = max_chars // 2
        tail = max_chars - head
        return f"{prompt[:head]}\n\n...[TRUNCATED]...\n\n{prompt[-tail:]}"

    def complete_json(self, prompt: str, schema: type[T]) -> T:
        if self.config.mode == "stub":
            result = self._stub_response(prompt, schema)
            self.last_raw_response = _coerce_raw_response(result)
            return result
        if self.config.mock_mode or self.config.mode == "mock":
            result = self._mock_response(prompt, schema)
            self.last_raw_response = _coerce_raw_response(result)
            return result
        schema_payload = schema.model_json_schema()
        guided_schema_payload = strip_regex_from_json_schema(schema_payload)
        prompt_working = prompt
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        url = f"{self.config.base_url}/chat/completions"
        last_error: Exception | None = None
        validation_errors: list[dict[str, Any]] | None = None
        repair_attempted = False
        content = ""
        self.last_guided_json_error = None
        self.last_guided_json_status = None
        self.last_guided_json_active = None
        guided_allowed = self._should_use_guided_json()
        for attempt in range(self.config.max_retries + 1):
            payload: dict[str, Any] = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": "Return strict JSON only."},
                    {"role": "user", "content": prompt_working},
                ],
                "temperature": 0.1,
            }
            if guided_allowed:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "schema": guided_schema_payload,
                    },
                }
            response = self._client.post(url, json=payload, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                error_text = response.text
                if response.status_code == 400 and "context length" in error_text.lower():
                    truncated = self._truncate_prompt(prompt_working)
                    if truncated != prompt_working:
                        prompt_working = truncated
                        continue
                if response.status_code == 400 and guided_allowed and _is_guided_json_error(error_text):
                    self.last_guided_json_error = _extract_error_substring(error_text)
                    self.last_guided_json_status = response.status_code
                    self.last_guided_json_active = True
                    guided_allowed = False
                    continue
                raise LlmJsonError(
                    f"LLM HTTP error {response.status_code}: {response.text}",
                    prompt,
                    error_text,
                    repair_attempted=False,
                    http_status=response.status_code,
                    error_substring=_extract_error_substring(error_text),
                    guided_json_active=guided_allowed,
                ) from exc
            content = response.json()["choices"][0]["message"]["content"]
            self.last_raw_response = content
            self._record_interaction(
                prompt=prompt_working,
                response=content,
                stage="completion",
                attempt=attempt,
                model=self.config.model,
            )
            try:
                parsed = self._parse_json(content)
                return schema.model_validate(parsed)
            except ValidationError as exc:
                last_error = exc
                validation_errors = exc.errors()
                repair_attempted = True
                repair = self._repair_json(content, schema)
                if repair is not None:
                    return repair
                if attempt >= self.config.max_retries:
                    break
                time.sleep(1 + attempt)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                repair_attempted = True
                repair = self._repair_json(content, schema)
                if repair is not None:
                    return repair
                if attempt >= self.config.max_retries:
                    break
                time.sleep(1 + attempt)
        raise LlmJsonError(
            f"Failed to parse JSON after retries: {last_error}",
            prompt,
            content,
            repair_attempted,
            validation_errors=validation_errors,
        )

    def _should_use_guided_json(self) -> bool:
        mode = (self.config.guided_json_mode or "auto").lower()
        if mode == "on":
            return True
        if mode == "off":
            return False
        base_url = self.config.base_url or ""
        base_url_lower = base_url.lower()
        if any(token in base_url_lower for token in ("localhost", "127.0.0.1", "ollama", "lm-studio", "lmstudio")):
            return False
        host = urlparse(base_url).hostname or ""
        host_lower = host.lower()
        if host_lower in {"localhost", "host.docker.internal"} or host_lower.endswith(".local"):
            return False
        if host_lower:
            try:
                ip = ipaddress.ip_address(host_lower)
                if ip.is_loopback or ip.is_private or ip.is_link_local:
                    return False
            except ValueError:
                pass
        return True

    def _parse_json(self, content: str) -> Any:
        cleaned = _strip_markdown_fences(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            snippet = _extract_first_json(cleaned)
            if snippet is None:
                raise
            return json.loads(snippet)

    def _mock_response(self, prompt: str, schema: type[T]) -> T:
        payload = self.config.mock_payloads or {}
        prompt_meta = _extract_prompt_meta(prompt)
        if prompt_meta:
            key = _build_mock_key(prompt_meta)
            if key in payload:
                return schema.model_validate(payload[key])
            prompt_key = prompt_meta.get("prompt_name")
            if prompt_key and prompt_key in payload:
                return schema.model_validate(payload[prompt_key])
        for key, value in payload.items():
            if key in prompt:
                return schema.model_validate(value)
        schema_name = schema.__name__
        if schema_name == "QueryExpansionResult":
            query = _extract_prompt_query(prompt)
            return schema.model_validate({"queries": [query] if query else []})
        if schema_name == "HydeResult":
            query = _extract_prompt_query(prompt)
            return schema.model_validate({"passage": query or ""})
        raise ValueError("Mock mode enabled but no matching payload provided")

    def _stub_response(self, prompt: str, schema: type[T]) -> T:
        schema_name = schema.__name__
        if schema_name == "HeaderExtractionResult":
            header_lines = _extract_section_lines(prompt, "Text:")
            title = header_lines[0] if header_lines else "Untitled"
            authors = [header_lines[1]] if len(header_lines) > 1 else []
            year = None
            for line in header_lines:
                if line.strip().isdigit():
                    year = line.strip()
                    break
            return schema.model_validate(
                {
                    "title": title,
                    "authors": authors,
                    "year": year,
                    "evidence": [
                        {
                            "quote": title,
                            "page": 1,
                            "chunk_id": "page-1",
                            "locator_hint": title,
                        }
                    ],
                    "confidence": 0.8,
                }
            )
        if schema_name == "AdjudicationResult":
            candidates = _extract_prompt_json(prompt, "Candidates:")
            row_id = None
            if isinstance(candidates, list) and candidates:
                row_id = str(candidates[0].get("row_id"))
            return schema.model_validate(
                {
                    "row_id": row_id,
                    "status": "matched" if row_id else "unmatched",
                    "top_candidates": candidates or [],
                    "confidence": 0.9 if row_id else 0.0,
                    "evidence": [],
                    "rationale": "Fake adjudication",
                }
            )
        if schema_name == "GroupExtractionResult":
            columns_payload = _extract_prompt_json(prompt, "Columns (use col_id in responses):")
            chunks = _extract_prompt_json(prompt, "Retrieved chunks:")
            proposals = []
            chunks_list = chunks or []
            first_chunk = chunks_list[0] if chunks_list else {}
            for column in columns_payload or []:
                col_id = column.get("col_id")
                column_name = column.get("name") or column.get("column") or "unknown"
                if first_chunk:
                    quote = str(first_chunk.get("text", "")).strip()
                    quote = quote.split(".")[0].strip() if quote else ""
                    proposals.append(
                        {
                            "col_id": col_id,
                            "column": column_name,
                            "proposed_value": quote or f"{column_name} value",
                            "status": "found" if quote else "unclear",
                            "confidence": 0.7,
                            "evidence_quality": "strong" if quote else "none",
                            "evidence": [
                                {
                                    "quote": quote,
                                    "page": first_chunk.get("page_start") or 1,
                                    "chunk_id": first_chunk.get("chunk_id"),
                                    "chunk_pk": first_chunk.get("chunk_pk"),
                                    "chunk_idx": first_chunk.get("chunk_idx"),
                                    "locator_hint": quote,
                                }
                            ]
                            if quote
                            else [],
                            "search_hints": [column_name] if not quote else [],
                            "needs_more_evidence": not bool(quote),
                            "rationale": "Fake extraction",
                        }
                    )
                else:
                    proposals.append(
                        {
                            "col_id": col_id,
                            "column": column_name,
                            "proposed_value": None,
                            "status": "unclear",
                            "confidence": 0.0,
                            "evidence_quality": "none",
                            "evidence": [],
                            "search_hints": [column_name],
                            "needs_more_evidence": True,
                            "rationale": "No evidence located in stub retrieval.",
                        }
                    )
            return schema.model_validate({"proposals": proposals})
        if schema_name in {"VerifyResult", "ProposalVerificationResult"}:
            cell_value_payload = _extract_prompt_json(prompt, "Cell value:") or {}
            proposed_value = _extract_prompt_json(prompt, "Proposed value:")
            if proposed_value is None:
                proposed_value = cell_value_payload.get("value") if isinstance(cell_value_payload, dict) else None
            evidence = _extract_prompt_json(prompt, "Evidence:") or []
            if not evidence:
                evidence = _extract_prompt_json(prompt, "Retrieved chunks:") or []
            quotes = " ".join([str(item.get("quote", "")) for item in evidence if isinstance(item, dict)])
            value_text = str(proposed_value or "")
            status = "supports" if value_text and value_text.lower() in quotes.lower() else "unclear"
            column_value = _extract_prompt_json(prompt, "Column:")
            if column_value is None and isinstance(cell_value_payload, dict):
                column_value = cell_value_payload.get("column")
            payload = {
                "column": column_value or "unknown",
                "status": status,
                "evidence": evidence if schema_name == "VerifyResult" else [],
                "rationale": "Fake verification",
                "needs_more_evidence": status != "supports",
            }
            return schema.model_validate(payload)
        if schema_name == "QueryExpansionResult":
            query = _extract_prompt_query(prompt)
            return schema.model_validate({"queries": [query] if query else []})
        if schema_name == "HydeResult":
            query = _extract_prompt_query(prompt)
            return schema.model_validate({"passage": query or ""})
        raise ValueError(f"Stub mode missing handler for {schema_name}")

    def _repair_json(self, content: str, schema: type[T]) -> T | None:
        schema_payload = schema.model_json_schema()
        guided_schema_payload = strip_regex_from_json_schema(schema_payload)
        guided_allowed = self._should_use_guided_json()
        repair_prompt = (
            "Repair the following content into strict JSON that matches the schema. "
            "Return JSON only, no markdown.\n\n"
            f"Schema:\n{json.dumps(guided_schema_payload if guided_allowed else schema_payload, indent=2)}\n\n"
            f"Content:\n{content}"
        )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are a JSON repair tool. Return strict JSON only."},
                {"role": "user", "content": repair_prompt},
            ],
            "temperature": 0.0,
        }
        if guided_allowed:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{schema.__name__}Repair",
                    "schema": guided_schema_payload,
                },
            }
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        url = f"{self.config.base_url}/chat/completions"
        response = self._client.post(url, json=payload, headers=headers)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            if response.status_code == 400 and guided_allowed and _is_guided_json_error(response.text):
                self.last_guided_json_error = _extract_error_substring(response.text)
                self.last_guided_json_status = response.status_code
                self.last_guided_json_active = True
                payload.pop("response_format", None)
                response = self._client.post(url, json=payload, headers=headers)
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    return None
            else:
                return None
        content = response.json()["choices"][0]["message"]["content"]
        self._record_interaction(
            prompt=repair_prompt,
            response=content,
            stage="repair",
            attempt=0,
            model=self.config.model,
        )
        try:
            parsed = self._parse_json(content)
            return schema.model_validate(parsed)
        except Exception:  # noqa: BLE001
            return None

    def _record_interaction(
        self,
        prompt: str,
        response: str,
        stage: str,
        attempt: int,
        model: str,
    ) -> None:
        if not self.config.record_path:
            return
        payload = {
            "timestamp": time.time(),
            "stage": stage,
            "attempt": attempt,
            "model": model,
            "prompt": prompt,
            "response": response,
            "prompt_meta": _extract_prompt_meta(prompt) or {},
        }
        with self.config.record_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload) + "\n")


def _extract_prompt_query(prompt: str) -> str | None:
    lines = [line.strip() for line in prompt.splitlines() if line.strip()]
    if not lines:
        return None
    for prefix in ("Base query:", "Prompt:"):
        for idx, line in enumerate(lines):
            if line.startswith(prefix):
                if idx + 1 < len(lines):
                    return lines[idx + 1]
                return None
    return lines[-1]


def _extract_prompt_json(prompt: str, marker: str) -> Any:
    idx = prompt.find(marker)
    if idx == -1:
        return None
    snippet = prompt[idx + len(marker) :].strip()
    first_line = snippet.splitlines()[0] if snippet else ""
    if first_line:
        try:
            return json.loads(first_line)
        except json.JSONDecodeError:
            pass
    start_obj = snippet.find("{")
    start_arr = snippet.find("[")
    if start_obj == -1 and start_arr == -1:
        return None
    if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
        start = start_arr
        opening, closing = "[", "]"
    else:
        start = start_obj
        opening, closing = "{", "}"
    depth = 0
    end = None
    for idx, char in enumerate(snippet[start:], start=start):
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                end = idx
                break
    if end is None:
        return None
    try:
        return json.loads(snippet[start : end + 1])
    except json.JSONDecodeError:
        return None


def _extract_section_lines(prompt: str, marker: str) -> list[str]:
    idx = prompt.find(marker)
    if idx == -1:
        return []
    snippet = prompt[idx + len(marker) :].strip()
    lines = [line.strip() for line in snippet.splitlines() if line.strip()]
    return lines


def _extract_prompt_meta(prompt: str) -> dict[str, Any] | None:
    marker = "PROMPT_META:"
    for line in prompt.splitlines():
        if line.startswith(marker):
            payload = line[len(marker) :].strip()
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None
    return None


def _coerce_raw_response(result: object) -> str:
    if hasattr(result, "model_dump"):
        return json.dumps(result.model_dump(mode="json"))
    try:
        return json.dumps(result)
    except TypeError:
        return str(result)


def _build_mock_key(meta: dict[str, Any]) -> str:
    prompt_name = meta.get("prompt_name") or ""
    pdf_id = meta.get("pdf_id") or ""
    column = meta.get("column") or ""
    group = meta.get("group") or ""
    scope = column or group
    return f"{prompt_name}|{pdf_id}|{scope}"


def _is_guided_json_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    return any(
        token in lowered
        for token in (
            "failed to process regex",
            "regex",
            "grammar",
            "guided",
            "json_schema",
            "response_format",
        )
    )


def strip_regex_from_json_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        cleaned = {}
        for key, value in schema.items():
            if key in {"pattern", "patternProperties"}:
                continue
            cleaned[key] = strip_regex_from_json_schema(value)
        return cleaned
    if isinstance(schema, list):
        return [strip_regex_from_json_schema(item) for item in schema]
    return schema


def _extract_error_substring(error_text: str) -> str:
    text = (error_text or "").strip()
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            if key in payload:
                return str(payload[key])
    return text


def _strip_markdown_fences(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _extract_first_json(content: str) -> str | None:
    start_positions = [pos for pos in (content.find("{"), content.find("[")) if pos != -1]
    if not start_positions:
        return None
    start = min(start_positions)
    stack = []
    for idx in range(start, len(content)):
        char = content[idx]
        if char in "{[":
            stack.append(char)
        elif char in "}]":
            if not stack:
                continue
            opening = stack.pop()
            if opening == "{" and char != "}":
                continue
            if opening == "[" and char != "]":
                continue
            if not stack:
                return content[start : idx + 1]
    return None
