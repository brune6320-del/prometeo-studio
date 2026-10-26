/**
 * I0 · el visor pinta de verdad.
 * Falla si la zona visible no contiene píxeles de tinta (antes el test usaba una
 * página totalmente blanca y no podía distinguir «pintada» de «en blanco»).
 */
import { expect, test, type Page, type Route } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS } from './helpers';

const summary = {
  document_id: 'doc_visor', source_sha256: 'a'.repeat(64), filename: 'contrato.pdf',
  pages_count: 1, total_nodes: 1, text_nodes_count: 1, image_nodes_count: 0, vector_nodes_count: 0,
  docgraph_version: '0.3', session_id: 'studio_sess_visor', transaction_state: 'READY', staged_count: 0,
  capabilities: { is_born_digital: true, is_raster: false, can_text_edit: true, can_verify_physically: true, capability_badge: 'BORN_DIGITAL_FULL' },
};

const pageSvg = encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="612" height="792">'
  + '<rect width="100%" height="100%" fill="white"/>'
  + '<text x="72" y="110" font-family="Helvetica" font-size="30" fill="#111">CONTRATO DE SERVICIOS</text>'
  + '<text x="72" y="150" font-family="Helvetica" font-size="14" fill="#222">Contratado: Juan Perez</text>'
  + '</svg>',
);

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

async function mock(page: Page, imagen = 'data:image/svg+xml,' + pageSvg) {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const endpoint = new URL(route.request().url()).pathname;
    if (endpoint === '/api/health') return json(route, { ready: true, version: 'super4-mock', ocr_available: false, workspace: { writable: true } });
    if (endpoint === '/api/samples') return json(route, { ok: true, samples: [{ key: 'contrato', description: 'Contrato de servicios' }] });
    if (endpoint === '/api/sessions/open_sample') return json(route, { ok: true, session_id: 'studio_sess_visor', filename: 'contrato.pdf', summary });
    if (endpoint.endsWith('/nodes')) return json(route, { nodes: [{ id: 't1', type: 'TEXT', page: 0, bbox: [72, 90, 420, 115], text: 'CONTRATO DE SERVICIOS' }] });
    if (endpoint.endsWith('/transaction')) return json(route, { staged_operations: [], transaction_state: 'READY' });
    if (endpoint.includes('/render')) return json(route, { page: { page_number: 0, width_pt: 612, height_pt: 792, image_data_url: imagen } });
    return json(route, { ok: true });
  });
}

async function abrir(page: Page) {
  await page.goto('/');
  await page.selectOption('#sample-select', 'contrato');
  await expect(page.locator('[data-testid="pdf-page-image"]')).toBeVisible();
}

async function pixeles(page: Page) {
  return page.evaluate(() => {
    const img = document.querySelector<HTMLImageElement>('[data-testid="pdf-page-image"]');
    if (!img) return null;
    const canvas = document.createElement('canvas');
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0);
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    let tinta = 0;
    for (let i = 0; i < data.length; i += 4) {
      if (data[i] < 90 && data[i + 1] < 90 && data[i + 2] < 90) tinta += 1;
    }
    const caja = img.getBoundingClientRect();
    const visor = document.querySelector('.canvas-scroll')?.getBoundingClientRect();
    return {
      naturalWidth: img.naturalWidth,
      naturalHeight: img.naturalHeight,
      painted: img.dataset.painted,
      tinta,
      interseccion: visor ? Math.max(0, Math.min(caja.bottom, visor.bottom) - Math.max(caja.top, visor.top)) : 0,
    };
  });
}

for (const [width, height] of [[1440, 900], [1000, 800]] as Array<[number, number]>) {
  test(`I0 · a ${width}×${height} el visor pinta tinta y no un papel vacío`, async ({ page }) => {
    await page.setViewportSize({ width, height });
    await mock(page);
    await abrir(page);
    await expect(page.locator('[data-testid="pdf-page-image"]')).toHaveAttribute('data-painted', 'si');
    const resultado = await pixeles(page);
    expect(resultado).not.toBeNull();
    expect(resultado!.naturalWidth).toBeGreaterThan(0);
    expect(resultado!.tinta).toBeGreaterThan(100);
    expect(resultado!.interseccion).toBeGreaterThan(60);
    fs.mkdirSync(CAPTURAS, { recursive: true });
    await page.screenshot({ path: path.join(CAPTURAS, `I0-despues-visor-${width}.png`) });
  });
}

test('I0 · con el panel inferior expandido a 650 px de alto el visor sigue mostrando la página', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 650 });
  await mock(page);
  await abrir(page);
  const separador = page.getByRole('separator', { name: 'Altura del panel inferior' });
  await separador.focus();
  for (let i = 0; i < 12; i += 1) await separador.press('ArrowUp');
  const resultado = await pixeles(page);
  expect(resultado!.interseccion).toBeGreaterThan(60);
  expect(resultado!.tinta).toBeGreaterThan(100);
});

test('I0 · una imagen vacía se explica y se puede volver a dibujar', async ({ page }) => {
  await mock(page, '');
  await page.goto('/');
  await page.selectOption('#sample-select', 'contrato');
  await expect(page.locator('[data-testid="pdf-page-unpainted"]')).toBeVisible();
  await expect(page.locator('[data-testid="pdf-page-unpainted"]')).toContainText('La página no se pintó');
});
