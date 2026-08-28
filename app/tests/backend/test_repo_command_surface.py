from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CLI_PATH = REPO_ROOT / "scripts" / "papers_to_table.py"


def _load_cli_module():
    spec = importlib.util.spec_from_file_location("papers_to_table_cli", CLI_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_central_cli_help_commands_exit_successfully():
    commands = [
        [sys.executable, "scripts/papers_to_table.py", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "review", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "preflight", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "headless", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "optimizer", "compare-models", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "optimizer", "full-benchmark", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "docs", "serve", "--help"],
        [sys.executable, "scripts/papers_to_table.py", "docs", "build", "--help"],
    ]

    for command in commands:
        completed = subprocess.run(command, cwd=REPO_ROOT, check=False, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stderr


def test_review_command_accepts_initial_runs_directory():
    cli = _load_cli_module()
    args = cli.build_parser().parse_args(["review", "--runs-dir", "C:/review-runs"])

    assert args.runs_dir == "C:/review-runs"


def test_documented_configs_exist_and_parse():
    json_files = [
        REPO_ROOT / "app" / "config.example.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_models.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_prompts.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_retrieval_parameters.json",
        REPO_ROOT / "tools" / "optimizer" / "configs" / "compare_extraction_features.json",
    ]

    for path in json_files:
        assert path.exists(), str(path)
        json.loads(path.read_text(encoding="utf-8"))


def test_documented_command_surface_files_exist():
    required_paths = [
        REPO_ROOT / "LICENSE",
        REPO_ROOT / "NOTICE",
        REPO_ROOT / "scripts" / "papers_to_table.py",
        REPO_ROOT / ".readthedocs.yaml",
        REPO_ROOT / "tools" / "docs" / "mkdocs.yml",
        REPO_ROOT / "tools" / "docs" / "requirements.txt",
        REPO_ROOT / "docs" / "README.md",
        REPO_ROOT / "docs" / "main-app" / "browser-review.md",
        REPO_ROOT / "docs" / "main-app" / "headless.md",
        REPO_ROOT / "docs" / "main-app" / "outputs-and-artifacts.md",
        REPO_ROOT / "docs" / "tools" / "eval.md",
        REPO_ROOT / "docs" / "tools" / "optimizer.md",
        REPO_ROOT / "docs" / "tools" / "papers-to-table-agent-kit.md",
        REPO_ROOT / "docs" / "tools" / "papers-to-table-local-app.md",
        REPO_ROOT / "docs" / "getting-started" / "troubleshooting.md",
        REPO_ROOT / "specs" / "spec.md",
        REPO_ROOT / "specs" / "architecture.md",
    ]

    for path in required_paths:
        assert path.exists(), str(path)


def test_readthedocs_config_uses_the_current_mkdocs_surface():
    config = (REPO_ROOT / ".readthedocs.yaml").read_text(encoding="utf-8")

    assert "version: 2" in config
    assert "configuration: tools/docs/mkdocs.yml" in config
    assert "requirements: tools/docs/requirements.txt" in config


def test_project_license_is_apache_2_0():
    license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8")
    notice_text = (REPO_ROOT / "NOTICE").read_text(encoding="utf-8")

    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "MIT License" not in license_text
    assert "Copyright 2026 jjfroehlich" in notice_text


def test_cli_resolves_path_executables_before_launch(monkeypatch):
    cli = _load_cli_module()
    monkeypatch.setattr(cli.shutil, "which", lambda name: f"C:/tools/{name}.CMD" if name == "npm" else None)

    assert cli._resolve_cmd(["npm", "--version"]) == ["C:/tools/npm.CMD", "--version"]


def test_install_runs_frontend_audit_fix_and_gate(monkeypatch):
    cli = _load_cli_module()
    commands = []

    def record_run(cmd, *, cwd, env=None):
        commands.append((cmd, cwd))
        return 0

    monkeypatch.setattr(cli, "_run", record_run)

    assert cli.cmd_install(object()) == 0
    assert commands[0] == ([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], cli.REPO_ROOT)
    assert (["npm", "audit", "fix"], cli.FRONTEND_DIR) in commands
    assert (["npm", "audit", "--audit-level=moderate"], cli.FRONTEND_DIR) in commands
