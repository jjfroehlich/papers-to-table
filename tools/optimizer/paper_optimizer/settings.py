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
        },
    )
    validate_config(config)
    return config


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

    benchmarks = _require(config, "benchmarks")
    if not isinstance(benchmarks, dict):
        raise ConfigError("benchmarks must be an object")

    manifests = _require(benchmarks, "manifests")
    if not isinstance(manifests, dict) or not manifests:
        raise ConfigError("benchmarks.manifests must be a non-empty object")

    for split in ["dev", "holdout"]:
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

    optimize = config.get("optimize", {})
    if not isinstance(optimize, dict):
        raise ConfigError("optimize must be an object when provided")

    rounds = optimize.get("rounds", 0)
    if not isinstance(rounds, int) or rounds < 0:
        raise ConfigError("optimize.rounds must be a non-negative integer")

    batch_size = optimize.get("batch_size", 1)
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ConfigError("optimize.batch_size must be a positive integer")

    confirmation_reruns = optimize.get("confirmation_reruns", {})
    if confirmation_reruns is not None:
        if not isinstance(confirmation_reruns, dict):
            raise ConfigError("optimize.confirmation_reruns must be an object when provided")
        if "enabled" in confirmation_reruns and not isinstance(confirmation_reruns["enabled"], bool):
            raise ConfigError("optimize.confirmation_reruns.enabled must be a boolean")
        if "count" in confirmation_reruns and (
            not isinstance(confirmation_reruns["count"], int) or confirmation_reruns["count"] < 0
        ):
            raise ConfigError("optimize.confirmation_reruns.count must be a non-negative integer")

    proposer = config.get("proposer", {})
    if proposer is not None:
        if not isinstance(proposer, dict):
            raise ConfigError("proposer must be an object when provided")
        if "enabled" in proposer and not isinstance(proposer["enabled"], bool):
            raise ConfigError("proposer.enabled must be a boolean")
        for key in ["provider", "model_id", "api_base"]:
            if key in proposer and proposer[key] is not None and not isinstance(proposer[key], str):
                raise ConfigError(f"proposer.{key} must be a string when provided")
        if "max_candidates" in proposer and (
            not isinstance(proposer["max_candidates"], int) or proposer["max_candidates"] <= 0
        ):
            raise ConfigError("proposer.max_candidates must be a positive integer")
