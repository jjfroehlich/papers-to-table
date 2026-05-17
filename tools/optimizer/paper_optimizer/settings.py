from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import read_json, resolve_path_fields


class ConfigError(ValueError):
    pass


def _require(config: dict[str, Any], key: str) -> Any:
    if key not in config:
        raise ConfigError(f"Missing required config key: {key}")
    return config[key]


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise ConfigError(f"Config file does not exist: {config_path}")
    raw = read_json(config_path)
    config = resolve_path_fields(
        raw,
        base_dir=config_path.resolve().parent,
        field_names={
            "repo_root",
            "base_config_path",
            "table_path",
            "schema_path",
            "pdf_dir",
            "gold_path",
            "eval_schema_path",
            "path",
        },
    )
    normalized = normalize_config(config)
    validate_config(normalized)
    return normalized


def normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(config)
    benchmarks = dict(normalized.get("benchmarks", {}))
    normalized["benchmarks"] = benchmarks
    suites = dict(normalized.get("benchmark_suites") or {})
    acceptance_primary = (
        normalized.get("acceptance", {}).get("primary_metric")
        if isinstance(normalized.get("acceptance"), dict)
        else "correctness"
    )
    for split in ["smoke", "dev"]:
        benchmark_id = benchmarks.get(split)
        suite_id = f"{split}_suite"
        if isinstance(benchmark_id, str) and suite_id not in suites:
            suites[suite_id] = {
                "benchmark_ids": [benchmark_id],
                "aggregation": {
                    "method": "weighted_mean",
                    "primary_metric": acceptance_primary,
                    "weights": {benchmark_id: 1.0},
                },
            }
    normalized["benchmark_suites"] = suites

    replicates = dict(normalized.get("replicates") or {})
    replicates.setdefault("count", 1)
    replicates.setdefault("continue_on_failure", True)
    normalized["replicates"] = replicates

    compare = dict(normalized.get("compare") or {})
    compare.setdefault("suite_id", "dev_suite")
    compare.pop("holdout_suite_id", None)
    compare.pop("holdout_top_k", None)
    normalized["compare"] = compare

    return normalized


def validate_config(config: dict[str, Any]) -> None:
    schema_version = _require(config, "schema_version")
    if not isinstance(schema_version, str):
        raise ConfigError("schema_version must be a string")

    experiment_id = _require(config, "experiment_id")
    if not isinstance(experiment_id, str) or not experiment_id.strip():
        raise ConfigError("experiment_id must be a non-empty string")

    baseline = _require(config, "baseline_candidate")
    if not isinstance(baseline, dict):
        raise ConfigError("baseline_candidate must be an object")

    for req in ["prompt_bundle_id", "text_model_id", "optimizer_knobs"]:
        if req not in baseline:
            raise ConfigError(f"baseline_candidate missing required key: {req}")

    if not isinstance(baseline["optimizer_knobs"], dict):
        raise ConfigError("baseline_candidate.optimizer_knobs must be an object")

    compare_candidates = config.get("compare_candidates", [])
    if compare_candidates is not None and not isinstance(compare_candidates, list):
        raise ConfigError("compare_candidates must be an array when provided")
    compare = config.get("compare", {})
    if compare is not None:
        if not isinstance(compare, dict):
            raise ConfigError("compare must be an object when provided")
        for bool_key in ["require_structured_output_for_extraction", "allow_degraded_candidates"]:
            if bool_key in compare and not isinstance(compare[bool_key], bool):
                raise ConfigError(f"compare.{bool_key} must be a boolean when provided")
        for suite_key in ["suite_id"]:
            if suite_key in compare and (not isinstance(compare[suite_key], str) or not compare[suite_key].strip()):
                raise ConfigError(f"compare.{suite_key} must be a non-empty string when provided")

    benchmarks = _require(config, "benchmarks")
    if not isinstance(benchmarks, dict):
        raise ConfigError("benchmarks must be an object")

    manifests = _require(benchmarks, "manifests")
    if not isinstance(manifests, dict) or not manifests:
        raise ConfigError("benchmarks.manifests must be a non-empty object")

    for split in ["dev"]:
        if split in benchmarks and not isinstance(benchmarks[split], str):
            raise ConfigError(f"benchmarks.{split} must be a string benchmark id")

    if "smoke" in benchmarks and not isinstance(benchmarks["smoke"], str):
        raise ConfigError("benchmarks.smoke must be a string benchmark id")

    for bench_id, manifest in manifests.items():
        if not isinstance(manifest, dict):
            raise ConfigError(f"benchmarks.manifests.{bench_id} must be an object")
        for path_key in ["table_path", "pdf_dir", "gold_path"]:
            if path_key in manifest and (not isinstance(manifest[path_key], str) or not manifest[path_key].strip()):
                raise ConfigError(f"benchmarks.manifests.{bench_id}.{path_key} must be a non-empty string when provided")
        for optional_path_key in ["schema_path", "eval_schema_path"]:
            if optional_path_key in manifest and manifest[optional_path_key] is not None and not isinstance(manifest[optional_path_key], str):
                raise ConfigError(f"benchmarks.manifests.{bench_id}.{optional_path_key} must be a string when provided")
        for optional_text_key in ["benchmark_kind", "benchmark_label"]:
            if optional_text_key in manifest and manifest[optional_text_key] is not None and not isinstance(manifest[optional_text_key], str):
                raise ConfigError(f"benchmarks.manifests.{bench_id}.{optional_text_key} must be a string when provided")
        if "require_non_fixture_inputs" in manifest and not isinstance(manifest["require_non_fixture_inputs"], bool):
            raise ConfigError(f"benchmarks.manifests.{bench_id}.require_non_fixture_inputs must be a boolean when provided")
        if "required_judges" in manifest:
            required_judges = manifest["required_judges"]
            if not isinstance(required_judges, list) or not all(isinstance(item, str) for item in required_judges):
                raise ConfigError(f"benchmarks.manifests.{bench_id}.required_judges must be an array of strings when provided")
        if "external_results" in manifest:
            external_results = manifest["external_results"]
            if not isinstance(external_results, list):
                raise ConfigError(f"benchmarks.manifests.{bench_id}.external_results must be an array when provided")
            for index, item in enumerate(external_results):
                if not isinstance(item, dict):
                    raise ConfigError(f"benchmarks.manifests.{bench_id}.external_results[{index}] must be an object")
                if not isinstance(item.get("path"), str) or not item.get("path", "").strip():
                    raise ConfigError(f"benchmarks.manifests.{bench_id}.external_results[{index}].path must be a non-empty string")
                if "label" in item and item["label"] is not None and not isinstance(item["label"], str):
                    raise ConfigError(f"benchmarks.manifests.{bench_id}.external_results[{index}].label must be a string")
                if "system" in item and item["system"] is not None and not isinstance(item["system"], str):
                    raise ConfigError(f"benchmarks.manifests.{bench_id}.external_results[{index}].system must be a string")
                if "eval_args" in item and (
                    not isinstance(item["eval_args"], list)
                    or not all(isinstance(arg, str) for arg in item["eval_args"])
                ):
                    raise ConfigError(f"benchmarks.manifests.{bench_id}.external_results[{index}].eval_args must be an array of strings")

    benchmark_suites = config.get("benchmark_suites", {})
    if benchmark_suites is not None:
        if not isinstance(benchmark_suites, dict):
            raise ConfigError("benchmark_suites must be an object when provided")
        known_benchmark_ids = set(manifests)
        for suite_id, suite in benchmark_suites.items():
            if not isinstance(suite_id, str) or not suite_id.strip():
                raise ConfigError("benchmark_suites keys must be non-empty suite ids")
            if not isinstance(suite, dict):
                raise ConfigError(f"benchmark_suites.{suite_id} must be an object")
            benchmark_ids = suite.get("benchmark_ids")
            if (
                not isinstance(benchmark_ids, list)
                or not benchmark_ids
                or not all(isinstance(item, str) and item.strip() for item in benchmark_ids)
            ):
                raise ConfigError(f"benchmark_suites.{suite_id}.benchmark_ids must be a non-empty array of benchmark ids")
            for benchmark_id in benchmark_ids:
                if benchmark_id not in known_benchmark_ids:
                    raise ConfigError(
                        f"benchmark_suites.{suite_id}.benchmark_ids references unknown benchmark id: {benchmark_id}"
                    )
            aggregation = suite.get("aggregation")
            if not isinstance(aggregation, dict):
                raise ConfigError(f"benchmark_suites.{suite_id}.aggregation must be an object")
            method = aggregation.get("method")
            if method != "weighted_mean":
                raise ConfigError(f"benchmark_suites.{suite_id}.aggregation.method must be 'weighted_mean'")
            acceptance_primary = config.get("acceptance", {}).get("primary_metric") if isinstance(config.get("acceptance"), dict) else None
            primary_metric = aggregation.get("primary_metric", acceptance_primary)
            if not isinstance(primary_metric, str) or not primary_metric.strip():
                raise ConfigError(f"benchmark_suites.{suite_id}.aggregation.primary_metric must be a non-empty string")
            weights = aggregation.get("weights", {})
            if weights is None:
                weights = {}
            if not isinstance(weights, dict):
                raise ConfigError(f"benchmark_suites.{suite_id}.aggregation.weights must be an object when provided")
            suite_benchmark_ids = set(benchmark_ids)
            for weight_key, weight in weights.items():
                if weight_key not in suite_benchmark_ids:
                    raise ConfigError(
                        f"benchmark_suites.{suite_id}.aggregation.weights references unknown suite benchmark id: {weight_key}"
                    )
                if not isinstance(weight, (int, float)) or float(weight) < 0:
                    raise ConfigError(
                        f"benchmark_suites.{suite_id}.aggregation.weights.{weight_key} must be a non-negative number"
                    )

        for section_name in ["compare"]:
            section = config.get(section_name, {})
            if not isinstance(section, dict):
                continue
            for suite_key in ["suite_id"]:
                suite_ref = section.get(suite_key)
                if isinstance(suite_ref, str) and suite_ref.strip() and suite_ref not in benchmark_suites:
                    raise ConfigError(f"{section_name}.{suite_key} references unknown benchmark suite: {suite_ref}")

    replicates = config.get("replicates", {})
    if replicates is not None:
        if not isinstance(replicates, dict):
            raise ConfigError("replicates must be an object when provided")
        count = replicates.get("count", 1)
        if not isinstance(count, int) or count <= 0:
            raise ConfigError("replicates.count must be a positive integer")
        if "continue_on_failure" in replicates and not isinstance(replicates["continue_on_failure"], bool):
            raise ConfigError("replicates.continue_on_failure must be a boolean when provided")

    main_app = _require(config, "main_app")
    eval_app = _require(config, "eval_app")
    for section_name, section in [("main_app", main_app), ("eval_app", eval_app)]:
        if not isinstance(section, dict):
            raise ConfigError(f"{section_name} must be an object")
        command = section.get("command")
        command_prefix = section.get("command_prefix")
        if command is not None and (not isinstance(command, list) or not command or not all(isinstance(x, str) for x in command)):
            raise ConfigError(f"{section_name}.command must be a non-empty string array")
        if command_prefix is not None and (
            not isinstance(command_prefix, list) or not command_prefix or not all(isinstance(x, str) for x in command_prefix)
        ):
            raise ConfigError(f"{section_name}.command_prefix must be a non-empty string array when provided")

    if "command" not in main_app:
        for key in ["repo_root", "base_config_path"]:
            if not isinstance(_require(main_app, key), str):
                raise ConfigError(f"main_app.{key} must be a string")

    if "command" not in eval_app:
        if not isinstance(_require(eval_app, "repo_root"), str):
            raise ConfigError("eval_app.repo_root must be a string")

    metric_groups = eval_app.get("metric_groups", {})
    if metric_groups is not None:
        if not isinstance(metric_groups, dict):
            raise ConfigError("eval_app.metric_groups must be an object when provided")
        for group_name in ["primary", "guardrail", "diagnostic"]:
            group = metric_groups.get(group_name, {})
            if not isinstance(group, (dict, list)):
                raise ConfigError(f"eval_app.metric_groups.{group_name} must be an object or array when provided")
            if isinstance(group, dict) and not all(isinstance(k, str) and isinstance(v, str) for k, v in group.items()):
                raise ConfigError(f"eval_app.metric_groups.{group_name} object values must be string-to-string mappings")
            if isinstance(group, list) and not all(isinstance(v, str) for v in group):
                raise ConfigError(f"eval_app.metric_groups.{group_name} array entries must be strings")

    acceptance = _require(config, "acceptance")
    if not isinstance(acceptance, dict):
        raise ConfigError("acceptance must be an object")
    if not isinstance(_require(acceptance, "primary_metric"), str):
        raise ConfigError("acceptance.primary_metric must be a string")
    if "min_improvement" in acceptance and not isinstance(acceptance["min_improvement"], (int, float)):
        raise ConfigError("acceptance.min_improvement must be numeric when provided")
    degraded_score_policy = acceptance.get("degraded_score_policy", "warn")
    if degraded_score_policy not in {"allow", "warn", "disallow"}:
        raise ConfigError("acceptance.degraded_score_policy must be one of: allow, warn, disallow")
    tie_break = acceptance.get("tie_break")
    if tie_break is not None:
        if not isinstance(tie_break, dict):
            raise ConfigError("acceptance.tie_break must be an object when provided")
        if "epsilon" in tie_break and not isinstance(tie_break["epsilon"], (int, float)):
            raise ConfigError("acceptance.tie_break.epsilon must be numeric when provided")
        secondary_objectives = tie_break.get("secondary_objectives", [])
        if not isinstance(secondary_objectives, list):
            raise ConfigError("acceptance.tie_break.secondary_objectives must be an array when provided")
        for index, objective in enumerate(secondary_objectives):
            if not isinstance(objective, dict):
                raise ConfigError(
                    f"acceptance.tie_break.secondary_objectives[{index}] must be an object"
                )
            metric_name = objective.get("metric")
            if not isinstance(metric_name, str) or not metric_name.strip():
                raise ConfigError(
                    f"acceptance.tie_break.secondary_objectives[{index}].metric must be a non-empty string"
                )
            direction = objective.get("direction", "max")
            if direction not in {"max", "min"}:
                raise ConfigError(
                    f"acceptance.tie_break.secondary_objectives[{index}].direction must be 'max' or 'min'"
                )
            if "min_improvement" in objective and not isinstance(objective["min_improvement"], (int, float)):
                raise ConfigError(
                    f"acceptance.tie_break.secondary_objectives[{index}].min_improvement must be numeric when provided"
                )
