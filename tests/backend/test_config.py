"""Tests for config loading, validation, defaults, and readiness."""
from __future__ import annotations

import json
import pathlib

import pytest
import respx
import httpx

from backend.app.config import (
    CANONICAL_PROVIDERS,
    PROVIDER_DISPLAY_NAMES,
    RunConfig,
    apply_overrides,
    check_readiness,
    load_config,
)


FIXTURE_CONFIG = "config.example.json"
FIXTURE_TABLE = "tests/fixtures/tables/literature_fixture.xlsx"
FIXTURE_SCHEMA = "tests/fixtures/tables/literature_fixture_schema.csv"
FIXTURE_PDF_DIR = "tests/fixtures/papers"


class TestCanonicalProviderPolicy:
    def test_lm_studio_is_canonical(self):
        assert "lm_studio" in CANONICAL_PROVIDERS

    def test_display_name(self):
        assert PROVIDER_DISPLAY_NAMES["lm_studio"] == "LM Studio"

    def test_reject_openai_token(self):
        with pytest.raises(Exception, match="Unknown provider token"):
            RunConfig.model_validate({
                "table_path": "t.xlsx",
                "pdf_dir": "pdfs/",
                "provider": {"token": "openai"},
            })

    def test_reject_lmstudio_variant(self):
        with pytest.raises(Exception, match="Unknown provider token"):
            RunConfig.model_validate({
                "table_path": "t.xlsx",
                "pdf_dir": "pdfs/",
                "provider": {"token": "lmstudio"},
            })

    def test_reject_LMStudio_variant(self):
        with pytest.raises(Exception, match="Unknown provider token"):
            RunConfig.model_validate({
                "table_path": "t.xlsx",
                "pdf_dir": "pdfs/",
                "provider": {"token": "LMStudio"},
            })

    def test_reject_empty_token(self):
        with pytest.raises(Exception):
            RunConfig.model_validate({
                "table_path": "t.xlsx",
                "pdf_dir": "pdfs/",
                "provider": {"token": ""},
            })


class TestLoadConfig:
    def test_load_example_config(self):
        config = load_config(FIXTURE_CONFIG)
        assert config.provider.token == "lm_studio"
        assert config.table_path == str(pathlib.Path(FIXTURE_TABLE).resolve())
        assert config.schema_path == str(pathlib.Path(FIXTURE_SCHEMA).resolve())
        assert config.pdf_dir == str(pathlib.Path(FIXTURE_PDF_DIR).resolve())

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent.json")

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        with pytest.raises(Exception):
            load_config(str(p))

    def test_defaults_applied(self, tmp_path):
        data = {
            "table_path": "t.xlsx",
            "pdf_dir": "pdfs/",
            "provider": {
                "token": "lm_studio",
                "text_model": {"model_id": "qwen/qwen3-30b-a3b-2507"},
            },
        }
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        config = load_config(str(p))
        assert config.output_dir == "./runs"
        assert config.verify_mode is False
        assert config.provider.base_url == "http://localhost:1234"
        assert config.parser.backend == "docling"
        assert config.matching.ambiguity_threshold == 0.15
        assert config.retrieval.top_k == 6

    def test_relative_paths_resolve_against_config_location(self, tmp_path):
        config_dir = tmp_path / "nested"
        config_dir.mkdir()
        data = {
            "table_path": "../table.xlsx",
            "schema_path": "../schema.csv",
            "pdf_dir": "../pdfs",
            "output_dir": "../runs",
            "provider": {
                "token": "lm_studio",
                "text_model": {"model_id": "qwen/qwen3-30b-a3b-2507"},
            },
        }
        config_path = config_dir / "config.json"
        config_path.write_text(json.dumps(data), encoding="utf-8")

        config = load_config(str(config_path))

        assert config.table_path == str((tmp_path / "table.xlsx").resolve())
        assert config.schema_path == str((tmp_path / "schema.csv").resolve())
        assert config.pdf_dir == str((tmp_path / "pdfs").resolve())
        assert config.output_dir == str((tmp_path / "runs").resolve())

    def test_text_model_id_default_preserved_until_readiness(self, tmp_path):
        data = {
            "table_path": "t.xlsx",
            "pdf_dir": "pdfs/",
            "provider": {"token": "lm_studio"},
        }
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        config = load_config(str(p))
        assert config.provider.text_model.model_id == "default"

    def test_separate_text_and_vision_model(self):
        config = load_config(FIXTURE_CONFIG)
        assert config.provider.text_model is not None
        assert config.provider.vision_model is not None

    def test_verify_mode_default_false(self):
        config = load_config(FIXTURE_CONFIG)
        assert config.verify_mode is False

    def test_eval_mode_default_false(self):
        config = load_config(FIXTURE_CONFIG)
        assert config.eval_mode is False

    def test_reject_verify_mode_and_eval_mode_together(self):
        with pytest.raises(Exception, match="verify_mode=true and eval_mode=true cannot be used together"):
            RunConfig.model_validate({
                "table_path": "t.xlsx",
                "pdf_dir": "pdfs/",
                "verify_mode": True,
                "eval_mode": True,
                "provider": {
                    "token": "lm_studio",
                    "text_model": {"model_id": "qwen/qwen3-30b-a3b-2507"},
                },
            })


class TestApplyOverrides:
    def test_override_table_path(self):
        config = load_config(FIXTURE_CONFIG)
        overridden = apply_overrides(config, {"table_path": "other.xlsx"})
        assert overridden.table_path == "other.xlsx"
        assert overridden.pdf_dir == config.pdf_dir  # unchanged

    def test_override_schema_path(self):
        config = load_config(FIXTURE_CONFIG)
        overridden = apply_overrides(config, {"schema_path": "other_schema.csv"})
        assert overridden.schema_path == "other_schema.csv"

    def test_override_pdf_dir(self):
        config = load_config(FIXTURE_CONFIG)
        overridden = apply_overrides(config, {"pdf_dir": "/new/pdfs"})
        assert overridden.pdf_dir == "/new/pdfs"

    def test_none_overrides_ignored(self):
        config = load_config(FIXTURE_CONFIG)
        overridden = apply_overrides(config, {"table_path": None})
        assert overridden.table_path == config.table_path

    def test_empty_overrides_unchanged(self):
        config = load_config(FIXTURE_CONFIG)
        overridden = apply_overrides(config, {})
        assert overridden.table_path == config.table_path

    def test_relative_overrides_resolve_against_base_dir(self, tmp_path):
        config = load_config(FIXTURE_CONFIG)
        overridden = apply_overrides(
            config,
            {"table_path": "alternate/table.xlsx", "pdf_dir": "alternate/pdfs"},
            base_dir=str(tmp_path),
        )

        assert overridden.table_path == str((tmp_path / "alternate" / "table.xlsx").resolve())
        assert overridden.pdf_dir == str((tmp_path / "alternate" / "pdfs").resolve())


class TestReadiness:
    @pytest.mark.asyncio
    @respx.mock
    async def test_provider_reachable(self, tmp_path, minimal_config_dict, monkeypatch):
        minimal_config_dict["output_dir"] = str(tmp_path / "runs")
        config = RunConfig.model_validate(minimal_config_dict)
        monkeypatch.setattr("backend.app.parsing.check_parser_readiness", lambda *_args: [])
        monkeypatch.setattr("backend.app.parsing.check_ocr_readiness", lambda *_args: [])
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "qwen/qwen3-30b-a3b-2507"}]})
        )
        result = await check_readiness(config)
        assert result.ok is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_rejects_default_text_model(self, tmp_path, minimal_config_dict, monkeypatch):
        minimal_config_dict["provider"].pop("text_model", None)
        minimal_config_dict["output_dir"] = str(tmp_path / "runs")
        config = RunConfig.model_validate(minimal_config_dict)
        monkeypatch.setattr("backend.app.parsing.check_parser_readiness", lambda *_args: [])
        monkeypatch.setattr("backend.app.parsing.check_ocr_readiness", lambda *_args: [])
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "qwen/qwen3-30b-a3b-2507"}]})
        )
        result = await check_readiness(config)
        assert result.ok is False
        assert any("text_model.model_id" in e for e in result.errors)

    @pytest.mark.asyncio
    @respx.mock
    async def test_rejects_unloaded_text_model(self, tmp_path, minimal_config_dict, monkeypatch):
        minimal_config_dict["output_dir"] = str(tmp_path / "runs")
        config = RunConfig.model_validate(minimal_config_dict)
        monkeypatch.setattr("backend.app.parsing.check_parser_readiness", lambda *_args: [])
        monkeypatch.setattr("backend.app.parsing.check_ocr_readiness", lambda *_args: [])
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "some-other-model"}]})
        )
        result = await check_readiness(config)
        assert result.ok is False
        assert any("not loaded in LM Studio" in e for e in result.errors)

    @pytest.mark.asyncio
    @respx.mock
    async def test_provider_unreachable(self, tmp_path, minimal_config_dict):
        minimal_config_dict["output_dir"] = str(tmp_path / "runs")
        config = RunConfig.model_validate(minimal_config_dict)
        respx.get("http://localhost:1234/v1/models").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = await check_readiness(config)
        assert result.ok is False
        assert any("LM Studio" in e or "lm_studio" in e.lower() or "1234" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_table_path(self, tmp_path, minimal_config_dict):
        minimal_config_dict["table_path"] = str(tmp_path / "nonexistent.xlsx")
        minimal_config_dict["output_dir"] = str(tmp_path / "runs")
        config = RunConfig.model_validate(minimal_config_dict)
        result = await check_readiness(config)
        assert result.ok is False
        assert any("table_path" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_missing_pdf_dir(self, tmp_path, minimal_config_dict):
        minimal_config_dict["pdf_dir"] = str(tmp_path / "nonexistent")
        minimal_config_dict["output_dir"] = str(tmp_path / "runs")
        config = RunConfig.model_validate(minimal_config_dict)
        result = await check_readiness(config)
        assert result.ok is False
        assert any("pdf_dir" in e for e in result.errors)

    @pytest.mark.asyncio
    @respx.mock
    async def test_output_dir_created_if_missing(self, tmp_path, minimal_config_dict, monkeypatch):
        out = tmp_path / "new_runs"
        minimal_config_dict["output_dir"] = str(out)
        config = RunConfig.model_validate(minimal_config_dict)
        monkeypatch.setattr("backend.app.parsing.check_parser_readiness", lambda *_args: [])
        monkeypatch.setattr("backend.app.parsing.check_ocr_readiness", lambda *_args: [])
        respx.get("http://localhost:1234/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "qwen/qwen3-30b-a3b-2507"}]})
        )
        result = await check_readiness(config)
        assert out.exists()
