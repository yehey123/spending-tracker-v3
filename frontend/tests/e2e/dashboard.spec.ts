import { test, expect } from '@playwright/test';

test('dashboard renders chart containers', async ({ page }) => {
  await page.goto('/');
  // Containers render even with no data (empty-state divs carry the testid)
  await expect(page.getByTestId('spending-donut')).toBeVisible();
  await expect(page.getByTestId('cashflow-bar')).toBeVisible();
});
