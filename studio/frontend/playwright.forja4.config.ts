import { defineConfig } from '@playwright/test';

/**
 * Forja 4 · contratos de oficio (H0–H9).
 * Servidor propio en 4191 para no mezclarse con L1/L2 ni con el motor PDF real.
 * Las capturas antes/después viven en REPORTES/capturas-forja4/.
 */
export default defineConfig({
  testDir: './e2e-forja4',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/forja4-results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:4191',
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
    command: 'npm run dev -- --host 127.0.0.1 --port 4191',
    url: 'http://127.0.0.1:4191',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
