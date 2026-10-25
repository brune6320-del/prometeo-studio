import { defineConfig, devices, type PlaywrightTestProject } from '@playwright/test';
import fs from 'fs';

const LOCAL_CHROMIUM = process.env.PROMETEO_E2E_CHROMIUM_PATH ?? '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser';
const projects: PlaywrightTestProject[] = [];
if (fs.existsSync(LOCAL_CHROMIUM)) {
  projects.push({ name: 'brave', use: { ...devices['Desktop Chrome'], launchOptions: { executablePath: LOCAL_CHROMIUM } } });
}

export default defineConfig({
  testDir: './e2e-forja3',
  timeout: 90_000,
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5174',
    viewport: { width: 1440, height: 900 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects,
  webServer: {
    command: 'npx vite --port 5174',
    url: 'http://localhost:5174',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
