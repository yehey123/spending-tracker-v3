import { test, expect } from '@playwright/test';

// Needs the backend started with ACCESS_TOKEN_EXPIRE_MINUTES=1. Skipped in normal runs.
test.skip(process.env.E2E_REFRESH !== '1', 'set E2E_REFRESH=1 (backend ACCESS_TOKEN_EXPIRE_MINUTES=1)');
test.setTimeout(180_000);

test('expired access token is refreshed transparently', async ({ page }) => {
  // storageState holds a session whose backend access token lives 1 minute.
  await page.waitForTimeout(75_000);

  const apiStatuses: number[] = [];
  page.on('response', (r) => {
    if (r.url().includes('/api/') && !r.url().includes('/api/auth/')) apiStatuses.push(r.status());
  });

  await page.goto('/accounts');
  await expect(page).not.toHaveURL(/\/login/);
  await page.waitForLoadState('networkidle');
  expect(apiStatuses.length).toBeGreaterThan(0);
  expect(apiStatuses.filter((s) => s === 401)).toEqual([]);

  // Parallel session reads + API calls: all must succeed with one refresh (single-flight).
  const results = await page.evaluate(async () => {
    const sessions = await Promise.all(
      [0, 1, 2, 3].map(() => fetch('/api/auth/session').then((r) => r.json())),
    );
    return Promise.all(
      sessions.map((s) =>
        fetch('/api/accounts', { headers: { Authorization: `Bearer ${s.accessToken}` } }).then(
          (r) => r.status,
        ),
      ),
    );
  });
  expect(results).toEqual([200, 200, 200, 200]);
  await expect(page).not.toHaveURL(/\/login/);
});
