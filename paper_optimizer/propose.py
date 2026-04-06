from __future__ import annotations

from dataclasses import replace

from .contracts import Candidate
from .search_space import SearchSpace


def _unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def propose_candidates(
    incumbent: Candidate,
    *,
    search_space: SearchSpace,
    round_index: int,
    batch_size: int,
    next_candidate_number_start: int,
) -> list[Candidate]:
    proposals: list[Candidate] = []

    prompt_options = _unique_preserve([incumbent.prompt_bundle_id] + search_space.prompt_bundle_ids)
    text_options = _unique_preserve([incumbent.text_model_id] + search_space.text_model_ids)
    vision_options = _unique_preserve([(incumbent.vision_model_id or "")] + search_space.vision_model_ids)

    numeric_axes = list(search_space.numeric_knobs.items())

    counter = next_candidate_number_start
    for prompt_id in prompt_options:
        for text_model_id in text_options:
            for vision_model_id_raw in vision_options:
                knobs = dict(incumbent.optimizer_knobs)
                if numeric_axes:
                    axis_name, axis_values = numeric_axes[(counter - next_candidate_number_start) % len(numeric_axes)]
                    knobs[axis_name] = axis_values[(counter - next_candidate_number_start) % len(axis_values)]

                candidate = replace(
                    incumbent,
                    candidate_id=f"cand_{counter:04d}",
                    prompt_bundle_id=prompt_id,
                    text_model_id=text_model_id,
                    vision_model_id=vision_model_id_raw or None,
                    optimizer_knobs=knobs,
                    parent_candidate_id=incumbent.candidate_id,
                    round_index=round_index,
                )

                # Skip exact incumbent clone.
                if (
                    candidate.prompt_bundle_id == incumbent.prompt_bundle_id
                    and candidate.text_model_id == incumbent.text_model_id
                    and candidate.vision_model_id == incumbent.vision_model_id
                    and candidate.optimizer_knobs == incumbent.optimizer_knobs
                ):
                    continue

                proposals.append(candidate)
                counter += 1
                if len(proposals) >= batch_size:
                    return proposals

    return proposals
