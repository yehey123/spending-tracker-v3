import { test, expect } from '@playwright/test';
import { apiURL, authedApiContext } from './fixtures';

let brokerAccountId: number;

test('portfolio shows empty holdings for new broker account', async ({ page }) => {
  const ctx = await authedApiContext();
  const resp = await ctx.post(`${apiURL()}/accounts`, {
    data: {
      name: 'E2E Broker Portfolio',
      type: 'broker',
      currency: 'USD',
      opening_balance: 0,
    },
  });
  const account = await resp.json();
  brokerAccountId = account.id;
  await ctx.dispose();

  await page.goto(`/portfolio/${account.id}`);
  await expect(page.getByText(/no holdings recorded/i)).toBeVisible();
});

test('cleanup — delete E2E broker account', async ({ page }) => {
  if (!brokerAccountId) return;
  const ctx = await authedApiContext();
  await ctx.delete(`${apiURL()}/accounts/${brokerAccountId}`);
  await ctx.dispose();

  await page.goto('/accounts');
});
