#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SPECS_DIR = REPO_ROOT / "specs"

CANONICAL_SPEC_FILES = [
    SPECS_DIR / "README.md",
    SPECS_DIR / "spec.md",
    SPECS_DIR / "architecture.md",
    SPECS_DIR / "contracts.md",
    SPECS_DIR / "ui-review-workflow.md",
    SPECS_DIR / "eval-and-optimizer.md",
    SPECS_DIR / "decisions.md",
    SPECS_DIR / "improvement-ideas.md",
    SPECS_DIR / "experiment-results.md",
    SPECS_DIR / "plan.md",
    SPECS_DIR / "tasks.md",
    SPECS_DIR / "AGENTS.md",
]

ACTIVE_SCAN_ROOTS = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "docs",
    REPO_ROOT / "skills",
    REPO_ROOT / "specs",
    REPO_ROOT / "tools" / "AGENTS.md",
    REPO_ROOT / "tools" / "docs",
]

TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
    ".txt",
    ".tsx",
    ".ts",
    ".js",
    ".jsx",
}

IGNORED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "site",
    ".venv",
    "venv",
}

MOVED_SPEC_PATTERNS = [
    re.compile(r"specs/(product|tools|architecture|process)/"),
    re.compile(
        r"specs/contracts/(run-bundle|proposals-and-evidence|eval-summary|optimizer-candidate)\.md"
    ),
]

CANONICAL_LINK_RE = re.compile(
    r"specs/(README|spec|architecture|contracts|ui-review-workflow|eval-and-optimizer|decisions|improvement-ideas|experiment-results|plan|tasks|AGENTS)\.md"
)

EXPECTED_BENCHMARK_DIRS = {
    "massively_parallel_reporter_assays",
    "genome_editing_tools",
    "spatial_transcriptomics",
}
BAD_SKILL_ROOT = "agent" + "-skills"
COMPATIBILITY_STATUS = "Status: " + "Compatibility reference"


def is_archive(path: Path) -> bool:
    try:
        rel = path.relative_to(SPECS_DIR)
    except ValueError:
        return False
    return bool(rel.parts and rel.parts[0] == "archive")


def iter_text_files() -> list[Path]:
    files: list[Path] = []
    for root in ACTIVE_SCAN_ROOTS:
        if not root.exists():
            continue
        if root.is_file():
            if root.suffix.lower() in TEXT_SUFFIXES:
                files.append(root)
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if any(part in IGNORED_DIR_NAMES for part in path.relative_to(REPO_ROOT).parts):
                continue
            files.append(path)
    return sorted(set(files))


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def check_required_files(errors: list[str]) -> None:
    for path in CANONICAL_SPEC_FILES:
        if not path.exists():
            fail(errors, f"Missing canonical spec file: {rel(path)}")

    schema_dir = SPECS_DIR / "contracts" / "schemas"
    if not schema_dir.exists():
        fail(errors, "Missing machine-readable schema directory: specs/contracts/schemas")
        return
    if not list(schema_dir.glob("*.json")):
        fail(errors, "No JSON schemas found under specs/contracts/schemas")


def check_active_references(errors: list[str]) -> None:
    specs_readme_referenced = False
    stale_hits: list[str] = []
    agent_skill_hits: list[str] = []
    compatibility_hits: list[str] = []

    for path in iter_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        archive = is_archive(path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if "specs/README.md" in line:
                specs_readme_referenced = True
            if BAD_SKILL_ROOT in line and not archive:
                agent_skill_hits.append(f"{rel(path)}:{lineno}: {line.strip()}")
            if COMPATIBILITY_STATUS in line and not archive:
                compatibility_hits.append(f"{rel(path)}:{lineno}: {line.strip()}")
            if not archive:
                normalized = line.replace("\\", "/")
                if any(pattern.search(normalized) for pattern in MOVED_SPEC_PATTERNS):
                    if "archive" not in normalized.lower() and "historical" not in normalized.lower():
                        stale_hits.append(f"{rel(path)}:{lineno}: {line.strip()}")

    if specs_readme_referenced and not (SPECS_DIR / "README.md").exists():
        fail(errors, "Active files reference specs/README.md, but it does not exist")
    if agent_skill_hits:
        fail(errors, f"Active files reference {BAD_SKILL_ROOT} even though the repo uses skills/:\n" + "\n".join(agent_skill_hits))
    if compatibility_hits:
        fail(errors, f"{COMPATIBILITY_STATUS} appears outside specs/archive:\n" + "\n".join(compatibility_hits))
    if stale_hits:
        fail(errors, "Active files reference moved compatibility spec paths:\n" + "\n".join(stale_hits))


def check_canonical_links(errors: list[str]) -> None:
    for path in iter_text_files():
        if is_archive(path):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in CANONICAL_LINK_RE.finditer(text):
            target = REPO_ROOT / match.group(0)
            if not target.exists():
                fail(errors, f"Broken canonical spec link in {rel(path)}: {match.group(0)}")


def check_benchmarks(errors: list[str]) -> None:
    benchmark_root = REPO_ROOT / "benchmark_datasets"
    actual = {
        path.name
        for path in benchmark_root.iterdir()
        if path.is_dir() and path.name != "data"
    } if benchmark_root.exists() else set()
    if actual != EXPECTED_BENCHMARK_DIRS:
        fail(
            errors,
            "Benchmark dataset directories do not match canonical spec expectation: "
            f"actual={sorted(actual)} expected={sorted(EXPECTED_BENCHMARK_DIRS)}",
        )

    for name in EXPECTED_BENCHMARK_DIRS:
        dataset_dir = benchmark_root / name
        for required in ["table_template.csv", "schema.csv", "table_gold.csv", "pdfs"]:
            if not (dataset_dir / required).exists():
                fail(errors, f"Missing benchmark dataset required path: {rel(dataset_dir / required)}")

    spec_text = (SPECS_DIR / "eval-and-optimizer.md").read_text(encoding="utf-8", errors="replace")
    for name in EXPECTED_BENCHMARK_DIRS:
        if name not in spec_text:
            fail(errors, f"eval-and-optimizer.md does not mention active benchmark dataset {name}")


def check_skill_root(errors: list[str]) -> None:
    skills_dir = REPO_ROOT / "skills"
    agent_skills_dir = REPO_ROOT / BAD_SKILL_ROOT
    if not skills_dir.exists():
        fail(errors, "Expected skill root is missing: skills/")
    if agent_skills_dir.exists():
        fail(errors, f"Unexpected active skill root exists: {BAD_SKILL_ROOT}/")
    for skill in ["papers-to-table-agent-kit", "papers-to-table-local-app"]:
        if not (skills_dir / skill).exists():
            fail(errors, f"Missing expected skill directory: skills/{skill}")


def main() -> int:
    errors: list[str] = []
    check_required_files(errors)
    check_active_references(errors)
    check_canonical_links(errors)
    check_benchmarks(errors)
    check_skill_root(errors)

    if errors:
        print("Spec drift check failed:\n", file=sys.stderr)
        for index, error in enumerate(errors, start=1):
            print(f"{index}. {error}\n", file=sys.stderr)
        return 1

    print("Spec drift check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
