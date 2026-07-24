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
  await expect(page.getByText(SEED_DESC).first()).toBeVisible();
  await expect(page.getByText('123.45').first()).toBeVisible();
});

test('direction filter shows seeded debit transaction', async ({ page }) => {
  await page.goto('/transactions');
  // The direction select is the combobox whose default option is "All directions"
  await page.locator('select', { hasText: /all directions/i }).selectOption('debit');
  await expect(page.getByText(SEED_DESC).first()).toBeVisible();
});

test('can manually create a transaction', async ({ page }) => {
  await page.goto('/transactions');
  await page.getByRole('button', { name: /add transaction/i }).click();
  await page.locator('input[type="date"]').first().fill('2026-01-20');
  await page.getByPlaceholder('0.00').fill('75.00');
  await page.getByPlaceholder(/coffee shop/i).fill('E2E_MANUAL_TX');
  await page.getByRole('button', { name: /save transaction/i }).click();
  await expect(page.getByText('E2E_MANUAL_TX').first()).toBeVisible();
});

test('can edit a transaction description', async ({ page }) => {
  await page.goto('/transactions');
  await expect(page.getByText(SEED_DESC).first()).toBeVisible();

  // Open inline edit for the seeded row
  await page.locator('li').filter({ hasText: SEED_DESC }).first()
    .locator('button[title="Edit transaction"]').click();

  // Description is the only type="text" input inside the open edit form
  await page.locator('li input[type="text"]').first().fill('E2E_EDITED_DESC');
  await page.getByRole('button', { name: 'Save' }).click();

  await expect(page.getByText('E2E_EDITED_DESC').first()).toBeVisible();
});

// Cleanup: reverse every active transaction seeded by this suite so the DB
// stays clean between local runs. Runs last (serial worker, alphabetical order).
test('cleanup — reverse all E2E-seeded transactions', async ({ page }) => {
  const E2E_DESCRIPTIONS = [SEED_DESC, 'E2E_MANUAL_TX', 'E2E_EDITED_DESC'];
  const ctx = await request.newContext();

  // Fetch all active transactions (paginated endpoint returns up to 50 by default)
  const listResp = await ctx.get(`${apiURL()}/transactions`);
  const transactions: Array<{ id: number; description: string; status: string }> =
    await listResp.json();

  const toReverse = transactions.filter(
    (tx) => E2E_DESCRIPTIONS.some((d) => tx.description.includes(d)) && tx.status === 'active',
  );

  if (toReverse.length > 0) {
    await ctx.post(`${apiURL()}/transactions/reverse`, {
      data: { ids: toReverse.map((tx) => tx.id), reason: 'user_error' },
    });
  }

  await ctx.dispose();

  // Navigate so the screenshot shows the cleaned-up transaction list
  await page.goto('/transactions');
});
