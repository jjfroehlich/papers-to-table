"""
E2e scaffolding: run-launch and status workflow.

These tests are opt-in (marked 'e2e') and require the full stack running.
They serve as the scaffolding that Batch 2+ will build on when the pipeline
is fully implemented.

To run:
    pytest tests/e2e -m e2e --base-url http://localhost:5173
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def backend_url() -> str:
    return "http://localhost:8000"


@pytest.fixture(scope="session")
def frontend_url() -> str:
    return "http://localhost:5173"


@pytest.mark.skip(reason="e2e tests require live server; run with: pytest tests/e2e -m e2e")
def test_health_endpoint_reachable(backend_url: str):
    """Backend /api/health returns 200."""
    import urllib.request
    with urllib.request.urlopen(f"{backend_url}/api/health") as resp:
        assert resp.status == 200


@pytest.mark.skip(reason="e2e tests require live server; run with: pytest tests/e2e -m e2e")
def test_frontend_loads(page, frontend_url: str):
    """Frontend serves and shows the main UI."""
    page.goto(frontend_url)
    page.wait_for_selector("h1", timeout=5000)
    assert "Paper Table Agent" in page.title() or page.locator("h1").inner_text() == "Paper Table Agent"


@pytest.mark.skip(reason="e2e tests require live server; run with: pytest tests/e2e -m e2e")
def test_run_view_shows_create_run_form(page, frontend_url: str):
    """Run view shows the config path input and Create Run button."""
    page.goto(frontend_url)
    page.wait_for_selector("input[placeholder*='config']", timeout=5000)
    assert page.locator("button:has-text('Create Run')").is_visible()


@pytest.mark.skip(reason="e2e tests require live server; run with: pytest tests/e2e -m e2e")
def test_review_tab_disabled_without_completed_run(page, frontend_url: str):
    """Review tab is disabled when no completed run is selected."""
    page.goto(frontend_url)
    review_btn = page.locator("button:has-text('Review')")
    assert review_btn.is_disabled()


@pytest.mark.skip(reason="e2e tests require live server; run with: pytest tests/e2e -m e2e")
def test_empty_run_list_shows_guidance(page, frontend_url: str):
    """Empty run list shows next-action guidance."""
    page.goto(frontend_url)
    assert page.locator("text=No runs yet").is_visible() or page.locator("text=config.json").is_visible()


@pytest.mark.skip(reason="e2e tests require live server; run with: pytest tests/e2e -m e2e")
def test_create_run_with_invalid_config_shows_error(page, frontend_url: str):
    """Creating a run with a nonexistent config shows an error message."""
    page.goto(frontend_url)
    page.fill("input[placeholder*='config']", "/nonexistent/config.json")
    page.click("button:has-text('Create Run')")
    page.wait_for_selector("[class*='red']", timeout=5000)


@pytest.mark.skip(reason="e2e tests require live server; run with: pytest tests/e2e -m e2e")
def test_create_run_completes_and_shows_detail(page, frontend_url: str):
    """Full happy path: create run with example config, see it complete."""
    page.goto(frontend_url)
    page.fill("input[placeholder*='config']", "config.example.json")
    page.click("button:has-text('Create Run')")
    # Wait for run to appear in list
    page.wait_for_selector("[class*='run_']", timeout=10000)
    # Wait for completion (pipeline stub completes fast)
    page.wait_for_selector("text=Completed", timeout=15000)
