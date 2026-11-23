import { test, expect } from '@playwright/test';
import { apiURL, authedApiContext } from './fixtures';

test('devices page loads', async ({ page }) => {
  await page.goto('/settings/devices');
  await expect(page.getByRole('heading', { name: /active sessions/i })).toBeVisible();
});

test('current session is listed with Current badge', async ({ page }) => {
  await page.goto('/settings/devices');
  await expect(page.getByText('Current', { exact: true })).toBeVisible({ timeout: 10000 });
});

test('revoke non-current session', async ({ page }) => {
  // Create a second session by logging in again via API
  const ctx = await authedApiContext();
  const email = process.env.E2E_EMAIL ?? 'e2e@example.com';
  const password = process.env.E2E_PASSWORD ?? 'e2epassword';
  const login = await ctx.post(`${apiURL()}/auth/login`, {
    data: { email, password, device_name: 'E2E-second-session' },
  });
  expect(login.ok()).toBeTruthy();
  await ctx.dispose();

  await page.goto('/settings/devices');

  // Scope to the row of the session created above (earlier runs may leave others behind)
  const label = page.getByText('E2E-second-session', { exact: true });
  const row = page
    .locator('div')
    .filter({ has: label })
    .filter({ has: page.getByRole('button', { name: /^revoke$/i }) })
    .last();
  const revokeBtn = row.getByRole('button', { name: /^revoke$/i });
  await expect(revokeBtn).toBeVisible({ timeout: 10000 });
  const before = await label.count();

  const deleted = page.waitForResponse(
    r => r.request().method() === 'DELETE' && r.url().includes('/auth/sessions/'),
  );
  await revokeBtn.click();
  await deleted;

  // One fewer second-session row after the list reloads
  await expect(label).toHaveCount(before - 1, { timeout: 10000 });
});
