import { defineConfig } from '@playwright/test';

/**
 * T-3 · caza de congelones sobre el build de producción.
 * Mismo escenario que H9 pero con observadores de longtask y LoAF, marcas de
 * la app (autosave, historial, LOD, índice, contain) y correlación por acción.
 *
 *   npx playwright test -c playwright.t3.config.ts
 *   T3_MINUTOS=3 T3_DIAGNOSTICO=1 npx playwright test -c playwright.t3.config.ts
 */
export default defineConfig({
  testDir: './e2e-forja4',
  testMatch: /t3-.*\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  timeout: 22 * 60 * 1000,
  use: {
    baseURL: 'http://127.0.0.1:4193',
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
    command: 'npm run build && npx vite preview --host 127.0.0.1 --port 4193',
    url: 'http://127.0.0.1:4193',
    reuseExistingServer: false,
    timeout: 180_000,
  },
});
