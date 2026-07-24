import { test, expect } from '@playwright/test';

test('receipts page shows empty state', async ({ page }) => {
  await page.goto('/receipts');
  await expect(page.getByText(/no receipts yet/i)).toBeVisible();
});
