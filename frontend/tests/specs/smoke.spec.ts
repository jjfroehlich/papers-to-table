import { test, expect } from '@playwright/test'

test('shows run launch and review workspace shells', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Run Launch and Setup')).toBeVisible()
  await page.getByRole('button', { name: 'Review' }).click()
  await expect(page.getByText('Review Workspace')).toBeVisible()
  await expect(page.getByText('No run selected. Switch to Run view and create a run.')).toBeVisible()
})
