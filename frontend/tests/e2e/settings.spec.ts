import { test, expect } from '@playwright/test';

test('settings page loads and AI provider selector works', async ({ page }) => {
  await page.goto('/settings');

  const aiProviderSelect = page.getByLabel(/ai.*provider/i).or(
    page.getByRole('combobox', { name: /ai.*provider/i })
  );
  await expect(aiProviderSelect).toBeVisible();

  // Switching to local shows URL input
  await aiProviderSelect.selectOption('local');
  await expect(
    page.getByPlaceholder(/localhost:11434/i).or(page.getByLabel(/api url/i))
  ).toBeVisible();

  // Switching to vertex shows project ID input
  await aiProviderSelect.selectOption('vertex');
  await expect(page.getByLabel(/project id/i)).toBeVisible();
});
