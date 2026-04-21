"""Playwright-backed e2e fixtures for review/export coverage and docs screenshots."""
from __future__ import annotations

import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

from .demo_stack import DemoRunIds, prepare_demo_runtime

APP_DIR = pathlib.Path(__file__).resolve().parents[2]
REPO_ROOT = APP_DIR.parent


def pytest_addoption(parser):
    parser.addoption(
        "--capture-doc-screenshots",
        action="store_true",
        default=False,
        help="Write refreshed README screenshots into docs/screenshots.",
    )
    parser.addoption(
        "--docs-screenshot-dir",
        action="store",
        default=str(REPO_ROOT / "docs" / "screenshots"),
        help="Destination directory for refreshed docs screenshots.",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: end-to-end tests requiring Playwright")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_http(url: str, timeout_seconds: int = 60) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}")


def _stop_process(process: subprocess.Popen[str] | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


@pytest.fixture(scope="session")
def live_stack(tmp_path_factory) -> dict[str, object]:
    runtime_root = tmp_path_factory.mktemp("playwright-runtime")
    demo_runtime = prepare_demo_runtime(runtime_root, APP_DIR)
    backend_port = _find_free_port()
    frontend_port = _find_free_port()
    backend_url = f"http://127.0.0.1:{backend_port}"
    frontend_url = f"http://127.0.0.1:{frontend_port}"

    backend_log = (runtime_root / "backend.log").open("w", encoding="utf-8")
    frontend_log = (runtime_root / "frontend.log").open("w", encoding="utf-8")

    backend_env = os.environ.copy()
    backend_env["PYTHONPATH"] = str(APP_DIR) + os.pathsep + backend_env.get("PYTHONPATH", "")
    backend_env["PAPER_APP_CORS_ORIGINS"] = ",".join(
        [frontend_url, "http://localhost:5173", "http://127.0.0.1:5173"]
    )
    backend_process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(backend_port),
        ],
        cwd=str(runtime_root),
        env=backend_env,
        stdout=backend_log,
        stderr=subprocess.STDOUT,
        text=True,
    )

    frontend_env = os.environ.copy()
    frontend_env["VITE_API_BASE_URL"] = backend_url
    frontend_process = subprocess.Popen(
        [_npm_command(), "run", "dev", "--", "--host", "127.0.0.1", "--port", str(frontend_port)],
        cwd=str(APP_DIR / "frontend"),
        env=frontend_env,
        stdout=frontend_log,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        _wait_for_http(f"{backend_url}/api/health")
        _wait_for_http(frontend_url)
        yield {
            "backend_url": backend_url,
            "frontend_url": frontend_url,
            "runtime_root": runtime_root,
            "demo_runtime": demo_runtime,
        }
    finally:
        _stop_process(frontend_process)
        _stop_process(backend_process)
        backend_log.close()
        frontend_log.close()


@pytest.fixture(scope="session")
def backend_url(live_stack: dict[str, object]) -> str:
    return str(live_stack["backend_url"])


@pytest.fixture(scope="session")
def frontend_url(live_stack: dict[str, object]) -> str:
    return str(live_stack["frontend_url"])


@pytest.fixture(scope="session")
def demo_run_ids(live_stack: dict[str, object]) -> DemoRunIds:
    demo_runtime = live_stack["demo_runtime"]
    assert hasattr(demo_runtime, "run_ids")
    return demo_runtime.run_ids  # type: ignore[return-value]


@pytest.fixture(scope="session")
def docs_screenshot_dir(pytestconfig) -> pathlib.Path:
    return pathlib.Path(pytestconfig.getoption("--docs-screenshot-dir")).resolve()


@pytest.fixture(scope="session")
def capture_doc_screenshots(pytestconfig) -> bool:
    return bool(pytestconfig.getoption("--capture-doc-screenshots"))
