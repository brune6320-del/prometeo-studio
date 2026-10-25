/**
 * V-3 · Entropía sobre la pizarra.
 * Tres tiradas con semillas nuevas y ♥ deja una sola tarjeta guardada con la
 * última semilla. Todo local: no depende del motor PDF.
 */
import { expect, test, type Page, type Route } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

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

const CAPTURAS = path.resolve(process.cwd(), '../../REPORTES/capturas');

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

test('V-3: tres tiradas y ♥ deja una tarjeta con la última semilla', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await mockReadyBackend(page);
  await page.goto('/');
  await openBoard(page);

  // La biblioteca aporta los referentes del proyecto, aunque el collage viva en otro tablero.
  await page.getByRole('button', { name: /^Biblioteca/ }).click();
  await page.getByRole('menuitem', { name: 'Importar referentes' }).click();
  await expect(page.getByText(/Biblioteca.*(creado|actualizado)/)).toBeVisible();
  await page.locator('.board-header').getByRole('button', { name: 'Crear tablero' }).click();
  await expect(page.getByText('Tu espacio de ideas está listo')).toBeVisible();

  await page.getByRole('button', { name: 'Añadir entropía' }).click();
  const viewport = page.locator('.board-viewport');
  const box = await viewport.boundingBox();
  if (!box) throw new Error('No hay viewport del tablero.');
  await page.mouse.move(box.x + 120, box.y + 180);
  await page.mouse.down();
  await page.mouse.move(box.x + 760, box.y + 650, { steps: 8 });
  await page.mouse.up();

  const marco = page.locator('[data-marco="entropia"]');
  await expect(marco).toBeVisible();
  await expect(marco.getByText('Sin tirada todavía')).toBeVisible();
  await marco.getByRole('button', { name: 'Tirar' }).click();

  const vivo = page.locator('[data-entropia="vivo"]');
  await expect(vivo.locator('.board-entropia-lienzo')).toBeVisible();
  const semillas: string[] = [];
  semillas.push((await vivo.getAttribute('data-semilla')) ?? '');
  await page.screenshot({ path: path.join(CAPTURAS, 'entropia-1-tirada.png') });

  await vivo.getByRole('button', { name: 'Otra' }).click();
  await expect.poll(async () => (await vivo.getAttribute('data-semilla')) ?? '').not.toBe(semillas[0]);
  semillas.push((await vivo.getAttribute('data-semilla')) ?? '');
  await vivo.getByRole('button', { name: 'Otra' }).click();
  await expect.poll(async () => (await vivo.getAttribute('data-semilla')) ?? '').not.toBe(semillas[1]);
  semillas.push((await vivo.getAttribute('data-semilla')) ?? '');
  await expect(vivo.locator('.board-entropia-meta')).toContainText('·');
  await page.screenshot({ path: path.join(CAPTURAS, 'entropia-2-tres-tiradas.png') });

  expect(semillas).toHaveLength(3);
  for (const semilla of semillas) expect(semilla).toMatch(/^[0-9a-f]{10}$/);

  const ultima = semillas[2];
  await vivo.getByRole('button', { name: /Me gusta y guardar/ }).click();
  const guardado = page.locator('[data-entropia="guardado"]');
  await expect(guardado).toHaveCount(1);
  await expect(guardado).toHaveAttribute('data-semilla', ultima);
  await expect(guardado.locator('.board-entropia-meta')).toContainText(/Dadá|Bauhaus|Constructivista|Fluxus|Situacionista|Suizo|Irene/);
  await page.screenshot({ path: path.join(CAPTURAS, 'entropia-3-guardado.png') });

  // ♥ también deja la memoria de gusto en el proyecto, no en localStorage.
  const projectId = await page.locator('#project-select').inputValue();
  await expect.poll(async () => {
    const gustos = await leerGustos(page, projectId);
    return Object.keys(gustos?.referentes ?? {}).length;
  }).toBeGreaterThan(0);
  const gustos = await leerGustos(page, projectId);
  expect(Object.keys(gustos?.referentes ?? {}).length).toBeGreaterThanOrEqual(2);
  expect(Object.keys(gustos?.reglas ?? {})).toHaveLength(1);

  // El marco vivo sigue en la pizarra; solo la copia queda congelada.
  await expect(page.locator('[data-entropia="vivo"]')).toHaveCount(1);
  await expect(page.locator('[data-entropia="guardado"]')).toHaveCount(1);
});
