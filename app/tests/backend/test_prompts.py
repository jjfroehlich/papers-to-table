from __future__ import annotations

import json
import pathlib

import pytest

from backend.app.prompts import clear_prompt_bundle_cache, get_prompt_bundle


def _write_bundle(base_dir: pathlib.Path, bundle_name: str, marker: str) -> pathlib.Path:
    bundle_dir = base_dir / bundle_name
    (bundle_dir / "text_extraction").mkdir(parents=True)
    (bundle_dir / "figure_extraction").mkdir(parents=True)
    (bundle_dir / "evidence_recovery").mkdir(parents=True)
    (bundle_dir / "style_profile").mkdir(parents=True)

    manifest = {
        "bundle_id": bundle_name,
        "bundle_version": "test-1",
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
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    (bundle_dir / "text_extraction" / "system.md").write_text(f"text-system-{marker}", encoding="utf-8")
    (bundle_dir / "text_extraction" / "user.md").write_text(
        "Extract: $column_name\nField description: $column_description\n\nPaper row context:\n$row_block$verify_block$long_text_note$field_contract$style_block\n\n$context_block\n\n$whole_document_block\n\nInstructions:\nReturn ONLY valid JSON matching the schema.",
        encoding="utf-8",
    )
    (bundle_dir / "figure_extraction" / "system.md").write_text(f"figure-system-{marker}", encoding="utf-8")
    (bundle_dir / "figure_extraction" / "user.md").write_text(f"figure-user-{marker}", encoding="utf-8")
    (bundle_dir / "evidence_recovery" / "system.md").write_text(f"recovery-system-{marker}", encoding="utf-8")
    (bundle_dir / "evidence_recovery" / "user.md").write_text(f"recovery-user-{marker}", encoding="utf-8")
    (bundle_dir / "style_profile" / "system.md").write_text(f"style-system-{marker}", encoding="utf-8")

    return bundle_dir


def test_default_bundle_loads():
    clear_prompt_bundle_cache()
    bundle = get_prompt_bundle()

    assert bundle["bundle_id"] == "default"
    assert bundle["manifest_hash"]
    assert bundle["bundle_hash"]
    assert bundle["prompt_files"]
    assert "text_extraction_user" in bundle["prompts"]


def test_context_balanced_bundle_loads():
    clear_prompt_bundle_cache()
    bundle = get_prompt_bundle(bundle="context_balanced")

    assert bundle["bundle_id"] == "context_balanced"
    assert bundle["manifest_hash"]
    assert bundle["bundle_hash"]
    assert "text_extraction_user" in bundle["prompts"]
    assert "reviewer-verifiable" in bundle["prompts"]["text_extraction_system"]


def test_checklist_guided_bundle_loads():
    clear_prompt_bundle_cache()
    bundle = get_prompt_bundle(bundle="checklist_guided")

    assert bundle["bundle_id"] == "checklist_guided"
    assert bundle["manifest_hash"]
    assert bundle["bundle_hash"]
    assert "text_extraction_user" in bundle["prompts"]
    assert "strict extraction protocol" in bundle["prompts"]["text_extraction_system"]


def test_explicit_bundle_selection(monkeypatch, tmp_path: pathlib.Path):
    bundles_root = tmp_path / "prompt_bundles"
    _write_bundle(bundles_root, "default", "default")
    _write_bundle(bundles_root, "variant_a", "variant")

    monkeypatch.setattr("backend.app.prompts.PROMPT_BUNDLES_DIR", bundles_root)
    clear_prompt_bundle_cache()

    selected = get_prompt_bundle(bundle="variant_a")

    assert selected["bundle_id"] == "variant_a"
    assert selected["prompts"]["text_extraction_system"] == "text-system-variant"


def test_bundle_path_takes_precedence_over_bundle_name(monkeypatch, tmp_path: pathlib.Path):
    bundles_root = tmp_path / "prompt_bundles"
    _write_bundle(bundles_root, "default", "default")
    alt_bundle = _write_bundle(tmp_path, "custom_bundle", "custom")

    monkeypatch.setattr("backend.app.prompts.PROMPT_BUNDLES_DIR", bundles_root)
    clear_prompt_bundle_cache()

    selected = get_prompt_bundle(bundle="default", bundle_path=str(alt_bundle))

    assert selected["bundle_id"] == "custom_bundle"
    assert selected["prompts"]["text_extraction_system"] == "text-system-custom"


def test_missing_manifest_fails_with_clear_error(tmp_path: pathlib.Path):
    clear_prompt_bundle_cache()
    with pytest.raises(FileNotFoundError, match="manifest"):
        get_prompt_bundle(bundle_path=str(tmp_path / "does_not_exist"))


def test_missing_prompt_file_fails_with_clear_error(tmp_path: pathlib.Path):
    bundle_dir = tmp_path / "broken"
    bundle_dir.mkdir(parents=True)
    manifest = {
        "bundle_id": "broken",
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
    (bundle_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    clear_prompt_bundle_cache()
    with pytest.raises(FileNotFoundError, match="text_extraction"):
        get_prompt_bundle(bundle_path=str(bundle_dir))


def test_hashes_are_stable_for_same_bundle(monkeypatch, tmp_path: pathlib.Path):
    bundles_root = tmp_path / "prompt_bundles"
    _write_bundle(bundles_root, "default", "stable")

    monkeypatch.setattr("backend.app.prompts.PROMPT_BUNDLES_DIR", bundles_root)
    clear_prompt_bundle_cache()

    bundle_a = get_prompt_bundle()
    bundle_b = get_prompt_bundle()

    assert bundle_a["manifest_hash"] == bundle_b["manifest_hash"]
    assert bundle_a["bundle_hash"] == bundle_b["bundle_hash"]
    assert bundle_a["prompt_files"]["text_extraction_system"]["sha256"] == bundle_b["prompt_files"]["text_extraction_system"]["sha256"]
