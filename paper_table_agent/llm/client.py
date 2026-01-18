from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LlmJsonError(RuntimeError):
    def __init__(self, message: str, prompt: str, response: str) -> None:
        super().__init__(message)
        self.prompt = prompt
        self.response = response


@dataclass
class LlmConfig:
    base_url: str
    api_key: str | None
    model: str
    timeout_s: float = 60.0
    max_retries: int = 2
    mock_mode: bool = False
    mock_payloads: dict[str, Any] | None = None


class LlmClient:
    def __init__(self, config: LlmConfig) -> None:
        self.config = config
        self._client = httpx.Client(timeout=self.config.timeout_s)

    def complete_json(self, prompt: str, schema: type[T]) -> T:
        if self.config.mock_mode:
            return self._mock_response(prompt, schema)
        schema_payload = schema.model_json_schema()
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "schema": schema_payload,
                },
            },
        }
        headers = {}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        url = f"{self.config.base_url}/chat/completions"
        last_error: Exception | None = None
        content = ""
        for attempt in range(self.config.max_retries + 1):
            response = self._client.post(url, json=payload, headers=headers)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"LLM HTTP error {response.status_code}: {response.text}"
                ) from exc
            content = response.json()["choices"][0]["message"]["content"]
            try:
                parsed = self._parse_json(content)
                return schema.model_validate(parsed)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                repair = self._repair_json(content, schema)
                if repair is not None:
                    return repair
                if attempt >= self.config.max_retries:
                    break
                time.sleep(1 + attempt)
        raise LlmJsonError(f"Failed to parse JSON after retries: {last_error}", prompt, content)

    def _parse_json(self, content: str) -> Any:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback: extract the first JSON object/array from mixed text
            start_obj = content.find("{")
            start_arr = content.find("[")
            if start_obj == -1 and start_arr == -1:
                raise
            if start_arr != -1 and (start_obj == -1 or start_arr < start_obj):
                start = start_arr
                end = content.rfind("]")
            else:
                start = start_obj
                end = content.rfind("}")
            if end == -1:
                raise
            snippet = content[start : end + 1]
            return json.loads(snippet)

    def _mock_response(self, prompt: str, schema: type[T]) -> T:
        payload = self.config.mock_payloads or {}
        for key, value in payload.items():
            if key in prompt:
                return schema.model_validate(value)
        raise ValueError("Mock mode enabled but no matching payload provided")

    def _repair_json(self, content: str, schema: type[T]) -> T | None:
        schema_payload = schema.model_json_schema()
        repair_prompt = (
            "Repair the following content into strict JSON that matches the schema. "
            "Return JSON only, no markdown.\n\n"
            f"Schema:\n{json.dumps(schema_payload, indent=2)}\n\n"
            f"Content:\n{content}"
        )
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are a JSON repair tool. Return strict JSON only."},
                {"role": "user", "content": repair_prompt},
            ],
            "temperature": 0.0,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": f"{schema.__name__}Repair",
                    "schema": schema_payload,
                },
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
            return None
        content = response.json()["choices"][0]["message"]["content"]
        try:
            parsed = self._parse_json(content)
            return schema.model_validate(parsed)
        except Exception:  # noqa: BLE001
            return None
