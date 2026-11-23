import { defineConfig } from '@playwright/test';

// Node-only unit specs (no browser, no global setup / backend needed).
// Separate from playwright.config.ts so the E2E run is unchanged.
export default defineConfig({
  testDir: './tests/unit',
  reporter: 'list',
});
