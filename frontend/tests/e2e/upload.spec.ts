import { test, expect, request } from '@playwright/test';
import { apiURL } from './fixtures';
import * as path from 'path';

const BLANK_PNG = path.join(__dirname, 'fixtures', 'blank.png');

test.afterEach(async () => {
  const ctx = await request.newContext();
  await ctx.patch(`${apiURL()}/settings`, { data: { review_before_commit: false } });
  await ctx.dispose();
});

test('upload page renders dropzone', async ({ page }) => {
  await page.goto('/upload');
  await expect(page.getByText(/drag a png, jpeg, or pdf/i)).toBeVisible();
});

test('file selection reveals statement kind toggle and upload button', async ({ page }) => {
  await page.goto('/upload');
  await page.locator('input[type="file"]').setInputFiles(BLANK_PNG);
  await expect(page.getByRole('button', { name: 'Bank Account' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Credit Card' })).toBeVisible();
  await expect(page.getByText(/upload & process/i)).toBeVisible();
});

test('upload with staging enabled redirects to review page', async ({ page }) => {
  const ctx = await request.newContext();
  await ctx.patch(`${apiURL()}/settings`, { data: { review_before_commit: true } });
  await ctx.dispose();

  await page.goto('/upload');
  await page.locator('input[type="file"]').setInputFiles(BLANK_PNG);
  await page.getByText(/upload & process/i).click();

  // OCR + pipeline may take several seconds
  await expect(page).toHaveURL(/\/statements\/\d+\/review/, { timeout: 30000 });
  await expect(page.getByRole('heading', { name: /review statement/i })).toBeVisible();
});
