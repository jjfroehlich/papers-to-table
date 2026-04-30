from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_central_cli_help_commands_exit_successfully():
    commands = [
        [sys.executable, "scripts/papers_to_table.py", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "preflight", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "headless", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "optimizer", "compare-models", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "optimizer", "optimize-one-model", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "optimizer", "overnight", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "docs", "serve", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "docs", "build", "--help"],
    ]

    for command in commands:
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr


def test_documented_configs_exist_and_parse():
    json_files = [
        REPO_ROOT / "app" / "config.example.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_models.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_prompts.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_retrieval.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_retrieval_modes.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "optimize_one_model.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_models_overnight.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "optimize_overnight.json",
    ]

    for path in json_files:
        assert path.exists(), str(path)
        json.loads(path.read_text(encoding="utf-8"))


def test_documented_command_surface_files_exist():
    required_paths = [
        REPO_ROOT / "scripts" / "papers_to_table.py",
        REPO_ROOT / "tools" / "docs" / "mkdocs.yml",
        REPO_ROOT / "tools" / "docs" / "requirements.txt",
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "docs" / "main-app" / "browser-review.md",
        REPO_ROOT / "docs" / "main-app" / "headless.md",
        REPO_ROOT / "docs" / "main-app" / "outputs-and-artifacts.md",
        REPO_ROOT / "docs" / "tools" / "eval.md",
        REPO_ROOT / "docs" / "tools" / "optimizer.md",
        REPO_ROOT / "docs" / "agents" / "papers-to-table-skill.md",
        REPO_ROOT / "docs" / "troubleshooting.md",
        REPO_ROOT / "specs" / "spec.md",
        REPO_ROOT / "specs" / "research.md",
    ]

    for path in required_paths:
        assert path.exists(), str(path)
