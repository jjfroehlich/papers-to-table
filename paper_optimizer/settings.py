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

    optimize = config.get("optimize", {})
    if not isinstance(optimize, dict):
        raise ConfigError("optimize must be an object when provided")

    rounds = optimize.get("rounds", 0)
    if not isinstance(rounds, int) or rounds < 0:
        raise ConfigError("optimize.rounds must be a non-negative integer")

    batch_size = optimize.get("batch_size", 1)
    if not isinstance(batch_size, int) or batch_size <= 0:
        raise ConfigError("optimize.batch_size must be a positive integer")
