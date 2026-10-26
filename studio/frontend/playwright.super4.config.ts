import { defineConfig } from '@playwright/test';

/**
 * SUPER-4 · tacto y ahorro.
 * Servidor propio en 4192; backend PDF simulado en las pruebas de documento y
 * localStorage/IndexedDB real para el tablero.
 */
export default defineConfig({
  testDir: './e2e-super4',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'test-results/super4-results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:4192',
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
    command: 'npm run dev -- --host 127.0.0.1 --port 4192',
    url: 'http://127.0.0.1:4192',
    reuseExistingServer: false,
    timeout: 30000,
  },
});
