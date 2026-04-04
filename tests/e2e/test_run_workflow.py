"""Runnable Playwright coverage for run setup and review gating."""
from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


def test_run_tab_gates_review_until_a_reviewable_run_is_selected(page: Page, frontend_url: str):
    page.goto(frontend_url)

    expect(page.locator("[data-testid='run-launch-surface']")).to_be_visible()
    expect(page.get_by_role("button", name="Review")).to_be_disabled()
    expect(page.get_by_role("heading", name="Create Run")).to_be_visible()


def test_browse_prefills_paths_without_removing_manual_editability(page: Page, frontend_url: str):
    page.goto(frontend_url)

    launch_surface = page.locator("[data-testid='run-launch-surface']")
    config_input = launch_surface.get_by_placeholder("e.g. config.example.json")
    file_inputs = launch_surface.locator("input[type='file']")

    file_inputs.nth(0).set_input_files(
        files=[{
            "name": "picked-config.json",
            "mimeType": "application/json",
            "buffer": b"{}",
        }]
    )
    expect(config_input).to_have_value("picked-config.json")

    config_input.fill("/tmp/runtime/config.json")
    expect(config_input).to_have_value("/tmp/runtime/config.json")

    launch_surface.get_by_role("button", name="▼ Show optional path overrides").click()
    table_input = launch_surface.get_by_placeholder("e.g. path/to/table.xlsx")

    file_inputs.nth(1).set_input_files(
        files=[{
            "name": "picked-table.xlsx",
            "mimeType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "buffer": b"fake-xlsx",
        }]
    )
    expect(table_input).to_have_value("picked-table.xlsx")

    table_input.fill("/tmp/runtime/table.xlsx")
    expect(table_input).to_have_value("/tmp/runtime/table.xlsx")


def test_picker_staging_shows_handle_for_table_override(page: Page, frontend_url: str):
    page.goto(frontend_url)

    launch_surface = page.locator("[data-testid='run-launch-surface']")
    launch_surface.get_by_role("button", name="▼ Show optional path overrides").click()

    file_inputs = launch_surface.locator("input[type='file']")
    file_inputs.nth(1).set_input_files(
        files=[{
            "name": "picked-table.csv",
            "mimeType": "text/csv",
            "buffer": b"Title\nPaper A\n",
        }]
    )

    expect(launch_surface.get_by_text("staged handle:")).to_be_visible()


def test_selecting_completed_run_enables_review_workspace(page: Page, frontend_url: str):
    page.goto(frontend_url)

    run_item = page.locator("[data-testid='run-item']").first
    expect(run_item).to_be_visible()
    run_item.click()

    review_tab = page.get_by_role("button", name="Review")
    expect(review_tab).to_be_enabled()
    review_tab.click()

    expect(page.locator("[data-testid='review-workspace']")).to_be_visible()
    expect(page.locator("[data-testid='review-toolbar']")).to_contain_text("Actionable review")
    expect(page.get_by_role("button", name="Export reviewed workbook")).to_be_visible()
