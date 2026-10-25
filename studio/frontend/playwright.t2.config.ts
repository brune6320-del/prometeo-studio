import { defineConfig } from '@playwright/test';

/**
 * T-2 · medición de rendimiento sobre el build de producción. El presupuesto de
 * fotogramas (>32 ms) solo se exige aquí, no en el servidor de desarrollo.
 */
export default defineConfig({
  testDir: './e2e-l1',
  testMatch: /board-t2\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://127.0.0.1:4189',
    viewport: { width: 1440, height: 900 },
    trace: 'off',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'produccion',
      use: {
        launchOptions: {
          executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
        },
      },
    },
  ],
  webServer: {
    command: 'npm run build && npx vite preview --host 127.0.0.1 --port 4189',
    url: 'http://127.0.0.1:4189',
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
