from __future__ import annotations

import importlib.util
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "tools" / "optimizer" / "scripts" / "generate_negative_controls.py"
SPEC = importlib.util.spec_from_file_location("generate_negative_controls", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
negative_controls = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(negative_controls)


def _fixture_rows() -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    fieldnames = ["row_id", "row_index", "metadata", "target_a", "target_b"]
    template_rows = [
        {"row_id": "row-1", "row_index": "0", "metadata": "Paper A", "target_a": "", "target_b": ""},
        {"row_id": "row-2", "row_index": "1", "metadata": "Paper B", "target_a": "", "target_b": ""},
    ]
    gold_rows = [
        {
            "row_id": "row-1",
            "row_index": "0",
            "metadata": "Paper A",
            "target_a": "alpha beta gamma",
            "target_b": "single",
        },
        {
            "row_id": "row-2",
            "row_index": "1",
            "metadata": "Paper B",
            "target_a": "",
            "target_b": "delta epsilon",
        },
    ]
    return fieldnames, template_rows, gold_rows


def test_target_inference_and_word_shuffle_preserve_table_contract() -> None:
    fieldnames, template_rows, gold_rows = _fixture_rows()
    target_columns = negative_controls.infer_target_columns(fieldnames, template_rows)

    generated, stats = negative_controls.generate_word_shuffle(gold_rows, target_columns, seed=1234)

    assert target_columns == ["target_a", "target_b"]
    assert [(row["row_id"], row["row_index"], row["metadata"]) for row in generated] == [
        ("row-1", "0", "Paper A"),
        ("row-2", "1", "Paper B"),
    ]
    assert generated[1]["target_a"] == ""
    assert generated[0]["target_b"] == "single"
    assert generated[0]["target_a"].split() != gold_rows[0]["target_a"].split()
    assert generated[1]["target_b"].split() != gold_rows[1]["target_b"].split()
    assert Counter(generated[0]["target_a"].split()) == Counter(gold_rows[0]["target_a"].split())
    assert Counter(generated[1]["target_b"].split()) == Counter(gold_rows[1]["target_b"].split())
    assert stats["changed_cell_count"] == 2
    assert stats["single_token_cell_count"] == 1
    assert stats["empty_target_cell_count"] == 1


def test_cross_field_control_is_a_value_level_derangement() -> None:
    _, _, gold_rows = _fixture_rows()
    target_columns = ["target_a", "target_b"]

    generated, stats = negative_controls.generate_cross_field(gold_rows, target_columns, seed=5678)

    original = [
        gold_rows[row_index][column]
        for row_index, column in [(0, "target_a"), (0, "target_b"), (1, "target_b")]
    ]
    shuffled = [
        generated[row_index][column]
        for row_index, column in [(0, "target_a"), (0, "target_b"), (1, "target_b")]
    ]
    assert Counter(shuffled) == Counter(original)
    assert all(before.strip() != after.strip() for before, after in zip(original, shuffled, strict=True))
    assert generated[1]["target_a"] == ""
    assert [row["metadata"] for row in generated] == ["Paper A", "Paper B"]
    assert stats["fixed_value_cell_count"] == 0
    assert stats["changed_cell_count"] == 3


def test_generation_is_deterministic_for_a_seed() -> None:
    _, _, gold_rows = _fixture_rows()
    target_columns = ["target_a", "target_b"]

    first, first_stats = negative_controls.generate_word_shuffle(gold_rows, target_columns, seed=91)
    second, second_stats = negative_controls.generate_word_shuffle(gold_rows, target_columns, seed=91)

    assert first == second
    assert first_stats == second_stats


def test_checked_in_negative_controls_match_generator() -> None:
    outputs = negative_controls.build_outputs(REPO_ROOT)

    assert negative_controls.check_outputs(REPO_ROOT, outputs) == []
    assert len(outputs) == 22
