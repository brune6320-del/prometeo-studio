import { expect, test, type Page, type Route } from '@playwright/test';

const mockSummary = {
  document_id: 'doc_mock',
  source_sha256: 'a'.repeat(64),
  filename: 'tres-paginas.pdf',
  pages_count: 3,
  total_nodes: 0,
  text_nodes_count: 0,
  image_nodes_count: 0,
  vector_nodes_count: 0,
  docgraph_version: '0.3',
  session_id: 'studio_sess_abcdef',
  transaction_state: 'READY',
  staged_count: 0,
  capabilities: {
    is_born_digital: true,
    is_raster: false,
    can_text_edit: true,
    can_verify_physically: true,
    capability_badge: 'BORN_DIGITAL_FULL',
  },
};

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

async function mockReadyBackend(page: Page) {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    if (path === '/api/health') return json(route, { ready: true, version: 'l1-mock', ocr_available: false, workspace: { writable: true } });
    if (path === '/api/samples') return json(route, { ok: true, samples: [{ key: 'mock_three_pages', description: 'PDF de tres páginas' }] });
    if (path === '/api/sessions/open_sample') return json(route, { ok: true, session_id: 'studio_sess_abcdef', filename: 'tres-paginas.pdf', summary: mockSummary });
    if (path.endsWith('/nodes')) return json(route, { nodes: [] });
    if (path.endsWith('/transaction')) return json(route, { staged_operations: [], transaction_state: 'READY' });
    if (path.includes('/render')) {
      const pageNumber = Number(path.match(/page\/(\d+)/)?.[1] ?? 0);
      const svg = encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="612" height="792"><rect width="100%" height="100%" fill="white"/></svg>');
      return json(route, { page: { page_number: pageNumber, width_pt: 612, height_pt: 792, image_data_url: 'data:image/svg+xml,' + svg } });
    }
    return json(route, { ok: true });
  });
}

async function openBoard(page: Page) {
  await page.getByRole('button', { name: 'Tablero' }).click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
}

test('R-02: el cierre desde el tablero muestra el diálogo y bloquea el fondo', async ({ page }) => {
  await page.addInitScript(() => {
    const original = window.setTimeout.bind(window);
    window.setTimeout = ((handler: TimerHandler, timeout?: number, ...args: unknown[]) =>
      original(handler, timeout === 400 ? 5000 : timeout, ...args)) as typeof window.setTimeout;
    const testWindow = window as unknown as {
      __PROMETEO_TEST_INVOKES__: Array<{ cmd: string; args?: Record<string, unknown> }>;
      __TAURI_INTERNALS__: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> };
    };
    testWindow.__PROMETEO_TEST_INVOKES__ = [];
    testWindow.__TAURI_INTERNALS__ = {
      invoke: async (cmd, args) => {
        testWindow.__PROMETEO_TEST_INVOKES__.push({ cmd, args });
        return null;
      },
    };
  });
  await mockReadyBackend(page);
  await page.goto('/');
  await openBoard(page);
  await page.getByRole('button', { name: 'Nueva nota' }).click();
  await expect(page.getByText('Guardando…', { exact: true })).toBeVisible();
  await expect.poll(() => page.evaluate(() => {
    const calls = (window as unknown as { __PROMETEO_TEST_INVOKES__: Array<{ cmd: string; args?: Record<string, unknown> }> }).__PROMETEO_TEST_INVOKES__;
    return calls.some((call) => call.cmd === 'set_unsaved_work' && call.args?.dirty === true && call.args?.kind === 'board_unsaved');
  })).toBe(true);
  await page.evaluate(() => {
    const handler = (window as unknown as Record<string, unknown>).__prometeoCloseRequested;
    if (typeof handler !== 'function') throw new Error('Manejador de cierre no instalado');
    handler();
  });
  const dialog = page.getByRole('alertdialog');
  await expect(dialog).toBeVisible();
  await expect.poll(() => page.evaluate(() => {
    const calls = (window as unknown as { __PROMETEO_TEST_INVOKES__: Array<{ cmd: string }> }).__PROMETEO_TEST_INVOKES__;
    return calls.some((call) => call.cmd === 'close_dialog_shown');
  })).toBe(true);
  await expect(dialog).toContainText('El tablero aún no está guardado');
  await expect(page.locator('.board-workspace')).toHaveAttribute('inert', '');
  await dialog.getByRole('button', { name: 'Cancelar' }).click();
  await expect(dialog).toHaveCount(0);
});

test('R-03: los atajos PDF no cambian de página ni abren búsqueda dentro del tablero', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await page.locator('[data-sample="mock_three_pages"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('tres-paginas.pdf');
  await expect(page.locator('#page-jump')).toHaveValue('1');
  await openBoard(page);
  await page.keyboard.press('PageDown');
  await page.keyboard.press('PageDown');
  await page.keyboard.press('Meta+f');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: /Buscar/ })).toHaveCount(0);
  await page.locator('.board-back').click();
  await expect(page.locator('#page-jump')).toHaveValue('1');
});

test('R-09: todas las herramientas quedan visibles sin desbordamiento horizontal', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await openBoard(page);
  // Desde Forja 2 las herramientas viven en un rail vertical y la barra superior
  // es una sola fila. El contrato es el mismo: nada se sale de su caja.
  const rail = await page.locator('.board-rail').evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
  }));
  expect(rail.scrollWidth).toBeLessThanOrEqual(rail.clientWidth + 1);
  expect(rail.scrollHeight).toBeLessThanOrEqual(rail.clientHeight + 1);
  const header = await page.locator('.board-header').evaluate((element) => ({
    scrollWidth: element.scrollWidth,
    clientWidth: element.clientWidth,
  }));
  expect(header.scrollWidth).toBeLessThanOrEqual(header.clientWidth + 1);
  // Las ocho herramientas del rail más «Más» siguen visibles a 800 px de alto.
  await expect(page.locator('.board-rail .board-rail-tool')).toHaveCount(9);
});

test('R-10: el tablero abre mientras el motor PDF no responde', async ({ page }) => {
  await page.route('**/api/health', (route) => route.abort('connectionrefused'));
  await page.goto('/');
  const button = page.getByRole('button', { name: /Abrir tablero visual/ });
  await expect(button).toBeVisible();
  await button.click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Nueva nota' }).click();
  await page.locator('.board-card-title').last().dblclick();
  await page.getByLabel('Título de tarjeta').last().fill('Persistencia sin motor');
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
  await page.locator('.board-back').click();
  await expect(button).toBeVisible();
  await button.click();
  await expect(page.locator('.board-card-title').last()).toHaveText('Persistencia sin motor');
});
