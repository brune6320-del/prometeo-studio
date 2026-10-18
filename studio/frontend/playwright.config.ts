import { defineConfig, devices, type PlaywrightTestProject } from '@playwright/test';
import { fileURLToPath } from 'url';
import path from 'path';
import fs from 'fs';
import os from 'os';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const REPO_ROOT = path.resolve(__dirname, '../..');

/**
 * Navegadores (CAMP-002 · F2):
 * - «brave»: Chromium ya instalado en este Mac (sin descargas). Ruta configurable con
 *   PROMETEO_E2E_CHROMIUM_PATH (Chrome, Edge, Brave…).
 * - «chromium» y «webkit»: navegadores de Playwright; solo si se pidieron (PROMETEO_E2E_PLAYWRIGHT_BROWSERS=1)
 *   porque hay que descargarlos (`npx playwright install`). WebKit real se cubre en las pruebas
 *   nativas (WKWebView de la app instalada).
 */
const LOCAL_CHROMIUM = process.env.PROMETEO_E2E_CHROMIUM_PATH ?? '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser';
const projects: PlaywrightTestProject[] = [];
if (fs.existsSync(LOCAL_CHROMIUM)) {
  projects.push({ name: 'brave', use: { ...devices['Desktop Chrome'], launchOptions: { executablePath: LOCAL_CHROMIUM } } });
}
if (process.env.PROMETEO_E2E_PLAYWRIGHT_BROWSERS === '1') {
  projects.push({ name: 'chromium', use: { ...devices['Desktop Chrome'] } });
  // WebKit es el motor del WKWebView de la app de escritorio (macOS).
  projects.push({ name: 'webkit', use: { ...devices['Desktop Safari'] } });
}
// El motor de pruebas escribe en una carpeta temporal, nunca dentro del repositorio.
const E2E_WORKSPACE = fs.mkdtempSync(path.join(os.tmpdir(), 'prometeo_e2e_ws_'));

export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.spec\.ts/,
  testIgnore: ['**/src/tests/**', '**/*.test.ts'],
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: process.env.PROMETEO_E2E_REPORT ?? 'test-results/e2e-report.json' }]],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
  },
  projects,
  webServer: [
    {
      command: `${process.env.PROMETEO_PYTHON ?? REPO_ROOT + '/.venv/bin/python'} -m uvicorn studio.backend.app:app --host 127.0.0.1 --port 8000`,
      cwd: REPO_ROOT,
      env: {
        PYTHONPATH: `${REPO_ROOT}:${REPO_ROOT}/fase0`,
        PYTHONDONTWRITEBYTECODE: '1',
        PROMETEO_WORKSPACE: E2E_WORKSPACE,
      },
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: true,
      timeout: 30000,
    },
    {
      command: 'npm run dev',
      cwd: __dirname,
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 30000,
    },
  ],
});
