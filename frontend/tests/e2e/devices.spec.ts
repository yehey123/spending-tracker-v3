import { test, expect } from '@playwright/test';
import { apiURL, authedApiContext } from './fixtures';

test('devices page loads', async ({ page }) => {
  await page.goto('/settings/devices');
  await expect(page.getByRole('heading', { name: /active sessions/i })).toBeVisible();
});

test('current session is listed with Current badge', async ({ page }) => {
  await page.goto('/settings/devices');
  await expect(page.getByText('Current')).toBeVisible({ timeout: 10000 });
});

test('revoke non-current session', async ({ page }) => {
  // Create a second session by logging in again via API
  const ctx = await authedApiContext();
  const email = process.env.E2E_EMAIL ?? 'e2e@example.com';
  const password = process.env.E2E_PASSWORD ?? 'e2epassword';
  await ctx.post(`${apiURL()}/auth/login`, {
    data: { email, password, device_name: 'E2E-second-session' },
  });
  await ctx.dispose();

  await page.goto('/settings/devices');
  // Wait for the sessions list to show at least 2 sessions
  await page.waitForFunction(() => document.querySelectorAll('button').length >= 2);

  // Find a non-current session's Revoke button (not the red "Log out" one)
  const revokeBtn = page.getByRole('button', { name: /^revoke$/i }).first();
  await expect(revokeBtn).toBeVisible();
  await revokeBtn.click();

  // The row should disappear
  await expect(page.getByRole('button', { name: /^revoke$/i })).toHaveCount(0, { timeout: 10000 });
});
