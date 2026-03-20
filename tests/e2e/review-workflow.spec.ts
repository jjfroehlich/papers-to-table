import { test, expect } from '@playwright/test'

test('review workflow renders the queue-first workspace', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Paper Table Agent')).toBeVisible()
  await expect(page.getByText('Run Summary')).toBeVisible()
  await expect(page.getByLabel('proposal-queue')).toBeVisible()
})
