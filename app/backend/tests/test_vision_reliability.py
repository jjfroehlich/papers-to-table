from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from backend.app.extraction import (
    VISION_EXTRACTION_SCHEMA,
    build_figure_planner_prompt,
    decide_vision_trigger_reasons,
    run_figure_review,
)
from backend.app.provider import (
    ProviderAdapter,
    _parse_and_validate_response_with_details,
    _should_retry_structured_output_error,
)
from backend.app.retrieval import RetrievalChunk, RetrievalResult
from backend.app.schemas import ProposalState, ProviderLocality, SchemaFieldType, SupportLabel


def _scratch_dir() -> Path:
    path = Path.cwd() / "tmp_vision_reliability" / uuid4().hex
    path.mkdir(parents=True)
    return path


class FakeProvider(ProviderAdapter):
    def __init__(self, planner_result: dict | Exception, vision_result: dict):
        self.planner_result = planner_result
        self.vision_result = vision_result
        self.planner_calls = 0
        self.vision_calls = 0
        self.vision_images: list[str] = []

    @property
    def token(self) -> str:
        return "fake"

    @property
    def locality(self) -> ProviderLocality:
        return ProviderLocality.local

    async def probe_capabilities(self, text_model_id: str, vision_model_id: str | None = None):
        raise NotImplementedError

    async def text_complete_raw(self, system: str, user: str, max_tokens: int = 512) -> str:
        raise NotImplementedError

    async def chat_complete_structured(
        self,
        messages: list[dict],
        response_schema: dict,
        model_id: str,
        max_tokens: int = 2048,
        temperature: float | None = None,
    ) -> dict:
        self.planner_calls += 1
        if isinstance(self.planner_result, Exception):
            raise self.planner_result
        return self.planner_result

    async def vision_complete_structured(
        self,
        messages: list[dict],
        response_schema: dict,
        model_id: str,
        image_b64: str,
        max_tokens: int = 2048,
        temperature: float | None = None,
        retry_malformed_structured_response: bool = True,
    ) -> dict:
        self.vision_calls += 1
        self.vision_images.append(image_b64)
        return self.vision_result


def _retrieval(chunk_type: str = "paragraph") -> RetrievalResult:
    return RetrievalResult(
        run_id="run",
        pdf_id="paper",
        column_name="Cell line",
        query="cell line",
        top_k=1,
        chunks=[
            RetrievalChunk(
                chunk_id="c1",
                source_block_id="b1",
                chunk_type=chunk_type,
                page_number=1,
                reading_order=1,
                display_text="HEK293T cells were used.",
                retrieval_text="HEK293T cells were used.",
            )
        ],
        retrieved_at="2026-05-18T00:00:00+00:00",
    )


def test_prompt_only_vision_schema_repairs_optional_and_na_values():
    parsed, details = _parse_and_validate_response_with_details(
        '{"proposed_value":"not numeric","state":"found","rationale":"caption only",'
        '"numeric_value_form":"N/A","figure_description":"diagram"}',
        VISION_EXTRACTION_SCHEMA,
        allow_degraded_normalization=True,
    )

    assert parsed["numeric_value_form"] is None
    assert "caption_relevant" not in parsed
    assert details["failure_stage"] == "ok"
    assert details["degraded_normalization_used"] is True


@pytest.mark.parametrize("raw_state", ["yes", "present", "visible", "clear", "success", "succeeded"])
def test_prompt_only_vision_schema_repairs_found_state_synonyms(raw_state: str):
    parsed, details = _parse_and_validate_response_with_details(
        '{"proposed_value":"supported value","state":"%s","rationale":"visible",'
        '"numeric_value_form":null,"figure_description":"diagram"}' % raw_state,
        VISION_EXTRACTION_SCHEMA,
        allow_degraded_normalization=True,
    )

    assert parsed["state"] == "found"
    assert "state_synonym_normalized" in details["degraded_normalization_repairs"]


def test_prompt_only_vision_schema_repairs_possible_to_inferred():
    parsed, details = _parse_and_validate_response_with_details(
        '{"proposed_value":"possible value","state":"possible","rationale":"may be visible",'
        '"numeric_value_form":null,"figure_description":"diagram"}',
        VISION_EXTRACTION_SCHEMA,
        allow_degraded_normalization=True,
    )

    assert parsed["state"] == "inferred"
    assert "state_synonym_normalized" in details["degraded_normalization_repairs"]


@pytest.mark.parametrize(
    ("raw_state", "proposed_value", "expected"),
    [("propose", "architecture", "found"), ("propose_value", "architecture", "found"), ("propose", None, "unclear")],
)
def test_prompt_only_vision_schema_repairs_malformed_propose_states(raw_state: str, proposed_value: str | None, expected: str):
    proposed_json = "null" if proposed_value is None else f'"{proposed_value}"'
    parsed, details = _parse_and_validate_response_with_details(
        '{"proposed_value":%s,"state":"%s","rationale":"draft",'
        '"numeric_value_form":null,"figure_description":"diagram"}' % (proposed_json, raw_state),
        VISION_EXTRACTION_SCHEMA,
        allow_degraded_normalization=True,
    )

    assert parsed["state"] == expected
    assert "state_synonym_normalized" in details["degraded_normalization_repairs"]


def test_state_repair_does_not_rewrite_unrelated_schema_enum():
    unrelated_schema = {
        "type": "object",
        "properties": {"state": {"type": "string", "enum": ["open", "closed"]}},
        "required": ["state"],
    }

    with pytest.raises(Exception):
        _parse_and_validate_response_with_details(
            '{"state":"clear"}',
            unrelated_schema,
            allow_degraded_normalization=True,
        )


def test_schema_validation_omission_does_not_request_retry():
    with pytest.raises(Exception) as exc_info:
        _parse_and_validate_response_with_details(
            '{"proposed_value":"x"}',
            VISION_EXTRACTION_SCHEMA,
            allow_degraded_normalization=True,
        )

    assert _should_retry_structured_output_error(exc_info.value) is False


def test_vision_gate_skips_direct_figure_context_alone_for_strong_non_visual_text():
    reasons = decide_vision_trigger_reasons(
        state=ProposalState.found,
        support=SupportLabel.direct_evidence,
        quotes=[{"text": "HEK293T cells were used."}],
        retrieval=_retrieval("caption"),
        needs_more_evidence=False,
        proposed_value="HEK293T",
        column_name="Cell line",
        column_description="Cell line used in the paper",
    )

    assert reasons == []


def test_vision_gate_keeps_direct_figure_context_when_text_is_weak():
    reasons = decide_vision_trigger_reasons(
        state=ProposalState.found,
        support=SupportLabel.weak_evidence,
        quotes=[],
        retrieval=_retrieval("caption"),
        needs_more_evidence=False,
        proposed_value="HEK293T",
        column_name="Cell line",
        column_description="Cell line used in the paper",
    )

    assert "text_weak" in reasons
    assert "direct_figure_context" in reasons


def test_vision_gate_keeps_visual_request_even_with_strong_text():
    reasons = decide_vision_trigger_reasons(
        state=ProposalState.found,
        support=SupportLabel.direct_evidence,
        quotes=[{"text": "Figure 1 contains UMAP plots."}],
        retrieval=_retrieval("figure"),
        needs_more_evidence=False,
        proposed_value="4",
        column_name="Number of UMAP plot panels",
        column_description="How many UMAP plot panels are visible in Figure 1?",
    )

    assert "visual_request" in reasons
    assert "direct_figure_context" in reasons


def test_vision_gate_keeps_visual_weak_cells_active():
    reasons = decide_vision_trigger_reasons(
        state=ProposalState.unclear,
        support=SupportLabel.weak_evidence,
        quotes=[],
        retrieval=_retrieval("figure"),
        needs_more_evidence=True,
        proposed_value=None,
        column_name="Number of UMAP plot panels",
        column_description="How many UMAP plot panels are visible in the main figure?",
    )

    assert "text_unclear" in reasons
    assert "direct_figure_context" in reasons
    assert "visual_request" in reasons


def test_figure_planner_prompt_discourages_non_visual_confirmation():
    messages = build_figure_planner_prompt(
        column_name="Cell line",
        column_description="Cell line used in the paper",
        row_context={},
        proposed_value="HEK293T",
        rationale="The retrieved snippet directly states HEK293T cells were used.",
        retrieval=_retrieval("caption"),
        figures=[],
    )
    prompt_text = "\n".join(str(message.get("content")) for message in messages)

    assert "Do not request vision for non-visual fields" in prompt_text
    assert "text or caption snippets already answer" in prompt_text


@pytest.mark.asyncio
async def test_planner_selected_full_page_is_used():
    scratch = _scratch_dir()
    try:
        page = scratch / "page_0001.png"
        page.write_bytes(b"fake-image")
        provider = FakeProvider(
            planner_result={
                "needs_vision": True,
                "target_figures": [{"figure_ref": "fig1", "preferred_image": "full_page", "reason": "count panels"}],
                "rejected_figures": [],
                "vision_question": "Count visible panels.",
                "planner_confidence": "high",
                "skip_reason": None,
            },
            vision_result={
                "proposed_value": "4",
                "state": "found",
                "rationale": "Four panels are visible.",
                "numeric_value_form": "exact",
                "figure_description": "Four UMAP panels.",
                "caption_relevant": False,
            },
        )
        attempts: list[dict] = []
        planner_diag: dict = {}

        hits = await run_figure_review(
            run_id="run",
            proposal_id="p1",
            pdf_id="paper",
            column_name="Number of UMAP plot panels",
            column_description="How many UMAP panels are visible?",
            doc_dict={
                "figures": [
                    {
                        "figure_id": "fig1",
                        "page_number": 1,
                        "caption_text": "Figure 1. UMAP panels.",
                        "full_page_path": "page_0001.png",
                    }
                ]
            },
            run_dir=scratch,
            provider=provider,
            text_model_id="text",
            vision_model_id="vision",
            field_type=SchemaFieldType.number,
            max_figures=2,
            max_calls=2,
            planner_enabled=True,
            planner_diagnostics=planner_diag,
            attempt_diagnostics=attempts,
        )

        assert provider.planner_calls == 1
        assert provider.vision_calls == 1
        assert hits[0].proposed_value == "4"
        assert attempts[0]["image_source"] == "full_page_preferred"
        assert attempts[0]["fallback_reason"] == "planner_preferred_full_page"
        assert planner_diag["target_figures"][0]["figure_ref"] == "fig1"
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


@pytest.mark.asyncio
async def test_invalid_planner_refs_fall_back_to_heuristic_shortlist():
    scratch = _scratch_dir()
    try:
        page = scratch / "page_0001.png"
        page.write_bytes(b"fake-image")
        provider = FakeProvider(
            planner_result={
                "needs_vision": True,
                "target_figures": [{"figure_ref": "missing", "preferred_image": "crop", "reason": "bad ref"}],
                "rejected_figures": [],
                "vision_question": "Inspect the figure.",
                "planner_confidence": "low",
                "skip_reason": None,
            },
            vision_result={
                "proposed_value": "schematic",
                "state": "found",
                "rationale": "Figure shows the architecture.",
                "numeric_value_form": None,
                "figure_description": "Architecture schematic.",
                "caption_relevant": False,
            },
        )
        planner_diag: dict = {}

        hits = await run_figure_review(
            run_id="run",
            proposal_id="p1",
            pdf_id="paper",
            column_name="Architecture source figure",
            column_description="Which figure shows the architecture?",
            doc_dict={
                "figures": [
                    {
                        "figure_id": "fig1",
                        "page_number": 1,
                        "caption_text": "Figure 1. Architecture schematic.",
                        "full_page_path": "page_0001.png",
                    }
                ]
            },
            run_dir=scratch,
            provider=provider,
            text_model_id="text",
            vision_model_id="vision",
            retrieval=_retrieval("caption"),
            max_figures=2,
            max_calls=1,
            planner_enabled=True,
            planner_diagnostics=planner_diag,
        )

        assert provider.planner_calls == 1
        assert provider.vision_calls == 1
        assert hits[0].evidence.figure_ref == "fig1"
        assert planner_diag["fallback_to_heuristic_shortlist"] is True
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
