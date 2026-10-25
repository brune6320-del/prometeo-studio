/**
 * H8 · el documento declara lo que puede y no finge.
 * Top 5 de A-1; debate D7; reglas 11 y 18, y regla 8 para el manifiesto.
 */
import { expect, test, type Page, type Route } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, leerTablero, mockReadyBackend, nota, tablero } from './helpers';

const NODE = { id: 't1', type: 'TEXT', page: 0, bbox: [100, 120, 330, 150], text: 'Contrato de prueba', font: 'Helvetica', size: 12 };

async function abrirPdf(page: Page) {
  await page.locator('[data-sample="mock_three_pages"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('tres-paginas.pdf');
}

test.beforeEach(async ({ page }) => {
  await mockReadyBackend(page);
  await page.route((url) => url.pathname.startsWith('/api/sessions/'), async (route: Route) => {
    const url = new URL(route.request().url());
    const endpoint = url.pathname;
    if (endpoint.endsWith('/nodes')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ nodes: [NODE] }) });
    }
    if (endpoint.includes('/node/t1')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(NODE) });
    }
    if (endpoint.endsWith('/typography')) {
      const body = route.request().postDataJSON() as { new_text?: string };
      if ((body.new_text ?? '').length > 20) {
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
          ok: false,
          code: 'TYPOGRAPHY_DOES_NOT_FIT',
          reason: 'El texto no cabe: necesita 380.0 pt y hay 230.0 pt.',
          measured_width_pt: 380,
          available_width_pt: 230,
          suggested_size_pt: 7.2,
        }) });
      }
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({
        ok: true,
        filename: 'tipografia.pdf',
        token: 'tipografia_abcdef123456',
        sha256: 'd'.repeat(64),
        others_unchanged: true,
      }) });
    }
    if (endpoint.endsWith('/annotate')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, filename: 'anotado.pdf', token: 'anotacion_abcdef123456', sha256: 'e'.repeat(64), layer: 'Prometeo · anotaciones' }) });
    }
    if (endpoint.endsWith('/organize_pages')) {
      return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, filename: 'paginas.pdf', token: 'paginas_abcdef123456', sha256: 'f'.repeat(64) }) });
    }
    return route.fallback();
  });
});

test('H8 · capacidades, selección de texto, tipografía verificada y rechazo explicado', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.goto('/');
  await abrirPdf(page);
  await expect(page.locator('.overlay[data-node-id="t1"]')).toBeVisible();
  const caja = await page.locator('.overlay[data-node-id="t1"]').boundingBox();
  if (!caja) throw new Error('Sin caja de texto.');
  await page.mouse.move(caja.x + 3, caja.y + caja.height / 2);
  await page.mouse.down();
  await page.mouse.move(caja.x + caja.width - 3, caja.y + caja.height / 2, { steps: 8 });
  await page.mouse.up();
  const seleccionado = await page.evaluate(() => window.getSelection()?.toString() ?? '');
  expect(seleccionado).toContain('Contrato');
  await page.screenshot({ path: path.join(CAPTURAS, 'H8-antes-texto-seleccion.png') });

  await page.getByRole('button', { name: 'Documento', exact: true }).click();
  const dialogo = page.getByRole('dialog', { name: 'Documento' });
  await expect(dialogo).toContainText('Texto nativo verificable');
  await page.screenshot({ path: path.join(CAPTURAS, 'H8-despues-capacidades.png') });

  await dialogo.getByRole('tab', { name: 'Tipografía' }).click();
  const texto = dialogo.getByLabel('Texto');
  await texto.fill('Contrato de prueba demasiado largo para la caja original');
  await dialogo.getByRole('button', { name: /Cambiar tipografía y verificar/ }).click();
  await expect(dialogo).toContainText('El texto no cabe');
  await expect(dialogo).toContainText('sugerido');
  await texto.fill('Contrato');
  await dialogo.getByRole('button', { name: /Cambiar tipografía y verificar/ }).click();
  await expect(dialogo).toContainText('Copia nueva creada');
  await expect(dialogo).toContainText('SHA-256');
});

test('H8 · anotar y organizar páginas producen una copia nueva', async ({ page }) => {
  await page.goto('/');
  await abrirPdf(page);
  await page.getByRole('button', { name: 'Documento', exact: true }).click();
  const dialogo = page.getByRole('dialog', { name: 'Documento' });

  await dialogo.getByRole('tab', { name: 'Anotar' }).click();
  await dialogo.getByLabel('Texto').fill('Nota de Prometeo');
  await dialogo.getByRole('button', { name: /Añadir en capa y crear copia/ }).click();
  await expect(dialogo).toContainText('Copia nueva creada');
  await expect(dialogo).toContainText('Prometeo · anotaciones');

  const capturado = page.waitForRequest((request) => request.url().endsWith('/organize_pages'));
  await dialogo.getByRole('tab', { name: 'Páginas' }).click();
  await dialogo.getByRole('button', { name: 'Bajar página 1' }).click();
  await dialogo.getByRole('button', { name: 'Rotar página 2' }).click();
  await dialogo.getByRole('button', { name: /Organizar \d+ páginas?/ }).click();
  const request = await capturado;
  const cuerpo = request.postDataJSON() as { order: number[]; rotate: Array<{ page: number; degrees: number }> };
  expect(cuerpo.order[0]).toBe(2);
  expect(cuerpo.rotate).toEqual([{ page: 2, degrees: 90 }]);
  await expect(dialogo).toContainText('Copia nueva creada');
});

test('H8 · el manifiesto llega como propuesta: Enter acepta y Esc descarta', async ({ page }) => {
  const board = tablero([
    {
      id: 'e1',
      type: 'marco',
      title: 'Collage',
      body: '',
      x: 160,
      y: 160,
      width: 560,
      color: 'paper',
      datos: {
        modo: 'entropia', semilla: 'abc123', regla: 'dada', reglaNombre: 'Dadá', restriccion: '',
        herramienta: 'note', fuentes: [], disposicion: [], ancho: 560, alto: 380,
        guardado: true, creado: new Date().toISOString(),
      },
    },
  ], 'board-h8-manifiesto', 'Propuesta');
  await mockReadyBackend(page);
  await page.route('**/api/manifiesto/escribir', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ disponible: true, modelo: 'mock', lineas: ['1. Abrir el archivo', '2. Cerrar la forma'] }) });
  });
  await page.goto('/');
  await sembrarBoard(page, board);
  await page.reload();
  await page.getByRole('button', { name: 'Tablero' }).click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: /^Biblioteca/ }).click();
  await page.getByRole('menuitem', { name: /Manifiesto/ }).click();
  const propuesta = page.getByRole('group', { name: 'Propuesta de manifiesto pendiente' });
  await expect(propuesta).toBeVisible();
  await expect(propuesta).toContainText('Enter o clic acepta');
  const antes = await leerTablero(page, 'board-h8-manifiesto');
  await page.keyboard.press('Escape');
  await expect(propuesta).toHaveCount(0);
  expect((await leerTablero(page, 'board-h8-manifiesto'))?.cards.length).toBe(antes?.cards.length);

  await page.getByRole('button', { name: /^Biblioteca/ }).click();
  await page.getByRole('menuitem', { name: /Manifiesto/ }).click();
  await expect(page.getByRole('group', { name: 'Propuesta de manifiesto pendiente' })).toBeVisible();
  await page.keyboard.press('Enter');
  await expect(propuesta).toHaveCount(0);
  await expect.poll(async () => (await leerTablero(page, 'board-h8-manifiesto'))?.cards.length).toBeGreaterThan(antes?.cards.length ?? 0);
  await page.screenshot({ path: path.join(CAPTURAS, 'H8-despues-propuesta-aceptada.png') });
});

async function sembrarBoard(page: Page, board: ReturnType<typeof tablero>) {
  await page.evaluate(async ({ board: valor, dbName }) => {
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open(dbName);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('boards')) db.createObjectStore('boards', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
      };
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction(['boards', 'meta'], 'readwrite');
        tx.objectStore('boards').put(valor);
        tx.objectStore('meta').put({ key: 'active-board-id', value: valor.id });
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
      request.onerror = () => reject(request.error);
    });
  }, { board, dbName: 'prometeo-studio-visual-board' });
}
