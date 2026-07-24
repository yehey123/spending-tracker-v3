import { test, expect, request } from '@playwright/test';
import { apiURL } from './fixtures';

const SEED_DESCS = ['E2E_BULK_TX_1', 'E2E_BULK_TX_2', 'E2E_BULK_TX_3'];

test.beforeAll(async () => {
  const ctx = await request.newContext();

  // Reverse any leftover E2E_BULK transactions from previous runs
  const listResp = await ctx.get(`${apiURL()}/transactions?limit=200`);
  const existing = await listResp.json() as Array<{ id: number; description: string }>;
  const stale = existing.filter((tx) => SEED_DESCS.some((d) => tx.description === d));
  if (stale.length > 0) {
    await ctx.post(`${apiURL()}/transactions/reverse`, {
      data: { ids: stale.map((tx) => tx.id), reason: 'user_error' },
    });
  }

  // Seed fresh transactions
  await Promise.all(
    SEED_DESCS.map((description, i) =>
      ctx.post(`${apiURL()}/transactions`, {
        data: {
          date: `2026-03-0${i + 1}T00:00:00Z`,
          amount: 10 * (i + 1),
          description,
          direction: 'debit',
        },
      }),
    ),
  );
  await ctx.dispose();
});

// Scope to transaction rows only (they contain a checkbox; nav li items do not)
function txRows(page: import('@playwright/test').Page, desc: string) {
  return page.locator('li').filter({ hasText: desc }).filter({ has: page.locator('input[type="checkbox"]') });
}

test('can reverse a single transaction via the per-row button', async ({ page }) => {
  await page.goto('/transactions');

  const row = txRows(page, SEED_DESCS[0]).first();
  await expect(row).toBeVisible();
  await row.locator('button[title="Reverse transaction"]').click();

  // Confirm button appears in place of the row content
  await page.getByRole('button', { name: /confirm reversal/i }).click();

  await expect(txRows(page, SEED_DESCS[0])).toHaveCount(0);
});

test('can bulk-reverse remaining transactions via multi-select', async ({ page }) => {
  await page.goto('/transactions');

  // TX_1 was reversed in the previous test — only TX_2 and TX_3 remain
  for (const desc of SEED_DESCS.slice(1)) {
    const row = txRows(page, desc).first();
    await expect(row).toBeVisible();
    await row.locator('input[type="checkbox"]').check();
  }

  await expect(page.getByText('2 selected')).toBeVisible();
  await page.locator('.bg-red-50 select').selectOption('user_error');
  await page.getByRole('button', { name: /reverse 2 transactions/i }).click();

  await expect(txRows(page, SEED_DESCS[1])).toHaveCount(0, { timeout: 10000 });
  await expect(txRows(page, SEED_DESCS[2])).toHaveCount(0);
});
