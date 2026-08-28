"""Refresh documentation screenshots from deterministic Playwright UI states."""
from __future__ import annotations

import pathlib

import pytest
from playwright.sync_api import Page, expect

from .demo_stack import DemoRunIds

pytestmark = pytest.mark.e2e
APP_DIR = pathlib.Path(__file__).resolve().parents[2]


def _open_review_workspace(page: Page, frontend_url: str, run_id: str) -> None:
    page.goto(frontend_url)
    run_item = page.locator("[data-testid='run-item']", has_text=run_id)
    expect(run_item).to_be_visible()
    run_item.click()
    review_tab = page.get_by_role("button", name="Review", exact=True)
    expect(review_tab).to_be_enabled()
    review_tab.click()
    expect(page.locator("[data-testid='review-workspace']")).to_be_visible()


def _select_run(page: Page, run_id: str) -> None:
    run_item = page.locator("[data-testid='run-item']", has_text=run_id)
    expect(run_item).to_be_visible()
    run_item.click()


def _capture(locator, path: pathlib.Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    locator.screenshot(path=str(path))


def _focus_primary_pdf_highlight(page: Page) -> None:
    highlight = page.get_by_test_id("evidence-highlight-primary")
    expect(highlight).to_be_visible()
    highlight.evaluate(
        "(node) => node.scrollIntoView({ behavior: 'instant', block: 'center', inline: 'center' })"
    )
    page.wait_for_timeout(150)


def test_capture_documentation_screenshots(
    page: Page,
    frontend_url: str,
    demo_run_ids: DemoRunIds,
    docs_screenshot_dir: pathlib.Path,
    capture_doc_screenshots: bool,
):
    if not capture_doc_screenshots:
        pytest.skip("Run with --capture-doc-screenshots to refresh documentation images.")

    page.set_viewport_size({"width": 1680, "height": 1180})

    page.goto(frontend_url)
    expect(page.locator("[data-testid='run-launch-surface']")).to_be_visible()
    _capture(page.locator("[data-testid='run-launch-surface']"), docs_screenshot_dir / "run-setup.png")

    _select_run(page, demo_run_ids.screenshots)
    page.wait_for_timeout(500)
    _capture(page.locator("main"), docs_screenshot_dir / "run-screen-cleanup.png")

    _open_review_workspace(page, frontend_url, demo_run_ids.screenshots)
    page.wait_for_timeout(1500)
    page.get_by_role("button", name="By Paper").click()
    expect(page.get_by_test_id("proposal-queue-scroll")).to_be_visible()
    _focus_primary_pdf_highlight(page)
    _capture(page.locator("[data-testid='review-workspace']"), docs_screenshot_dir / "review-workspace.png")

    page.get_by_role("button", name="Diagnostics").click()
    expect(page.get_by_role("heading", name="Run diagnostics")).to_be_visible()
    _capture(page.locator("[data-testid='review-workspace']"), docs_screenshot_dir / "review-diagnostics-open.png")
    page.get_by_role("button", name="Close").click()

    queue_scroll = page.get_by_test_id("proposal-queue-scroll")
    queue_scroll.evaluate("(node) => { node.scrollTop = Math.max(node.scrollHeight * 0.45, 240); return node.scrollTop; }")
    page.wait_for_timeout(300)
    _focus_primary_pdf_highlight(page)
    _capture(page.locator("[data-testid='review-workspace']"), docs_screenshot_dir / "review-queue-scrolled.png")

    _focus_primary_pdf_highlight(page)
    _capture(page.locator("[data-testid='review-workspace']"), docs_screenshot_dir / "review-evidence-scrolled.png")

    page.get_by_role("button", name="Accept", exact=True).click()
    expect(page.get_by_text("HEK293T", exact=True).first).to_be_visible()
    page.locator("select").select_option("all")
    species_card = page.locator("button[data-proposal-id]", has_text="Species")
    expect(species_card).to_be_visible()
    species_card.click()
    _focus_primary_pdf_highlight(page)
    page.get_by_role("button", name="Export reviewed workbook").click()
    expect(page.get_by_text("Export completed at")).to_be_visible()
    page.get_by_role("button", name="Diagnostics").click()
    _capture(page.locator("[data-testid='review-workspace']"), docs_screenshot_dir / "export-diagnostics.png")
