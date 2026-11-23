import { test, expect } from '@playwright/test';

test('settings page loads and OCR provider selector works', async ({ page }) => {
  await page.goto('/settings');

  await expect(page.getByRole('heading', { name: 'OCR Provider' })).toBeVisible();

  // Provider select lives inside the OCR Provider section
  const providerSelect = page.locator('section').filter({ hasText: 'OCR Provider' }).getByRole('combobox').first();
  await expect(providerSelect).toBeVisible();

  // Core build offers only Tesseract; AI providers appear only when the plugin is installed.
  await providerSelect.selectOption('tesseract');
  await expect(providerSelect).toHaveValue('tesseract');
  await expect(providerSelect.locator('option[value="anthropic"]')).toHaveCount(0);
});
