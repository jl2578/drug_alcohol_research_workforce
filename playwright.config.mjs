import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir: './tests/browser',
  timeout: 45000,
  expect: {timeout: 12000},
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:8124/drug_alcohol_research_workforce/dashboard/',
    viewport: {width: 1440,height: 1000},
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    acceptDownloads: true,
  },
  projects: [{name:'chromium',use:{browserName:'chromium'}}],
  webServer: {
    command: 'node scripts/serve_dashboard.mjs',
    url: 'http://127.0.0.1:8124/drug_alcohol_research_workforce/dashboard/',
    reuseExistingServer: !process.env.CI,
    timeout: 15000,
  },
});
