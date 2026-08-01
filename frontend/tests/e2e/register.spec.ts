import { test, expect } from '@playwright/test';

test.use({ storageState: { cookies: [], origins: [] } });

test('register page without token shows warning message', async ({ page }) => {
  await page.goto('/register');
  await expect(page.getByText(/invite link is required/i)).toBeVisible();
  // Submit button is disabled when no token is present
  await expect(page.getByRole('button', { name: /create account/i })).toBeDisabled();
});

test('register with invalid token shows error', async ({ page }) => {
  await page.goto('/register?token=badtoken');
  await page.locator('input[type="email"]').fill(`e2e-reg-${Date.now()}@example.com`);
  await page.locator('input[type="password"]').first().fill('Password123!');
  await page.locator('input[type="password"]').nth(1).fill('Password123!');
  await page.getByRole('button', { name: /create account/i }).click();
  await expect(page.getByText(/invalid|expired|already.used/i)).toBeVisible({ timeout: 10000 });
});

// SKIP: No API endpoint returns a raw invite token.
// POST /admin/resend-invite emails the token and returns {"status": "sent"}.
// TODO: Implement when a token-retrieval endpoint exists or when email is interceptable in tests.
test.skip('register with valid invite token succeeds', async () => {});

test('password mismatch shows validation error', async ({ page }) => {
  await page.goto('/register?token=sometoken');
  await page.locator('input[type="email"]').fill(`e2e-reg-${Date.now()}@example.com`);
  await page.locator('input[type="password"]').first().fill('Password123!');
  await page.locator('input[type="password"]').nth(1).fill('DifferentPass!');
  await page.getByRole('button', { name: /create account/i }).click();
  await expect(page.getByText(/passwords do not match/i)).toBeVisible();
});
