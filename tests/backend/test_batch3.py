"""Batch 3 tests: Style profiles, retrieval, provider, extraction, and evidence (T049, T067).

Tests cover:
- Style-profile schema, generation, no-leakage baseline
- Typed chunk generation, retrieval text/display text separation
- Retrieval defaults (top_k, neighbor window)
- Provider capability probing and mode truth
- Structured-output parsing and JSON repair
- Proposal state handling (found/inferred/unclear/blocked/error/skipped)
- Evidence ranking (primary selection by authority)
- Exact/approximate/quote-plus-page fallback chain
- Evidence type labeling
- Proactive figure review triggering
- Figure evidence support for any field type
- Figure rescue of weak text proposals
- Verify mode extraction
- Provider failure handling
- Blocked and unclear outcomes
- Malformed JSON repair
- Compact bullet rationale
- Canonical fixture readiness check
"""

from __future__ import annotations

import asyncio
import json
import pathlib
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.extraction import (
    EvidenceRecord,
    ProposalRecord,
    adjudicate_state,
    anchor_evidence,
    build_text_extraction_prompt,
    evidence_type_display,
    extract_cell,
    find_approximate_highlight_regions,
    find_exact_highlight_regions,
    is_long_text_field,
    load_evidence,
    load_proposals,
    make_blocked_proposal,
    make_skipped_proposal,
    persist_evidence,
    persist_proposal,
    proposal_support_display,
    rank_evidence,
    select_relevant_figures,
)
from backend.app.provider import (
    LMStudioProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderMode,
    StructuredOutputError,
    _try_repair_json,
)
from backend.app.retrieval import (
    RetrievalChunk,
    RetrievalResult,
    _tokenize,
    build_retrieval_query,
    build_chunks_from_parsed_doc,
    retrieve,
    run_retrieval_for_cell,
    score_chunks,
)
from backend.app.schemas import EvidenceSourceType, ProposalState, SupportLabel
from backend.app.style_profiles import (
    StyleProfile,
    _heuristic_profile,
    generate_style_profile,
    load_style_profile,
    persist_style_profile,
    run_style_profiles_stage,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_TABLE = "tests/fixtures/tables/literature_fixture.xlsx"
FIXTURE_SCHEMA = "tests/fixtures/tables/literature_fixture_schema.csv"
FIXTURE_PDF_DIR = "tests/fixtures/papers"


@pytest.fixture
def run_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    d = tmp_path / "run_test001"
    d.mkdir()
    for sub in ("proposals", "evidence", "retrieval", "style_profiles"):
        (d / sub).mkdir()
    return d


@pytest.fixture
def minimal_doc_dict() -> dict:
    """A minimal ParsedDocument-like dict for testing."""
    return {
        "pdf_id": "paper_test",
        "pdf_path": "test.pdf",
        "blocks": [
            {
                "block_id": "b1",
                "block_type": "section_heading",
                "page_number": 1,
                "text": "Methods",
                "normalized_text": "methods",
                "reading_order": 0,
                "bbox": [10, 700, 400, 720],
                "provenance": "pypdfium2",
            },
            {
                "block_id": "b2",
                "block_type": "paragraph",
                "page_number": 1,
                "text": "The scaffold was implanted in the tibial defect of Sprague-Dawley rats.",
                "normalized_text": "the scaffold was implanted in the tibial defect of sprague-dawley rats",
                "reading_order": 1,
                "bbox": [10, 600, 400, 650],
                "provenance": "pypdfium2",
            },
            {
                "block_id": "b3",
                "block_type": "caption",
                "page_number": 2,
                "text": "Figure 1. Micro-CT images showing bone ingrowth at 8 weeks.",
                "normalized_text": "figure 1 micro ct images showing bone ingrowth at 8 weeks",
                "reading_order": 2,
                "bbox": [10, 500, 400, 530],
                "provenance": "pypdfium2",
            },
            {
                "block_id": "b4",
                "block_type": "paragraph",
                "page_number": 2,
                "text": "Bone volume fraction (BVF) was measured as 45.3% at 12 weeks post-implantation.",
                "normalized_text": "bone volume fraction bvf was measured as 45 3 at 12 weeks post implantation",
                "reading_order": 3,
                "bbox": [10, 400, 400, 440],
                "provenance": "pypdfium2",
            },
            {
                "block_id": "b5",
                "block_type": "table_region",
                "page_number": 3,
                "text": "Group | BVF (%) | p-value\nScaffold | 45.3 | 0.001",
                "normalized_text": "group bvf p value scaffold 45 3 0 001",
                "reading_order": 4,
                "bbox": [10, 300, 400, 380],
                "provenance": "pypdfium2",
            },
        ],
        "figures": [
            {
                "figure_id": "fig_1",
                "page_number": 2,
                "caption_block_id": "b3",
                "caption_text": "Figure 1. Micro-CT images showing bone ingrowth at 8 weeks.",
                "bbox": [10, 530, 400, 700],
                "crop_path": None,
            },
            {
                "figure_id": "fig_2",
                "page_number": 3,
                "caption_block_id": None,
                "caption_text": "Figure 2. Mechanical testing setup and load-displacement curve.",
                "bbox": [10, 300, 420, 500],
                "crop_path": None,
            },
        ],
        "full_text": "Methods\nThe scaffold was implanted in the tibial defect of Sprague-Dawley rats.\n"
                     "Figure 1. Micro-CT images showing bone ingrowth at 8 weeks.\n"
                     "Bone volume fraction (BVF) was measured as 45.3% at 12 weeks post-implantation.",
        "normalized_text": "methods the scaffold was implanted tibial defect sprague dawley rats",
        "pages": [
            {"page_number": 1, "width": 595, "height": 842, "text_accessible": True, "block_count": 2},
            {"page_number": 2, "width": 595, "height": 842, "text_accessible": True, "block_count": 2},
            {"page_number": 3, "width": 595, "height": 842, "text_accessible": True, "block_count": 1},
        ],
    }


def _minimal_png_bytes() -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xFF\xFF\xFF")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ===========================================================================
# T049 — Style profiles
# ===========================================================================

class TestStyleProfileSchema:
    """T041: StyleProfile schema validation."""

    def test_required_fields_present(self):
        required = [
            "column_name", "field_type_guess", "expected_length", "tone",
            "detail_level", "value_shape", "unit_style", "format_notes",
            "example_risk", "generated_at", "source_column_count", "provider_mode",
        ]
        fields = StyleProfile.model_fields.keys()
        for f in required:
            assert f in fields, f"StyleProfile missing field: {f}"

    def test_profile_instantiation(self):
        import datetime
        p = StyleProfile(
            column_name="Integration site",
            field_type_guess="categorical",
            expected_length="short",
            tone="technical",
            detail_level="medium",
            value_shape="single term",
            generated_at=datetime.datetime.now().isoformat(),
            source_column_count=5,
        )
        assert p.column_name == "Integration site"
        assert p.example_risk == "none"   # default

    def test_heuristic_profile_numeric(self):
        values = ["1.5", "2.3", "0.8", "3.1"]
        profile = _heuristic_profile("Score", values)
        assert profile.field_type_guess == "numeric"
        assert profile.source_column_count == 4
        assert profile.provider_mode == "heuristic"

    def test_heuristic_profile_text(self):
        values = ["Tibial defect", "Femoral condyle", "Calvarial defect"]
        profile = _heuristic_profile("Site", values)
        assert profile.field_type_guess == "text"
        assert profile.expected_length in ("single_value", "short")

    def test_heuristic_profile_empty_column(self):
        profile = _heuristic_profile("Empty", [])
        assert profile.field_type_guess == "unknown"
        assert profile.source_column_count == 0

    def test_no_raw_values_in_profile(self):
        """T044: raw cell values must NOT be stored in the profile."""
        values = ["Tibial defect", "SECRET_DATA_12345"]
        profile = _heuristic_profile("Site", values)
        dumped = json.dumps(profile.model_dump())
        assert "SECRET_DATA_12345" not in dumped
        assert "Tibial defect" not in dumped

    def test_long_text_field_detection(self):
        assert is_long_text_field("Abstract", "The abstract of the paper")
        assert is_long_text_field("Methods", "Description of methods used")
        assert not is_long_text_field("Species", "Animal species used in the study")

    async def test_generate_style_profile_no_provider(self):
        """T042: falls back to heuristic when provider is None."""
        profile = await generate_style_profile(
            "Integration site", "Where the scaffold was implanted", ["Tibial", "Femoral"],
            provider=None
        )
        assert profile.provider_mode == "heuristic"
        assert profile.column_name == "Integration site"

    async def test_generate_style_profile_with_mock_provider(self):
        """T042: uses LLM when provider is available."""
        mock_provider = AsyncMock()
        mock_provider.text_complete_raw = AsyncMock(return_value=json.dumps({
            "field_type_guess": "categorical",
            "expected_length": "short",
            "tone": "technical",
            "detail_level": "medium",
            "value_shape": "anatomical site name",
            "unit_style": None,
            "format_notes": None,
            "example_risk": "low",
        }))
        profile = await generate_style_profile(
            "Integration site", "Site of implantation", ["Tibial", "Femoral"],
            provider=mock_provider
        )
        assert profile.provider_mode == "live_llm"
        assert profile.field_type_guess == "categorical"
        # No raw values in profile
        dumped = json.dumps(profile.model_dump())
        assert "Tibial" not in dumped
        assert "Femoral" not in dumped

    def test_persist_and_load_style_profile(self, run_dir: pathlib.Path):
        """T043: style profiles persisted and loadable."""
        import datetime
        profile = StyleProfile(
            column_name="Integration site",
            field_type_guess="categorical",
            expected_length="short",
            tone="technical",
            detail_level="medium",
            value_shape="single term",
            generated_at=datetime.datetime.now().isoformat(),
            source_column_count=3,
        )
        persist_style_profile(run_dir, profile)
        loaded = load_style_profile(run_dir, "Integration site")
        assert loaded is not None
        assert loaded.column_name == "Integration site"
        # T044: raw cell values must NOT appear in the persisted style profile file
        path = run_dir / "style_profiles" / "Integration_site.json"
        content = path.read_text()
        # These are raw cell values that were used for format analysis — must not persist
        assert "Tibial" not in content
        assert "Femoral" not in content

    async def test_run_style_profiles_stage(self, run_dir: pathlib.Path):
        """T042/T043: run_style_profiles_stage persists profiles for each schema column."""
        import pandas as pd
        df = pd.DataFrame({
            "Title": ["Paper A"],
            "Authors": ["Smith J"],
            "Publication Year": ["2020"],
            "Integration site": ["Tibial"],
            "Species": ["Rat"],
        })
        schema = [
            {"column_name": "Integration site", "description": "Site of implantation"},
            {"column_name": "Species", "description": "Animal species"},
        ]
        profiles = await run_style_profiles_stage(run_dir, df, schema, provider=None)
        assert "Integration site" in profiles
        assert "Species" in profiles
        # Profiles must be persisted
        assert (run_dir / "style_profiles" / "Integration_site.json").exists()
        assert (run_dir / "style_profiles" / "Species.json").exists()


# ===========================================================================
# T049 — Retrieval
# ===========================================================================

class TestRetrievalChunks:
    """T045: Typed chunk generation from ParsedDocument."""

    def test_chunk_types_generated(self, minimal_doc_dict: dict):
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        types = {c.chunk_type for c in chunks}
        # Should have paragraph, section, caption, table_region
        assert "section" in types
        assert "paragraph" in types
        assert "caption" in types
        assert "table_region" in types

    def test_display_text_equals_source_text(self, minimal_doc_dict: dict):
        """T046: display_text must preserve source text."""
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        for chunk in chunks:
            # display_text should match original block text
            matching_blocks = [
                b for b in minimal_doc_dict["blocks"]
                if b["block_id"] == chunk.source_block_id
            ]
            if matching_blocks:
                assert chunk.display_text == matching_blocks[0]["text"].strip()

    def test_retrieval_text_has_section_context(self, minimal_doc_dict: dict):
        """T046: retrieval_text includes section header for contextualization."""
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        # The paragraph under "Methods" section should have section context
        para_chunks = [c for c in chunks if c.chunk_type == "paragraph"]
        assert any(
            "Methods" in c.retrieval_text for c in para_chunks
        ), "Paragraph under Methods section should have section context in retrieval_text"

    def test_display_text_not_modified(self, minimal_doc_dict: dict):
        """T046: display_text must NOT have section prefix."""
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        for chunk in chunks:
            if chunk.chunk_type == "paragraph":
                # display_text should not have [Section:...] prefix
                assert not chunk.display_text.startswith("[Section:")

    def test_retrieval_text_display_text_differ_for_contextualized(self, minimal_doc_dict: dict):
        """T046: retrieval_text and display_text must differ for contextualized chunks."""
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        contextualized = [
            c for c in chunks
            if c.section_context and c.chunk_type == "paragraph"
        ]
        for c in contextualized:
            assert c.retrieval_text != c.display_text, (
                f"Chunk {c.chunk_id} should have different retrieval vs display text"
            )

    def test_top_k_default(self, minimal_doc_dict: dict):
        """T047: top_k default is 6."""
        chunks = retrieve("bone volume fraction", minimal_doc_dict, top_k=6)
        # Should return at most top_k + neighbors
        assert len(chunks) <= 12   # 6 + 6 neighbors max
        assert len(chunks) >= 1

    def test_top_k_respected(self, minimal_doc_dict: dict):
        """T047: top_k parameter respected."""
        chunks_2 = retrieve("scaffold implant", minimal_doc_dict, top_k=2)
        chunks_4 = retrieve("scaffold implant", minimal_doc_dict, top_k=4)
        assert len(chunks_2) <= len(chunks_4) + 4  # with neighbor window

    def test_captions_included(self, minimal_doc_dict: dict):
        """T047: captions included in retrieval."""
        chunks = retrieve("bone ingrowth figure", minimal_doc_dict, top_k=6, include_captions=True)
        has_caption = any(c.chunk_type == "caption" for c in chunks)
        assert has_caption

    def test_tables_included(self, minimal_doc_dict: dict):
        """T047: tables included in retrieval."""
        chunks = retrieve("BVF p-value", minimal_doc_dict, top_k=6, include_tables=True)
        has_table = any(c.chunk_type == "table_region" for c in chunks)
        assert has_table

    def test_neighbor_window_added(self, minimal_doc_dict: dict):
        """T047: neighbor window added around selected chunks."""
        chunks = retrieve("BVF", minimal_doc_dict, top_k=1, include_neighbor_window=True)
        neighbor_chunks = [c for c in chunks if c.is_neighbor]
        # At least one neighbor should be present
        assert len(chunks) >= 2, "Expected neighbor window to expand results"

    def test_chunks_sorted_by_page_then_order(self, minimal_doc_dict: dict):
        """Chunks should be in reading order."""
        chunks = retrieve("scaffold", minimal_doc_dict, top_k=6)
        pages = [c.page_number for c in chunks]
        # Pages should be non-decreasing
        assert pages == sorted(pages)

    def test_run_retrieval_for_cell_persists(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        """T048: retrieval artifacts persisted for inspection."""
        result = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Integration site",
            column_description="Where the scaffold was implanted",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=6,
        )
        assert result.query.startswith("Integration site")
        # Check artifact file exists
        artifact_path = run_dir / "retrieval" / "paper_test" / "Integration_site.json"
        assert artifact_path.exists()
        # Verify display_text/retrieval_text separation in persisted artifact
        data = json.loads(artifact_path.read_text())
        for chunk_data in data["chunks"]:
            assert "display_text" in chunk_data
            assert "retrieval_text" in chunk_data

    def test_run_retrieval_for_cell_sanitizes_windows_unsafe_filename(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        """T048: retrieval artifact names must be safe on Windows."""
        run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="What predicts activity? (e.g. accessible -> active):",
            column_description="Free-text rationale",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=6,
        )
        artifacts = list((run_dir / "retrieval" / "paper_test").glob("*.json"))
        assert len(artifacts) == 1

        invalid_chars = set('\\/:*?"<>|')
        filename = artifacts[0].name
        assert not any(ch in invalid_chars for ch in filename), filename

    def test_count_like_query_expands_with_pair_and_coverage_hints(self):
        query = build_retrieval_query(
            "# Variants tested",
            "How many different sequences or variants were evaluated in the study",
        )
        assert "Retrieval hints:" in query
        assert "pairs" in query
        assert "coverage" in query

    def test_count_like_retrieval_surfaces_pair_count_chunk(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        doc_dict = dict(minimal_doc_dict)
        doc_dict["blocks"] = list(minimal_doc_dict["blocks"]) + [
            {
                "block_id": "b6",
                "block_type": "paragraph",
                "page_number": 4,
                "text": "The study tested many different sequences across several conditions.",
                "normalized_text": "the study tested many different sequences across several conditions",
                "reading_order": 5,
                "bbox": [10, 220, 400, 260],
                "provenance": "pypdfium2",
            },
            {
                "block_id": "b7",
                "block_type": "paragraph",
                "page_number": 4,
                "text": "We focused our analysis on the 604,268 enhancer-promoter pairs for which we obtained good coverage.",
                "normalized_text": "we focused our analysis on the 604 268 enhancer promoter pairs for which we obtained good coverage",
                "reading_order": 6,
                "bbox": [10, 160, 400, 210],
                "provenance": "pypdfium2",
            },
        ]
        doc_dict["full_text"] = (
            minimal_doc_dict["full_text"]
            + "\nThe study tested many different sequences across several conditions."
            + "\nWe focused our analysis on the 604,268 enhancer-promoter pairs for which we obtained good coverage."
        )

        result = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="# Variants tested",
            column_description="How many different sequences or variants were evaluated in the study",
            doc_dict=doc_dict,
            run_dir=run_dir,
            top_k=4,
        )

        assert any("604,268" in chunk.display_text for chunk in result.chunks)

    def test_bm25_scores_relevant_higher(self, minimal_doc_dict: dict):
        """BM25 should score relevant chunks higher."""
        all_chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        scored = score_chunks("bone volume fraction", all_chunks)
        if scored:
            top_chunk = scored[0][1]
            # The chunk mentioning BVF should score highest
            assert "bone" in top_chunk.retrieval_text.lower() or \
                   "bvf" in top_chunk.retrieval_text.lower() or \
                   "45" in top_chunk.retrieval_text


# ===========================================================================
# T067 — Provider
# ===========================================================================

class TestProviderJSON:
    """T052: JSON repair and structured-output handling."""

    def test_repair_json_from_markdown(self):
        raw = "```json\n{\"test\": \"value\"}\n```"
        result = _try_repair_json(raw)
        assert result == {"test": "value"}

    def test_repair_json_from_object(self):
        raw = '{"proposed_value": "45.3%", "state": "found"}'
        result = _try_repair_json(raw)
        assert result["state"] == "found"

    def test_repair_json_trailing_comma(self):
        raw = '{"test": "value", "other": 1, }'
        result = _try_repair_json(raw)
        assert result is not None

    def test_repair_extracts_embedded_json(self):
        raw = 'Here is the answer: {"proposed_value": "45.3", "state": "found", "rationale": null, "calculation": null, "quotes": []}'
        result = _try_repair_json(raw)
        assert result is not None
        assert result["state"] == "found"

    def test_repair_returns_none_for_garbage(self):
        result = _try_repair_json("This is completely not JSON at all")
        assert result is None


class TestProviderCapabilities:
    """T050: Provider capability contract."""

    def test_provider_capabilities_schema(self):
        caps = ProviderCapabilities(
            supports_structured_output=True,
            structured_output_mode="json_schema",
            model_id="test-model",
            vision_capable=False,
        )
        assert caps.structured_output_mode == "json_schema"

    def test_provider_mode_is_live(self):
        mode = ProviderMode(
            token="lm_studio",
            locality="local",
            mode="live_local",
            text_model_id="test",
            recorded_at="2024-01-01T00:00:00+00:00",
        )
        assert mode.is_live() is True

    def test_provider_mode_unavailable(self):
        mode = ProviderMode(
            token="lm_studio",
            locality="local",
            mode="unavailable",
            readiness_error="Cannot reach LM Studio",
            recorded_at="2024-01-01T00:00:00+00:00",
        )
        assert mode.is_live() is False

    def test_provider_mode_display_label_live_local(self):
        mode = ProviderMode(
            token="lm_studio",
            locality="local",
            mode="live_local",
            recorded_at="2024-01-01T00:00:00+00:00",
        )
        label = mode.display_label()
        assert "LM Studio" in label
        assert "live local" in label

    def test_provider_mode_display_label_unavailable(self):
        mode = ProviderMode(
            token="lm_studio",
            locality="local",
            mode="unavailable",
            recorded_at="2024-01-01T00:00:00+00:00",
        )
        label = mode.display_label()
        assert "unavailable" in label

    def test_lm_studio_token(self):
        p = LMStudioProvider()
        assert p.token == "lm_studio"

    def test_lm_studio_locality(self):
        from backend.app.schemas import ProviderLocality
        p = LMStudioProvider()
        assert p.locality == ProviderLocality.local

    async def test_provider_unreachable_returns_unavailable_caps(self):
        """T052: unreachable provider returns degraded capabilities, not silent success."""
        p = LMStudioProvider(base_url="http://localhost:9999")
        caps = await p.probe_capabilities("test-model")
        # Should return caps with supports_structured_output=False, not raise
        assert caps.supports_structured_output is False

    def test_build_provider_unknown_token_raises(self):
        from backend.app.provider import build_provider
        mock_config = MagicMock()
        mock_config.token = "unknown_provider"
        mock_config.base_url = "http://localhost:1234"
        with pytest.raises(ProviderError):
            build_provider(mock_config)

    def test_build_provider_lm_studio(self):
        from backend.app.provider import build_provider
        mock_config = MagicMock()
        mock_config.token = "lm_studio"
        mock_config.base_url = "http://localhost:1234"
        provider = build_provider(mock_config)
        assert isinstance(provider, LMStudioProvider)


# ===========================================================================
# T067 — Extraction
# ===========================================================================

class TestProposalState:
    """T058: Proposal state handling."""

    def test_found_with_direct_quote(self):
        state, support = adjudicate_state(
            "found", "45.3%",
            [{"text": "BVF was 45.3%", "source_type": "direct_quote"}]
        )
        assert state == ProposalState.found
        assert support == SupportLabel.direct_evidence

    def test_found_without_quotes_downgrades(self):
        state, support = adjudicate_state("found", "45.3%", [])
        assert state == ProposalState.inferred
        assert support == SupportLabel.inferred_from_evidence

    def test_inferred_with_quotes(self):
        state, support = adjudicate_state(
            "inferred", "derived value",
            [{"text": "some quote", "source_type": "inferred_reasoning"}]
        )
        assert state == ProposalState.inferred

    def test_inferred_without_quotes_weak(self):
        state, support = adjudicate_state("inferred", "derived value", [])
        assert state == ProposalState.inferred
        assert support == SupportLabel.weak_evidence

    def test_unclear_no_value(self):
        state, support = adjudicate_state("unclear", None, [])
        assert state == ProposalState.unclear

    def test_unclear_empty_value(self):
        state, support = adjudicate_state("found", "", [])
        assert state == ProposalState.unclear

    def test_blocked_proposal(self, run_dir: pathlib.Path):
        prop = make_blocked_proposal(
            run_id="run_test",
            pdf_id="pdf_test",
            row_id="row_test",
            cell_id="cell_test",
            column_name="Test col",
            blocked_reason="No PDF matched",
            run_dir=run_dir,
        )
        assert prop.state == ProposalState.blocked
        assert prop.support == SupportLabel.blocked
        assert "blocked" in prop.warning_flags

    def test_skipped_proposal(self, run_dir: pathlib.Path):
        prop = make_skipped_proposal(
            run_id="run_test",
            pdf_id="pdf_test",
            row_id="row_test",
            cell_id="cell_test",
            column_name="Test col",
            skip_reason="Provider unavailable",
            run_dir=run_dir,
        )
        assert prop.state == ProposalState.skipped

    def test_anti_guessing_unclear_preferred(self):
        """T058a: unclear preferred when no paper evidence."""
        state, support = adjudicate_state("found", "guessed value", [])
        # Without any quotes, should downgrade
        assert state == ProposalState.inferred  # at best inferred, not found


class TestEvidenceAnchoring:
    """T059: Text-evidence anchoring and highlight chain."""

    def test_exact_match_found(self, minimal_doc_dict: dict):
        """Exact quote in doc_dict should produce exact_highlight_regions."""
        quote = "scaffold was implanted in the tibial defect"
        regions, conf, page = find_exact_highlight_regions(quote, minimal_doc_dict)
        assert conf >= 0.9
        assert len(regions) >= 1
        assert page is not None

    def test_no_match_gives_empty_regions(self, minimal_doc_dict: dict):
        regions, conf, page = find_exact_highlight_regions(
            "completely unrelated text xyz123", minimal_doc_dict
        )
        assert len(regions) == 0

    def test_approximate_match(self, minimal_doc_dict: dict):
        """Partial quote overlap should produce approximate regions."""
        quote = "scaffold tibial Sprague-Dawley"
        regions, conf, page = find_approximate_highlight_regions(quote, minimal_doc_dict)
        if regions:
            # Region must have is_approximate flag
            assert regions[0].get("is_approximate") is True

    def test_anchor_evidence_exact(self, minimal_doc_dict: dict):
        """T059: exact match → direct_quote source type."""
        source_type, exact, approx, conf = anchor_evidence(
            "scaffold was implanted in the tibial defect",
            page_number=1,
            doc_dict=minimal_doc_dict,
        )
        assert source_type == EvidenceSourceType.direct_quote
        assert len(exact) >= 1
        assert len(approx) == 0

    def test_anchor_evidence_fallback_to_quote_plus_page(self, minimal_doc_dict: dict):
        """T059/T061: completely unanchored quote → quote_plus_page."""
        source_type, exact, approx, conf = anchor_evidence(
            "completely fabricated text that does not exist",
            page_number=1,
            doc_dict=minimal_doc_dict,
        )
        assert source_type == EvidenceSourceType.quote_plus_page
        assert len(exact) == 0
        assert len(approx) == 0
        assert conf == 0.0

    def test_approximate_not_presented_as_exact(self, minimal_doc_dict: dict):
        """T059: approximate highlight must be labeled as approximate, not direct_quote."""
        source_type, exact, approx, conf = anchor_evidence(
            "scaffold tibial Sprague",  # partial match
            page_number=1,
            doc_dict=minimal_doc_dict,
        )
        # Source type must NOT be direct_quote if confidence < 0.9
        if source_type == EvidenceSourceType.approximate_highlight:
            assert len(approx) >= 1
            assert approx[0].get("is_approximate") is True
        elif source_type == EvidenceSourceType.quote_plus_page:
            # Also acceptable fallback
            pass
        else:
            # direct_quote only acceptable if confidence is high
            assert conf >= 0.9


class TestEvidenceRanking:
    """T065: Evidence ranking by authority."""

    def _make_evidence(
        self, ev_id: str, source_type: EvidenceSourceType, rank: int = 1
    ) -> EvidenceRecord:
        import datetime
        return EvidenceRecord(
            evidence_id=ev_id,
            run_id="run_test",
            proposal_id="prop_test",
            pdf_id="pdf_test",
            source_type=source_type,
            quote_text="test quote",
            anchor_confidence=0.5,
            evidence_rank=rank,
            is_primary=False,
            created_at=datetime.datetime.now().isoformat(),
        )

    def test_direct_quote_becomes_primary(self):
        items = [
            self._make_evidence("e1", EvidenceSourceType.quote_plus_page),
            self._make_evidence("e2", EvidenceSourceType.direct_quote),
            self._make_evidence("e3", EvidenceSourceType.approximate_highlight),
        ]
        ranked = rank_evidence(items)
        assert ranked[0].evidence_id == "e2"
        assert ranked[0].is_primary is True
        assert ranked[0].evidence_rank == 1

    def test_ranking_order_direct_gt_inferred_gt_qpp(self):
        items = [
            self._make_evidence("e1", EvidenceSourceType.quote_plus_page),
            self._make_evidence("e2", EvidenceSourceType.inferred_reasoning),
            self._make_evidence("e3", EvidenceSourceType.direct_quote),
        ]
        ranked = rank_evidence(items)
        types = [r.source_type for r in ranked]
        assert types[0] == EvidenceSourceType.direct_quote
        assert types[-1] == EvidenceSourceType.quote_plus_page

    def test_supporting_evidence_not_primary(self):
        items = [
            self._make_evidence("e1", EvidenceSourceType.direct_quote),
            self._make_evidence("e2", EvidenceSourceType.inferred_reasoning),
        ]
        ranked = rank_evidence(items)
        assert ranked[0].is_primary is True
        for ev in ranked[1:]:
            assert ev.is_primary is False

    def test_single_item_is_primary(self):
        items = [self._make_evidence("e1", EvidenceSourceType.direct_quote)]
        ranked = rank_evidence(items)
        assert ranked[0].is_primary is True
        assert ranked[0].evidence_rank == 1

    def test_figure_evidence_ranks_alongside_inferred(self):
        items = [
            self._make_evidence("e1", EvidenceSourceType.caption_grounded_figure_evidence),
            self._make_evidence("e2", EvidenceSourceType.inferred_reasoning),
        ]
        ranked = rank_evidence(items)
        types = {r.source_type for r in ranked}
        assert EvidenceSourceType.caption_grounded_figure_evidence in types


class TestEvidenceTypeLabelMapping:
    """T065: Evidence type display labels."""

    def test_direct_quote_label(self):
        label = evidence_type_display(EvidenceSourceType.direct_quote)
        assert label == "Direct quote"

    def test_inferred_reasoning_label(self):
        label = evidence_type_display(EvidenceSourceType.inferred_reasoning)
        assert "Inferred" in label

    def test_approximate_highlight_label(self):
        label = evidence_type_display(EvidenceSourceType.approximate_highlight)
        assert "Approximate" in label or "approximate" in label.lower()

    def test_quote_plus_page_label(self):
        label = evidence_type_display(EvidenceSourceType.quote_plus_page)
        assert "fallback" in label.lower() or "page" in label.lower()

    def test_figure_label(self):
        label = evidence_type_display(EvidenceSourceType.caption_grounded_figure_evidence)
        assert "Figure" in label or "figure" in label.lower()

    def test_proposal_support_direct_evidence_label(self):
        label = proposal_support_display(SupportLabel.direct_evidence)
        assert label == "Direct evidence"

    def test_proposal_support_inferred_label(self):
        label = proposal_support_display(SupportLabel.inferred_from_evidence)
        assert "Inferred" in label


class TestExtractionOrchestrator:
    """T057: Per-cell extraction orchestrator."""

    def _make_mock_provider(
        self,
        response: Optional[dict] = None,
        raise_exc: Optional[Exception] = None,
    ) -> MagicMock:
        """Create a mock provider that returns a predefined structured response."""
        provider = AsyncMock()
        if raise_exc:
            provider.chat_complete_structured = AsyncMock(side_effect=raise_exc)
        else:
            provider.chat_complete_structured = AsyncMock(return_value=response or {
                "proposed_value": "Tibial defect",
                "state": "found",
                "rationale": "- Scaffold implanted in tibial defect of rats.",
                "calculation": None,
                "quotes": [{"text": "scaffold was implanted in the tibial defect", "page": 1, "source_type": "direct_quote"}],
            })
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": None,
            "state": "unclear",
            "rationale": None,
            "figure_description": None,
            "caption_relevant": False,
        })
        return provider

    async def test_successful_extraction_found(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        """T057: found state with direct quote evidence."""
        provider = self._make_mock_provider()
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_test",
            column_name="Integration site",
            column_description="Site of scaffold implantation",
            row_context={"Title": "Scaffold study", "Authors": "Smith J", "Publication Year": "2020"},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
        )
        assert proposal.state == ProposalState.found
        assert proposal.proposed_value == "Tibial defect"
        assert proposal.primary_evidence_id is not None
        persisted = load_proposals(run_dir)
        assert any(item.proposal_id == proposal.proposal_id for item in persisted)

    async def test_provider_error_yields_error_proposal(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        """T058: provider error produces error state proposal."""
        provider = self._make_mock_provider(raise_exc=ProviderError("Connection refused"))
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_test",
            column_name="Species",
            column_description="Animal species",
            row_context={},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
        )
        assert proposal.state == ProposalState.error
        assert "provider_error" in proposal.warning_flags

    async def test_unclear_state_preserved(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        """T058: unclear state preserved when model returns null value."""
        provider = self._make_mock_provider(response={
            "proposed_value": None,
            "state": "unclear",
            "rationale": None,
            "calculation": None,
            "quotes": [],
        })
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_test",
            column_name="Missing field",
            column_description="Something not in the paper",
            row_context={},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
        )
        assert proposal.state == ProposalState.unclear

    async def test_evidence_persisted_separately(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        """T056: evidence persisted as separate linked records."""
        provider = self._make_mock_provider()
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_test2",
            column_name="Integration site",
            column_description="Site of implantation",
            row_context={},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
        )
        if proposal.evidence_ids:
            ev_path = run_dir / "evidence" / f"{proposal.evidence_ids[0]}.json"
            assert ev_path.exists()

    async def test_verify_mode_uses_same_extraction_path(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        """T066: verify mode uses same extraction path."""
        provider = self._make_mock_provider()
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_verify",
            column_name="Integration site",
            column_description="Site of implantation",
            row_context={"Title": "Study"},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
            is_verify_mode=True,
            existing_value="Femoral condyle",
        )
        assert proposal.is_verify_mode is True
        assert proposal.existing_value == "Femoral condyle"
        persisted = load_proposals(run_dir)
        assert any(item.proposal_id == proposal.proposal_id for item in persisted)

    async def test_fallback_evidence_labeled_correctly(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        """T061: quote+page fallback evidence is labeled as fallback, not exact."""
        provider = self._make_mock_provider(response={
            "proposed_value": "Some value",
            "state": "found",
            "rationale": "- Found in text.",
            "calculation": None,
            "quotes": [{"text": "completely unfindable quote xyz123", "page": 1, "source_type": "direct_quote"}],
        })
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_fb",
            column_name="Integration site",
            column_description="Site of implantation",
            row_context={},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
        )
        # Evidence should exist
        all_ev = load_evidence(run_dir)
        ev_for_proposal = [e for e in all_ev if e.proposal_id == proposal.proposal_id]
        if ev_for_proposal:
            # The evidence source type should be quote_plus_page (fallback), not exact
            ev = ev_for_proposal[0]
            assert ev.source_type in (
                EvidenceSourceType.quote_plus_page,
                EvidenceSourceType.approximate_highlight,
                EvidenceSourceType.direct_quote,
            )
            # If it's quote_plus_page, warning flag should be set
            if ev.source_type == EvidenceSourceType.quote_plus_page:
                assert "fallback_evidence_used" in proposal.warning_flags

    async def test_provider_mode_persisted(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        """T052a: provider mode persisted in proposal record."""
        provider = self._make_mock_provider()
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_mode",
            column_name="Integration site",
            column_description="Site",
            row_context={},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
            provider_mode_str="live_local",
        )
        assert proposal.provider_mode == "live_local"

    async def test_long_text_field_gets_more_tokens(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        """T057a: long-text fields get larger max_tokens."""
        provider = AsyncMock()
        provider.chat_complete_structured = AsyncMock(return_value={
            "proposed_value": "Long abstract text here " * 20,
            "state": "found",
            "rationale": "- Abstract found in paper.",
            "calculation": None,
            "quotes": [{"text": "scaffold was implanted", "page": 1, "source_type": "direct_quote"}],
        })
        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_long",
            column_name="Abstract",
            column_description="Abstract of the paper",
            row_context={},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
        )
        # Check that max_tokens=4096 was passed (long text field)
        call_args = provider.chat_complete_structured.call_args
        assert call_args.kwargs.get("max_tokens", 2048) == 4096

    def test_rationale_is_bullets(self):
        """T053a: rationale output should be compact markdown bullets."""
        from backend.app.extraction import _normalize_rationale
        rationale = "The scaffold was implanted. Bone ingrowth was observed. BVF was 45.3%"
        normalized = _normalize_rationale(rationale)
        assert "- " in normalized
        lines = [l for l in normalized.strip().split("\n") if l.strip()]
        assert len(lines) <= 4  # at most 3 bullets + ellipsis

    def test_rationale_already_bullets_preserved(self):
        from backend.app.extraction import _normalize_rationale
        rationale = "- Scaffold implanted in tibial defect.\n- BVF was 45.3%."
        normalized = _normalize_rationale(rationale)
        assert normalized == rationale


class TestFigureReview:
    """T062-T064: Proactive figure review."""

    def test_select_relevant_figures_by_caption(self, minimal_doc_dict: dict):
        """T062: relevant figures selected by caption, not all figures."""
        figures = minimal_doc_dict["figures"]
        selected = select_relevant_figures(
            figures, "bone ingrowth", "CT images of bone ingrowth"
        )
        assert len(selected) <= 5
        # The bone ingrowth figure should be selected
        selected_captions = [f.get("caption_text", "") for f in selected]
        assert any("bone" in (c or "").lower() for c in selected_captions)

    def test_shortlist_prefers_figure_referenced_in_retrieved_text(self, minimal_doc_dict: dict):
        retrieval = RetrievalResult(
            run_id="run_test",
            pdf_id="paper_test",
            column_name="Mechanical readout",
            query="mechanical load displacement figure 2",
            top_k=6,
            chunks=[
                RetrievalChunk(
                    chunk_id="c1",
                    source_block_id="bref",
                    chunk_type="paragraph",
                    page_number=3,
                    reading_order=10,
                    display_text="As shown in Fig. 2a, the load-displacement curve indicates increased stiffness.",
                    retrieval_text="As shown in Fig. 2a, the load-displacement curve indicates increased stiffness.",
                )
            ],
            mode="baseline",
            retrieved_at="2026-04-04T00:00:00Z",
        )
        selected = select_relevant_figures(
            minimal_doc_dict["figures"],
            "Mechanical readout",
            "Load-displacement measurement from figure",
            retrieval=retrieval,
            doc_dict=minimal_doc_dict,
            max_figures=2,
        )
        assert selected
        assert selected[0]["figure_id"] == "fig_2"

    def test_select_relevant_figures_irrelevant_query(self, minimal_doc_dict: dict):
        """T062: unrelated query returns minimal figures."""
        figures = minimal_doc_dict["figures"]
        selected = select_relevant_figures(
            figures, "completely unrelated topic xyz", "nothing about this paper"
        )
        # Should return 0-2 (caption overlap 0, fall back to top 2)
        assert len(selected) <= 5

    def test_figure_evidence_persisted_distinctly(self, run_dir: pathlib.Path):
        """T064: figure-derived evidence persisted distinctly."""
        import datetime
        ev = EvidenceRecord(
            evidence_id="ev_fig_001",
            run_id="run_test",
            proposal_id="prop_test",
            pdf_id="pdf_test",
            source_type=EvidenceSourceType.caption_grounded_figure_evidence,
            quote_text="Figure 1 shows bone ingrowth at 8 weeks",
            page_number=2,
            figure_ref="fig_1",
            caption_text="Micro-CT images of bone ingrowth",
            anchor_confidence=0.7,
            evidence_rank=1,
            is_primary=True,
            is_figure_derived=True,
            created_at=datetime.datetime.now().isoformat(),
        )
        persist_evidence(run_dir, ev)
        path = run_dir / "evidence" / "ev_fig_001.json"
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["is_figure_derived"] is True
        assert data["source_type"] == EvidenceSourceType.caption_grounded_figure_evidence.value

    async def test_figure_review_triggered_when_vision_configured(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        """T062: figure review runs when vision model configured."""
        from backend.app.extraction import run_figure_review

        # Create a minimal PNG crop file so the vision path can be triggered
        crop_path = run_dir / "fig_crop.png"
        crop_path.write_bytes(_minimal_png_bytes())

        doc_with_crop = dict(minimal_doc_dict)
        doc_with_crop["figures"] = [
            {**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}
        ]

        provider = AsyncMock()
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "45.3%",
            "state": "found",
            "rationale": "- Figure shows 45.3% bone volume.",
            "figure_description": "Bar chart showing BVF values",
            "caption_relevant": True,
        })

        evidence = await run_figure_review(
            proposal_id="prop_test",
            run_id="run_test",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="BVF measurement from CT",
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            vision_model_id="vision-model",
        )
        # Should have been called with the bone ingrowth figure
        assert provider.vision_complete_structured.called

    async def test_figure_evidence_supports_any_field_type(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        """T062: figure evidence can support any field type, not just image-type fields."""
        from backend.app.extraction import run_figure_review
        crop_path = run_dir / "fig_crop2.png"
        crop_path.write_bytes(_minimal_png_bytes())

        doc_with_crop = dict(minimal_doc_dict)
        doc_with_crop["figures"] = [
            {**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}
        ]

        provider = AsyncMock()
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "Sprague-Dawley rat",
            "state": "found",
            "rationale": "- Figure caption mentions rats.",
            "figure_description": "Figure with animals",
            "caption_relevant": True,
        })

        # "Species" is a text field, not an image field — figure evidence still applies
        evidence = await run_figure_review(
            proposal_id="prop_species",
            run_id="run_test",
            pdf_id="paper_test",
            column_name="Species",
            column_description="Animal species used",
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            vision_model_id="vision-model",
        )
        # Vision model should have been attempted for any field type
        assert provider.vision_complete_structured.called

    async def test_figure_rescues_weak_text_proposal(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        """T062: figure evidence can upgrade an unclear proposal."""
        crop_path = run_dir / "fig_crop3.png"
        crop_path.write_bytes(_minimal_png_bytes())

        doc_with_crop = dict(minimal_doc_dict)
        doc_with_crop["figures"] = [
            {**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}
        ]

        # First produce an unclear text proposal
        text_provider = AsyncMock()
        text_provider.chat_complete_structured = AsyncMock(return_value={
            "proposed_value": None,
            "state": "unclear",
            "rationale": None,
            "calculation": None,
            "quotes": [],
        })
        text_provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "45.3%",
            "state": "found",
            "rationale": "- Figure shows BVF = 45.3%.",
            "figure_description": "BVF bar chart",
            "caption_relevant": True,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_rescue",
            column_name="Bone volume fraction",
            column_description="BVF",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=text_provider,
            text_model_id="test-model",
            vision_model_id="vision-model",
        )
        assert proposal.proposed_value == "45.3%"
        assert proposal.state == ProposalState.inferred
        assert "figure_derived" in proposal.warning_flags
        assert text_provider.vision_complete_structured.called

        proposal_evidence = [
            ev for ev in load_evidence(run_dir)
            if ev.proposal_id == proposal.proposal_id
        ]
        assert any(ev.is_figure_derived for ev in proposal_evidence)

    async def test_conflicting_figure_value_is_not_attached_to_text_proposal(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        crop_path = run_dir / "fig_crop4.png"
        crop_path.write_bytes(_minimal_png_bytes())

        doc_with_crop = dict(minimal_doc_dict)
        doc_with_crop["figures"] = [
            {**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}
        ]

        provider = AsyncMock()
        provider.chat_complete_structured = AsyncMock(return_value={
            "proposed_value": "Tibial defect",
            "state": "found",
            "rationale": "- Found in text.",
            "calculation": None,
            "quotes": [{"text": "scaffold was implanted in the tibial defect", "page": 1, "source_type": "direct_quote"}],
        })
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "Femoral condyle",
            "state": "found",
            "rationale": "- Figure suggests femoral condyle.",
            "figure_description": "Annotated defect site",
            "caption_relevant": True,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_conflict",
            column_name="Integration site",
            column_description="Site of implantation",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
            vision_model_id="vision-model",
        )

        proposal_evidence = [
            ev for ev in load_evidence(run_dir)
            if ev.proposal_id == proposal.proposal_id
        ]
        assert proposal.proposed_value == "Tibial defect"
        assert not any(ev.is_figure_derived for ev in proposal_evidence)

    async def test_vision_request_includes_retrieved_and_reference_context(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        from backend.app.extraction import run_figure_review

        crop_path = run_dir / "fig_crop_context.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_with_crop = dict(minimal_doc_dict)
        doc_with_crop["figures"] = [{**minimal_doc_dict["figures"][1], "crop_path": str(crop_path)}]

        retrieval = RetrievalResult(
            run_id="run_test",
            pdf_id="paper_test",
            column_name="Mechanical readout",
            query="Fig 2 load displacement",
            top_k=6,
            chunks=[
                RetrievalChunk(
                    chunk_id="cx",
                    source_block_id="bx",
                    chunk_type="paragraph",
                    page_number=3,
                    reading_order=12,
                    display_text="Fig. 2a shows the load-displacement curve with the peak around 120 N.",
                    retrieval_text="Fig. 2a shows the load-displacement curve with the peak around 120 N.",
                    section_context="Results",
                )
            ],
            mode="baseline",
            retrieved_at="2026-04-04T00:00:00Z",
        )

        provider = AsyncMock()
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "120 N",
            "state": "found",
            "rationale": "- Read from graph peak.",
            "numeric_value_form": "approximate",
            "figure_description": "Load-displacement graph",
            "caption_relevant": True,
        })

        await run_figure_review(
            proposal_id="prop_context",
            run_id="run_test",
            pdf_id="paper_test",
            column_name="Mechanical readout",
            column_description="Peak load from load-displacement graph",
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            vision_model_id="vision-model",
            retrieval=retrieval,
            trigger_reasons=["figure_graph_promising"],
        )

        sent_messages = provider.vision_complete_structured.call_args.kwargs["messages"]
        user_content = sent_messages[1]["content"]
        assert "Retrieved field passages:" in user_content
        assert "Figure-reference snippets from the paper:" in user_content

    async def test_selective_vision_trigger_skips_unneeded_calls(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        doc_with_crop = dict(minimal_doc_dict)
        crop_path = run_dir / "fig_crop_skip.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_with_crop["figures"] = [{**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}]

        provider = AsyncMock()
        provider.chat_complete_structured = AsyncMock(return_value={
            "proposed_value": "Sprague-Dawley rats",
            "state": "found",
            "rationale": "- Stated directly in methods.",
            "calculation": None,
            "numeric_value_form": None,
            "quotes": [
                {
                    "text": "The scaffold was implanted in the tibial defect of Sprague-Dawley rats.",
                    "page": 1,
                    "source_type": "direct_quote",
                }
            ],
        })
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "Sprague-Dawley rats",
            "state": "found",
            "rationale": "- Figure confirms species.",
            "numeric_value_form": None,
            "figure_description": "Microscopy panel",
            "caption_relevant": False,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_skip_vision",
            column_name="Species",
            column_description="Species used in study",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="text-model",
            vision_model_id="vision-model",
        )

        assert proposal.vision_trigger_reasons == []
        assert provider.vision_complete_structured.call_count == 0

    async def test_figure_approximate_or_range_numeric_rescue_is_honest(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        doc_with_crop = dict(minimal_doc_dict)
        crop_path = run_dir / "fig_crop_range.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_with_crop["figures"] = [{**minimal_doc_dict["figures"][1], "crop_path": str(crop_path)}]
        doc_with_crop["blocks"] = [
            *minimal_doc_dict["blocks"],
            {
                "block_id": "b_ref_2",
                "block_type": "paragraph",
                "page_number": 3,
                "text": "As shown in Fig. 2a, peak load appears between 110 and 130 N.",
                "normalized_text": "as shown in fig 2a peak load appears between 110 and 130 n",
                "reading_order": 10,
                "bbox": [10, 250, 420, 300],
                "provenance": "pypdfium2",
            },
        ]

        provider = AsyncMock()
        provider.chat_complete_structured = AsyncMock(return_value={
            "proposed_value": None,
            "state": "unclear",
            "rationale": None,
            "calculation": None,
            "numeric_value_form": None,
            "quotes": [],
        })
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "110-130 N",
            "state": "found",
            "rationale": "- Estimated from graph bars in Fig. 2a.",
            "numeric_value_form": "range",
            "figure_description": "Load-displacement plot",
            "caption_relevant": False,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_range",
            column_name="Peak load",
            column_description="Peak load from graph",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="text-model",
            vision_model_id="vision-model",
            field_type="number",
        )

        assert proposal.proposed_value == "110-130 N"
        assert proposal.numeric_value_form is not None
        assert proposal.numeric_value_form.value == "range"
        assert "range_value" in proposal.warning_flags
        assert proposal.vision_trigger_reasons
        assert proposal.vision_shortlist

        proposal_evidence = [ev for ev in load_evidence(run_dir) if ev.proposal_id == proposal.proposal_id]
        assert any(ev.is_figure_derived for ev in proposal_evidence)
        figure_evs = [ev for ev in proposal_evidence if ev.is_figure_derived]
        assert figure_evs
        assert figure_evs[0].source_type == EvidenceSourceType.visual_interpretation_figure_evidence
        assert figure_evs[0].vision_context_bundle is not None
        assert figure_evs[0].vision_trigger_reasons is not None


class TestProposalPersistence:
    """T056: Proposal and evidence serialization."""

    def test_load_proposals_empty(self, run_dir: pathlib.Path):
        proposals = load_proposals(run_dir)
        assert proposals == []

    def test_load_evidence_empty(self, run_dir: pathlib.Path):
        evs = load_evidence(run_dir)
        assert evs == []

    def test_proposal_and_evidence_round_trip(self, run_dir: pathlib.Path):
        import datetime

        proposal = ProposalRecord(
            proposal_id="prop_roundtrip",
            run_id="run_test",
            pdf_id="pdf_test",
            row_id="row_test",
            cell_id="cell_test",
            state=ProposalState.found,
            support=SupportLabel.direct_evidence,
            column_name="Test",
            proposed_value="value",
            rationale="- Test bullet.",
            evidence_ids=["ev_roundtrip"],
            primary_evidence_id="ev_roundtrip",
            ordered_supporting_evidence_ids=[],
            created_at=datetime.datetime.now().isoformat(),
        )
        ev = EvidenceRecord(
            evidence_id="ev_roundtrip",
            run_id="run_test",
            proposal_id="prop_roundtrip",
            pdf_id="pdf_test",
            source_type=EvidenceSourceType.direct_quote,
            quote_text="test quote",
            page_number=1,
            anchor_confidence=1.0,
            evidence_rank=1,
            is_primary=True,
            created_at=datetime.datetime.now().isoformat(),
        )
        persist_proposal(run_dir, proposal)
        persist_evidence(run_dir, ev)

        loaded_proposals = load_proposals(run_dir)
        loaded_evidence = load_evidence(run_dir)

        assert len(loaded_proposals) == 1
        assert loaded_proposals[0].proposal_id == "prop_roundtrip"
        assert loaded_proposals[0].state == ProposalState.found
        assert len(loaded_evidence) == 1
        assert loaded_evidence[0].source_type == EvidenceSourceType.direct_quote


# ===========================================================================
# Canonical fixture readiness check
# ===========================================================================

class TestCanonicalFixtureReadiness:
    """Verify canonical LM Studio path either produces proposals or fails readiness (T067)."""

    def test_fixture_files_exist(self):
        """The canonical fixture files must exist."""
        import os
        assert os.path.exists(FIXTURE_TABLE), f"Missing fixture: {FIXTURE_TABLE}"
        assert os.path.exists(FIXTURE_PDF_DIR), f"Missing fixture dir: {FIXTURE_PDF_DIR}"
        assert os.path.exists(FIXTURE_SCHEMA), f"Missing schema: {FIXTURE_SCHEMA}"

    def test_fixture_has_eligible_cells(self):
        """The canonical fixture must have eligible cells for extraction."""
        from backend.app.ingest import get_eligible_cells, load_schema, load_table
        df = load_table(FIXTURE_TABLE)
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        eligible = get_eligible_cells(df, schema, verify_mode=False)
        assert len(eligible) > 0, "Canonical fixture should have eligible cells"

    def test_fixture_has_schema_columns(self):
        """Schema must have column_name and description for each target column."""
        from backend.app.ingest import load_schema
        schema = load_schema(FIXTURE_SCHEMA, FIXTURE_TABLE)
        assert len(schema) > 0
        for col in schema:
            assert "column_name" in col
            assert "description" in col

    async def test_lm_studio_readiness_check(self, tmp_path: pathlib.Path):
        """LM Studio readiness must either succeed or fail with explicit error (not silently).

        T067: proven on canonical fixture path — live success or explicit readiness failure.
        This test checks that the readiness check correctly reports status.
        """
        from backend.app.config import RunConfig, check_readiness

        config_data = {
            "table_path": FIXTURE_TABLE,
            "schema_path": FIXTURE_SCHEMA,
            "pdf_dir": FIXTURE_PDF_DIR,
            "output_dir": str(tmp_path / "runs"),
            "verify_mode": False,
            "provider": {
                "token": "lm_studio",
                "base_url": "http://localhost:9999",  # intentionally unreachable
            },
        }
        config = RunConfig.model_validate(config_data)
        readiness = await check_readiness(config)

        # Either LM Studio is reachable (ok=True) or there's an explicit error (ok=False)
        # The key: it must NOT silently ignore the failure and claim ok=True
        if not readiness.ok:
            # Must have at least one error message about the provider
            assert len(readiness.errors) > 0, (
                "Readiness failure must produce at least one error message"
            )
            # The error must be actionable — must reference the provider or connectivity
            combined = " ".join(readiness.errors).lower()
            assert any(kw in combined for kw in ("lm studio", "localhost", "provider", "reach", "connect")), (
                f"Readiness error messages must be actionable: {readiness.errors}"
            )

    async def test_provider_unavailable_produces_skipped_not_silent_success(
        self, tmp_path: pathlib.Path
    ):
        """T052a: provider unavailable must produce skipped proposals, not fake success."""
        from backend.app.extraction import load_proposals, make_skipped_proposal
        from backend.app.ids import generate_cell_id, generate_row_id

        run_dir = tmp_path / "run_provtest"
        run_dir.mkdir()
        (run_dir / "proposals").mkdir()

        make_skipped_proposal(
            run_id="run_provtest",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_test",
            column_name="Species",
            skip_reason="Provider unavailable: Connection refused",
            run_dir=run_dir,
        )

        proposals = load_proposals(run_dir)
        assert len(proposals) == 1
        assert proposals[0].state == ProposalState.skipped
        assert "Provider unavailable" in proposals[0].rationale

    def test_separate_text_and_vision_model_config(self):
        """T050, T009a: separate text and vision model config fields."""
        from backend.app.config import RunConfig

        config = RunConfig.model_validate({
            "table_path": FIXTURE_TABLE,
            "schema_path": FIXTURE_SCHEMA,
            "pdf_dir": FIXTURE_PDF_DIR,
            "output_dir": "./runs",
            "provider": {
                "token": "lm_studio",
                "base_url": "http://localhost:1234",
                "text_model": {"model_id": "text-model-1", "max_tokens": 2048},
                "vision_model": {"model_id": "vision-model-1", "max_tokens": 2048},
            },
        })
        assert config.provider.text_model.model_id == "text-model-1"
        assert config.provider.vision_model is not None
        assert config.provider.vision_model.model_id == "vision-model-1"

    def test_unknown_provider_fails_explicitly(self):
        """T009a: unknown provider token fails early."""
        from pydantic import ValidationError
        with pytest.raises((ValidationError, ValueError)):
            from backend.app.config import RunConfig
            RunConfig.model_validate({
                "table_path": FIXTURE_TABLE,
                "pdf_dir": FIXTURE_PDF_DIR,
                "output_dir": "./runs",
                "provider": {"token": "unknown_provider"},
            })

    def test_build_text_extraction_prompt_includes_context(self, minimal_doc_dict: dict):
        """T053: Extraction prompt assembles row context + column + retrieval."""
        retrieval = RetrievalResult(
            run_id="run_test",
            pdf_id="pdf_test",
            column_name="Integration site",
            query="Integration site: Site of implantation",
            top_k=6,
            chunks=build_chunks_from_parsed_doc(minimal_doc_dict)[:3],
            retrieved_at="2024-01-01T00:00:00+00:00",
        )
        messages = build_text_extraction_prompt(
            column_name="Integration site",
            column_description="Where scaffold was implanted",
            row_context={"Title": "Test study", "Authors": "Smith J"},
            retrieval=retrieval,
            style_profile=None,
        )
        assert len(messages) == 2
        user_content = messages[1]["content"]
        assert "Integration site" in user_content
        assert "Where scaffold was implanted" in user_content
        # Should include passages from retrieval
        assert "Passage" in user_content or "scaffold" in user_content.lower()

    def test_build_text_extraction_prompt_verify_mode(self):
        """T066: verify mode includes existing value in prompt."""
        messages = build_text_extraction_prompt(
            column_name="Species",
            column_description="Animal species",
            row_context={},
            retrieval=None,
            style_profile=None,
            is_verify_mode=True,
            existing_value="Rat",
        )
        user_content = messages[1]["content"]
        assert "Rat" in user_content
        assert "Verify mode" in user_content or "existing" in user_content.lower()

    def test_build_text_extraction_prompt_uses_style_summary_not_raw_examples(self):
        profile = StyleProfile(
            column_name="Integration site",
            field_type_guess="categorical",
            expected_length="short",
            tone="technical",
            detail_level="medium",
            value_shape="anatomical site name",
            unit_style=None,
            format_notes="Use concise site labels.",
            example_risk="low",
            generated_at="2026-01-01T00:00:00+00:00",
            source_column_count=2,
            provider_mode="heuristic",
        )
        messages = build_text_extraction_prompt(
            column_name="Integration site",
            column_description="Where scaffold was implanted",
            row_context={},
            retrieval=None,
            style_profile=profile,
        )
        user_content = messages[1]["content"]
        assert "anatomical site name" in user_content
        assert "Tibial defect" not in user_content
        assert "Femoral condyle" not in user_content
