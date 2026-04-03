"""
E2e tests for the Batch 5 review workspace.

These tests are opt-in (marked 'e2e') and require the full stack running
with a completed run available.

To run:
    pytest tests/e2e/test_review_workspace.py -m e2e --base-url http://localhost:5173
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


@pytest.mark.skip(reason="e2e tests require live server with a completed run")
def test_review_tab_available_for_completed_run(page, frontend_url: str):
    """Review tab becomes enabled when a completed run is selected."""
    page.goto(frontend_url)
    page.wait_for_selector("h1", timeout=5000)

    # The Review tab should exist but may be disabled initially
    review_tab = page.locator("button", has_text="Review")
    assert review_tab.is_visible()

    # If a completed run is listed, select it and verify Review tab becomes enabled
    # (This requires at least one completed run in the runs list)
    runs = page.locator("[data-testid='run-item']")
    if runs.count() > 0:
        runs.first.click()
        # Review tab should become enabled
        page.wait_for_function(
            "() => !document.querySelector('button[disabled]')?.textContent?.includes('Review')",
            timeout=3000,
        )


@pytest.mark.skip(reason="e2e tests require live server with a completed run")
def test_review_workspace_renders_three_panes(page, frontend_url: str):
    """Review workspace shows three panes: queue, detail, evidence."""
    page.goto(frontend_url)
    page.wait_for_selector("h1", timeout=5000)

    # Navigate to review tab (requires completed run selected first)
    review_tab = page.locator("button", has_text="Review")
    if review_tab.get_attribute("disabled") is None:
        review_tab.click()

        # Check for queue (left pane)
        page.wait_for_selector("text=By Paper", timeout=3000)
        assert page.locator("text=By Paper").is_visible()
        assert page.locator("text=By Column").is_visible()

        # Check for evidence viewer controls (right pane)
        # Zoom controls appear when a PDF is loaded
        # Detail pane placeholder visible initially
        placeholder = page.locator("text=Select a proposal from the queue")
        assert placeholder.is_visible()


@pytest.mark.skip(reason="e2e tests require live server with a completed run and proposals")
def test_selecting_proposal_shows_detail_pane(page, frontend_url: str):
    """Selecting a proposal from the queue loads the detail pane."""
    page.goto(frontend_url)
    page.wait_for_selector("h1", timeout=5000)

    review_tab = page.locator("button", has_text="Review")
    if review_tab.get_attribute("disabled") is None:
        review_tab.click()

        # Wait for queue to populate
        page.wait_for_selector("[class*='border-blue']", timeout=5000)

        # Click first proposal card
        first_card = page.locator("[class*='border-blue']").first
        first_card.click()

        # Detail pane should show proposed value
        page.wait_for_selector("text=Proposed", timeout=3000)


@pytest.mark.skip(reason="e2e tests require live server with a completed run and proposals")
def test_decision_buttons_present_and_clickable(page, frontend_url: str):
    """Decision buttons (Accept, Reject, No Data) are visible and clickable."""
    page.goto(frontend_url)
    page.wait_for_selector("h1", timeout=5000)

    review_tab = page.locator("button", has_text="Review")
    if review_tab.get_attribute("disabled") is None:
        review_tab.click()

        # Wait for queue
        page.wait_for_selector("text=By Paper", timeout=5000)

        # Select first proposal
        cards = page.locator("[class*='border-l-4']")
        if cards.count() > 0:
            cards.first.click()

            # Decision buttons should be visible
            page.wait_for_selector("text=Accept", timeout=3000)
            assert page.locator("text=Accept").first.is_visible()
            assert page.locator("text=Reject").first.is_visible()
            assert page.locator("text=No Data").first.is_visible()


@pytest.mark.skip(reason="e2e tests require live server with a completed run and proposals")
def test_fast_sequential_review_supports_auto_advance_and_evidence_cycling(page, frontend_url: str):
    """Sequential review keeps evidence navigation and auto-advance usable."""
    page.goto(frontend_url)
    page.wait_for_selector("h1", timeout=5000)

    review_tab = page.locator("button", has_text="Review")
    if review_tab.get_attribute("disabled") is None:
        review_tab.click()
        page.wait_for_selector("text=Actionable review", timeout=5000)

        cards = page.locator("[class*='border-l-4']")
        if cards.count() > 0:
            cards.first.click()
            page.wait_for_selector("text=Next evidence", timeout=5000)
            page.click("button:has-text('Next evidence')")
            page.click("button:has-text('Accept')")
            page.wait_for_timeout(500)


@pytest.mark.skip(reason="e2e tests require live server with a completed run and explicit export support")
def test_review_workspace_keeps_export_manual(page, frontend_url: str):
    """Export remains an explicit reviewer action from the review workspace."""
    page.goto(frontend_url)
    page.wait_for_selector("h1", timeout=5000)

    review_tab = page.locator("button", has_text="Review")
    if review_tab.get_attribute("disabled") is None:
        review_tab.click()
        page.wait_for_selector("button:has-text('Export reviewed workbook')", timeout=5000)
        export_button = page.locator("button", has_text="Export reviewed workbook")
        assert export_button.is_visible()
