import { test, expect } from '@playwright/test';

test.use({ storageState: { cookies: [], origins: [] } });

test('request-access page renders', async ({ page }) => {
  await page.goto('/request-access');
  await expect(page.locator('input[type="email"]')).toBeVisible();
  await expect(page.getByRole('button', { name: /request access/i })).toBeVisible();
});

test('submit with email shows success state', async ({ page }) => {
  await page.goto('/request-access');
  await page.locator('input[type="email"]').fill(`e2e-access-${Date.now()}@example.com`);
  await page.getByRole('button', { name: /request access/i }).click();
  await expect(page.getByText(/request submitted/i)).toBeVisible({ timeout: 10000 });
});

test('duplicate email shows appropriate response', async ({ page }) => {
  const dupeEmail = `e2e-dupe-${Date.now()}@example.com`;

  await page.goto('/request-access');
  await page.locator('input[type="email"]').fill(dupeEmail);
  await page.getByRole('button', { name: /request access/i }).click();
  await expect(page.getByText(/request submitted/i)).toBeVisible({ timeout: 10000 });

  await page.goto('/request-access');
  await page.locator('input[type="email"]').fill(dupeEmail);
  await page.getByRole('button', { name: /request access/i }).click();
  // Backend either accepts again (202) or shows "already submitted" — either is valid
  await expect(
    page.getByText(/request submitted|already submitted|already received/i)
  ).toBeVisible({ timeout: 10000 });
});
