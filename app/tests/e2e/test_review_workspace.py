"""Playwright coverage for the fast review loop and explicit export workflow."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from .demo_stack import DemoRunIds

pytestmark = pytest.mark.e2e


def _open_review_workspace(page: Page, frontend_url: str, run_id: str) -> None:
    page.goto(frontend_url)
    run_item = page.locator("[data-testid='run-item']", has_text=run_id)
    expect(run_item).to_be_visible()
    run_item.click()
    review_tab = page.get_by_role("button", name="Review", exact=True)
    expect(review_tab).to_be_enabled()
    review_tab.click()
    expect(page.locator("[data-testid='review-workspace']")).to_be_visible()
    expect(page.locator("[data-testid='review-toolbar']")).to_contain_text("reviewed")


def test_fast_sequential_review_supports_auto_advance_and_evidence_cycling(
    page: Page,
    frontend_url: str,
    demo_run_ids: DemoRunIds,
):
    _open_review_workspace(page, frontend_url, demo_run_ids.review)

    expect(page.get_by_text("human", exact=True).first).to_be_visible()
    page.get_by_role("button", name="Next evidence").click()
    expect(page.get_by_text("Text fallback – exact highlighting unavailable")).to_be_visible()

    page.get_by_role("button", name="Accept", exact=True).click()

    expect(page.get_by_text("HEK293T", exact=True).first).to_be_visible()


def test_review_workspace_keeps_export_manual(
    page: Page,
    frontend_url: str,
    demo_run_ids: DemoRunIds,
):
    _open_review_workspace(page, frontend_url, demo_run_ids.export)

    expect(page.get_by_role("link", name="Workbook")).to_have_count(0)
    page.get_by_role("button", name="Accept", exact=True).click()
    expect(page.get_by_text("HEK293T", exact=True).first).to_be_visible()

    page.get_by_role("button", name="Export reviewed workbook").click()

    expect(page.get_by_text("Export completed at")).to_be_visible()
    expect(page.get_by_role("link", name="Workbook")).to_be_visible()
    expect(page.get_by_role("link", name="Audit log")).to_be_visible()
    expect(page.get_by_role("link", name="Run summary")).to_be_visible()
    expect(page.get_by_role("link", name="Reviewer summary")).to_be_visible()


def test_review_workspace_exposes_warning_truth_and_unresolved_panel(
    page: Page,
    frontend_url: str,
    demo_run_ids: DemoRunIds,
):
    _open_review_workspace(page, frontend_url, demo_run_ids.review)

    expect(page.get_by_test_id("review-toolbar").get_by_text("2 warnings")).to_be_visible()

    page.get_by_role("button", name="Diagnostics").click()

    expect(page.get_by_text("No unmatched PDFs in this run.")).to_be_visible()


def test_review_workspace_supports_guarded_multi_cell_selection(
    page: Page,
    frontend_url: str,
    demo_run_ids: DemoRunIds,
):
    _open_review_workspace(page, frontend_url, demo_run_ids.review)

    cells = page.locator("button[data-proposal-id]")
    expect(cells).to_have_count(2)
    cells.nth(0).hover()
    page.mouse.down()
    cells.nth(1).hover()
    page.mouse.up()

    selection_bar = page.get_by_test_id("bulk-selection-bar")
    expect(selection_bar).to_contain_text("2 cells selected")
    selection_bar.get_by_role("button", name="Reject").click()
    expect(selection_bar).to_contain_text("decision_source=human_bulk_selection")
    expect(selection_bar.get_by_role("button", name="Confirm selected cells")).to_be_visible()
