import { test, expect, request } from '@playwright/test';
import { apiURL } from './fixtures';

const E2E_ACCOUNT_NAMES = ['E2E Test Bank'];

test('can create an account', async ({ page }) => {
  await page.goto('/accounts');
  await expect(page.getByRole('button', { name: /add/i })).toBeVisible();
  await page.getByRole('button', { name: /add/i }).click();

  await page.getByPlaceholder(/account name/i).fill('E2E Test Bank');
  await page.getByRole('combobox').selectOption('checking');
  await page.getByPlaceholder(/currency/i).fill('PHP');
  await page.getByRole('button', { name: /create account/i }).click();

  await expect(page.getByText('E2E Test Bank').first()).toBeVisible();
});

// Cleanup: delete all accounts created by this suite (accounts + portfolio specs).
// Uses page so Playwright captures a screenshot of the accounts list post-cleanup.
test('cleanup — delete all E2E-created accounts', async ({ page }) => {
  const ctx = await request.newContext();

  const listResp = await ctx.get(`${apiURL()}/accounts`);
  const accounts: Array<{ id: number; name: string }> = await listResp.json();

  const toDelete = accounts.filter((a) =>
    E2E_ACCOUNT_NAMES.some((n) => a.name.includes(n)),
  );

  await Promise.all(
    toDelete.map((a) => ctx.delete(`${apiURL()}/accounts/${a.id}`)),
  );

  await ctx.dispose();

  // Navigate so the screenshot shows the cleaned-up accounts list
  await page.goto('/accounts');
});
