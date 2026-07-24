import { test, expect } from '@playwright/test';

test('review page shows empty state when no flags pending', async ({ page }) => {
  await page.goto('/review');
  await expect(page.getByText(/no open suggestions/i)).toBeVisible();
});
