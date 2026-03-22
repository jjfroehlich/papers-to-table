import { test, expect } from '@playwright/test'

test('review workflow renders the queue-first workspace', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Paper Table Agent')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Run launcher' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Run summary' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Proposal queue' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Run setup' })).toBeVisible()
  await expect(page.locator('ul[aria-label="proposal-queue"] > li').first()).toBeVisible()
  await expect(page.getByText('Download workbook')).toBeVisible()
})

test('run launcher can start a new run and show validating status', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Start run' }).click()
  await expect(page.locator('[aria-label="run-summary"]').getByText(/validating|running|completed/i).first()).toBeVisible()
})

test('processing state does not expose workbook downloads before review is ready', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Start run' }).click()
  await expect(page.getByText(/workbook, audit-log, and summary downloads appear after the run reaches a reviewable completed state/i)).toBeVisible()
})
