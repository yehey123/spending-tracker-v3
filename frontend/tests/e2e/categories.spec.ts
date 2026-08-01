import { test, expect } from '@playwright/test';
import { apiURL, authedApiContext } from './fixtures';

const E2E_CATEGORY = 'E2E Dining';
const E2E_SUBCATEGORY = 'E2E Fast Food';
let categoryId: number;

// Seed the parent category once before all tests in this file
test.beforeAll(async () => {
  const ctx = await authedApiContext();
  const resp = await ctx.post(`${apiURL()}/categories`, {
    data: { name: E2E_CATEGORY, slug: 'e2e-dining', color: '#f97316' },
  });
  const cat = await resp.json();
  categoryId = cat.id;
  await ctx.dispose();
});

// ─── Category UI ─────────────────────────────────────────────────────────────

test('seeded category appears in settings list', async ({ page }) => {
  await page.goto('/settings');
  const catSection = page.locator('section').filter({ hasText: 'Categories' });
  await expect(catSection.getByText(E2E_CATEGORY).first()).toBeVisible();
});

test('can create a subcategory via settings page', async ({ page }) => {
  await page.goto('/settings');
  const catSection = page.locator('section').filter({ hasText: 'Categories' });

  await catSection.getByPlaceholder(/new category name/i).fill(E2E_SUBCATEGORY);
  // Select the E2E parent in the parent picker
  await catSection.locator('select', { hasText: /top-level/i }).selectOption({ label: E2E_CATEGORY });
  await catSection.getByRole('button', { name: /^add$/i }).click();

  await expect(catSection.getByText(E2E_SUBCATEGORY).first()).toBeVisible();
});

// ─── Category assignment + filter ────────────────────────────────────────────

test('category filter shows only transactions in that category', async ({ page }) => {
  // Seed a transaction assigned to the E2E category via API
  const ctx = await authedApiContext();
  await ctx.post(`${apiURL()}/transactions`, {
    data: {
      date: '2026-02-01T00:00:00Z',
      amount: 350,
      description: 'E2E_CATEGORIZED_TX',
      direction: 'debit',
      category_id: categoryId,
    },
  });
  await ctx.dispose();

  await page.goto('/transactions');
  // Filter by the E2E category — only the categorized row should match
  await page.locator('select', { hasText: /all categories/i }).selectOption({ label: E2E_CATEGORY });
  await expect(page.getByText('E2E_CATEGORIZED_TX').first()).toBeVisible();
});

// ─── Credit direction ─────────────────────────────────────────────────────────

test('credit transaction appears with + prefix in list', async ({ page }) => {
  const ctx = await authedApiContext();
  await ctx.post(`${apiURL()}/transactions`, {
    data: {
      date: '2026-02-02T00:00:00Z',
      amount: 5000,
      description: 'E2E_CREDIT_TX',
      direction: 'credit',
    },
  });
  await ctx.dispose();

  await page.goto('/transactions');
  await expect(page.getByText('E2E_CREDIT_TX').first()).toBeVisible();
  // Amount row should show a + prefix (credit displays as "+PHP 5000.00" etc.)
  const row = page.locator('li').filter({ hasText: 'E2E_CREDIT_TX' }).first();
  await expect(row.getByText(/^\+/)).toBeVisible();
});

test('credit direction filter shows credit and hides debit transactions', async ({ page }) => {
  await page.goto('/transactions');
  await page.locator('select', { hasText: /all directions/i }).selectOption('credit');
  await expect(page.getByText('E2E_CREDIT_TX').first()).toBeVisible();
  // The standard debit seed from transactions.spec.ts should not appear
  await expect(page.getByText('E2E_TEST_MERCHANT_TX')).toHaveCount(0);
});

test('debit direction filter hides credit transactions', async ({ page }) => {
  await page.goto('/transactions');
  await page.locator('select', { hasText: /all directions/i }).selectOption('debit');
  await expect(page.getByText('E2E_CREDIT_TX')).toHaveCount(0);
});

// ─── Cleanup ──────────────────────────────────────────────────────────────────

test('cleanup — reverse E2E transactions and delete E2E categories', async ({ page }) => {
  const ctx = await authedApiContext();

  // Reverse E2E transactions seeded in this file
  const txResp = await ctx.get(`${apiURL()}/transactions`);
  const transactions: Array<{ id: number; description: string; status: string }> =
    await txResp.json();
  const toReverse = transactions.filter(
    (tx) =>
      ['E2E_CATEGORIZED_TX', 'E2E_CREDIT_TX'].some((d) => tx.description.includes(d)) &&
      tx.status === 'active',
  );
  if (toReverse.length > 0) {
    await ctx.post(`${apiURL()}/transactions/reverse`, {
      data: { ids: toReverse.map((tx) => tx.id), reason: 'user_error' },
    });
  }

  // Delete subcategory before parent (FK constraint)
  const catResp = await ctx.get(`${apiURL()}/categories`);
  const categories: Array<{ id: number; name: string; children?: Array<{ id: number; name: string }> }> =
    await catResp.json();
  const parent = categories.find((c) => c.name === E2E_CATEGORY);
  if (parent) {
    const sub = (parent.children ?? []).find((c) => c.name === E2E_SUBCATEGORY);
    if (sub) await ctx.delete(`${apiURL()}/categories/${sub.id}`);
    await ctx.delete(`${apiURL()}/categories/${parent.id}`);
  }

  await ctx.dispose();

  // Navigate so the screenshot shows the cleaned-up settings/categories list
  await page.goto('/settings');
});
