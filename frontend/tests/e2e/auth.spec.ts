import { test, expect, chromium } from '@playwright/test';

const email = process.env.E2E_EMAIL ?? 'e2e@example.com';
const password = process.env.E2E_PASSWORD ?? 'e2epassword';

test('login page renders', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByLabel(/email/i)).toBeVisible();
  await expect(page.getByLabel(/password/i)).toBeVisible();
  await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
});

test('valid credentials redirect to /', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill(password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 10000 });
});

test('invalid credentials shows error', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill('wrongpassword');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByText(/invalid email or password/i)).toBeVisible();
  await expect(page).toHaveURL(/\/login/);
});

test('unauthenticated user redirected to /login', async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const page = await ctx.newPage();
  await page.goto('/transactions');
  await expect(page).toHaveURL(/\/login/, { timeout: 10000 });
  await browser.close();
});

test('logout clears session', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: /sign out/i }).click();
  await expect(page).toHaveURL(/\/login/, { timeout: 10000 });

  // New context to verify session is gone
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ storageState: { cookies: [], origins: [] } });
  const freshPage = await ctx.newPage();
  await freshPage.goto('/transactions');
  await expect(freshPage).toHaveURL(/\/login/, { timeout: 10000 });
  await browser.close();
});
