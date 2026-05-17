import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : undefined,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [
    ['line'],
    ['allure-playwright', { outputFolder: 'allure-results', detail: true, suiteTitle: false }],
    ['html', { outputFolder: 'playwright-report', open: 'never' }]
  ],
  use: {
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 20_000
  },
  projects: [
    { name: 'unit', testMatch: /tests\/unit\/.*\.spec\.ts$/ },
    { name: 'api', testMatch: /tests\/api\/.*\.spec\.ts$/, use: { ...devices['Desktop Chrome'] } },
    { name: 'ui', testMatch: /tests\/ui\/.*\.spec\.ts$/, use: { ...devices['Desktop Chrome'] } },
    { name: 'e2e', testMatch: /tests\/e2e\/.*\.spec\.ts$/, use: { ...devices['Desktop Chrome'] } }
  ]
});
