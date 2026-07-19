import { test, expect, request } from '@playwright/test';
import { apiURL } from './fixtures';

const SEED_DESC = 'E2E_TEST_MERCHANT_TX';

test.beforeEach(async () => {
  const ctx = await request.newContext();
  await ctx.post(`${apiURL()}/transactions`, {
    data: {
      date: '2026-01-15T00:00:00Z',
      amount: 123.45,
      description: SEED_DESC,
      direction: 'debit',
    },
  });
  await ctx.dispose();
});

test('seeded transaction appears in list', async ({ page }) => {
  await page.goto('/transactions');
  await expect(page.getByText(SEED_DESC)).toBeVisible();
  await expect(page.getByText('123.45')).toBeVisible();
});

test('search filters to seeded transaction', async ({ page }) => {
  await page.goto('/transactions');
  const searchInput = page.getByPlaceholder(/search/i);
  await searchInput.fill(SEED_DESC);
  await expect(page.getByText(SEED_DESC)).toBeVisible();
  // After clearing, the row is still present
  await searchInput.clear();
  await expect(page.getByText(SEED_DESC)).toBeVisible();
});
