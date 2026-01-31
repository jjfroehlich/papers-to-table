from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_CAPABILITY_CACHE: dict[tuple[str, str], dict[str, bool]] = {}


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
        error_class: str | None = None,
    ) -> None:
        super().__init__(message)
        self.prompt = prompt
        self.response = response
        self.repair_attempted = repair_attempted
        self.validation_errors = validation_errors or []
        self.http_status = http_status
        self.error_substring = error_substring
        self.guided_json_active = guided_json_active
        self.error_class = error_class


@dataclass
class LlmConfig:
    mode: str
    base_url: str
    api_key: str | None
    model: str
    timeout_s: float = 60.0
    read_timeout_s: float | None = None
    max_retries: int = 2
    max_prompt_chars: int = 12000
    max_prompt_tokens: int | None = None
    mock_mode: bool = False
    mock_payloads: dict[str, Any] | None = None
    guided_json_mode: str = "auto"
    record_path: Path | None = None
    payload_record_path: Path | None = None
    llm_debug: bool = False
    log_snippet_chars: int = 240
    logger: logging.Logger | None = None


class LlmClient:
    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        self._client = httpx.Client(timeout=_build_timeout(config))
        self.last_raw_response: str | None = None
        self.last_request_log: dict[str, Any] | None = None
        self.last_guided_json_error: str | None = None
        self.last_guided_json_status: int | None = None
        self.last_guided_json_active: bool | None = None
        if self.config.record_path:
            self.config.record_path.parent.mkdir(parents=True, exist_ok=True)
        if self.config.payload_record_path:
            self.config.payload_record_path.parent.mkdir(parents=True, exist_ok=True)

    def _truncate_prompt(self, prompt: str, max_tokens: int | None = None) -> str:
        max_chars = self.config.max_prompt_chars
        max_tokens = max_tokens if max_tokens is not None else self.config.max_prompt_tokens
        prompt_working = prompt
        if max_tokens:
            prompt_working = _truncate_by_tokens(prompt_working, max_tokens)
        if len(prompt_working) <= max_chars:
            return prompt_working
        head = max_chars // 2
        tail = max_chars - head
        return f"{prompt_working[:head]}\n\n...[TRUNCATED]...\n\n{prompt_working[-tail:]}"

    def _debug_enabled(self) -> bool:
        if self.config.llm_debug:
            return True
        return _env_truthy("PAPER_TABLE_AGENT_LLM_DEBUG")

    def _record_capability(self, name: str, value: bool) -> None:
        _set_capability(self.config, name, value)

    def _log_debug(self, message: str, payload: dict[str, Any] | None = None) -> None:
        if not self._debug_enabled():
            return
        logger = self.config.logger
        if logger is None:
            return
        if payload:
            logger.info("LLM DEBUG %s: %s", message, payload)
        else:
            logger.info("LLM DEBUG %s", message)

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
        prompt_working = self._truncate_prompt(prompt)
        if prompt_working != prompt:
            self._log_debug(
                "prompt_truncated",
                {
                    "model": self.config.model,
                    "original_chars": len(prompt),
                    "original_tokens_est": _estimate_tokens(prompt),
                    "truncated_chars": len(prompt_working),
                    "truncated_tokens_est": _estimate_tokens(prompt_working),
                },
            )
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
        constraint_mode = "guided" if guided_allowed else "prompt_only"
        prompt_only_retry = False
        for attempt in range(self.config.max_retries + 1):
            payload: dict[str, Any] = {
                "model": self.config.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Return strict JSON only."
                            if constraint_mode == "guided"
                            else "Return ONLY JSON. No markdown. No preamble."
                        ),
                    },
                    {"role": "user", "content": prompt_working},
                ],
                "temperature": 0.0 if prompt_only_retry and constraint_mode == "prompt_only" else 0.1,
            }
            if constraint_mode == "guided":
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "schema": guided_schema_payload,
                    },
                }
            self._record_payload(
                payload,
                stage="completion",
                attempt=attempt,
            )
            request_log = _build_request_log(
                payload,
                url=url,
                timeout=self.config.timeout_s,
                read_timeout=_effective_read_timeout(self.config),
                attempt=attempt,
                snippet_chars=self.config.log_snippet_chars,
                constraint_mode=constraint_mode,
            )
            self.last_request_log = request_log
            self._log_debug("request", request_log)
            try:
                response = self._client.post(url, json=payload, headers=headers)
            except httpx.TimeoutException as exc:
                self._log_debug(
                    "timeout",
                    {
                        "model": self.config.model,
                        "url": url,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )
                last_error = exc
                if attempt >= self.config.max_retries:
                    raise LlmJsonError(
                        "LLM request timed out.",
                        prompt,
                        "",
                        repair_attempted=False,
                        http_status=408,
                        error_substring=str(exc),
                        guided_json_active=guided_allowed,
                    ) from exc
                time.sleep(1 + attempt)
                continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                error_text = response.text
                if response.status_code == 400:
                    self._log_debug(
                        "http_400",
                        {
                            "model": self.config.model,
                            "url": url,
                            "attempt": attempt,
                            "response_body": error_text,
                        },
                    )
                    if _is_context_limit_error(error_text):
                        max_tokens = _infer_context_max_tokens(error_text)
                        if max_tokens is not None and self.config.max_prompt_tokens is not None:
                            max_tokens = min(max_tokens, self.config.max_prompt_tokens)
                        truncated = self._truncate_prompt(prompt_working, max_tokens=max_tokens)
                        if truncated != prompt_working:
                            prompt_working = truncated
                            self._log_debug(
                                "prompt_truncated_context",
                                {
                                    "model": self.config.model,
                                    "max_tokens": max_tokens,
                                    "truncated_chars": len(prompt_working),
                                    "truncated_tokens_est": _estimate_tokens(prompt_working),
                                },
                            )
                            continue
                if response.status_code == 400 and _is_guided_json_error(error_text):
                    self.last_guided_json_error = _extract_error_substring(error_text)
                    self.last_guided_json_status = response.status_code
                    self.last_guided_json_active = constraint_mode == "guided"
                    if constraint_mode == "guided":
                        self._record_capability("guided_json", False)
                    if self.config.logger is not None:
                        self.config.logger.warning(
                            "guided JSON rejected; retrying without constraints: %s",
                            self.last_guided_json_error,
                        )
                    if constraint_mode == "guided":
                        constraint_mode = "prompt_only"
                        prompt_only_retry = True
                        continue
                    if not prompt_only_retry:
                        prompt_only_retry = True
                        continue
                raise LlmJsonError(
                    f"LLM HTTP error {response.status_code}: {response.text}",
                    prompt,
                    error_text,
                    repair_attempted=False,
                    http_status=response.status_code,
                    error_substring=_extract_error_substring(error_text),
                    guided_json_active=constraint_mode == "guided",
                    error_class=_classify_error(error_text),
                ) from exc
            content = response.json()["choices"][0]["message"]["content"]
            self.last_raw_response = content
            if constraint_mode == "guided":
                self._record_capability("guided_json", True)
            else:
                self._record_capability("prompt_json", True)
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
        if mode == "off":
            return False
        capabilities = _get_capabilities(self.config)
        if capabilities.get("guided_json") is False:
            return False
        if capabilities.get("guided_json") is True:
            return True
        if mode == "on":
            return True
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
        text = _strip_think_blocks(content.strip())
        blocks = _extract_json_blocks_from_markdown(text)
        for block in reversed(blocks):
            block = block.strip()
            if not block:
                continue
            try:
                return json.loads(block)
            except json.JSONDecodeError:
                snippet = _extract_first_json(block)
                if snippet:
                    return json.loads(snippet)
        cleaned = _strip_markdown_fences(text)
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
        constraint_mode = "guided" if guided_allowed else "prompt_only"
        prompt_only_retry = False
        repair_prompt = (
            "Repair the following content into strict JSON that matches the schema. "
            "Return JSON only, no markdown.\n\n"
            f"Schema:\n{json.dumps(guided_schema_payload if guided_allowed else schema_payload, indent=2)}\n\n"
            f"Content:\n{content}"
        )
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a JSON repair tool. Return strict JSON only."
                        if constraint_mode == "guided"
                        else "Return ONLY JSON. No markdown. No preamble."
                    ),
                },
                {"role": "user", "content": repair_prompt},
            ],
            "temperature": 0.0 if constraint_mode == "prompt_only" else 0.0,
        }
        if constraint_mode == "guided":
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
        self._record_payload(
            payload,
            stage="repair",
            attempt=0,
        )
        request_log = _build_request_log(
            payload,
            url=url,
            timeout=self.config.timeout_s,
            read_timeout=_effective_read_timeout(self.config),
            attempt=0,
            snippet_chars=self.config.log_snippet_chars,
            constraint_mode=constraint_mode,
        )
        self.last_request_log = request_log
        self._log_debug("request_repair", request_log)
        try:
            response = self._client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            self._log_debug(
                "timeout_repair",
                {
                    "model": self.config.model,
                    "url": url,
                    "attempt": 0,
                    "error": str(exc),
                },
            )
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError:
            if response.status_code == 400:
                self._log_debug(
                    "http_400_repair",
                    {
                        "model": self.config.model,
                        "url": url,
                        "attempt": 0,
                        "response_body": response.text,
                    },
                )
            if response.status_code == 400 and _is_guided_json_error(response.text):
                self.last_guided_json_error = _extract_error_substring(response.text)
                self.last_guided_json_status = response.status_code
                self.last_guided_json_active = constraint_mode == "guided"
                if constraint_mode == "guided":
                    self._record_capability("guided_json", False)
                if not prompt_only_retry:
                    payload.pop("response_format", None)
                    payload["messages"][0]["content"] = "Return ONLY JSON. No markdown. No preamble."
                    constraint_mode = "prompt_only"
                    prompt_only_retry = True
                    response = self._client.post(url, json=payload, headers=headers)
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError:
                        return None
                else:
                    return None
            else:
                return None
        content = response.json()["choices"][0]["message"]["content"]
        if constraint_mode == "guided":
            self._record_capability("guided_json", True)
        else:
            self._record_capability("prompt_json", True)
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

    def probe_json_capabilities(self, schema: type[T]) -> dict[str, bool]:
        prompt = "Return JSON for a test response."
        results: dict[str, bool] = {}
        capabilities = _get_capabilities(self.config)
        if capabilities.get("guided_json") is None:
            results["guided_json"] = self._probe_json(prompt, schema, use_guided=True)
        if capabilities.get("prompt_json") is None:
            results["prompt_json"] = self._probe_json(prompt, schema, use_guided=False)
        return results

    def probe_backend(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": "ping"}],
            "temperature": 0.0,
        }
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        url = f"{self.config.base_url}/chat/completions"
        try:
            response = self._client.post(url, json=payload, headers=headers)
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "error_class": "backend_unreachable"}
        if response.status_code >= 400:
            error_text = response.text
            return {
                "ok": False,
                "http_status": response.status_code,
                "error_substring": _extract_error_substring(error_text),
                "error_class": _classify_error(error_text) or "backend_error",
            }
        return {"ok": True}

    def _probe_json(self, prompt: str, schema: type[T], *, use_guided: bool) -> bool:
        schema_payload = schema.model_json_schema()
        guided_schema_payload = strip_regex_from_json_schema(schema_payload)
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return strict JSON only."
                        if use_guided
                        else "Return ONLY JSON. No markdown. No preamble."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
        }
        if use_guided:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{schema.__name__}Probe",
                    "schema": guided_schema_payload,
                },
            }
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        url = f"{self.config.base_url}/chat/completions"
        try:
            response = self._client.post(url, json=payload, headers=headers)
        except Exception as exc:  # noqa: BLE001
            self._log_debug(
                "probe_failed",
                {"model": self.config.model, "error": str(exc), "use_guided": use_guided},
            )
            if use_guided:
                self._record_capability("guided_json", False)
            else:
                self._record_capability("prompt_json", False)
            return False
        if response.status_code == 400 and _is_guided_json_error(response.text):
            if use_guided:
                self._record_capability("guided_json", False)
            return False
        if response.status_code >= 400:
            if use_guided:
                self._record_capability("guided_json", False)
            else:
                self._record_capability("prompt_json", False)
            return False
        try:
            content = response.json()["choices"][0]["message"]["content"]
            parsed = self._parse_json(content)
            schema.model_validate(parsed)
        except Exception:  # noqa: BLE001
            if use_guided:
                self._record_capability("guided_json", False)
            else:
                self._record_capability("prompt_json", False)
            return False
        if use_guided:
            self._record_capability("guided_json", True)
        else:
            self._record_capability("prompt_json", True)
        return True

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

    def _record_payload(self, payload: dict[str, Any], stage: str, attempt: int) -> None:
        if not self.config.payload_record_path:
            return
        record = {
            "timestamp": time.time(),
            "stage": stage,
            "attempt": attempt,
            "model": self.config.model,
            "url": f"{self.config.base_url}/chat/completions",
            "payload": payload,
            "prompt_meta": _extract_prompt_meta(payload.get("messages", [{}])[-1].get("content", "")) or {},
        }
        with self.config.payload_record_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


def _capability_key(config: LlmConfig) -> tuple[str, str]:
    return (config.base_url or "", config.model or "")


def _get_capabilities(config: LlmConfig) -> dict[str, bool]:
    key = _capability_key(config)
    return _CAPABILITY_CACHE.setdefault(key, {})


def _set_capability(config: LlmConfig, name: str, value: bool) -> None:
    key = _capability_key(config)
    _CAPABILITY_CACHE.setdefault(key, {})[name] = value


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


def _classify_error(error_text: str) -> str | None:
    lowered = (error_text or "").lower()
    if "failed to process regex" in lowered or "regex" in lowered:
        return "model_incompatible_backend_regex"
    if "grammar" in lowered or "json_schema" in lowered or "response_format" in lowered:
        return "model_incompatible_backend_constraints"
    return None


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


def _extract_json_blocks_from_markdown(content: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(r"```(?:json)?\s*([\s\S]*?)```", content, re.IGNORECASE):
        block = match.group(1).strip()
        if block:
            blocks.append(block)
    return blocks


def _strip_think_blocks(content: str) -> str:
    if not content:
        return content
    text = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<analysis>.*?</analysis>", "", text, flags=re.DOTALL | re.IGNORECASE)
    return text.strip()


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


def _build_timeout(config: LlmConfig) -> httpx.Timeout:
    read_timeout = _effective_read_timeout(config)
    return httpx.Timeout(timeout=config.timeout_s, read=read_timeout)


def _effective_read_timeout(config: LlmConfig) -> float:
    return config.read_timeout_s if config.read_timeout_s is not None else config.timeout_s


def _env_truthy(key: str) -> bool:
    value = os.getenv(key)
    if value is None:
        return False
    return value.strip().lower() not in {"0", "false", "no", "off", ""}


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, int((len(text) / 4) + 0.999))


def _truncate_by_tokens(text: str, max_tokens: int) -> str:
    tokens = _estimate_tokens(text)
    if tokens <= max_tokens:
        return text
    ratio = max_tokens / max(tokens, 1)
    target_chars = max(1, int(len(text) * ratio))
    head = target_chars // 2
    tail = target_chars - head
    return f"{text[:head]}\n\n...[TRUNCATED]...\n\n{text[-tail:]}"


def _is_context_limit_error(error_text: str) -> bool:
    lowered = (error_text or "").lower()
    return "context length" in lowered or "n_ctx" in lowered or "n_keep" in lowered


def _infer_context_max_tokens(error_text: str) -> int | None:
    match = re.search(r"n_ctx\\s*\\(?\\s*(\\d+)", error_text or "")
    if not match:
        return None
    try:
        n_ctx = int(match.group(1))
    except ValueError:
        return None
    return max(1, n_ctx - 256)


def _build_request_log(
    payload: dict[str, Any],
    *,
    url: str,
    timeout: float,
    read_timeout: float,
    attempt: int,
    snippet_chars: int,
    constraint_mode: str | None = None,
) -> dict[str, Any]:
    messages = payload.get("messages", [])
    message_chars = 0
    message_tokens = 0
    prompt_snippet = ""
    prompt_chars = 0
    prompt_tokens = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "")
        message_chars += len(content)
        message_tokens += _estimate_tokens(content)
        if message.get("role") == "user" and not prompt_snippet:
            prompt_snippet = content[:snippet_chars]
            prompt_chars = len(content)
            prompt_tokens = _estimate_tokens(content)
    response_format = payload.get("response_format")
    response_format_summary: dict[str, Any] | None = None
    if isinstance(response_format, dict):
        response_format_summary = {"type": response_format.get("type")}
        schema_payload = response_format.get("json_schema")
        if isinstance(schema_payload, dict):
            response_format_summary["schema_name"] = schema_payload.get("name")
    flags = {}
    for key in (
        "stop",
        "max_tokens",
        "temperature",
        "seed",
        "n_keep",
        "truncate",
        "stream",
        "grammar",
        "guided_regex",
        "regex",
        "json_schema",
    ):
        if key in payload:
            flags[key] = _summarize_flag_value(payload.get(key))
    if response_format_summary:
        flags["response_format"] = response_format_summary
    return {
        "model": payload.get("model"),
        "url": url,
        "attempt": attempt,
        "timeout_s": timeout,
        "read_timeout_s": read_timeout,
        "constraint_mode": constraint_mode,
        "prompt_chars": prompt_chars,
        "prompt_tokens_est": prompt_tokens,
        "message_chars": message_chars,
        "message_tokens_est": message_tokens,
        "prompt_snippet": prompt_snippet,
        "payload_flags": flags,
    }


def _summarize_flag_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {"keys": list(value.keys())[:6]}
    if isinstance(value, list):
        return f"list(len={len(value)})"
    return value


def estimate_tokens(text: str) -> int:
    return _estimate_tokens(text)
