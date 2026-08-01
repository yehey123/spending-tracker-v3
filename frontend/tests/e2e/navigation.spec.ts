import { test, expect } from '@playwright/test';

const routes: { label: RegExp; path: string }[] = [
  { label: /transactions/i, path: '/transactions' },
  { label: /upload/i, path: '/upload' },
  { label: /accounts/i, path: '/accounts' },
  { label: /devices/i, path: '/settings/devices' },
];

for (const { label, path } of routes) {
  test(`bottom nav navigates to ${path}`, async ({ page }) => {
    await page.goto('/');
    await page.getByRole('link', { name: label }).first().click();
    await expect(page).toHaveURL(new RegExp(path));
  });
}

test('Admin link visible in nav for admin user', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('link', { name: /admin/i })).toBeVisible();
});
