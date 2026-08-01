import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: process.env.CI ? 'github' : 'html',
  globalSetup: './tests/global-setup.ts',
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost',
    storageState: 'tests/playwright/.auth/user.json',
    serviceWorkers: 'block',
    trace: 'on-first-retry',
    screenshot: 'on',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
