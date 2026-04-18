"""Tests for artifact I/O and run bundle layout."""
from __future__ import annotations

import json
import pathlib

import pytest

from backend.app.artifacts import (
    append_jsonl,
    get_config_snapshot_path,
    get_diagnostics_dir,
    get_evidence_dir,
    get_input_summary_path,
    get_provider_diagnostics_path,
    get_provider_mode_path,
    get_provider_model_management_path,
    get_provider_probe_path,
    get_provider_request_counts_path,
    get_provider_trace_path,
    get_proposals_dir,
    get_review_dir,
    get_reviewer_summary_path,
    get_run_dir,
    get_run_json_path,
    get_run_summary_path,
    get_run_stats_path,
    get_summaries_dir,
    init_run_bundle,
    list_run_ids,
    lookup_by_id,
    read_json,
    read_jsonl,
    write_json,
)


class TestPathHelpers:
    def test_get_run_dir(self, tmp_path):
        d = get_run_dir(str(tmp_path), "run_abc")
        assert d == tmp_path / "run_abc"

    def test_get_run_json_path(self, tmp_path):
        p = get_run_json_path(str(tmp_path), "run_abc")
        assert p.name == "run.json"
        assert p.parent.name == "run_abc"

    def test_get_config_snapshot_path(self, tmp_path):
        p = get_config_snapshot_path(str(tmp_path), "run_abc")
        assert p.name == "config.snapshot.json"

    def test_get_input_summary_path(self, tmp_path):
        p = get_input_summary_path(str(tmp_path), "run_abc")
        assert p.name == "input_summary.json"
        assert "inputs" in str(p)

    def test_get_proposals_dir(self, tmp_path):
        p = get_proposals_dir(str(tmp_path), "run_abc")
        assert p.name == "proposals"

    def test_get_evidence_dir(self, tmp_path):
        p = get_evidence_dir(str(tmp_path), "run_abc")
        assert p.name == "evidence"

    def test_get_review_dir(self, tmp_path):
        p = get_review_dir(str(tmp_path), "run_abc")
        assert p.name == "review"

    def test_get_run_summary_path(self, tmp_path):
        p = get_run_summary_path(str(tmp_path), "run_abc")
        assert p.name == "run_summary.json"
        assert "summaries" in str(p)

    def test_get_summaries_dir(self, tmp_path):
        p = get_summaries_dir(str(tmp_path), "run_abc")
        assert p.name == "summaries"

    def test_get_diagnostics_dir(self, tmp_path):
        p = get_diagnostics_dir(str(tmp_path), "run_abc")
        assert p.name == "diagnostics"

    def test_get_reviewer_summary_path(self, tmp_path):
        p = get_reviewer_summary_path(str(tmp_path), "run_abc")
        assert p.name == "reviewer_summary.json"

    def test_get_run_stats_path(self, tmp_path):
        p = get_run_stats_path(str(tmp_path), "run_abc")
        assert p.name == "run_stats.json"
        assert "diagnostics" in str(p)

    def test_get_provider_mode_path(self, tmp_path):
        p = get_provider_mode_path(str(tmp_path), "run_abc")
        assert p.name == "provider_mode.json"
        assert "summaries" in str(p)

    def test_get_provider_diagnostics_path(self, tmp_path):
        p = get_provider_diagnostics_path(str(tmp_path), "run_abc")
        assert p.name == "provider_diagnostics.json"
        assert "diagnostics" in str(p)

    def test_get_provider_request_counts_path(self, tmp_path):
        p = get_provider_request_counts_path(str(tmp_path), "run_abc")
        assert p.name == "provider_request_counts.json"
        assert "diagnostics" in str(p)

    def test_get_provider_probe_path(self, tmp_path):
        p = get_provider_probe_path(str(tmp_path), "run_abc")
        assert p.name == "provider_probe.json"

    def test_get_provider_model_management_path(self, tmp_path):
        p = get_provider_model_management_path(str(tmp_path), "run_abc")
        assert p.name == "provider_model_management.json"
        assert "diagnostics" in str(p)

    def test_get_provider_trace_path(self, tmp_path):
        p = get_provider_trace_path(str(tmp_path), "run_abc")
        assert p.name == "provider_trace.jsonl"
        assert "diagnostics" in str(p)

class TestInitRunBundle:
    def test_creates_all_subdirs(self, tmp_path):
        run_dir = init_run_bundle(str(tmp_path), "run_test")
        required_subdirs = [
            "inputs", "style_profiles", "parsed", "matching",
            "retrieval", "proposals", "evidence", "review",
            "diagnostics",
            "summaries", "exports",
        ]
        for sub in required_subdirs:
            assert (run_dir / sub).is_dir(), f"Missing subdir: {sub}"

    def test_returns_run_dir_path(self, tmp_path):
        run_dir = init_run_bundle(str(tmp_path), "run_test")
        assert run_dir.is_dir()
        assert run_dir.name == "run_test"

    def test_idempotent(self, tmp_path):
        init_run_bundle(str(tmp_path), "run_test")
        init_run_bundle(str(tmp_path), "run_test")  # should not raise


class TestWriteReadJson:
    def test_roundtrip(self, tmp_path):
        p = tmp_path / "data.json"
        data = {"key": "value", "num": 42, "nested": {"a": [1, 2, 3]}}
        write_json(p, data)
        result = read_json(p)
        assert result == data

    def test_atomic_creates_parent(self, tmp_path):
        p = tmp_path / "a" / "b" / "c" / "data.json"
        write_json(p, {"x": 1})
        assert p.exists()

    def test_no_tmp_file_left(self, tmp_path):
        p = tmp_path / "data.json"
        write_json(p, {"x": 1})
        tmp_files = list(tmp_path.glob("*.tmp"))
        assert len(tmp_files) == 0

    def test_overwrite(self, tmp_path):
        p = tmp_path / "data.json"
        write_json(p, {"v": 1})
        write_json(p, {"v": 2})
        assert read_json(p)["v"] == 2

    def test_unicode(self, tmp_path):
        p = tmp_path / "data.json"
        write_json(p, {"text": "日本語テスト"})
        result = read_json(p)
        assert result["text"] == "日本語テスト"

    def test_tmp_name_does_not_inherit_long_target_name(self, tmp_path):
        nested = tmp_path / ("nested_" * 8)
        p = nested / ("x" * 80 + ".json")
        write_json(p, {"ok": True})
        assert p.exists()
        tmp_files = list(nested.glob("*.tmp"))
        assert tmp_files == []


class TestJsonl:
    def test_append_and_read(self, tmp_path):
        p = tmp_path / "records.jsonl"
        append_jsonl(p, {"id": "a", "val": 1})
        append_jsonl(p, {"id": "b", "val": 2})
        records = read_jsonl(p)
        assert len(records) == 2
        assert records[0]["id"] == "a"
        assert records[1]["val"] == 2

    def test_read_empty_file(self, tmp_path):
        p = tmp_path / "empty.jsonl"
        records = read_jsonl(p)
        assert records == []

    def test_append_creates_parent(self, tmp_path):
        p = tmp_path / "subdir" / "records.jsonl"
        append_jsonl(p, {"x": 1})
        assert p.exists()

    def test_multiple_appends_accumulate(self, tmp_path):
        p = tmp_path / "records.jsonl"
        for i in range(10):
            append_jsonl(p, {"i": i})
        records = read_jsonl(p)
        assert len(records) == 10


class TestLookupById:
    def test_found(self, tmp_path):
        p = tmp_path / "records.jsonl"
        append_jsonl(p, {"proposal_id": "p1", "value": "foo"})
        append_jsonl(p, {"proposal_id": "p2", "value": "bar"})
        result = lookup_by_id(p, "proposal_id", "p2")
        assert result is not None
        assert result["value"] == "bar"

    def test_not_found(self, tmp_path):
        p = tmp_path / "records.jsonl"
        append_jsonl(p, {"proposal_id": "p1", "value": "foo"})
        assert lookup_by_id(p, "proposal_id", "missing") is None

    def test_missing_file(self, tmp_path):
        p = tmp_path / "nonexistent.jsonl"
        assert lookup_by_id(p, "id", "x") is None


class TestListRunIds:
    def test_empty_dir(self, tmp_path):
        ids = list_run_ids(str(tmp_path))
        assert ids == []

    def test_nonexistent_dir(self, tmp_path):
        ids = list_run_ids(str(tmp_path / "nonexistent"))
        assert ids == []

    def test_lists_run_dirs_with_run_json(self, tmp_path):
        for rid in ["run_aaa", "run_bbb", "run_ccc"]:
            init_run_bundle(str(tmp_path), rid)
            write_json(get_run_json_path(str(tmp_path), rid), {"run_id": rid})
        ids = list_run_ids(str(tmp_path))
        assert set(ids) == {"run_aaa", "run_bbb", "run_ccc"}

    def test_ignores_dirs_without_run_json(self, tmp_path):
        # create a dir without run.json
        (tmp_path / "not_a_run").mkdir()
        init_run_bundle(str(tmp_path), "run_real")
        write_json(get_run_json_path(str(tmp_path), "run_real"), {"run_id": "run_real"})
        ids = list_run_ids(str(tmp_path))
        assert ids == ["run_real"]
