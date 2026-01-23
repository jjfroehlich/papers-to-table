from __future__ import annotations

import re
from pathlib import Path


def run_doctor(verbose: bool = False) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    errors: list[str] = []
    warnings: list[str] = []

    cli_commands = _cli_commands(repo_root / "paper_table_agent" / "cli.py")
    readme_path = repo_root / "README.md"
    spec_paths = [
        repo_root / "specs" / "spec.md",
        repo_root / "specs" / "plan.md",
        repo_root / "specs" / "tasks.md",
    ]

    if not readme_path.exists():
        errors.append("README.md is missing.")
    else:
        readme_text = readme_path.read_text(encoding="utf-8")
        commands = _commands_in_text(readme_text)
        missing_commands = sorted(set(commands) - cli_commands)
        if missing_commands:
            errors.append(f"README references unknown CLI commands: {', '.join(missing_commands)}")
        errors.extend(_missing_paths(readme_text, repo_root, source="README.md"))

    for spec_path in spec_paths:
        if not spec_path.exists():
            errors.append(f"Missing spec file: {spec_path.relative_to(repo_root)}")
            continue
        text = spec_path.read_text(encoding="utf-8").strip()
        if not text:
            errors.append(f"Spec file is empty: {spec_path.relative_to(repo_root)}")
        errors.extend(_missing_paths(text, repo_root, source=str(spec_path.relative_to(repo_root))))

    errors.extend(_check_spec_consistency(spec_paths, repo_root))

    _print_report(errors, warnings, verbose)
    return 1 if errors else 0


def _cli_commands(cli_path: Path) -> set[str]:
    if not cli_path.exists():
        return set()
    text = cli_path.read_text(encoding="utf-8")
    return set(re.findall(r'add_parser\("([a-z0-9\-]+)"', text))


def _commands_in_text(text: str) -> list[str]:
    return re.findall(r"paper-table-agent\\s+([a-z0-9\\-]+)", text)


def _missing_paths(text: str, repo_root: Path, source: str) -> list[str]:
    errors: list[str] = []
    cleaned = re.sub(r"```.*?```", "", text, flags=re.S)
    runtime_outputs = {
        "proposals.sqlite",
        "run_report.json",
        "checkpoints.sqlite",
        "updated_table.xlsx",
        "audit_log.csv",
        "pdf_row_matches.csv",
        "mapping_report.html",
        "proposals.jsonl",
        "run.log",
    }
    runtime_prefixes = ("runs/", "exports/", "artifacts/", "logs/")
    for match in re.findall(r"`([^`\n]+)`", cleaned):
        if match.startswith("http"):
            continue
        if "paper-table-agent" in match:
            continue
        if "<" in match or ">" in match or "..." in match:
            continue
        if match in runtime_outputs or match.startswith(runtime_prefixes):
            continue
        if "=" in match and "/" not in match:
            continue
        if "/" not in match and "." in match and not match.endswith(
            (".md", ".py", ".json", ".csv", ".xlsx", ".sql", ".jsonl", ".txt")
        ):
            continue
        if "/" not in match and "." not in match:
            continue
        candidate = (repo_root / match).resolve()
        if not candidate.exists():
            errors.append(f"{source} references missing path: {match}")
    return errors


def _check_spec_consistency(spec_paths: list[Path], repo_root: Path) -> list[str]:
    errors: list[str] = []
    plan_path = repo_root / "specs" / "plan.md"
    tasks_path = repo_root / "specs" / "tasks.md"
    if not plan_path.exists() or not tasks_path.exists():
        return errors
    plan_text = plan_path.read_text(encoding="utf-8")
    tasks_text = tasks_path.read_text(encoding="utf-8")
    plan_phases = set(re.findall(r"Phase\\s+(P\\d+)", plan_text))
    task_phases = set(re.findall(r"\\*\\*(P\\d+)\\.", tasks_text))
    missing_in_plan = sorted(task_phases - plan_phases)
    if missing_in_plan:
        errors.append(f"Tasks reference phases missing in plan.md: {', '.join(missing_in_plan)}")
    return errors


def _print_report(errors: list[str], warnings: list[str], verbose: bool) -> None:
    print("Doctor report:")
    if errors:
        print("  Errors:")
        for error in errors:
            print(f"    - {error}")
    if warnings:
        print("  Warnings:")
        for warning in warnings:
            print(f"    - {warning}")
    if not errors and not warnings:
        print("  OK: no issues found.")
    if verbose and not errors:
        print("  CLI commands and docs/specs are consistent.")
