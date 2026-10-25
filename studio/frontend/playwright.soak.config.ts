import { defineConfig } from '@playwright/test';

/**
 * H9 · soak sobre el build de producción. Vite preview sirve el bundle real.
 * El presupuesto de fotogramas se mide con rAF dentro de la página.
 */
export default defineConfig({
  testDir: './e2e-forja4',
  testMatch: /h9-soak\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  timeout: 16 * 60 * 1000,
  use: {
    baseURL: 'http://127.0.0.1:4192',
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
    command: 'npm run build && npx vite preview --host 127.0.0.1 --port 4192',
    url: 'http://127.0.0.1:4192',
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
