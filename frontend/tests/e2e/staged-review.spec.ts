import { test, expect } from '@playwright/test';
import { apiURL, authedApiContext } from './fixtures';
import * as fs from 'fs';
import * as path from 'path';

const BLANK_PNG = path.join(__dirname, 'fixtures', 'blank.png');

async function seedStagedStatement(): Promise<number> {
  const ctx = await authedApiContext();
  await ctx.patch(`${apiURL()}/settings`, { data: { review_before_commit: true } });
  const buffer = fs.readFileSync(BLANK_PNG);
  const resp = await ctx.post(`${apiURL()}/statements/upload`, {
    multipart: {
      file: { name: 'blank.png', mimeType: 'image/png', buffer },
      statement_kind: 'bank_account',
    },
  });
  const data = await resp.json();
  await ctx.dispose();
  return data.id as number;
}

test.afterEach(async () => {
  const ctx = await authedApiContext();
  await ctx.patch(`${apiURL()}/settings`, { data: { review_before_commit: false } });
  await ctx.dispose();
});

test('staged review shows commit and discard buttons', async ({ page }) => {
  const id = await seedStagedStatement();
  await page.goto(`/statements/${id}/review`);
  await expect(page.getByRole('heading', { name: /review statement/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /commit/i })).toBeVisible();
  await expect(page.getByRole('button', { name: /discard/i })).toBeVisible();
});

test('discard navigates back to upload', async ({ page }) => {
  const id = await seedStagedStatement();
  await page.goto(`/statements/${id}/review`);
  await page.getByRole('button', { name: /discard/i }).click();
  await expect(page).toHaveURL('/upload', { timeout: 10000 });
});
