"""
Tests for T067 — extraction: structured-output parsing, provider failure handling,
proposal/evidence serialization, blocked/unclear/skipped outcomes, evidence recovery,
quote+page fallback, figure fallback trigger, and Verify mode extraction.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from backend.app.extraction import (
    TEXT_EXTRACTION_SCHEMA,
    VISION_EXTRACTION_SCHEMA,
    ExtractionRequest,
    FigureInputPackage,
    _parse_proposal_state,
    attempt_evidence_recovery,
    build_extraction_request,
    build_extraction_system_prompt,
    build_extraction_user_prompt,
    build_figure_fallback_packages,
    extract_cell,
    map_support_label,
    persist_proposal_and_evidence,
    run_extraction_for_run,
    should_trigger_figure_fallback,
    validate_and_anchor_evidence,
)
from backend.app.parsing import (
    BoundingBox,
    ParsedBlock,
    ParsedDocument,
    ParsedFigure,
    ParsedPage,
    ParsedTable,
    ExtractedMetadata,
)
from backend.app.provider import (
    LMStudioProvider,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderError,
    StructuredOutputError,
)
from backend.app.schemas import (
    EvidenceSourceType,
    ProposalState,
    SupportLabel,
)
from backend.app.artifacts import RunArtifacts
from backend.app.retrieval import build_chunks, build_retrieval_result
from backend.app.style_profiles import StyleProfile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_artifacts(tmp_path: Path) -> RunArtifacts:
    from backend.app.artifacts import BUNDLE_DIRS
    run_root = tmp_path / "run_test"
    run_root.mkdir()
    for d in BUNDLE_DIRS:
        (run_root / d).mkdir(parents=True, exist_ok=True)
    return RunArtifacts(run_root)


def _make_doc(
    pdf_id: str = "pdf_001",
    blocks: list[ParsedBlock] | None = None,
    figures: list[ParsedFigure] | None = None,
) -> ParsedDocument:
    blocks = blocks or [
        ParsedBlock(
            block_id="b1",
            block_type="paragraph",
            text="The drug was administered at 10 mg/kg body weight.",
            normalized_text="the drug was administered at 10 mg/kg body weight.",
            page_no=1,
            reading_order=0,
        )
    ]
    full_text = " ".join(b.text for b in blocks)
    return ParsedDocument(
        pdf_id=pdf_id,
        source_path=f"/fake/{pdf_id}.pdf",
        metadata=ExtractedMetadata(title="Test Study"),
        pages=[ParsedPage(page_no=1, width=595.0, height=842.0)],
        blocks=blocks,
        figures=figures or [],
        tables=[],
        full_text=full_text,
        normalized_full_text=full_text.lower(),
    )


def _make_provider_with_response(response: dict[str, Any]) -> ProviderAdapter:
    """Return a mock ProviderAdapter that returns the given JSON response."""
    mock = MagicMock(spec=ProviderAdapter)
    mock.capabilities = ProviderCapabilities(
        provider_name="mock",
        model_name="mock-model",
        supports_structured_output=True,
        supports_vision=False,
    )
    mock.complete_json.return_value = response
    mock.complete_text.return_value = ""
    return mock


def _make_vision_provider(response: dict[str, Any]) -> ProviderAdapter:
    mock = MagicMock(spec=ProviderAdapter)
    mock.capabilities = ProviderCapabilities(
        provider_name="mock",
        model_name="vision-model",
        supports_structured_output=True,
        supports_vision=True,
    )
    mock.complete_json.return_value = response
    mock.complete_vision_json.return_value = response
    mock.complete_text.return_value = ""
    return mock


# ---------------------------------------------------------------------------
# T054 — Text schema shape
# ---------------------------------------------------------------------------

def test_text_schema_required_fields() -> None:
    required = set(TEXT_EXTRACTION_SCHEMA["required"])
    assert "proposal_state" in required
    assert "proposed_value" in required
    assert "rationale" in required


def test_text_schema_proposal_state_enum() -> None:
    states = TEXT_EXTRACTION_SCHEMA["properties"]["proposal_state"]["enum"]
    assert "found" in states
    assert "inferred" in states
    assert "unclear" in states
    assert "skipped" in states


# ---------------------------------------------------------------------------
# T055 — Vision schema shape
# ---------------------------------------------------------------------------

def test_vision_schema_has_figure_fields() -> None:
    assert "figure_ref" in VISION_EXTRACTION_SCHEMA["properties"]
    assert "caption_text" in VISION_EXTRACTION_SCHEMA["properties"]


# ---------------------------------------------------------------------------
# T053 — Extraction request builder
# ---------------------------------------------------------------------------

def test_build_extraction_request_has_required_fields() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    result = build_retrieval_result(doc, chunks, "Dose", "Drug dose", top_k=6)
    request = build_extraction_request(
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        row_data={"Title": "Study A", "Authors": "Smith J", "Dose": "10 mg/kg"},
        column_name="Dose",
        column_description="Drug dose administered",
        style_profile=None,
        retrieval_result=result,
        all_chunks=chunks,
        verify_mode=False,
    )
    assert request.column_name == "Dose"
    assert request.pdf_id == "pdf_001"
    assert request.run_id == "run_001"
    assert len(request.retrieved_passages) > 0


def test_build_extraction_request_verify_mode_includes_current_value() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    request = build_extraction_request(
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        row_data={"Title": "Study A", "Dose": "existing_value"},
        column_name="Dose",
        column_description="Drug dose",
        style_profile=None,
        retrieval_result=None,
        all_chunks=chunks,
        verify_mode=True,
    )
    assert request.verify_mode is True
    assert request.current_value == "existing_value"


def test_build_extraction_request_no_verify_current_value_none() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    request = build_extraction_request(
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        row_data={"Title": "Study A", "Dose": "10 mg/kg"},
        column_name="Dose",
        column_description="Drug dose",
        style_profile=None,
        retrieval_result=None,
        all_chunks=chunks,
        verify_mode=False,
    )
    assert request.current_value is None


def test_build_extraction_request_style_profile_used() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    profile = StyleProfile(column_name="Dose", field_type_guess="numeric", unit_style="mg/kg")
    request = build_extraction_request(
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        row_data={"Title": "Study A"},
        column_name="Dose",
        column_description="Drug dose",
        style_profile=profile,
        retrieval_result=None,
        all_chunks=chunks,
        verify_mode=False,
    )
    assert request.style_profile.get("unit_style") == "mg/kg"


def test_user_prompt_contains_column_name() -> None:
    request = ExtractionRequest(
        run_id="r1",
        pdf_id="p1",
        row_id="row1",
        column_name="Sample Size",
        column_description="Total number of participants",
        retrieved_passages=["100 patients enrolled."],
    )
    prompt = build_extraction_user_prompt(request)
    assert "Sample Size" in prompt
    assert "participants" in prompt


# ---------------------------------------------------------------------------
# T058 — Proposal state parsing
# ---------------------------------------------------------------------------

def test_parse_proposal_state_found() -> None:
    assert _parse_proposal_state("found") == ProposalState.FOUND


def test_parse_proposal_state_inferred() -> None:
    assert _parse_proposal_state("inferred") == ProposalState.INFERRED


def test_parse_proposal_state_unclear() -> None:
    assert _parse_proposal_state("unclear") == ProposalState.UNCLEAR


def test_parse_proposal_state_skipped() -> None:
    assert _parse_proposal_state("skipped") == ProposalState.SKIPPED


def test_parse_proposal_state_unknown_defaults_to_error() -> None:
    assert _parse_proposal_state("nonsense") == ProposalState.ERROR


# ---------------------------------------------------------------------------
# T056 + T058 — extract_cell: proposal serialization and state handling
# ---------------------------------------------------------------------------

def test_extract_cell_found_state(tmp_path: Path) -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = _make_provider_with_response({
        "proposal_state": "found",
        "proposed_value": "10 mg/kg",
        "rationale": "Found in methods section.",
        "calculation": "",
        "needs_more_evidence": False,
        "evidence_quote": "The drug was administered at 10 mg/kg body weight.",
        "evidence_page": 1,
    })
    request = build_extraction_request(
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        row_data={"Title": "Study A"},
        column_name="Dose",
        column_description="Drug dose administered",
        style_profile=None,
        retrieval_result=None,
        all_chunks=chunks,
        verify_mode=False,
    )
    proposal, evidence_list = extract_cell(
        request=request,
        provider=provider,
        doc=doc,
        run_id="run_001",
        all_chunks=chunks,
    )
    assert proposal.proposal_state == ProposalState.FOUND
    assert proposal.proposed_value == "10 mg/kg"
    assert len(evidence_list) > 0


def test_extract_cell_unclear_state(tmp_path: Path) -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = _make_provider_with_response({
        "proposal_state": "unclear",
        "proposed_value": "",
        "rationale": "Not mentioned in the paper.",
        "calculation": "",
        "needs_more_evidence": True,
        "evidence_quote": "",
        "evidence_page": None,
    })
    request = build_extraction_request(
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        row_data={"Title": "Study A"},
        column_name="Outcome",
        column_description="Primary outcome measure",
        style_profile=None,
        retrieval_result=None,
        all_chunks=chunks,
        verify_mode=False,
    )
    proposal, evidence_list = extract_cell(request, provider, doc, "run_001", chunks)
    assert proposal.proposal_state == ProposalState.UNCLEAR


def test_extract_cell_skipped_state() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = _make_provider_with_response({
        "proposal_state": "skipped",
        "proposed_value": "",
        "rationale": "Column not applicable.",
        "calculation": "",
        "needs_more_evidence": False,
        "evidence_quote": "",
        "evidence_page": None,
    })
    request = build_extraction_request(
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        row_data={"Title": "Study A"},
        column_name="Notes",
        column_description="Misc notes",
        style_profile=None,
        retrieval_result=None,
        all_chunks=chunks,
        verify_mode=False,
    )
    proposal, _ = extract_cell(request, provider, doc, "run_001", chunks)
    assert proposal.proposal_state == ProposalState.SKIPPED


# ---------------------------------------------------------------------------
# T052 — Provider failure handling
# ---------------------------------------------------------------------------

def test_extract_cell_provider_error_yields_error_state() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = MagicMock(spec=ProviderAdapter)
    provider.complete_json.side_effect = ProviderError("Connection refused")
    request = build_extraction_request(
        run_id="run_001", pdf_id="pdf_001", row_id="Study A",
        row_data={"Title": "Study A"}, column_name="Dose",
        column_description="Drug dose", style_profile=None,
        retrieval_result=None, all_chunks=chunks, verify_mode=False,
    )
    proposal, _ = extract_cell(request, provider, doc, "run_001", chunks)
    assert proposal.proposal_state == ProposalState.ERROR
    assert "provider error" in proposal.rationale.lower()


def test_extract_cell_structured_output_error_yields_error_state() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = MagicMock(spec=ProviderAdapter)
    provider.complete_json.side_effect = StructuredOutputError("Invalid JSON")
    request = build_extraction_request(
        run_id="run_001", pdf_id="pdf_001", row_id="Study A",
        row_data={"Title": "Study A"}, column_name="Dose",
        column_description="Drug dose", style_profile=None,
        retrieval_result=None, all_chunks=chunks, verify_mode=False,
    )
    proposal, _ = extract_cell(request, provider, doc, "run_001", chunks)
    assert proposal.proposal_state == ProposalState.ERROR


# ---------------------------------------------------------------------------
# T059 — Text evidence anchoring
# ---------------------------------------------------------------------------

def test_validate_and_anchor_evidence_found_in_doc() -> None:
    doc = _make_doc()
    quote = "The drug was administered at 10 mg/kg body weight."
    validated_quote, page, confidence = validate_and_anchor_evidence(
        proposed_value="10 mg/kg",
        evidence_quote=quote,
        evidence_page=1,
        doc=doc,
    )
    assert confidence >= 0.7
    assert page == 1


def test_validate_and_anchor_evidence_not_found_low_confidence() -> None:
    doc = _make_doc()
    _, _, confidence = validate_and_anchor_evidence(
        proposed_value="some value",
        evidence_quote="A quote completely absent from this document.",
        evidence_page=1,
        doc=doc,
    )
    assert confidence == 0.3


def test_validate_and_anchor_evidence_empty_quote() -> None:
    doc = _make_doc()
    quote, page, confidence = validate_and_anchor_evidence(
        proposed_value="10 mg/kg",
        evidence_quote="",
        evidence_page=None,
        doc=doc,
    )
    assert confidence == 0.0
    assert quote is None


# ---------------------------------------------------------------------------
# T060 — Evidence recovery pass
# ---------------------------------------------------------------------------

def test_attempt_evidence_recovery_finds_value() -> None:
    doc = _make_doc()
    quote, page = attempt_evidence_recovery(
        column_name="Dose",
        proposed_value="10 mg/kg",
        doc=doc,
        all_chunks=build_chunks(doc),
    )
    assert quote is not None
    assert page == 1


def test_attempt_evidence_recovery_value_absent() -> None:
    doc = _make_doc()
    quote, page = attempt_evidence_recovery(
        column_name="Dose",
        proposed_value="XYZ_NOT_IN_DOC_12345",
        doc=doc,
        all_chunks=build_chunks(doc),
    )
    assert quote is None
    assert page is None


# ---------------------------------------------------------------------------
# T061 — Weak proposal with quote+page (low confidence but still reviewable)
# ---------------------------------------------------------------------------

def test_extract_cell_keeps_low_confidence_quote_evidence() -> None:
    """Even with low anchor confidence, a quote+page evidence record should be stored."""
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = _make_provider_with_response({
        "proposal_state": "found",
        "proposed_value": "10 mg/kg",
        "rationale": "Found.",
        "calculation": "",
        "needs_more_evidence": False,
        "evidence_quote": "Partial quote that matches",
        "evidence_page": 1,
    })
    # Patch validate_and_anchor_evidence to simulate low but non-zero confidence
    with patch("backend.app.extraction.validate_and_anchor_evidence", return_value=("Partial quote that matches", 1, 0.4)):
        request = build_extraction_request(
            run_id="run_001", pdf_id="pdf_001", row_id="Study A",
            row_data={"Title": "Study A"}, column_name="Dose",
            column_description="Drug dose", style_profile=None,
            retrieval_result=None, all_chunks=chunks, verify_mode=False,
        )
        proposal, evidence_list = extract_cell(request, provider, doc, "run_001", chunks)
    assert len(evidence_list) > 0
    assert evidence_list[0].source_type == EvidenceSourceType.TEXT_QUOTE


# ---------------------------------------------------------------------------
# T062 — Figure fallback trigger
# ---------------------------------------------------------------------------

def test_figure_fallback_triggered_for_figure_field_with_weak_retrieval() -> None:
    result = should_trigger_figure_fallback(
        column_name="Figure 2 value",
        column_description="Value from figure showing results",
        proposal_state=ProposalState.UNCLEAR,
        retrieval_result=None,
    )
    assert result is True


def test_figure_fallback_not_triggered_when_proposal_found() -> None:
    result = should_trigger_figure_fallback(
        column_name="Figure 2 value",
        column_description="Description from figure",
        proposal_state=ProposalState.FOUND,
        retrieval_result=None,
    )
    assert result is False


def test_figure_fallback_not_triggered_for_non_figure_field() -> None:
    result = should_trigger_figure_fallback(
        column_name="Sample Size",
        column_description="Total participants enrolled",
        proposal_state=ProposalState.UNCLEAR,
        retrieval_result=None,
    )
    assert result is False


# ---------------------------------------------------------------------------
# T063 — Figure fallback input package
# ---------------------------------------------------------------------------

def test_figure_packages_skipped_when_no_crop(tmp_path: Path) -> None:
    figure = ParsedFigure(figure_id="fig_001", page_no=1)
    doc = _make_doc(figures=[figure])
    packages = build_figure_fallback_packages(doc, tmp_path)
    # No crop file exists, so no packages should be built
    assert len(packages) == 0


def test_figure_packages_built_when_crop_exists(tmp_path: Path) -> None:
    figure = ParsedFigure(figure_id="fig_001", page_no=1, caption_text="Figure 1: Results")
    doc = _make_doc(figures=[figure])
    # Create a fake crop file
    crop_dir = tmp_path / "parsed" / doc.pdf_id / "figures"
    crop_dir.mkdir(parents=True)
    crop_file = crop_dir / "fig_001_crop.png"
    crop_file.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal PNG header
    packages = build_figure_fallback_packages(doc, tmp_path)
    assert len(packages) == 1
    assert packages[0].figure_id == "fig_001"
    assert packages[0].caption_text == "Figure 1: Results"
    assert packages[0].crop_b64 is not None


# ---------------------------------------------------------------------------
# T064 — Figure-derived evidence records are distinct
# ---------------------------------------------------------------------------

def test_figure_derived_evidence_has_figure_source_type() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = _make_provider_with_response({
        "proposal_state": "found",
        "proposed_value": "42%",
        "rationale": "From figure 2.",
        "calculation": "",
        "needs_more_evidence": False,
        "evidence_quote": "",
        "evidence_page": 2,
        "figure_ref": "Figure 2",
        "caption_text": "Fig 2: Results",
    })
    request = build_extraction_request(
        run_id="run_001", pdf_id="pdf_001", row_id="Study A",
        row_data={"Title": "Study A"}, column_name="Efficacy",
        column_description="Efficacy from figure", style_profile=None,
        retrieval_result=None, all_chunks=chunks, verify_mode=False,
    )
    request.source_mode = "vision"
    _, evidence_list = extract_cell(request, provider, doc, "run_001", chunks)
    assert any(e.source_type == EvidenceSourceType.FIGURE_CROP for e in evidence_list)


# ---------------------------------------------------------------------------
# T065 — Support label mapping
# ---------------------------------------------------------------------------

def test_map_support_label_direct_evidence() -> None:
    label = map_support_label(ProposalState.FOUND, anchor_confidence=0.9, source_mode="text")
    assert label == SupportLabel.DIRECT_EVIDENCE


def test_map_support_label_weak_evidence() -> None:
    label = map_support_label(ProposalState.FOUND, anchor_confidence=0.3, source_mode="text")
    assert label == SupportLabel.WEAK_EVIDENCE


def test_map_support_label_inferred() -> None:
    label = map_support_label(ProposalState.INFERRED, anchor_confidence=0.8, source_mode="text")
    assert label == SupportLabel.INFERRED_FROM_EVIDENCE


def test_map_support_label_figure_based() -> None:
    label = map_support_label(
        ProposalState.FOUND, anchor_confidence=0.6, source_mode="vision", is_figure_derived=True
    )
    assert label == SupportLabel.FIGURE_BASED_EVIDENCE


# ---------------------------------------------------------------------------
# T056 — Proposal/evidence serialization to artifacts
# ---------------------------------------------------------------------------

def test_persist_proposal_and_evidence(tmp_path: Path) -> None:
    from backend.app.schemas import ProposalRecord, EvidenceRecord
    artifacts = _make_artifacts(tmp_path)
    proposal = ProposalRecord(
        proposal_id="proposal_abc",
        run_id="run_001",
        pdf_id="pdf_001",
        row_id="Study A",
        column_name="Dose",
        cell_id="cell_xyz",
        proposal_state=ProposalState.FOUND,
        support_label=SupportLabel.DIRECT_EVIDENCE,
        proposed_value="10 mg/kg",
        rationale="Found in methods.",
    )
    evidence = EvidenceRecord(
        evidence_id="evidence_001",
        proposal_id="proposal_abc",
        pdf_id="pdf_001",
        source_type=EvidenceSourceType.TEXT_QUOTE,
        page=1,
        quote_text="10 mg/kg body weight",
        anchor_confidence=0.9,
    )
    persist_proposal_and_evidence(artifacts, proposal, [evidence])

    proposals = artifacts.read_jsonl("proposals/proposals.jsonl")
    evidences = artifacts.read_jsonl("evidence/evidence.jsonl")
    assert len(proposals) == 1
    assert proposals[0]["proposal_id"] == "proposal_abc"
    assert len(evidences) == 1
    assert evidences[0]["evidence_id"] == "evidence_001"


# ---------------------------------------------------------------------------
# T066 — Verify mode extraction
# ---------------------------------------------------------------------------

def test_extract_cell_verify_mode_prompt_contains_existing_value() -> None:
    doc = _make_doc()
    chunks = build_chunks(doc)
    provider = _make_provider_with_response({
        "proposal_state": "found",
        "proposed_value": "10 mg/kg",
        "rationale": "Confirmed.",
        "calculation": "",
        "needs_more_evidence": False,
        "evidence_quote": "drug was administered at 10 mg/kg",
        "evidence_page": 1,
    })
    request = build_extraction_request(
        run_id="run_001", pdf_id="pdf_001", row_id="Study A",
        row_data={"Title": "Study A", "Dose": "10 mg/kg"},
        column_name="Dose", column_description="Drug dose",
        style_profile=None, retrieval_result=None, all_chunks=chunks,
        verify_mode=True,
    )
    prompt = build_extraction_user_prompt(request)
    assert "10 mg/kg" in prompt
    assert "verify" in prompt.lower()


def test_system_prompt_verify_mode_mentions_verify() -> None:
    prompt = build_extraction_system_prompt(verify_mode=True)
    assert "verify" in prompt.lower()


# ---------------------------------------------------------------------------
# T067 — run_extraction_for_run: no provider → skipped proposals
# ---------------------------------------------------------------------------

def test_run_extraction_no_provider_skips_all(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    doc = _make_doc()
    schema_rows = [{"column_name": "Dose", "description": "Drug dose"}]
    table_rows = [{"Title": "Study A", "Authors": "Smith", "Dose": ""}]
    matched_pdfs = {"pdf_001": "Study A"}
    parsed_docs = {"pdf_001": doc}
    chunks = build_chunks(doc)
    all_chunks_by_pdf = {"pdf_001": chunks}
    retrieval_results: dict = {}

    class FakeConfig:
        verify_mode = False
        placeholders_treated_as_empty = ["", " "]
        provider = {}
        retrieval = {}

    result = run_extraction_for_run(
        run_id="run_001",
        artifacts=artifacts,
        config=FakeConfig(),
        matched_pdfs=matched_pdfs,
        parsed_docs=parsed_docs,
        schema_rows=schema_rows,
        table_rows=table_rows,
        provider=None,
        style_profiles={},
        all_chunks_by_pdf=all_chunks_by_pdf,
        retrieval_results=retrieval_results,
    )
    assert result["skipped_no_provider"] >= 1
    proposals = artifacts.read_jsonl("proposals/proposals.jsonl")
    assert len(proposals) >= 1
    assert all(p["proposal_state"] == "skipped" for p in proposals)


def test_run_extraction_with_provider_generates_proposals(tmp_path: Path) -> None:
    artifacts = _make_artifacts(tmp_path)
    doc = _make_doc()
    schema_rows = [{"column_name": "Dose", "description": "Drug dose"}]
    table_rows = [{"Title": "Study A", "Authors": "Smith", "Dose": ""}]
    matched_pdfs = {"pdf_001": "Study A"}
    parsed_docs = {"pdf_001": doc}
    chunks = build_chunks(doc)

    provider = _make_provider_with_response({
        "proposal_state": "found",
        "proposed_value": "10 mg/kg",
        "rationale": "Found in methods.",
        "calculation": "",
        "needs_more_evidence": False,
        "evidence_quote": "drug was administered at 10 mg/kg",
        "evidence_page": 1,
    })

    class FakeConfig:
        verify_mode = False
        placeholders_treated_as_empty = ["", " "]
        retrieval = {}

    result = run_extraction_for_run(
        run_id="run_001",
        artifacts=artifacts,
        config=FakeConfig(),
        matched_pdfs=matched_pdfs,
        parsed_docs=parsed_docs,
        schema_rows=schema_rows,
        table_rows=table_rows,
        provider=provider,
        style_profiles={},
        all_chunks_by_pdf={"pdf_001": chunks},
        retrieval_results={},
    )
    assert result["proposals_generated"] >= 1
    proposals = artifacts.read_jsonl("proposals/proposals.jsonl")
    assert len(proposals) >= 1


# ---------------------------------------------------------------------------
# Provider unit tests (T050-T052)
# ---------------------------------------------------------------------------

def test_lmstudio_provider_parse_valid_json() -> None:
    provider = LMStudioProvider()
    result = provider._parse_json_response('{"key": "value"}', {})
    assert result == {"key": "value"}


def test_lmstudio_provider_parse_json_with_surrounding_text() -> None:
    provider = LMStudioProvider()
    result = provider._parse_json_response('Sure! Here is the JSON:\n{"key": "value"}\nDone.', {})
    assert result == {"key": "value"}


def test_lmstudio_provider_parse_invalid_json_raises() -> None:
    provider = LMStudioProvider()
    with pytest.raises(StructuredOutputError):
        provider._parse_json_response("not json at all", {})


def test_lmstudio_provider_parse_non_object_raises() -> None:
    provider = LMStudioProvider()
    with pytest.raises(StructuredOutputError):
        provider._parse_json_response("[1, 2, 3]", {})


def test_provider_unavailable_returns_false_capabilities() -> None:
    """When LM Studio is not running, capabilities.available should be False."""
    provider = LMStudioProvider(base_url="http://localhost:19999", timeout=1)
    caps = provider.capabilities
    assert caps.available is False
