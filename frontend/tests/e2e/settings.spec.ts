import { test, expect } from '@playwright/test';

test('settings page loads and OCR provider selector works', async ({ page }) => {
  await page.goto('/settings');

  await expect(page.getByRole('heading', { name: 'OCR Provider' })).toBeVisible();

  // Provider select lives inside the OCR Provider section
  const providerSelect = page.locator('section').filter({ hasText: 'OCR Provider' }).getByRole('combobox').first();
  await expect(providerSelect).toBeVisible();

  // Switching to anthropic reveals API key input
  await providerSelect.selectOption('anthropic');
  await expect(page.getByPlaceholder(/anthropic api key/i)).toBeVisible();

  // Switching to vertex reveals Google Cloud Project ID input
  await providerSelect.selectOption('vertex');
  await expect(page.getByPlaceholder(/google cloud project id/i)).toBeVisible();
});
