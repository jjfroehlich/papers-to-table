import { test, expect } from '@playwright/test'

test('shows run launch surface', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText('Run Launch and Setup')).toBeVisible()
})
