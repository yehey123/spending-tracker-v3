import { test, expect } from '@playwright/test';

test('can create an account', async ({ page }) => {
  await page.goto('/accounts');
  await expect(page.getByRole('button', { name: /add account/i })).toBeVisible();
  await page.getByRole('button', { name: /add account/i }).click();

  await page.getByLabel(/name/i).fill('E2E Test Bank');
  await page.getByLabel(/type/i).selectOption('checking');
  await page.getByLabel(/currency/i).fill('PHP');
  await page.getByLabel(/opening date/i).fill('2026-01-01');
  await page.getByRole('button', { name: /save|create/i }).click();

  await expect(page.getByText('E2E Test Bank')).toBeVisible();
});
