from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib import request

from .bundle import build_candidate_from_dict
from .contracts import Candidate, ProposedCandidateDelta, ProposerRequest, ProposerResponse
from .search_space import SearchSpace
from .utils import write_json


def build_proposer_request(
    incumbent: Candidate,
    *,
    search_space: SearchSpace,
    round_index: int,
    max_candidates: int,
) -> ProposerRequest:
    return ProposerRequest(
        round_index=round_index,
        max_candidates=max_candidates,
        incumbent={
            "prompt_bundle_id": incumbent.prompt_bundle_id,
            "text_model_id": incumbent.text_model_id,
            "vision_model_id": incumbent.vision_model_id,
            "optimizer_knobs": dict(incumbent.optimizer_knobs),
        },
        allowed_prompt_bundle_ids=sorted({incumbent.prompt_bundle_id, *search_space.prompt_bundle_ids}),
        allowed_text_model_ids=sorted({incumbent.text_model_id, *search_space.text_model_ids}),
        allowed_vision_model_ids=sorted({(incumbent.vision_model_id or ""), *search_space.vision_model_ids}),
        allowed_numeric_knobs={key: list(values) for key, values in sorted(search_space.numeric_knobs.items())},
    )


def collect_proposer_candidates(
    config: dict[str, Any],
    *,
    incumbent: Candidate,
    search_space: SearchSpace,
    round_index: int,
    batch_size: int,
    next_candidate_number_start: int,
    experiment_dir: Path,
) -> list[Candidate]:
    proposer_config = config.get("proposer", {})
    if not proposer_config.get("enabled", False):
        return []

    max_candidates = min(int(proposer_config.get("max_candidates", batch_size) or batch_size), batch_size)
    proposer_request = build_proposer_request(
        incumbent,
        search_space=search_space,
        round_index=round_index,
        max_candidates=max_candidates,
    )
    response, error_message = _call_lm_studio_proposer(proposer_config, proposer_request)

    accepted_candidates: list[Candidate] = []
    accepted_payloads: list[dict[str, Any]] = []
    rejected_payloads: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str, str | None, str]] = set()

    for raw_candidate in response.raw_response.get("candidates", []):
        payload, rejection_reason = _coerce_candidate_payload(raw_candidate, incumbent, search_space)
        if payload is None:
            rejected_payloads.append({"candidate": raw_candidate, "reason": rejection_reason})
            continue
        signature = (
            payload["prompt_bundle_id"],
            payload["text_model_id"],
            payload.get("vision_model_id"),
            str(sorted(payload["optimizer_knobs"].items())),
        )
        if signature in seen_signatures:
            rejected_payloads.append({"candidate": raw_candidate, "reason": "duplicate_candidate"})
            continue
        seen_signatures.add(signature)
        candidate = build_candidate_from_dict(
            f"cand_{next_candidate_number_start + len(accepted_candidates):04d}",
            payload,
            parent_candidate_id=incumbent.candidate_id,
            round_index=round_index,
        )
        accepted_candidates.append(candidate)
        accepted_payloads.append(payload)
        if len(accepted_candidates) >= max_candidates:
            break

    _write_proposer_audit(
        experiment_dir,
        round_index=round_index,
        request_payload=proposer_request.to_dict(),
        response_payload=response.to_dict(),
        accepted_payloads=accepted_payloads,
        rejected_payloads=rejected_payloads,
        error_message=error_message,
    )
    return accepted_candidates


def _write_proposer_audit(
    experiment_dir: Path,
    *,
    round_index: int,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    accepted_payloads: list[dict[str, Any]],
    rejected_payloads: list[dict[str, Any]],
    error_message: str | None,
) -> None:
    proposer_dir = experiment_dir / "proposer"
    proposer_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        proposer_dir / f"round_{round_index:04d}.json",
        {
            "request": request_payload,
            "response": response_payload,
            "accepted_candidates": accepted_payloads,
            "rejected_candidates": rejected_payloads,
            "error": error_message,
        },
    )


def _call_lm_studio_proposer(
    proposer_config: dict[str, Any],
    proposer_request: ProposerRequest,
) -> tuple[ProposerResponse, str | None]:
    api_base = str(proposer_config.get("api_base") or "http://127.0.0.1:1234/v1").rstrip("/")
    model_id = str(proposer_config.get("model_id") or "")
    payload = {
        "model": model_id,
        "temperature": float(proposer_config.get("temperature", 0.0) or 0.0),
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Return JSON with a single key 'candidates'. Each candidate must only use allowed prompt bundles, "
                    "allowed text models, allowed vision models, and allowed numeric knob values."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(proposer_request.to_dict(), sort_keys=True),
            },
        ],
    }
    try:
        req = request.Request(
            f"{api_base}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as response_handle:
            response_payload = json.loads(response_handle.read().decode("utf-8"))
        content = response_payload["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        candidates = []
        for item in parsed.get("candidates", []):
            if not isinstance(item, dict):
                continue
            candidates.append(
                ProposedCandidateDelta(
                    prompt_bundle_id=item.get("prompt_bundle_id"),
                    text_model_id=item.get("text_model_id"),
                    vision_model_id=item.get("vision_model_id"),
                    optimizer_knobs=dict(item.get("optimizer_knobs", {})),
                )
            )
        return (
            ProposerResponse(
                candidates=candidates,
                response_mode="json_object",
                raw_response={"candidates": [candidate.to_dict() for candidate in candidates], "provider_response": response_payload},
            ),
            None,
        )
    except Exception as exc:
        return ProposerResponse(candidates=[], response_mode="json_object", raw_response={"candidates": []}), str(exc)


def _coerce_candidate_payload(
    raw_candidate: Any,
    incumbent: Candidate,
    search_space: SearchSpace,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(raw_candidate, dict):
        return None, "candidate_must_be_object"

    payload = {
        "prompt_bundle_id": raw_candidate.get("prompt_bundle_id") or incumbent.prompt_bundle_id,
        "text_model_id": raw_candidate.get("text_model_id") or incumbent.text_model_id,
        "vision_model_id": raw_candidate.get("vision_model_id", incumbent.vision_model_id),
        "optimizer_knobs": dict(incumbent.optimizer_knobs),
    }
    if raw_candidate.get("optimizer_knobs") is not None:
        if not isinstance(raw_candidate.get("optimizer_knobs"), dict):
            return None, "optimizer_knobs_must_be_object"
        payload["optimizer_knobs"].update(raw_candidate["optimizer_knobs"])

    allowed_prompt_ids = {incumbent.prompt_bundle_id, *search_space.prompt_bundle_ids}
    if payload["prompt_bundle_id"] not in allowed_prompt_ids:
        return None, "invalid_prompt_bundle_id"

    allowed_text_model_ids = {incumbent.text_model_id, *search_space.text_model_ids}
    if payload["text_model_id"] not in allowed_text_model_ids:
        return None, "invalid_text_model_id"

    allowed_vision_model_ids = {(incumbent.vision_model_id or ""), *search_space.vision_model_ids}
    vision_model_id = payload["vision_model_id"] or ""
    if vision_model_id not in allowed_vision_model_ids:
        return None, "invalid_vision_model_id"
    payload["vision_model_id"] = payload["vision_model_id"] or None

    for knob_name, knob_value in payload["optimizer_knobs"].items():
        if knob_name not in incumbent.optimizer_knobs and knob_name not in search_space.numeric_knobs:
            return None, f"unknown_optimizer_knob:{knob_name}"
        allowed_values = search_space.numeric_knobs.get(knob_name)
        if allowed_values is not None and knob_value not in allowed_values:
            return None, f"invalid_optimizer_knob_value:{knob_name}"

    return payload, None