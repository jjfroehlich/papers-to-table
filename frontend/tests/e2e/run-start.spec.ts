import { expect, test } from '@playwright/test'

test('shows run launch baseline guidance', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Paper Table Agent' })).toBeVisible()
  await expect(page.getByText('Start run from config file')).toBeVisible()
  await expect(page.getByText('No runs yet.')).toBeVisible()
})
