from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class BenchmarkError(ValueError):
    pass


@dataclass(frozen=True)
class BenchmarkManifest:
    benchmark_id: str
    expected_items: int | None
    table_path: str | None
    schema_path: str | None
    pdf_dir: str | None
    gold_path: str | None
    gold_sheet: str | None
    eval_schema_path: str | None
    main_args: list[str]
    eval_args: list[str]
    benchmark_kind: str | None
    benchmark_label: str | None
    require_non_fixture_inputs: bool = False
    required_judges: list[str] | None = None


@dataclass(frozen=True)
class Benchmarks:
    split_to_id: dict[str, str]
    manifests: dict[str, BenchmarkManifest]



def load_benchmarks(config: dict[str, Any]) -> Benchmarks:
    raw = config["benchmarks"]
    manifests_raw = raw["manifests"]

    manifests: dict[str, BenchmarkManifest] = {}
    for bench_id, manifest in manifests_raw.items():
        if not isinstance(manifest, dict):
            raise BenchmarkError(f"Benchmark manifest must be an object: {bench_id}")
        manifests[bench_id] = BenchmarkManifest(
            benchmark_id=bench_id,
            expected_items=manifest.get("expected_items"),
            table_path=manifest.get("table_path"),
            schema_path=manifest.get("schema_path"),
            pdf_dir=manifest.get("pdf_dir"),
            gold_path=manifest.get("gold_path"),
            gold_sheet=manifest.get("gold_sheet"),
            eval_schema_path=manifest.get("eval_schema_path"),
            main_args=list(manifest.get("main_args", [])),
            eval_args=list(manifest.get("eval_args", [])),
            benchmark_kind=manifest.get("benchmark_kind"),
            benchmark_label=manifest.get("benchmark_label"),
            require_non_fixture_inputs=bool(manifest.get("require_non_fixture_inputs", False)),
            required_judges=list(manifest.get("required_judges", [])),
        )

    split_to_id: dict[str, str] = {}
    for split in ["smoke", "dev", "holdout"]:
        if split in raw:
            split_to_id[split] = raw[split]

    for split, bench_id in split_to_id.items():
        if bench_id not in manifests:
            raise BenchmarkError(f"benchmarks.{split} references unknown benchmark id: {bench_id}")

    dev_id = split_to_id.get("dev")
    holdout_id = split_to_id.get("holdout")
    if dev_id and holdout_id and dev_id == holdout_id:
        raise BenchmarkError("dev and holdout must reference distinct benchmark ids")

    return Benchmarks(split_to_id=split_to_id, manifests=manifests)

