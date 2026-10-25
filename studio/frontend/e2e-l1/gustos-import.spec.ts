/**
 * V-4 · «Importar gustos» suma al proyecto los votos del muro de Entropía.
 * Se comprueba en IndexedDB, que es donde vive la memoria del proyecto.
 */
import { expect, test, type Page, type Route } from '@playwright/test';
import fs from 'node:fs';

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
    const endpoint = url.pathname;
    if (endpoint === '/api/health') return json(route, { ready: true, version: 'l1-mock', ocr_available: false, workspace: { writable: true } });
    if (endpoint === '/api/samples') return json(route, { ok: true, samples: [{ key: 'mock_three_pages', description: 'PDF de tres páginas' }] });
    if (endpoint === '/api/sessions/open_sample') return json(route, { ok: true, session_id: 'studio_sess_abcdef', filename: 'tres-paginas.pdf', summary: mockSummary });
    if (endpoint.endsWith('/nodes')) return json(route, { nodes: [] });
    if (endpoint.endsWith('/transaction')) return json(route, { staged_operations: [], transaction_state: 'READY' });
    if (endpoint.includes('/render')) {
      const pageNumber = Number(endpoint.match(/page\/(\d+)/)?.[1] ?? 0);
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

async function leerGustos(page: Page, projectId: string) {
  return page.evaluate(async (id) => new Promise<{ referentes?: Record<string, number>; reglas?: Record<string, number>; herramientas?: Record<string, number>; pares?: Record<string, number> } | null>((resolve) => {
    const request = indexedDB.open('prometeo-studio-project-workspace');
    request.onerror = () => resolve(null);
    request.onsuccess = () => {
      const database = request.result;
      const transaction = database.transaction('projects', 'readonly');
      const get = transaction.objectStore('projects').get(id);
      get.onerror = () => resolve(null);
      get.onsuccess = () => {
        const project = get.result as { gustos?: Record<string, Record<string, number>> } | undefined;
        resolve(project?.gustos ?? null);
      };
    };
  }), projectId);
}

test('V-4: importar gustos-parcial suma ♥ y ✕ al proyecto activo', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await openBoard(page);
  await page.getByRole('button', { name: /^Biblioteca/ }).click();
  await page.getByRole('menuitem', { name: 'Importar referentes' }).click();
  await expect(page.getByText(/Biblioteca.*(creado|actualizado)/)).toBeVisible();
  const projectId = await page.locator('#project-select').inputValue();

  const archivo = test.info().outputPath('gustos-parcial.json');
  fs.writeFileSync(archivo, JSON.stringify({
    format: 'prometeo-entropia-gustos',
    version: 1,
    proyecto: 'prueba',
    items: [
      {
        semilla: 'a',
        regla: 'dada',
        herramienta: 'note',
        restriccion: 'solo dos colores',
        referentes: ['referente-letterform', 'referente-archives-design'],
        voto: 'like',
      },
      {
        semilla: 'b',
        regla: 'suizo',
        herramienta: 'marco',
        restriccion: 'quita lo más bonito',
        referentes: ['referente-nypl', 'referente-cooper-hewitt'],
        voto: 'nope',
      },
    ],
  }, null, 2));

  await page.locator('input[aria-label="Archivo de gustos parciales"]').setInputFiles(archivo);
  await expect(page.getByText(/Gustos importados: 1 ♥ y 1 ✕/)).toBeVisible();

  await expect.poll(async () => {
    const gustos = await leerGustos(page, projectId);
    return gustos?.referentes?.['referente-letterform'];
  }).toBe(2);

  const gustos = await leerGustos(page, projectId);
  expect(gustos?.referentes?.['referente-archives-design']).toBe(2);
  expect(gustos?.referentes?.['referente-nypl']).toBe(0.2);
  expect(gustos?.referentes?.['referente-cooper-hewitt']).toBe(0.2);
  expect(gustos?.reglas?.dada).toBe(2);
  expect(gustos?.reglas?.suizo).toBe(0.2);
  expect(gustos?.herramientas?.note).toBe(2);
  expect(gustos?.herramientas?.marco).toBe(0.2);
  expect(gustos?.pares?.['referente-archives-design|referente-letterform']).toBe(2);
  expect(gustos?.pares?.['referente-cooper-hewitt|referente-nypl']).toBe(0.2);

  // Importar dos veces el mismo archivo suma otra vez, no reemplaza.
  await page.locator('input[aria-label="Archivo de gustos parciales"]').setInputFiles(archivo);
  await expect.poll(async () => {
    const despues = await leerGustos(page, projectId);
    return despues?.referentes?.['referente-letterform'];
  }).toBe(3);
});
