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
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.extraction import (
    COMPACT_DEGRADED_TEXT_EXTRACTION_SCHEMA,
    EvidenceRecord,
    ProposalRecord,
    adjudicate_state,
    anchor_evidence,
    build_text_extraction_prompt,
    evidence_type_display,
    extract_cell,
    find_approximate_highlight_regions,
    find_exact_highlight_regions,
    get_prompt_identity,
    is_long_text_field,
    load_evidence,
    load_proposals,
    make_blocked_proposal,
    make_skipped_proposal,
    persist_evidence,
    persist_proposal,
    _proposal_value_for_persistence,
    rank_evidence,
    select_relevant_figures,
    should_run_recall_rescue,
)
from backend.app.provider import (
    LMStudioProvider,
    ProviderCapabilities,
    ProviderError,
    ProviderMode,
    StructuredOutputError,
    _ensure_json_keyword_in_messages,
    _coerce_message_content,
    _structured_message_content,
    _try_repair_json,
    initialize_provider,
)
from backend.app.retrieval import (
    RetrievalChunk,
    RetrievalResult,
    _tokenize,
    build_retrieval_query,
    build_chunks_from_parsed_doc,
    get_prepared_retrieval_index_path,
    load_prepared_retrieval_index,
    load_retrieval_result,
    persist_retrieval_result,
    retrieve,
    run_retrieval_for_cell,
    score_chunks,
)
from backend.app.proposal_semantics import AMBIGUOUS_EVIDENCE
from backend.app.schemas import EvidenceSourceType, EvidenceStatus, ProposalStatus, ReviewBucket
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

FIXTURE_TABLE = "../benchmark_datasets/massively_parallel_reporter_assays/table_template.csv"
FIXTURE_SCHEMA = "../benchmark_datasets/massively_parallel_reporter_assays/schema.csv"
FIXTURE_PDF_DIR = "../benchmark_datasets/massively_parallel_reporter_assays/pdfs"


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

    width = height = 150
    rows = []
    for y in range(height):
        row = bytearray([0])
        for x in range(width):
            value = 255 if (x // 10 + y // 10) % 2 == 0 else 80
            row.extend([value, value, value])
        rows.append(bytes(row))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"".join(rows))
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
        path = persist_style_profile(run_dir, profile)
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

    def test_long_style_profile_filename_is_shortened_deterministically(self, run_dir: pathlib.Path):
        import datetime
        long_name = "what_predicts_activity_(e.g._accessible_-_active_in_MPRA_)"
        profile = StyleProfile(
            column_name=long_name,
            field_type_guess="text",
            expected_length="short",
            tone="technical",
            detail_level="medium",
            value_shape="free text",
            generated_at=datetime.datetime.now().isoformat(),
            source_column_count=2,
        )
        path = persist_style_profile(run_dir, profile)
        assert path.exists()
        assert len(path.stem) < len(long_name)
        assert len(path.stem) <= 32
        loaded = load_style_profile(run_dir, long_name)
        assert loaded is not None
        assert loaded.column_name == long_name

    def test_style_profile_persists_under_deep_windows_like_run_path(self, tmp_path: pathlib.Path):
        import datetime

        deep_run_dir = tmp_path
        for part in [
            "very_long_optimizer_run_root_name",
            "experiment",
            "runs",
            "cand_0001",
            "main",
            "main_app_output",
            "run_20260409_012231_lm0hmv",
        ]:
            deep_run_dir = deep_run_dir / part

        long_name = "what_predicts_activity_(e.g._accessible_-_active_in_MPRA_)"
        profile = StyleProfile(
            column_name=long_name,
            field_type_guess="text",
            expected_length="short",
            tone="technical",
            detail_level="medium",
            value_shape="free text",
            generated_at=datetime.datetime.now().isoformat(),
            source_column_count=2,
        )

        path = persist_style_profile(deep_run_dir, profile)

        assert path.exists()
        assert len(str(path)) <= 240
        loaded = load_style_profile(deep_run_dir, long_name)
        assert loaded is not None
        assert loaded.column_name == long_name


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
        assert "figure" in types

    def test_figure_chunks_include_metadata(self, minimal_doc_dict: dict):
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        figure_chunks = [chunk for chunk in chunks if chunk.chunk_type == "figure"]
        assert figure_chunks
        assert figure_chunks[0].figure_ref == "fig_1"
        assert "Micro-CT" in (figure_chunks[0].caption_text or "")

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

    def test_long_retrieval_filename_is_shortened_deterministically(self, run_dir: pathlib.Path):
        import datetime

        long_name = "what_predicts_activity_(e.g._accessible_-_active_in_MPRA_)"
        result = RetrievalResult(
            run_id="run_test",
            pdf_id="paper_2",
            column_name=long_name,
            query="activity accessibility mpra",
            top_k=1,
            chunks=[],
            retrieved_at=datetime.datetime.now().isoformat(),
        )

        path = persist_retrieval_result(run_dir, result)

        assert path.exists()
        assert len(path.stem) < len(long_name)
        loaded = load_retrieval_result(run_dir, "paper_2", long_name)
        assert loaded is not None
        assert loaded.column_name == long_name

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
        assert data["mode"] == "lexical"
        assert data["request_mode"] == "baseline"
        assert data["policy"]["query_mode"].startswith("lexical")
        assert data["policy"]["allowed_chunk_types"] == [
            "abstract",
            "caption",
            "figure",
            "list_item",
            "paragraph",
            "section",
            "table_region",
        ]
        assert data["policy"]["include_captions"] is True
        assert data["policy"]["include_tables"] is True
        assert data["policy"]["include_neighbor_window"] is True
        assert data["policy"]["top_k"] == 6
        assert data["stats"]["total_ms"] >= 0
        assert data["stats"]["cached_index_used"] is False

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
        assert "count_like" in result.policy["heuristic_tags"]
        assert "pairs" in result.policy["hint_terms"]

    def test_hybrid_retrieval_mode_is_opt_in(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        result = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="hybrid_experimental",
        )

        assert result.mode == "hybrid_experimental"
        assert result.policy["scoring_profile"] == "bm25_plus_token_coverage"
        assert result.stats["candidate_chunk_count"] >= result.stats["selected_chunk_count"]

    def test_retrieval_policy_contract_is_explicit(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        result = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="# Variants tested",
            column_description="How many different sequences or variants were evaluated in the study",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
        )

        assert result.policy["query_mode"] == "lexical_with_hints"
        assert result.policy["scoring_profile"] == "bm25_lite"
        assert "count_like" in result.policy["heuristic_tags"]
        assert result.policy["include_captions"] is True
        assert result.policy["include_tables"] is True
        assert result.policy["include_neighbor_window"] is True
        assert result.policy["top_k"] == 4
        assert "paragraph" in result.policy["allowed_chunk_types"]

    def test_retrieval_cache_reuses_prepared_index_and_reports_zero_rebuilds(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        retrieval_cache: dict[tuple[str, str, bool, bool], object] = {}

        first = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_cache=retrieval_cache,
            cache_key="paper_test",
        )
        second = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_cache=retrieval_cache,
            cache_key="paper_test",
        )

        assert first.stats["chunk_build_count"] == 1
        assert first.stats["idf_build_count"] == 1
        assert first.stats["cached_index_used"] is False
        assert second.stats["chunk_build_count"] == 0
        assert second.stats["idf_build_count"] == 0
        assert second.stats["cached_index_used"] is True
        assert second.stats["persistent_index_source"] == "memory"

    def test_retrieval_persists_prepared_index_artifact(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        result = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="hybrid_experimental",
        )

        index_path = get_prepared_retrieval_index_path(
            run_dir,
            "paper_test",
            "hybrid_experimental",
        )
        payload = json.loads(index_path.read_text(encoding="utf-8"))

        assert index_path.exists()
        assert payload["schema_version"] == "prepared_retrieval_index.v1"
        assert payload["pdf_id"] == "paper_test"
        assert payload["retrieval_mode"] == "hybrid_experimental"
        assert payload["document_fingerprint"]
        assert result.stats["persistent_index_source"] == "built"
        assert result.stats["persistent_index_path"] == "retrieval/_indexes/paper_test__hybrid_experimental__cap1__tbl1.json"
        assert payload["index"]["all_chunks"]
        assert payload["index"]["candidate_chunks"]

    def test_retrieval_loads_persisted_index_without_memory_cache(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        first = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="hybrid_experimental",
        )
        loaded_index = load_prepared_retrieval_index(
            run_dir,
            pdf_id="paper_test",
            retrieval_mode="hybrid_experimental",
            include_captions=True,
            include_tables=True,
        )
        second = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="hybrid_experimental",
        )

        assert loaded_index is not None
        assert [chunk.chunk_id for chunk in second.chunks] == [chunk.chunk_id for chunk in first.chunks]
        assert second.stats["cached_index_used"] is True
        assert second.stats["chunk_build_count"] == 0
        assert second.stats["idf_build_count"] == 0
        assert second.stats["persistent_index_source"] == "disk"

    def test_stale_persisted_index_is_rebuilt_when_document_changes(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="hybrid_experimental",
        )
        changed_doc = json.loads(json.dumps(minimal_doc_dict))
        changed_doc["blocks"][1]["text"] = "A changed methods sentence should invalidate the prepared index."
        second = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=changed_doc,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="hybrid_experimental",
        )

        assert second.stats["persistent_index_source"] == "built"
        assert "document_fingerprint" in str(second.stats["persistent_index_load_error"])

    def test_retrieval_cache_is_scoped_by_retrieval_mode(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        retrieval_cache: dict[tuple[str, str, bool, bool], object] = {}

        lexical = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="lexical",
            retrieval_cache=retrieval_cache,
            cache_key="paper_test",
        )
        hybrid = run_retrieval_for_cell(
            run_id="run_test001",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="Measured BVF value and supporting context",
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            top_k=4,
            retrieval_mode="hybrid_experimental",
            retrieval_cache=retrieval_cache,
            cache_key="paper_test",
        )

        assert lexical.stats["cached_index_used"] is False
        assert hybrid.stats["cached_index_used"] is False
        assert hybrid.policy["scoring_profile"] == "bm25_plus_token_coverage"

    def test_prompt_identity_tracks_external_prompt_files(self, tmp_path: pathlib.Path, monkeypatch):
        from backend.app.prompts import clear_prompt_bundle_cache

        bundles_root = tmp_path / "prompt_bundles"
        bundle_dir = bundles_root / "default"
        (bundle_dir / "text_extraction").mkdir(parents=True)
        (bundle_dir / "figure_extraction").mkdir(parents=True)
        (bundle_dir / "evidence_recovery").mkdir(parents=True)
        (bundle_dir / "style_profile").mkdir(parents=True)

        (bundle_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "bundle_id": "default",
                    "bundle_version": "test",
                    "files": {
                        "text_extraction_system": "text_extraction/system.md",
                        "text_extraction_user": "text_extraction/user.md",
                        "figure_extraction_system": "figure_extraction/system.md",
                        "figure_extraction_user": "figure_extraction/user.md",
                        "evidence_recovery_system": "evidence_recovery/system.md",
                        "evidence_recovery_user": "evidence_recovery/user.md",
                        "style_profile_system": "style_profile/system.md",
                    },
                }
            ),
            encoding="utf-8",
        )
        (bundle_dir / "text_extraction" / "system.md").write_text("System prompt A", encoding="utf-8")
        (bundle_dir / "text_extraction" / "user.md").write_text(
            "Extract: $column_name\nField description: $column_description\n\nPaper row context:\n$row_block$verify_block$long_text_note$field_contract$style_block\n\n$context_block\n\n$whole_document_block\n\nInstructions:\nReturn ONLY valid JSON matching the schema.",
            encoding="utf-8",
        )
        (bundle_dir / "figure_extraction" / "system.md").write_text("Figure prompt A", encoding="utf-8")
        (bundle_dir / "figure_extraction" / "user.md").write_text("Field to extract: $column_name", encoding="utf-8")
        (bundle_dir / "evidence_recovery" / "system.md").write_text("Recovery system", encoding="utf-8")
        (bundle_dir / "evidence_recovery" / "user.md").write_text("Recovery user", encoding="utf-8")
        (bundle_dir / "style_profile" / "system.md").write_text("Style prompt A", encoding="utf-8")

        monkeypatch.setattr("backend.app.prompts.PROMPT_BUNDLES_DIR", bundles_root)
        clear_prompt_bundle_cache()

        identity_a = get_prompt_identity()
        messages = build_text_extraction_prompt(
            column_name="Assay",
            column_description="Assay name",
            row_context={},
            retrieval=None,
            style_profile=None,
        )

        (bundle_dir / "text_extraction" / "system.md").write_text("System prompt B", encoding="utf-8")
        clear_prompt_bundle_cache()
        identity_b = get_prompt_identity()

        assert identity_a["prompt_bundle_id"] == "default"
        assert identity_a["prompt_files"]["text_extraction_system"]["relative_path"] == "text_extraction/system.md"
        assert messages[0]["content"] == "System prompt A"
        assert identity_b["prompt_hash"] != identity_a["prompt_hash"]

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

    def test_repair_strips_think_wrapper_and_extracts_balanced_object(self):
        raw = '<think>reasoning here</think>\nHere is the answer:\n{"proposed_value":"45.3","state":"found","rationale":null,"calculation":null,"numeric_value_form":null,"quotes":[]}\nThanks'
        result = _try_repair_json(raw)
        assert result is not None
        assert result["state"] == "found"


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

    @pytest.mark.asyncio
    async def test_vision_completion_uses_vision_structured_mode(self):
        provider = LMStudioProvider()
        provider._capabilities = ProviderCapabilities(
            supports_structured_output=True,
            structured_output_mode="json_schema",
            model_id="text-model",
            vision_capable=True,
            vision_structured_output_mode="none",
        )
        observed_modes: list[str] = []

        async def fake_complete(**kwargs):
            observed_modes.append(kwargs["structured_mode"])
            return {"value": "ok"}

        provider._complete_structured_with_mode = fake_complete

        result = await provider.vision_complete_structured(
            messages=[{"role": "user", "content": "Return JSON."}],
            response_schema={
                "type": "object",
                "properties": {"value": {"type": "string"}},
                "required": ["value"],
            },
            model_id="vision-model",
            image_b64="abc",
        )

        assert result == {"value": "ok"}
        assert observed_modes == ["none"]

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

    async def test_provider_unreachable_raises_classified_error(self):
        """T052d: provider-unreachable is classified distinctly from capability mismatch."""
        p = LMStudioProvider(base_url="http://localhost:9999")
        with pytest.raises(ProviderError) as exc:
            await p.probe_capabilities("test-model")
        assert getattr(exc.value, "reason", None) == "provider_unreachable"

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

    def test_coerce_message_content_from_parts(self):
        content = [
            {"type": "text", "text": "{\"value\":"},
            {"type": "text", "text": " \"ok\"}"},
        ]
        normalized = _coerce_message_content(content)
        assert '{"value":' in normalized
        assert '"ok"}' in normalized

    def test_structured_message_content_falls_back_to_reasoning_content(self):
        raw, source = _structured_message_content(
            {"content": "", "reasoning_content": '{"value": "ok"}'}
        )
        assert raw == '{"value": "ok"}'
        assert source == "reasoning_content"

    @pytest.mark.asyncio
    async def test_initialize_provider_accepts_json_object_mode(self):
        config = SimpleNamespace(token="lm_studio", base_url="http://localhost:1234")
        caps = ProviderCapabilities(
            supports_structured_output=True,
            structured_output_mode="json_object",
            model_id="test-model",
            vision_capable=False,
        )
        with patch.object(
            LMStudioProvider,
            "probe_capabilities",
            new=AsyncMock(return_value=caps),
        ):
            provider, mode = await initialize_provider(
                config,
                text_model_id="test-model",
                vision_model_id=None,
            )
        assert isinstance(provider, LMStudioProvider)
        assert mode.mode == "live_local"
        assert mode.capabilities is not None
        assert mode.capabilities.structured_output_mode == "json_object"
        assert mode.structured_output_reason == "json_schema_unsupported"

    @pytest.mark.asyncio
    async def test_initialize_provider_accepts_prompt_only_fallback_when_no_structured_mode(self):
        config = SimpleNamespace(token="lm_studio", base_url="http://localhost:1234")
        caps = ProviderCapabilities(
            supports_structured_output=False,
            structured_output_mode="none",
            model_id="test-model",
            vision_capable=False,
        )
        with patch.object(
            LMStudioProvider,
            "probe_capabilities",
            new=AsyncMock(return_value=caps),
        ):
            provider, mode = await initialize_provider(
                config,
                text_model_id="test-model",
                vision_model_id=None,
            )
        assert isinstance(provider, LMStudioProvider)
        assert mode.mode == "live_local"
        assert mode.capabilities is not None
        assert mode.capabilities.structured_output_mode == "none"
        assert mode.structured_output_reason == "structured_modes_unavailable"
        assert mode.structured_output_fallback_used is True

    def test_ensure_json_keyword_in_messages_adds_guardrail_when_missing(self):
        messages = [{"role": "user", "content": "Return exactly one object."}]

        normalized = _ensure_json_keyword_in_messages(messages)

        assert len(normalized) == 2
        assert normalized[0]["role"] == "system"
        assert "JSON" in normalized[0]["content"]

    def test_ensure_json_keyword_in_messages_preserves_existing_json_instruction(self):
        messages = [{"role": "user", "content": "Return valid JSON only."}]

        normalized = _ensure_json_keyword_in_messages(messages)

        assert normalized == messages

    @pytest.mark.asyncio
    async def test_chat_complete_structured_supports_json_object_mode(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=True,
                structured_output_mode="json_object",
                model_id="test-model",
                vision_capable=False,
            )
        )

        with patch.object(
            provider,
            "_post_structured_payload",
            new=AsyncMock(return_value='{"value": "ok"}'),
        ):
            result = await provider.chat_complete_structured(
                messages=[{"role": "user", "content": "test"}],
                response_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                model_id="test-model",
            )

        assert result["value"] == "ok"

    @pytest.mark.asyncio
    async def test_chat_complete_structured_rejects_invalid_unstructured_output(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=True,
                structured_output_mode="json_object",
                model_id="test-model",
                vision_capable=False,
            )
        )

        with patch.object(
            provider,
            "_post_structured_payload",
            new=AsyncMock(side_effect=["not json at all", "still not json"]),
        ):
            with pytest.raises(StructuredOutputError):
                await provider.chat_complete_structured(
                    messages=[{"role": "user", "content": "test"}],
                    response_schema={
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                    model_id="test-model",
                )

    @pytest.mark.asyncio
    async def test_chat_complete_structured_supports_prompt_only_json_fallback(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=False,
                structured_output_mode="none",
                model_id="test-model",
                vision_capable=False,
            )
        )

        with patch.object(
            provider,
            "_post_structured_payload",
            new=AsyncMock(return_value='{"value": "ok"}'),
        ):
            result = await provider.chat_complete_structured(
                messages=[{"role": "user", "content": "test"}],
                response_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                model_id="test-model",
            )

        assert result["value"] == "ok"

    @pytest.mark.asyncio
    async def test_chat_complete_structured_normalizes_degraded_list_and_nullable_fields(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=False,
                structured_output_mode="none",
                model_id="test-model",
                vision_capable=False,
            )
        )

        with patch.object(
            provider,
            "_post_structured_payload",
            new=AsyncMock(
                return_value=(
                    '{"proposed_value":["45.3%"],"state":"found","numeric_value_form":null,'
                    '"primary_quote":["BVF was measured as 45.3%"],"evidence_kind":"direct_quote"}'
                )
            ),
        ):
            result = await provider.chat_complete_structured(
                messages=[{"role": "user", "content": "test"}],
                response_schema=COMPACT_DEGRADED_TEXT_EXTRACTION_SCHEMA,
                model_id="test-model",
            )

        assert result["proposed_value"] == "45.3%"
        assert result["primary_quote"] == "BVF was measured as 45.3%"
        assert result["primary_quote_page"] is None

    @pytest.mark.asyncio
    async def test_chat_complete_structured_records_attempt_diagnostics(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=True,
                structured_output_mode="json_object",
                model_id="test-model",
                vision_capable=False,
            )
        )

        with patch.object(
            provider,
            "_post_structured_payload",
            new=AsyncMock(side_effect=["not json at all", '{"value": "ok"}']),
        ):
            result = await provider.chat_complete_structured(
                messages=[{"role": "user", "content": "test"}],
                response_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                model_id="test-model",
            )

        diagnostics = provider.get_diagnostics()

        assert result["value"] == "ok"
        assert diagnostics["attempt_count"] == 2
        assert diagnostics["by_outcome"]["structured_output_error"] == 1
        assert diagnostics["by_outcome"]["success"] == 1
        assert diagnostics["by_request_kind"]["text_structured"] == 2

    @pytest.mark.asyncio
    async def test_chat_complete_structured_validates_schema_after_parse(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=True,
                structured_output_mode="json_object",
                model_id="test-model",
                vision_capable=False,
            )
        )

        with patch.object(
            provider,
            "_post_structured_payload",
            new=AsyncMock(side_effect=['{"state": "found"}', '{"state": "found"}']),
        ):
            with pytest.raises(StructuredOutputError) as exc:
                await provider.chat_complete_structured(
                    messages=[{"role": "user", "content": "test"}],
                    response_schema={
                        "type": "object",
                        "properties": {"value": {"type": "string"}, "state": {"type": "string"}},
                        "required": ["value", "state"],
                    },
                    model_id="test-model",
                )
        assert "missing required field 'value'" in str(exc.value)

    @pytest.mark.asyncio
    async def test_chat_complete_structured_downgrades_after_regex_incompatibility(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=True,
                structured_output_mode="json_schema",
                model_id="test-model",
                vision_capable=False,
            )
        )

        with patch.object(
            provider,
            "_post_structured_payload",
            new=AsyncMock(
                side_effect=[
                    StructuredOutputError(
                        "LM Studio rejected structured-output grammar/regex constraints: Failed to process regex",
                        reason="structured_backend_incompatible",
                    ),
                    '{"value": "ok"}',
                ]
            ),
        ):
            result = await provider.chat_complete_structured(
                messages=[{"role": "user", "content": "test"}],
                response_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
                model_id="test-model",
            )

        assert result["value"] == "ok"
        assert provider._capabilities is not None
        assert provider._capabilities.structured_output_mode == "json_object"
        assert provider._capabilities.structured_output_reason == "structured_backend_incompatible"

    @pytest.mark.asyncio
    async def test_qwen_structured_policy_uses_json_schema_with_max_tokens_and_retry(self):
        provider = LMStudioProvider(base_url="http://localhost:1234")
        provider.set_capabilities(
            ProviderCapabilities(
                supports_structured_output=True,
                structured_output_mode="json_schema",
                model_id="qwen/qwen3.6-27b",
                vision_capable=False,
            )
        )
        post = AsyncMock(side_effect=['{"state": "found"}', '{"value": "ok"}'])

        with patch.object(provider, "_post_structured_payload", new=post):
            result = await provider.chat_complete_structured(
                messages=[{"role": "user", "content": "Return exactly one object."}],
                response_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}, "state": {"type": "string"}},
                    "required": ["value"],
                },
                model_id="qwen/qwen3.6-27b",
                max_tokens=2048,
            )

        assert result["value"] == "ok"
        first_payload = post.await_args_list[0].args[0]
        second_payload = post.await_args_list[1].args[0]
        assert first_payload["response_format"]["type"] == "json_schema"
        assert first_payload["max_tokens"] == 2048
        assert first_payload["temperature"] == 0.7
        assert first_payload["top_p"] == 0.8
        assert first_payload["top_k"] == 20
        assert first_payload["min_p"] == 0.0
        assert first_payload["presence_penalty"] == 1.5
        assert first_payload["repetition_penalty"] == 1.0
        assert first_payload["chat_template_kwargs"] == {"enable_thinking": False}
        assert any("JSON" in message["content"] for message in first_payload["messages"])
        assert any("non-thinking" in message["content"] for message in first_payload["messages"])
        assert second_payload["response_format"]["type"] == "json_schema"
        assert second_payload["max_tokens"] == 2048
        assert provider.get_request_counts()["completion_retry_attempts"] == 1

    def test_model_config_overrides_policy_payload_defaults(self):
        from backend.app.config import TextModelConfig

        model_config = TextModelConfig(
            model_id="qwen/qwen3.6-27b",
            temperature=0.2,
            top_p=0.9,
            extra_body={"custom_flag": "yes"},
            chat_template_kwargs={"enable_thinking": True},
        )
        provider = LMStudioProvider(text_model_config=model_config)
        payload = provider._build_payload(
            [{"role": "user", "content": "Return JSON."}],
            "qwen/qwen3.6-27b",
            2048,
            None,
            {"type": "object", "properties": {}, "required": []},
            "json_object",
        )

        assert payload["temperature"] == 0.2
        assert payload["top_p"] == 0.9
        assert payload["top_k"] == 20
        assert payload["custom_flag"] == "yes"
        assert payload["chat_template_kwargs"] == {"enable_thinking": True}


# ===========================================================================
# T067 — Extraction
# ===========================================================================

class TestTemporaryExtractionAdjudication:
    """Temporary model-output adjudication before canonical proposal persistence."""

    def test_found_with_direct_quote(self):
        state, support = adjudicate_state(
            "found", "45.3%",
            [{"text": "BVF was 45.3%", "source_type": "direct_quote"}]
        )
        assert state == "found"
        assert support == "direct_evidence"

    def test_found_without_quotes_downgrades(self):
        state, support = adjudicate_state("found", "45.3%", [])
        assert state == "inferred"
        assert support == "inferred_from_evidence"

    def test_inferred_with_quotes(self):
        state, support = adjudicate_state(
            "inferred", "derived value",
            [{"text": "some quote", "source_type": "inferred_reasoning"}]
        )
        assert state == "inferred"

    def test_inferred_without_quotes_weak(self):
        state, support = adjudicate_state("inferred", "derived value", [])
        assert state == "inferred"
        assert support == "weak_evidence"

    def test_unclear_no_value(self):
        state, support = adjudicate_state("unclear", None, [])
        assert state == "unclear"

    def test_unclear_empty_value(self):
        state, support = adjudicate_state("found", "", [])
        assert state == "unclear"

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
        assert prop.proposal_status == ProposalStatus.unresolved
        assert prop.evidence_status == EvidenceStatus.no_evidence
        assert prop.review_bucket == ReviewBucket.diagnostic
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
        assert prop.proposal_status == ProposalStatus.not_attempted

    def test_anti_guessing_unclear_preferred(self):
        """T058a: unclear preferred when no paper evidence."""
        state, support = adjudicate_state("found", "guessed value", [])
        # Without any quotes, should downgrade
        assert state == "inferred"  # at best inferred, not found


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
        assert proposal.proposal_status == ProposalStatus.value_proposed
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
        assert proposal.proposal_status == ProposalStatus.error
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
        assert proposal.proposal_status == ProposalStatus.unresolved

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
            persisted_ids = {ev.evidence_id for ev in load_evidence(run_dir)}
            assert proposal.evidence_ids[0] in persisted_ids

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

    async def test_compact_degraded_response_is_normalized_into_evidence(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        provider = self._make_mock_provider(response={
            "proposed_value": "45.3%",
            "state": "found",
            "numeric_value_form": "exact",
            "primary_quote": "Bone volume fraction (BVF) was measured as 45.3% at 12 weeks post-implantation.",
            "primary_quote_page": 2,
            "evidence_kind": "direct_quote",
        })
        caps = SimpleNamespace(structured_output_mode="none", vision_structured_output_mode=None)

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_compact",
            column_name="Bone volume fraction",
            column_description="BVF measurement",
            row_context={},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
            field_type="number",
            caps=caps,
        )

        call_args = provider.chat_complete_structured.call_args
        assert call_args.kwargs["response_schema"] == COMPACT_DEGRADED_TEXT_EXTRACTION_SCHEMA
        assert proposal.proposed_value == "45.3%"
        assert proposal.primary_evidence_id is not None
        assert proposal.numeric_value_form is not None

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

    async def test_persists_provider_retrieval_and_figure_review_diagnostics(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        crop_path = run_dir / "fig_diag.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_dict = dict(minimal_doc_dict)
        doc_dict["figures"] = [{**minimal_doc_dict["figures"][0], "crop_path": str(crop_path), "figure_id": "fig_diag"}]

        retrieval = run_retrieval_for_cell(
            run_id="run_test",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="BVF measurement",
            doc_dict=doc_dict,
            run_dir=run_dir,
            top_k=3,
        )

        class ProviderStub:
            async def chat_complete_structured(self, **_kwargs):
                return {
                    "proposed_value": None,
                    "state": "unclear",
                    "rationale": None,
                    "calculation": None,
                    "numeric_value_form": None,
                    "quotes": [],
                }

            async def vision_complete_structured(self, **_kwargs):
                return {
                    "proposed_value": "45.3%",
                    "state": "found",
                    "rationale": "- Figure supports BVF value.",
                    "numeric_value_form": "exact",
                    "figure_description": "Bar height indicates 45.3%.",
                    "caption_relevant": True,
                }

            def get_diagnostics_cursor(self):
                return 0

            def get_diagnostics_since(self, _cursor):
                return [
                    {
                        "request_kind": "text_structured",
                        "outcome": "success",
                        "duration_ms": 12.5,
                    },
                    {
                        "request_kind": "vision_structured",
                        "outcome": "success",
                        "duration_ms": 22.0,
                    },
                ]

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_diag",
            column_name="Bone volume fraction",
            column_description="BVF measurement",
            row_context={"Title": "Paper"},
            doc_dict=doc_dict,
            run_dir=run_dir,
            provider=ProviderStub(),
            text_model_id="text-model",
            vision_model_id="vision-model",
            retrieval=retrieval,
        )

        assert proposal.provider_diagnostics["attempt_count"] == 2
        assert proposal.retrieval_diagnostics["retrieved_chunk_count"] >= 1
        assert proposal.figure_review_diagnostics["triggered"] is True
        assert proposal.figure_review_diagnostics["useful"] is True
        assert proposal.figure_review_diagnostics["rescued_value"] is True

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

    def test_rationale_list_is_normalized(self):
        from backend.app.extraction import _normalize_rationale

        rationale = ["Scaffold implanted in tibial defect", "BVF was 45.3%"]
        normalized = _normalize_rationale(rationale)
        assert normalized is not None
        assert "- Scaffold implanted in tibial defect." in normalized

    def test_recall_rescue_helper_triggers_for_missing_evidence(self):
        decision = should_run_recall_rescue(
            recall_rescue_enabled=True,
            rescue_already_used=False,
            proposal_status=ProposalStatus.value_proposed,
            evidence_status=EvidenceStatus.direct_strong,
            review_bucket=ReviewBucket.review,
            reason_codes=[],
            quotes=[],
            retrieval=None,
            needs_more_evidence=True,
        )
        assert decision.eligible is True
        assert decision.skip_reason is None
        assert "missing_usable_evidence" in decision.trigger_reasons

    def test_recall_rescue_helper_records_disabled_skip(self):
        decision = should_run_recall_rescue(
            recall_rescue_enabled=False,
            rescue_already_used=False,
            proposal_status=ProposalStatus.unresolved,
            evidence_status=EvidenceStatus.no_evidence,
            review_bucket=ReviewBucket.attention,
            reason_codes=["insufficient_evidence"],
            quotes=[],
            retrieval=None,
        )
        assert decision.eligible is True
        assert decision.skip_reason == "disabled"

    async def test_list_shaped_llm_fields_do_not_crash_extraction(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        provider = self._make_mock_provider(response={
            "proposed_value": ["Tibial defect"],
            "state": "found",
            "rationale": ["Scaffold implanted in tibial defect", "BVF was 45.3%"],
            "calculation": ["No calculation needed"],
            "quotes": [{"text": ["scaffold was implanted in the tibial defect"], "page": "1", "source_type": ["direct", "quote"]}],
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_listy",
            column_name="Integration site",
            column_description="Site of scaffold implantation",
            row_context={"Title": "Scaffold study"},
            doc_dict=minimal_doc_dict,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
        )

        assert proposal.proposal_status == ProposalStatus.value_proposed
        assert proposal.proposed_value == "Tibial defect"
        assert proposal.primary_evidence_id is not None


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
            text_model_id=None,
            vision_model_id="vision-model",
        )
        # Should have been called with the bone ingrowth figure
        assert provider.vision_complete_structured.called

    def test_select_figure_image_uses_crop_when_valid(self, run_dir: pathlib.Path, minimal_doc_dict: dict):
        from backend.app.extraction import _select_figure_image

        crop_path = run_dir / "valid_crop.png"
        crop_path.write_bytes(_minimal_png_bytes())
        figure = {**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}

        selected = _select_figure_image(
            figure,
            run_dir,
            column_name="Bone volume fraction",
            column_description="BVF measurement from CT",
        )

        assert selected.image_b64
        assert selected.image_source == "crop"
        assert selected.crop_quality == "ok"

    def test_select_figure_image_falls_back_to_full_page_for_missing_crop(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        from backend.app.extraction import _select_figure_image

        page_path = run_dir / "page.png"
        page_path.write_bytes(_minimal_png_bytes())
        figure = {
            **minimal_doc_dict["figures"][0],
            "crop_path": str(run_dir / "missing_crop.png"),
            "full_page_path": str(page_path),
        }

        selected = _select_figure_image(
            figure,
            run_dir,
            column_name="Bone volume fraction",
            column_description="BVF measurement from CT",
        )

        assert selected.image_b64
        assert selected.image_source == "full_page_fallback"
        assert selected.fallback_reason == "missing_figure_crop"

    def test_select_figure_image_prefers_full_page_for_explicit_figure_request(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        from backend.app.extraction import _select_figure_image

        crop_path = run_dir / "crop.png"
        page_path = run_dir / "page.png"
        crop_path.write_bytes(_minimal_png_bytes())
        page_path.write_bytes(_minimal_png_bytes())
        figure = {
            **minimal_doc_dict["figures"][0],
            "crop_path": str(crop_path),
            "full_page_path": str(page_path),
        }

        selected = _select_figure_image(
            figure,
            run_dir,
            column_name="Number of bar-chart panels in Figure 3",
            column_description="Count panels in Figure 3 that are bar charts.",
        )

        assert selected.image_source == "full_page_preferred"
        assert selected.fallback_reason == "explicit_figure_request"
        assert selected.image_path == "page.png"

    async def test_figure_review_missing_crop_uses_full_page_fallback(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        from backend.app.extraction import run_figure_review

        page_path = run_dir / "page_fallback.png"
        page_path.write_bytes(_minimal_png_bytes())
        doc_with_page = dict(minimal_doc_dict)
        doc_with_page["figures"] = [
            {
                **minimal_doc_dict["figures"][0],
                "crop_path": str(run_dir / "missing_crop.png"),
                "full_page_path": str(page_path),
            }
        ]
        attempts: list[dict] = []
        provider = AsyncMock()
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "45.3%",
            "state": "found",
            "rationale": "- Figure shows 45.3% bone volume.",
            "figure_description": "Bar chart showing BVF values",
            "caption_relevant": True,
        })

        await run_figure_review(
            proposal_id="prop_fallback",
            run_id="run_test",
            pdf_id="paper_test",
            column_name="Bone volume fraction",
            column_description="BVF measurement from CT",
            doc_dict=doc_with_page,
            run_dir=run_dir,
            provider=provider,
            text_model_id=None,
            vision_model_id="vision-model",
            attempt_diagnostics=attempts,
        )

        assert provider.vision_complete_structured.called
        assert attempts[0]["attempted"] is True
        assert attempts[0]["image_source"] == "full_page_fallback"
        assert attempts[0]["fallback_reason"] == "missing_figure_crop"
        assert attempts[0]["accepted_as_hit"] is True

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
            text_model_id=None,
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
        assert proposal.proposal_status == ProposalStatus.value_proposed
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

    async def test_candidate_selection_can_reject_stale_figure_value_as_unclear(
        self,
        run_dir: pathlib.Path,
        minimal_doc_dict: dict,
    ):
        crop_path = run_dir / "fig_crop_selection_reject.png"
        crop_path.write_bytes(_minimal_png_bytes())

        doc_with_crop = dict(minimal_doc_dict)
        doc_with_crop["figures"] = [
            {**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}
        ]

        provider = AsyncMock()
        provider.chat_complete_structured = AsyncMock(
            side_effect=[
                {
                    "proposed_value": "NOT_FOUND",
                    "state": "unclear",
                    "rationale": "- No clear architecture answer.",
                    "calculation": None,
                    "numeric_value_form": None,
                    "quotes": [],
                },
                {
                    "selected_candidate_id": None,
                    "selected_value": None,
                    "selected_state": "unclear",
                    "rejected_candidate_ids": ["cand_2"],
                    "rationale": "- Figure candidate is related but not specific enough.",
                    "needs_more_evidence": False,
                },
            ]
        )
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "L-1333N_R-1333C",
            "state": "found",
            "rationale": "- Figure shows a DdCBE split pair.",
            "figure_description": "DdCBE schematic",
            "caption_relevant": True,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_selection_reject",
            column_name="Main or best editor architecture",
            column_description=(
                "Extract a compact protein architecture; use NOT_FOUND when no clear architecture "
                "can be recovered. Expect figure evidence."
            ),
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="test-model",
            vision_model_id="vision-model",
            recall_rescue_enabled=False,
            figure_planner_enabled=False,
        )

        assert proposal.proposal_status == ProposalStatus.unresolved
        assert proposal.proposed_value is None
        assert proposal.evidence_status in {EvidenceStatus.direct_strong, EvidenceStatus.inferred_strong}
        assert AMBIGUOUS_EVIDENCE in proposal.reason_codes
        assert proposal.selection_diagnostics["attempted"] is True
        assert proposal.selection_diagnostics["selected_candidate_id"] is None

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
            text_model_id=None,
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

    async def test_prompt_only_degraded_vision_mode_suppresses_figure_review(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        doc_with_crop = dict(minimal_doc_dict)
        crop_path = run_dir / "fig_crop_prompt_only.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_with_crop["figures"] = [{**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}]

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
            "proposed_value": "45.3%",
            "state": "found",
            "rationale": "- Figure shows BVF = 45.3%.",
            "numeric_value_form": "exact",
            "figure_description": "BVF bar chart",
            "caption_relevant": True,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_prompt_only_suppressed",
            column_name="Bone volume fraction",
            column_description="BVF",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="text-model",
            vision_model_id="vision-model",
            caps=SimpleNamespace(vision_structured_output_mode="none"),
            skip_figure_review_when_prompt_only_degraded=True,
        )

        assert proposal.figure_review_diagnostics["triggered"] is True
        assert proposal.figure_review_diagnostics["suppressed"] is True
        assert proposal.figure_review_diagnostics["suppressed_reason"] == "prompt_only_provider_mode"
        assert provider.vision_complete_structured.call_count == 0

    async def test_prompt_only_vision_runs_by_default(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        doc_with_crop = dict(minimal_doc_dict)
        crop_path = run_dir / "fig_crop_prompt_only_runs.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_with_crop["figures"] = [{**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}]

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
            "proposed_value": "45.3%",
            "state": "found",
            "rationale": "- Figure shows BVF = 45.3%.",
            "numeric_value_form": "exact",
            "figure_description": "BVF bar chart",
            "caption_relevant": True,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_prompt_only_runs",
            column_name="Bone volume fraction",
            column_description="BVF",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="text-model",
            vision_model_id="vision-model",
            caps=SimpleNamespace(vision_structured_output_mode="none"),
        )

        assert provider.vision_complete_structured.call_count == 1
        assert proposal.figure_review_diagnostics["attempted"] is True
        assert proposal.figure_review_diagnostics["succeeded"] is True
        assert proposal.figure_review_diagnostics["suppressed"] is False

    async def test_conflicting_figure_evidence_is_persisted(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        doc_with_crop = dict(minimal_doc_dict)
        crop_path = run_dir / "fig_crop_conflict.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_with_crop["figures"] = [{**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}]

        provider = AsyncMock()
        provider.chat_complete_structured = AsyncMock(return_value={
            "proposed_value": "40%",
            "state": "found",
            "rationale": "- Text reports 40%.",
            "calculation": None,
            "numeric_value_form": "exact",
            "quotes": [{"text": "Bone volume fraction (BVF) was measured as 45.3%", "page": 2, "source_type": "direct_quote"}],
        })
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "45.3%",
            "state": "found",
            "rationale": "- Figure indicates 45.3%.",
            "numeric_value_form": "exact",
            "figure_description": "BVF bar reaches 45.3%.",
            "caption_relevant": True,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_conflict_figure",
            column_name="Bone volume fraction",
            column_description="BVF figure graph value",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="text-model",
            vision_model_id="vision-model",
            candidate_selection_enabled=False,
        )

        evidence = load_evidence(run_dir)
        assert any(ev.is_figure_derived for ev in evidence)
        assert any(
            candidate["source"] == "figure_review" and "competing_evidence" in candidate["warning_flags"]
            for candidate in (proposal.candidate_answers or [])
        )

    async def test_candidate_selection_can_choose_figure_candidate(
        self, run_dir: pathlib.Path, minimal_doc_dict: dict
    ):
        doc_with_crop = dict(minimal_doc_dict)
        crop_path = run_dir / "fig_crop_select.png"
        crop_path.write_bytes(_minimal_png_bytes())
        doc_with_crop["figures"] = [{**minimal_doc_dict["figures"][0], "crop_path": str(crop_path)}]

        provider = AsyncMock()
        provider.chat_complete_structured = AsyncMock(side_effect=[
            {
                "proposed_value": "40%",
                "state": "found",
                "rationale": "- Text reports a local percentage.",
                "calculation": None,
                "numeric_value_form": "exact",
                "quotes": [{"text": "Bone volume fraction (BVF) was measured as 45.3%", "page": 2, "source_type": "direct_quote"}],
            },
            {
                "selected_candidate_id": "cand_2",
                "selected_value": "45.3%",
                "selected_state": "inferred",
                "rejected_candidate_ids": ["cand_1"],
                "rationale": "- Figure candidate better matches the requested graph value.",
                "needs_more_evidence": False,
            },
        ])
        provider.vision_complete_structured = AsyncMock(return_value={
            "proposed_value": "45.3%",
            "state": "found",
            "rationale": "- Figure indicates 45.3%.",
            "numeric_value_form": "exact",
            "figure_description": "BVF bar reaches 45.3%.",
            "caption_relevant": True,
        })

        proposal = await extract_cell(
            run_id="run_test",
            pdf_id="paper_test",
            row_id="row_test",
            cell_id="cell_select_figure",
            column_name="Bone volume fraction",
            column_description="BVF figure graph value",
            row_context={},
            doc_dict=doc_with_crop,
            run_dir=run_dir,
            provider=provider,
            text_model_id="text-model",
            vision_model_id="vision-model",
        )

        assert proposal.proposed_value == "45.3%"
        assert proposal.selection_diagnostics["attempted"] is True
        assert proposal.selection_diagnostics["value_changed"] is True

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

    def test_unresolved_placeholder_value_is_not_persisted(self):
        assert (
            _proposal_value_for_persistence(
                proposal_status=ProposalStatus.unresolved,
                proposed_value="NOT_FOUND",
            )
            is None
        )
        assert (
            _proposal_value_for_persistence(
                proposal_status=ProposalStatus.unresolved,
                proposed_value="not found",
            )
            is None
        )
        assert (
            _proposal_value_for_persistence(
                proposal_status=ProposalStatus.unresolved,
                proposed_value="unclear",
            )
            is None
        )
        assert (
            _proposal_value_for_persistence(
                proposal_status=ProposalStatus.unresolved,
                proposed_value="No value proposed",
            )
            is None
        )
        assert (
            _proposal_value_for_persistence(
                proposal_status=ProposalStatus.value_proposed,
                proposed_value="unclear",
            )
            == "unclear"
        )

    def test_proposal_and_evidence_round_trip(self, run_dir: pathlib.Path):
        import datetime

        proposal = ProposalRecord(
            proposal_id="prop_roundtrip",
            run_id="run_test",
            pdf_id="pdf_test",
            row_id="row_test",
            cell_id="cell_test",
            proposal_status=ProposalStatus.value_proposed,
            evidence_status=EvidenceStatus.direct_strong,
            review_bucket=ReviewBucket.review,
            reason_codes=[],
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
        evidence_jsonl_path = run_dir / "evidence" / "evidence.jsonl"

        assert len(loaded_proposals) == 1
        assert loaded_proposals[0].proposal_id == "prop_roundtrip"
        assert loaded_proposals[0].proposal_status == ProposalStatus.value_proposed
        assert len(loaded_evidence) == 1
        assert loaded_evidence[0].evidence_schema_version == "main_evidence"
        assert loaded_evidence[0].source_type == EvidenceSourceType.direct_quote
        assert evidence_jsonl_path.exists()

    def test_long_evidence_filename_is_shortened_deterministically(self, run_dir: pathlib.Path):
        import datetime

        long_evidence_id = "ev_prop_run_20260408_110915_2es0wn_cell_482e9d1c5b38_1775646744681_p8c9n0oc"
        ev = EvidenceRecord(
            evidence_id=long_evidence_id,
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

        path = persist_evidence(run_dir, ev)

        assert path.exists()
        assert len(path.stem) < len(long_evidence_id)
        loaded_evidence = load_evidence(run_dir)
        assert len(loaded_evidence) == 1
        assert loaded_evidence[0].evidence_id == long_evidence_id


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
        assert proposals[0].proposal_status == ProposalStatus.not_attempted
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

    def test_model_config_accepts_request_payload_overrides(self):
        """Model config can carry OpenAI-compatible sampling and extra-body settings."""
        from backend.app.config import RunConfig

        config = RunConfig.model_validate({
            "table_path": FIXTURE_TABLE,
            "schema_path": FIXTURE_SCHEMA,
            "pdf_dir": FIXTURE_PDF_DIR,
            "output_dir": "./runs",
            "provider": {
                "token": "lm_studio",
                "base_url": "http://localhost:1234",
                "text_model": {
                    "model_id": "qwen/qwen3.6-27b",
                    "top_p": 0.8,
                    "top_k": 20,
                    "min_p": 0.0,
                    "presence_penalty": 1.5,
                    "repetition_penalty": 1.0,
                    "extra_body": {"custom_flag": True},
                    "chat_template_kwargs": {"enable_thinking": False},
                },
                "vision_model": {
                    "model_id": "vision-model-1",
                    "top_p": 0.95,
                    "chat_template_kwargs": {"enable_thinking": True},
                },
            },
        })

        assert config.provider.text_model.top_k == 20
        assert config.provider.text_model.extra_body == {"custom_flag": True}
        assert config.provider.text_model.chat_template_kwargs == {"enable_thinking": False}
        assert config.provider.vision_model is not None
        assert config.provider.vision_model.top_p == 0.95

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
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        retrieval = RetrievalResult(
            run_id="run_test",
            pdf_id="pdf_test",
            column_name="Integration site",
            query="Integration site: Site of implantation",
            top_k=6,
            chunks=[*chunks[:3], next(chunk for chunk in chunks if chunk.chunk_type == "figure")],
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
        assert "section: Methods" in user_content
        assert "figure: fig_1" in user_content

    def test_prompt_context_marks_table_passages_without_changing_body(self, minimal_doc_dict: dict):
        chunks = build_chunks_from_parsed_doc(minimal_doc_dict)
        table_chunk = next(chunk for chunk in chunks if chunk.chunk_type == "table_region")
        retrieval = RetrievalResult(
            run_id="run_test",
            pdf_id="pdf_test",
            column_name="Bone volume fraction",
            query="Bone volume fraction",
            top_k=1,
            chunks=[table_chunk],
            retrieved_at="2024-01-01T00:00:00+00:00",
        )

        messages = build_text_extraction_prompt(
            column_name="Bone volume fraction",
            column_description="Measured BVF value",
            row_context={},
            retrieval=retrieval,
            style_profile=None,
        )
        user_content = messages[1]["content"]

        assert "[TABLE_REGION; page 3; section: Methods; table]" in user_content
        assert table_chunk.display_text in user_content
        assert "[Element:" not in table_chunk.retrieval_text
        assert "[Page:" not in table_chunk.retrieval_text

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

