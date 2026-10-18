import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e-l2',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/l2-app-results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:4188',
    viewport: { width: 1280, height: 800 },
    trace: 'off',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'brave',
      use: {
        launchOptions: {
          executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
        },
      },
    },
  ],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 4188',
    url: 'http://127.0.0.1:4188',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
