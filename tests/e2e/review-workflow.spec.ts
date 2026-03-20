import { test, expect } from '@playwright/test'

test('review workflow renders the queue-first workspace', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Paper Table Agent')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Run summary' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Proposal queue' })).toBeVisible()
  await expect(page.locator('ul[aria-label="proposal-queue"] > li').first()).toBeVisible()
  await expect(page.getByText('Download workbook')).toBeVisible()
})
