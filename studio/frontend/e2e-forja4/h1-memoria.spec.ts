/**
 * H1 · Memoria de 30 días, historial persistente y volcado al cerrar.
 * Top 1 y 15 de A-1; debates D3, D13 y D15.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, DB_NAME, abrirTableroSembrado, leerTablero, mockReadyBackend, nota, openBoard, sembrar, tablero } from './helpers';

async function leerMemoria(page: Page) {
  return page.evaluate(async () => new Promise<Array<{ id: string; kind: string; label: string; payload: Record<string, unknown> }>>((resolve) => {
    const request = indexedDB.open('prometeo-studio-memoria');
    request.onerror = () => resolve([]);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('borrados')) db.createObjectStore('borrados', { keyPath: 'id' });
      if (!db.objectStoreNames.contains('historial')) db.createObjectStore('historial', { keyPath: 'boardId' });
    };
    request.onsuccess = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('borrados')) { db.close(); resolve([]); return; }
      const tx = db.transaction('borrados', 'readonly');
      const get = tx.objectStore('borrados').getAll();
      get.onsuccess = () => { db.close(); resolve(get.result as Array<{ id: string; kind: string; label: string; payload: Record<string, unknown> }>); };
      get.onerror = () => { db.close(); resolve([]); };
    };
  }));
}

test('H1 · un tablero borrado se recupera desde Archivo después de recargar', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await mockReadyBackend(page);
  await page.goto('/');
  await openBoard(page);
  await page.getByRole('button', { name: 'Nueva nota' }).click();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
  await page.locator('.board-card-title').dblclick();
  await page.getByLabel('Título de tarjeta').fill('Memoria viva');
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'Eliminar tablero' }).click();
  const toast = page.getByTestId('board-undo-toast');
  await expect(toast).toContainText('30 días en Archivo');
  await page.screenshot({ path: path.join(CAPTURAS, 'H1-antes-aviso-5s.png') });

  await expect.poll(async () => (await leerMemoria(page)).length).toBeGreaterThan(0);
  const memoria = await leerMemoria(page);
  const entrada = memoria.find((item) => item.kind === 'board');
  expect(entrada).toBeTruthy();
  expect((entrada!.payload.board as { cards: unknown[] }).cards).toHaveLength(1);

  await page.reload();
  await openBoard(page);
  await page.getByRole('button', { name: 'Archivo y recientes borrados' }).click();
  const dialog = page.getByRole('dialog', { name: 'Archivo' });
  await expect(dialog.getByRole('heading', { name: 'Recientes borrados' })).toBeVisible();
  await expect(dialog).toContainText('Tablero «Mi tablero»');
  await page.screenshot({ path: path.join(CAPTURAS, 'H1-despues-archivo.png') });
  await dialog.getByRole('button', { name: 'Restaurar' }).first().click();
  await expect(page.locator('.board-card-title')).toHaveText('Memoria viva');
  await expect(page.getByText('Tablero «Mi tablero» recuperado.')).toBeVisible();
});

test('H1 · borrar 150 tarjetas en un gesto deja una entrada y un solo paso de deshacer', async ({ page }) => {
  const cards = Array.from({ length: 150 }, (_, indice) => nota(`n${indice}`, (indice % 15) * 280, Math.floor(indice / 15) * 200, `n${indice}`));
  const board = tablero(cards, 'board-150', 'Ciento cincuenta');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  await expect(page.locator('[data-card-id]')).toHaveCount(150);

  await page.keyboard.press('Meta+a');
  await page.keyboard.press('Delete');
  await expect(page.locator('[data-card-id]')).toHaveCount(0);
  await expect(page.getByTestId('board-undo-toast')).toContainText('150 tarjetas eliminadas');

  await expect.poll(async () => (await leerMemoria(page)).some((item) => item.kind === 'cards')).toBe(true);
  const memoria = await leerMemoria(page);
  const entrada = memoria.find((item) => item.kind === 'cards');
  const payload = entrada?.payload as { cards?: { cards?: unknown[] } } | undefined;
  expect(payload?.cards?.cards).toHaveLength(150);

  await page.keyboard.press('Meta+z');
  await expect(page.locator('[data-card-id]')).toHaveCount(150);
});

test('H1 · el historial de deshacer se restaura al recargar y, si no hay, declara sesión nueva', async ({ page }) => {
  const board = tablero([nota('n1', 200, 200, 'Historial')], 'board-h1', 'Historial');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  await expect(page.getByTestId('history-status')).toContainText('sesión nueva');

  await page.locator('[data-card-id="n1"]').click();
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1200);
  const guardado = await leerTablero(page, 'board-h1');
  expect(guardado?.cards[0].x).toBe(201);

  await page.reload();
  await openBoard(page);
  await expect(page.getByTestId('history-status')).toContainText('historial restaurado');
  const deshacer = page.getByRole('button', { name: 'Deshacer' });
  await expect(deshacer).toBeEnabled();
  await deshacer.click();
  await expect(page.locator('[data-card-id="n1"]')).toHaveAttribute('style', /left:\s*200px/);
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
  await expect.poll(async () => (await leerTablero(page, 'board-h1'))?.cards[0].x, { timeout: 10_000 }).toBe(200);
});

test('H1 · cerrar con cambios pendientes fuerza el volcado antes de confirmar', async ({ page }) => {
  await page.addInitScript(() => {
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
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Nueva nota' }).click();
  await expect(page.getByText('Guardando…', { exact: true })).toBeVisible();

  // En el mismo fotograma del cambio: el cierre debe volcar, no preguntar.
  await page.evaluate(() => {
    const handler = (window as unknown as Record<string, unknown>).__prometeoCloseRequested;
    if (typeof handler !== 'function') throw new Error('Sin manejador de cierre');
    handler();
  });
  await expect.poll(() => page.evaluate(() => {
    const calls = (window as unknown as { __PROMETEO_TEST_INVOKES__: Array<{ cmd: string }> }).__PROMETEO_TEST_INVOKES__;
    return calls.some((call) => call.cmd === 'confirm_close');
  })).toBe(true);
  await expect(page.getByTestId('unsaved-dialog')).toHaveCount(0);

  const tableroGuardado = await page.evaluate(async (dbName) => new Promise<number>((resolve) => {
    const request = indexedDB.open(dbName);
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction('boards', 'readonly');
      const get = tx.objectStore('boards').getAll();
      get.onsuccess = () => {
        db.close();
        const boards = get.result as Array<{ cards?: unknown[] }>;
        resolve(boards.reduce((total, board) => total + (board.cards?.length ?? 0), 0));
      };
      get.onerror = () => { db.close(); resolve(-1); };
    };
    request.onerror = () => resolve(-1);
  }), DB_NAME);
  expect(tableroGuardado).toBe(1);
});
