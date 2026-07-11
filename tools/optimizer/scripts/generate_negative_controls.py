from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ALGORITHM_VERSION = "gold_negative_controls_v1"
SCHEMA_VERSION = "papers_to_table.negative_controls.v1"
REPLICATE_COUNT = 3
IDENTITY_COLUMNS = {"row_id", "row_index"}
DATASET_NAMES = (
    "massively_parallel_reporter_assays",
    "genome_editing_tools",
    "spatial_transcriptomics",
)
CONTROL_SPECS = {
    "word_shuffle": {
        "output_dir": "20260710_gold_word_shuffle",
        "title": "Gold word-shuffle negative control",
        "description": (
            "Whitespace-delimited tokens are shuffled independently within each non-empty target cell. "
            "Single-token and otherwise unshufflable cells remain unchanged, making this a weak negative "
            "control for word-order sensitivity rather than a guaranteed score floor."
        ),
    },
    "cross_field": {
        "output_dir": "20260710_gold_cross_field",
        "title": "Gold cross-field negative control",
        "description": (
            "Whole non-empty gold values are reassigned across target rows and columns within each dataset. "
            "The generator requires a value-level derangement, so no non-empty target cell retains its "
            "original rendered value. This intentionally mixes field types and is a strong score-floor control."
        ),
    },
}


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _seed_for(control: str, dataset_name: str, replicate_index: int) -> tuple[int, str]:
    material = f"{ALGORITHM_VERSION}|{control}|{dataset_name}|replicate={replicate_index}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
    return int(digest[:16], 16), digest


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        fieldnames = list(reader.fieldnames)
        rows = [{key: value or "" for key, value in row.items()} for row in reader]
    if not rows:
        raise ValueError(f"CSV has no data rows: {path}")
    return fieldnames, rows


def _write_csv_bytes(fieldnames: list[str], rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _copy_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(row) for row in rows]


def infer_target_columns(fieldnames: list[str], template_rows: list[dict[str, str]]) -> list[str]:
    target_columns = [
        column
        for column in fieldnames
        if column not in IDENTITY_COLUMNS
        and all(not str(row.get(column, "")).strip() for row in template_rows)
    ]
    if not target_columns:
        raise ValueError("No target columns were inferred from the all-blank template columns")
    return target_columns


def _validate_sources(
    *,
    dataset_name: str,
    template_fieldnames: list[str],
    template_rows: list[dict[str, str]],
    gold_fieldnames: list[str],
    gold_rows: list[dict[str, str]],
) -> list[str]:
    if template_fieldnames != gold_fieldnames:
        raise ValueError(f"Template and gold headers differ for {dataset_name}")
    if len(template_rows) != len(gold_rows):
        raise ValueError(f"Template and gold row counts differ for {dataset_name}")
    for row_index, (template_row, gold_row) in enumerate(zip(template_rows, gold_rows, strict=True)):
        for identity_column in sorted(IDENTITY_COLUMNS):
            if template_row.get(identity_column, "") != gold_row.get(identity_column, ""):
                raise ValueError(
                    f"Template and gold {identity_column} differ for {dataset_name} row {row_index}"
                )
    return infer_target_columns(template_fieldnames, template_rows)


def _shuffle_tokens(tokens: list[str], rng: random.Random) -> list[str] | None:
    if len(tokens) < 2 or len(set(tokens)) < 2:
        return None
    for _ in range(100):
        shuffled = list(tokens)
        rng.shuffle(shuffled)
        if shuffled != tokens:
            return shuffled
    for offset in range(1, len(tokens)):
        shifted = tokens[offset:] + tokens[:offset]
        if shifted != tokens:
            return shifted
    raise RuntimeError("Could not produce a changed token ordering")


def generate_word_shuffle(
    gold_rows: list[dict[str, str]],
    target_columns: list[str],
    *,
    seed: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rng = random.Random(seed)
    output_rows = _copy_rows(gold_rows)
    stats: Counter[str] = Counter()

    for row_index, gold_row in enumerate(gold_rows):
        for column in target_columns:
            original = gold_row.get(column, "")
            if not original.strip():
                stats["empty_target_cell_count"] += 1
                continue
            stats["nonempty_target_cell_count"] += 1
            tokens = original.split()
            shuffled = _shuffle_tokens(tokens, rng)
            if shuffled is None:
                stats["unchanged_nonempty_cell_count"] += 1
                if len(tokens) < 2:
                    stats["single_token_cell_count"] += 1
                else:
                    stats["repeated_token_unshufflable_cell_count"] += 1
                continue
            output_rows[row_index][column] = " ".join(shuffled)
            stats["changed_cell_count"] += 1

    stats["target_cell_count"] = len(gold_rows) * len(target_columns)
    return output_rows, dict(sorted(stats.items()))


def generate_cross_field(
    gold_rows: list[dict[str, str]],
    target_columns: list[str],
    *,
    seed: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    rng = random.Random(seed)
    output_rows = _copy_rows(gold_rows)
    positions: list[tuple[int, str]] = []
    values: list[str] = []
    empty_target_cell_count = 0

    for row_index, gold_row in enumerate(gold_rows):
        for column in target_columns:
            value = gold_row.get(column, "")
            if value.strip():
                positions.append((row_index, column))
                values.append(value)
            else:
                empty_target_cell_count += 1

    if len(values) < 2:
        raise ValueError("Cross-field control requires at least two non-empty target cells")

    shuffled: list[str] | None = None
    attempts = 0
    for attempts in range(1, 10_001):
        candidate = list(values)
        rng.shuffle(candidate)
        if all(new.strip() != old.strip() for old, new in zip(values, candidate, strict=True)):
            shuffled = candidate
            break
    if shuffled is None:
        raise RuntimeError("Could not generate a value-level cross-field derangement in 10,000 attempts")

    for (row_index, column), value in zip(positions, shuffled, strict=True):
        output_rows[row_index][column] = value

    if Counter(value.strip() for value in values) != Counter(value.strip() for value in shuffled):
        raise AssertionError("Cross-field control did not preserve the non-empty value multiset")
    fixed_count = sum(
        output_rows[row_index][column].strip() == gold_rows[row_index][column].strip()
        for row_index, column in positions
    )
    if fixed_count:
        raise AssertionError(f"Cross-field control retained {fixed_count} gold values in place")

    return output_rows, {
        "target_cell_count": len(gold_rows) * len(target_columns),
        "nonempty_target_cell_count": len(values),
        "empty_target_cell_count": empty_target_cell_count,
        "changed_cell_count": len(values),
        "unchanged_nonempty_cell_count": 0,
        "fixed_value_cell_count": fixed_count,
        "derangement_attempt_count": attempts,
    }


def _readme_text(control: str) -> str:
    spec = CONTROL_SPECS[control]
    return f"""# {spec['title']}

Generated from the active checked-in gold tables by
`python tools/optimizer/scripts/generate_negative_controls.py`.

{spec['description']}

The generator preserves CSV headers, row order, `row_id`, `row_index`, metadata columns, and the
blank/non-empty target-cell mask. It creates three deterministic replicates for every active benchmark
dataset. Exact source hashes, seeds, target columns, and cell counts are recorded in
`generation_manifest.json`.

Verify that the checked-in files still match their sources and algorithm with:

```bash
python tools/optimizer/scripts/generate_negative_controls.py --check
```

These files are Eval inputs and report controls. They are not extraction outputs and must not participate
in optimizer winner or recommended-default selection.
"""


def build_outputs(repo_root: Path) -> dict[Path, bytes]:
    benchmark_root = repo_root / "benchmark_datasets"
    data_root = benchmark_root / "data"
    outputs: dict[Path, bytes] = {}
    manifests: dict[str, dict[str, Any]] = {
        control: {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "control": control,
            "description": spec["description"],
            "replicate_count": REPLICATE_COUNT,
            "datasets": {},
        }
        for control, spec in CONTROL_SPECS.items()
    }

    for dataset_name in DATASET_NAMES:
        dataset_root = benchmark_root / dataset_name
        template_path = dataset_root / "table_template.csv"
        gold_path = dataset_root / "table_gold.csv"
        template_fieldnames, template_rows = _read_csv(template_path)
        gold_fieldnames, gold_rows = _read_csv(gold_path)
        target_columns = _validate_sources(
            dataset_name=dataset_name,
            template_fieldnames=template_fieldnames,
            template_rows=template_rows,
            gold_fieldnames=gold_fieldnames,
            gold_rows=gold_rows,
        )

        generated_by_control: dict[str, list[bytes]] = {control: [] for control in CONTROL_SPECS}
        for control, spec in CONTROL_SPECS.items():
            dataset_manifest: dict[str, Any] = {
                "template_path": template_path.relative_to(repo_root).as_posix(),
                "template_sha256": _sha256_file(template_path),
                "gold_path": gold_path.relative_to(repo_root).as_posix(),
                "gold_sha256": _sha256_file(gold_path),
                "target_columns": target_columns,
                "replicates": [],
            }
            manifests[control]["datasets"][dataset_name] = dataset_manifest

            for replicate_index in range(1, REPLICATE_COUNT + 1):
                seed, seed_sha256 = _seed_for(control, dataset_name, replicate_index)
                if control == "word_shuffle":
                    generated_rows, stats = generate_word_shuffle(gold_rows, target_columns, seed=seed)
                else:
                    generated_rows, stats = generate_cross_field(gold_rows, target_columns, seed=seed)
                payload = _write_csv_bytes(gold_fieldnames, generated_rows)
                generated_by_control[control].append(payload)
                output_relative = Path("rep" + str(replicate_index)) / f"{dataset_name}_filled.csv"
                output_path = data_root / spec["output_dir"] / output_relative
                outputs[output_path] = payload
                dataset_manifest["replicates"].append(
                    {
                        "replicate_index": replicate_index,
                        "seed": seed,
                        "seed_sha256": seed_sha256,
                        "output_path": output_path.relative_to(repo_root).as_posix(),
                        "output_sha256": _sha256_bytes(payload),
                        "stats": stats,
                    }
                )

        for control, payloads in generated_by_control.items():
            if len(set(payloads)) != REPLICATE_COUNT:
                raise RuntimeError(f"{control} generated duplicate replicates for {dataset_name}")

    for control, spec in CONTROL_SPECS.items():
        output_root = data_root / spec["output_dir"]
        outputs[output_root / "readme.md"] = _readme_text(control).encode("utf-8")
        manifest_text = json.dumps(manifests[control], indent=2, sort_keys=True) + "\n"
        outputs[output_root / "generation_manifest.json"] = manifest_text.encode("utf-8")

    return outputs


def _unexpected_files(repo_root: Path, expected_paths: set[Path]) -> list[Path]:
    data_root = repo_root / "benchmark_datasets" / "data"
    unexpected: list[Path] = []
    for spec in CONTROL_SPECS.values():
        output_root = data_root / spec["output_dir"]
        if not output_root.exists():
            continue
        unexpected.extend(
            path
            for path in output_root.rglob("*")
            if path.is_file() and path not in expected_paths
        )
    return sorted(unexpected)


def check_outputs(repo_root: Path, outputs: dict[Path, bytes]) -> list[str]:
    errors: list[str] = []
    for path, expected in sorted(outputs.items()):
        relative = path.relative_to(repo_root).as_posix()
        if not path.exists():
            errors.append(f"missing: {relative}")
        elif path.read_bytes() != expected:
            errors.append(f"out of date: {relative}")
    for path in _unexpected_files(repo_root, set(outputs)):
        errors.append(f"unexpected: {path.relative_to(repo_root).as_posix()}")
    return errors


def write_outputs(repo_root: Path, outputs: dict[Path, bytes]) -> None:
    unexpected = _unexpected_files(repo_root, set(outputs))
    if unexpected:
        rendered = ", ".join(path.relative_to(repo_root).as_posix() for path in unexpected)
        raise RuntimeError(f"Refusing to overwrite control directories with unexpected files: {rendered}")
    for path, payload in sorted(outputs.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate deterministic gold-derived negative-control tables.")
    parser.add_argument("--check", action="store_true", help="Verify checked-in controls without writing files.")
    parser.add_argument("--repo-root", type=Path, default=repository_root(), help=argparse.SUPPRESS)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    outputs = build_outputs(repo_root)
    if args.check:
        errors = check_outputs(repo_root, outputs)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            return 1
        print(f"Verified {len(outputs)} deterministic negative-control files.")
        return 0

    write_outputs(repo_root, outputs)
    print(f"Wrote {len(outputs)} deterministic negative-control files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
