from __future__ import annotations

from itertools import product
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


def _numeric_knob_combinations(
    incumbent_knobs: dict[str, float | int],
    numeric_knobs: dict[str, list[float | int]],
) -> list[dict[str, float | int]]:
    if not numeric_knobs:
        return [dict(incumbent_knobs)]

    knob_names = list(numeric_knobs.keys())
    value_lists: list[list[float | int]] = []
    for knob_name in knob_names:
        incumbent_value = incumbent_knobs.get(knob_name)
        values = list(numeric_knobs[knob_name])
        if incumbent_value is not None:
            values = [incumbent_value, *values]
        deduped: list[float | int] = []
        for value in values:
            if value not in deduped:
                deduped.append(value)
        value_lists.append(deduped)

    combinations: list[dict[str, float | int]] = []
    for combo in product(*value_lists):
        knobs = dict(incumbent_knobs)
        for knob_name, knob_value in zip(knob_names, combo):
            knobs[knob_name] = knob_value
        combinations.append(knobs)
    return combinations


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

    knob_combinations = _numeric_knob_combinations(incumbent.optimizer_knobs, search_space.numeric_knobs)

    counter = next_candidate_number_start
    for prompt_id in prompt_options:
        for text_model_id in text_options:
            for vision_model_id_raw in vision_options:
                for knobs in knob_combinations:
                    candidate = replace(
                        incumbent,
                        candidate_id=f"cand_{counter:04d}",
                        prompt_bundle_id=prompt_id,
                        text_model_id=text_model_id,
                        vision_model_id=vision_model_id_raw or None,
                        optimizer_knobs=dict(knobs),
                        parent_candidate_id=incumbent.candidate_id,
                        round_index=round_index,
                    )

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
