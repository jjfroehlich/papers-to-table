"""Refresh README screenshots from deterministic Playwright UI states."""
from __future__ import annotations

import pathlib

import pytest
from playwright.sync_api import Page, expect

from .demo_stack import DemoRunIds

pytestmark = pytest.mark.e2e
APP_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _open_review_workspace(page: Page, frontend_url: str, run_id: str) -> None:
    page.goto(frontend_url)
    run_item = page.locator("[data-testid='run-item']", has_text=run_id)
    expect(run_item).to_be_visible()
    run_item.click()
    review_tab = page.get_by_role("button", name="Review")
    expect(review_tab).to_be_enabled()
    review_tab.click()
    expect(page.locator("[data-testid='review-workspace']")).to_be_visible()


def _capture(locator, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    locator.screenshot(path=str(path))


def test_capture_readme_screenshots(
    page: Page,
    frontend_url: str,
    demo_run_ids: DemoRunIds,
    docs_screenshot_dir: pathlib.Path,
    capture_doc_screenshots: bool,
):
    if not capture_doc_screenshots:
        pytest.skip("Run with --capture-doc-screenshots to refresh README images.")

    page.set_viewport_size({"width": 1680, "height": 1180})

    page.goto(frontend_url)
    page.get_by_placeholder("e.g. config.example.json").fill(str(APP_ROOT / "config.example.json"))
    page.get_by_role("button", name="▼ Show optional path overrides").click()
    page.get_by_role("button", name="Run preflight").click()
    expect(page.get_by_text("Resolved launch context")).to_be_visible()
    _capture(page.locator("[data-testid='run-launch-surface']"), docs_screenshot_dir / "run-setup.png")

    _open_review_workspace(page, frontend_url, demo_run_ids.screenshots)
    page.wait_for_timeout(1500)
    _capture(page.locator("[data-testid='review-workspace']"), docs_screenshot_dir / "review-workspace.png")

    page.get_by_role("button", name="Accept", exact=True).click()
    expect(page.get_by_text("HEK293T", exact=True)).to_be_visible()
    page.get_by_role("button", name="Export reviewed workbook").click()
    expect(page.get_by_text("Export completed at")).to_be_visible()
    page.get_by_role("button", name="Diagnostics & run inspection").click()
    _capture(page.locator("[data-testid='review-workspace']"), docs_screenshot_dir / "export-diagnostics.png")
