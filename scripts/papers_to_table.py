#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
APP_DIR = REPO_ROOT / "app"
BACKEND_SRC_DIR = APP_DIR / "backend" / "src"
FRONTEND_DIR = APP_DIR / "frontend"
EVAL_DIR = REPO_ROOT / "tools" / "eval"
OPTIMIZER_DIR = REPO_ROOT / "tools" / "optimizer"
MKDOCS_CONFIG = REPO_ROOT / "tools" / "docs" / "mkdocs.yml"
DOCS_REQUIREMENTS = REPO_ROOT / "tools" / "docs" / "requirements.txt"


def _env_with_pythonpath(*extra_paths: Path) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath_parts = [str(path) for path in extra_paths]
    existing = env.get("PYTHONPATH")
    if existing:
        pythonpath_parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def _resolve_executable(name: str) -> str | None:
    if os.path.dirname(name):
        return name
    return shutil.which(name)


def _resolve_cmd(cmd: list[str]) -> list[str] | None:
    executable = _resolve_executable(cmd[0])
    if executable is None:
        print(
            f"Required executable '{cmd[0]}' was not found on PATH. "
            "Install it or start a shell where it is available, then rerun the command.",
            file=sys.stderr,
        )
        return None
    return [executable, *cmd[1:]]


def _run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> int:
    resolved_cmd = _resolve_cmd(cmd)
    if resolved_cmd is None:
        return 127
    completed = subprocess.run(resolved_cmd, cwd=str(cwd), env=env, check=False)
    return int(completed.returncode)


def _popen(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.Popen[bytes] | None:
    resolved_cmd = _resolve_cmd(cmd)
    if resolved_cmd is None:
        return None
    return subprocess.Popen(resolved_cmd, cwd=str(cwd), env=env)


def _mkdocs_cmd(subcommand: str) -> list[str] | None:
    mkdocs_bin = shutil.which("mkdocs")
    if mkdocs_bin is not None:
        return [mkdocs_bin, subcommand, "-f", str(MKDOCS_CONFIG)]
    try:
        import mkdocs  # type: ignore  # noqa: F401
    except Exception:
        print(
            f"mkdocs is not installed. Install docs dependencies with: python -m pip install -r {DOCS_REQUIREMENTS.relative_to(REPO_ROOT).as_posix()}",
            file=sys.stderr,
        )
        return None
    return [sys.executable, "-m", "mkdocs", subcommand, "-f", str(MKDOCS_CONFIG)]


def _optimizer_default_out(name: str) -> Path:
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return OPTIMIZER_DIR / "runs" / f"{name}_{timestamp}"


def cmd_install(_args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(BACKEND_SRC_DIR, EVAL_DIR, OPTIMIZER_DIR)
    commands = [
        ([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], REPO_ROOT),
        ([sys.executable, "-m", "pip", "install", "-e", "./backend[test]"], APP_DIR),
        (["npm", "install"], FRONTEND_DIR),
        (["npm", "audit", "fix"], FRONTEND_DIR),
        (["npm", "audit", "--audit-level=moderate"], FRONTEND_DIR),
        ([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], EVAL_DIR),
        ([sys.executable, "-m", "pip", "install", "-e", ".[dev]"], OPTIMIZER_DIR),
    ]
    for cmd, cwd in commands:
        exit_code = _run(cmd, cwd=cwd, env=env)
        if exit_code != 0:
            return exit_code
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(BACKEND_SRC_DIR)
    backend_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--reload",
        "--host",
        args.backend_host,
        "--port",
        str(args.backend_port),
    ]
    frontend_cmd = [
        "npm",
        "run",
        "dev",
        "--",
        "--host",
        args.frontend_host,
        "--port",
        str(args.frontend_port),
    ]

    backend = _popen(backend_cmd, cwd=APP_DIR, env=env)
    if backend is None:
        return 127
    frontend = None
    try:
        health_url = f"http://{args.backend_host}:{args.backend_port}/api/health"
        for _ in range(60):
            if backend.poll() is not None:
                return int(backend.returncode or 1)
            try:
                with urllib.request.urlopen(health_url, timeout=1):
                    break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(1)
        frontend = _popen(frontend_cmd, cwd=FRONTEND_DIR, env=os.environ.copy())
        if frontend is None:
            return 127
        print(
            f"papers-to-table review mode ready.\n"
            f"Backend:  {health_url}\n"
            f"Frontend: http://{args.frontend_host}:{args.frontend_port}\n"
            f"Press Ctrl+C to stop both processes.",
            flush=True,
        )
        while True:
            if backend.poll() is not None:
                return int(backend.returncode or 1)
            if frontend.poll() is not None:
                return int(frontend.returncode or 1)
            time.sleep(1)
    except KeyboardInterrupt:
        return 130
    finally:
        for process in (frontend, backend):
            if process is None or process.poll() is not None:
                continue
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()




def _resolve_repo_path(path_value: str) -> str:
    candidate = Path(path_value)
    if candidate.is_absolute():
        return str(candidate)
    repo_candidate = (REPO_ROOT / candidate).resolve()
    if repo_candidate.exists():
        return str(repo_candidate)
    return path_value

def _backend_automation_cmd(args: argparse.Namespace, command: str) -> list[str]:
    cmd = [sys.executable, "-m", "backend.app.automation", command, "--config-path", _resolve_repo_path(args.config)]
    if args.table_path:
        cmd.extend(["--table-path", args.table_path])
    if args.schema_path:
        cmd.extend(["--schema-path", args.schema_path])
    if args.pdf_dir:
        cmd.extend(["--pdf-dir", args.pdf_dir])
    timeout = getattr(args, "timeout_seconds", None)
    if timeout is not None:
        cmd.extend(["--timeout-seconds", str(timeout)])
    return cmd


def cmd_preflight(args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(BACKEND_SRC_DIR)
    return _run(_backend_automation_cmd(args, "preflight"), cwd=APP_DIR, env=env)


def cmd_headless(args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(BACKEND_SRC_DIR)
    cmd = _backend_automation_cmd(args, "headless")
    if args.accept_all:
        cmd.append("--accept-all")
    if args.export:
        cmd.append("--export")
    return _run(cmd, cwd=APP_DIR, env=env)




def cmd_verify_contract(args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(BACKEND_SRC_DIR)
    cmd = [sys.executable, "-m", "backend.app.contract_verify_cli", "--run", args.run]
    if args.json:
        cmd.append("--json")
    return _run(cmd, cwd=APP_DIR, env=env)

def cmd_eval(args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(EVAL_DIR)
    cmd = [sys.executable, "-m", "paper_eval", "evaluate"]
    if args.run:
        cmd.extend(["--run", args.run])
    if args.runs_root:
        cmd.extend(["--runs-root", args.runs_root])
    cmd.extend(["--gold", args.gold, "--out", args.out])
    if args.schema:
        cmd.extend(["--schema", args.schema])
    if args.judge_model:
        cmd.extend(["--judge-model", args.judge_model])
    if args.judge_model_b:
        cmd.extend(["--judge-model-b", args.judge_model_b])
    if args.gold_sheet:
        cmd.extend(["--gold-sheet", args.gold_sheet])
    if args.judge_api_base:
        cmd.extend(["--judge-api-base", args.judge_api_base])
    if args.judge_api_base_b:
        cmd.extend(["--judge-api-base-b", args.judge_api_base_b])
    if args.json_output:
        cmd.extend(["--json-output", args.json_output])
    return _run(cmd, cwd=EVAL_DIR, env=env)


def cmd_optimizer_compare(args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(OPTIMIZER_DIR, EVAL_DIR, BACKEND_SRC_DIR)
    config = args.config or str(OPTIMIZER_DIR / "configs" / "compare_models.json")
    out = args.out or str(_optimizer_default_out("compare_models"))
    cmd = [sys.executable, "-m", "paper_optimizer.cli", "optimize", "--study-type", "compare", "--config", config, "--out", out]
    return _run(cmd, cwd=OPTIMIZER_DIR, env=env)


def cmd_optimizer_optimize_one_model(args: argparse.Namespace) -> int:
    env = _env_with_pythonpath(OPTIMIZER_DIR, EVAL_DIR, BACKEND_SRC_DIR)
    config = args.config or str(OPTIMIZER_DIR / "configs" / "optimize_one_model.json")
    out = args.out or str(_optimizer_default_out("optimize_one_model"))
    cmd = [sys.executable, "-m", "paper_optimizer.cli", "optimize", "--study-type", "optimize", "--config", config, "--out", out]
    return _run(cmd, cwd=OPTIMIZER_DIR, env=env)


def cmd_optimizer_overnight(args: argparse.Namespace) -> int:
    label = args.label or f"overnight_{time.strftime('%Y%m%d-%H%M%S')}"
    cmd = ["bash", str(OPTIMIZER_DIR / "scripts" / "run_overnight.sh"), label]
    return _run(cmd, cwd=OPTIMIZER_DIR, env=os.environ.copy())


def cmd_docs_serve(args: argparse.Namespace) -> int:
    cmd = _mkdocs_cmd("serve")
    if cmd is None:
        return 2
    cmd.extend(["--dev-addr", f"{args.host}:{args.port}"])
    return _run(cmd, cwd=REPO_ROOT, env=os.environ.copy())


def cmd_docs_build(args: argparse.Namespace) -> int:
    cmd = _mkdocs_cmd("build")
    if cmd is None:
        return 2
    if args.strict:
        cmd.append("--strict")
    return _run(cmd, cwd=REPO_ROOT, env=os.environ.copy())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="papers-to-table")
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="Install backend, frontend, eval, and optimizer dependencies")
    install.set_defaults(func=cmd_install)

    review = subparsers.add_parser("review", help="Start backend and frontend together for browser review mode")
    review.add_argument("--backend-host", default="127.0.0.1")
    review.add_argument("--backend-port", type=int, default=8000)
    review.add_argument("--frontend-host", default="127.0.0.1")
    review.add_argument("--frontend-port", type=int, default=5173)
    review.set_defaults(func=cmd_review)

    for name, help_text, handler in (
        ("preflight", "Run main-app preflight from the terminal", cmd_preflight),
        ("headless", "Run main-app extraction without the browser UI", cmd_headless),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("--config", required=True)
        sub.add_argument("--table-path")
        sub.add_argument("--schema-path")
        sub.add_argument("--pdf-dir")
        sub.add_argument("--timeout-seconds", type=float)
        if name == "headless":
            sub.add_argument("--accept-all", action="store_true")
            sub.add_argument("--export", action="store_true")
        sub.set_defaults(func=handler)

    verify_cmd = subparsers.add_parser("verify-contract", help="Validate run-bundle artifact contracts")
    verify_cmd.add_argument("--run", required=True, help="Path to run bundle directory")
    verify_cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    verify_cmd.set_defaults(func=cmd_verify_contract)

    eval_cmd = subparsers.add_parser("eval", help="Evaluate one run bundle or a runs root")
    eval_cmd.add_argument("--run")
    eval_cmd.add_argument("--runs-root")
    eval_cmd.add_argument("--gold", required=True)
    eval_cmd.add_argument("--schema")
    eval_cmd.add_argument("--out", required=True)
    eval_cmd.add_argument("--judge-model")
    eval_cmd.add_argument("--judge-model-b")
    eval_cmd.add_argument("--gold-sheet", help="Gold workbook sheet name override for reproducible eval joins")
    eval_cmd.add_argument("--judge-api-base", help="Primary judge API base URL")
    eval_cmd.add_argument("--judge-api-base-b", help="Secondary judge API base URL for dual-judge mode")
    eval_cmd.add_argument("--json-output", help="Path to write machine-readable eval JSON output")
    eval_cmd.set_defaults(func=cmd_eval)

    optimizer = subparsers.add_parser("optimizer", help="Run optimizer companion workflows")
    optimizer_sub = optimizer.add_subparsers(dest="optimizer_command", required=True)

    compare = optimizer_sub.add_parser("compare-models", help="Run the canonical compare-models study")
    compare.add_argument("--config")
    compare.add_argument("--out")
    compare.set_defaults(func=cmd_optimizer_compare)

    optimize_one = optimizer_sub.add_parser("optimize-one-model", help="Run the canonical single-model optimize study")
    optimize_one.add_argument("--config")
    optimize_one.add_argument("--out")
    optimize_one.set_defaults(func=cmd_optimizer_optimize_one_model)

    overnight = optimizer_sub.add_parser("overnight", help="Run the multi-stage overnight optimizer workflow")
    overnight.add_argument("--label")
    overnight.set_defaults(func=cmd_optimizer_overnight)

    docs = subparsers.add_parser("docs", help="Serve or build the MkDocs manual")
    docs_sub = docs.add_subparsers(dest="docs_command", required=True)

    docs_serve = docs_sub.add_parser("serve", help="Serve docs locally")
    docs_serve.add_argument("--host", default="127.0.0.1")
    docs_serve.add_argument("--port", type=int, default=8001)
    docs_serve.set_defaults(func=cmd_docs_serve)

    docs_build = docs_sub.add_parser("build", help="Build static docs")
    docs_build.add_argument("--strict", action="store_true")
    docs_build.set_defaults(func=cmd_docs_build)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
