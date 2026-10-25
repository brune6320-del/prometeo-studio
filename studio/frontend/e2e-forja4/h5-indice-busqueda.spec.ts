/**
 * H5 · índice del tablero y búsqueda que lleva.
 * Top 8 y 9 de A-1; debates D8 y D10; regla 17.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, DB_NAME, leerTablero, mockReadyBackend, nota, openBoard, tablero, type SeedBoard } from './helpers';

async function sembrarVarios(page: Page, boards: SeedBoard[], activeId: string) {
  await page.evaluate(async ({ boards: lista, activeId: activo, dbName }) => {
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open(dbName);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('boards')) db.createObjectStore('boards', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
      };
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction(['boards', 'meta'], 'readwrite');
        for (const board of lista) tx.objectStore('boards').put(board);
        tx.objectStore('meta').put({ key: 'active-board-id', value: activo });
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
    });
  }, { boards, activeId, dbName: DB_NAME });
}

test('H5 · el índice virtualiza 500, busca, multiselecciona, bloquea y trae al frente', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  const cartas = Array.from({ length: 500 }, (_, indice) => nota(`n${indice}`, (indice % 20) * 280, Math.floor(indice / 20) * 210, `Tarjeta ${indice}`));
  const board = tablero(cartas, 'board-h5', 'Índice 500');
  await mockReadyBackend(page);
  await page.goto('/');
  await sembrarVarios(page, [board], 'board-h5');
  await page.reload();
  await openBoard(page);
  await expect(page.locator('[data-card-id]')).toHaveCount(500);

  await page.keyboard.press('l');
  const panel = page.getByRole('complementary', { name: 'Índice del tablero' });
  await expect(panel).toBeVisible();
  expect(await panel.locator('.board-index-row').count()).toBeLessThan(80);
  await page.screenshot({ path: path.join(CAPTURAS, 'H5-antes-indice-500.png') });

  await page.getByLabel('Buscar en el índice').fill('Tarjeta 499');
  await expect(panel.locator('.board-index-row')).toHaveCount(1);
  await panel.locator('.board-index-row').click();
  await expect(page.getByTestId('selection-live')).toHaveText('1 seleccionada');
  await panel.getByRole('button', { name: 'Traer al frente' }).click();
  await expect.poll(async () => (await leerTablero(page, 'board-h5'))?.cards.at(-1)?.id).toBe('n499');

  await page.getByLabel('Buscar en el índice').fill('');
  await panel.locator('.board-index-row').first().click();
  await panel.locator('.board-index-row').nth(1).click({ modifiers: ['Shift'] });
  await expect(page.getByTestId('selection-live')).toHaveText('2 seleccionadas');
  await panel.locator('.board-index-row').first().getByRole('button', { name: /^Bloquear/ }).click();
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h5');
    return guardado?.cards.find((card) => card.id === 'n499')?.locked;
  }).toBe(true);
  await page.screenshot({ path: path.join(CAPTURAS, 'H5-despues-indice-gestion.png') });

  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  expect(await page.evaluate(() => (document.activeElement as HTMLElement | null)?.classList.contains('board-viewport'))).toBe(true);
});

test('H5 · ⌘F encuentra, cuenta, cambia de alcance y lleva al resultado', async ({ page }) => {
  const a = tablero([nota('a1', 120, 120, 'alfa uno')], 'board-busqueda-a', 'Tablero A');
  const b = tablero([
    nota('b1', 120, 120, 'alfa dos'),
    { id: 'ref', type: 'referente', title: 'alfa referente', body: '', x: 500, y: 120, width: 280, color: 'paper', datos: { nombre: 'alfa referente', imagenes: [], etiquetas: [] } },
  ], 'board-busqueda-b', 'Tablero B');
  await mockReadyBackend(page);
  await page.goto('/');
  await sembrarVarios(page, [a, b], 'board-busqueda-a');
  await page.reload();
  await openBoard(page);

  await page.keyboard.press('Meta+f');
  const buscador = page.getByLabel('Buscar tarjetas');
  await expect(buscador).toBeFocused();
  await buscador.fill('alfa');
  await expect(page.getByTestId('search-count')).toHaveText('1 resultado');
  await page.keyboard.press('Enter');
  await expect(page.getByTestId('selection-live')).toHaveText('1 seleccionada');
  const caja = await page.locator('[data-card-id="a1"]').boundingBox();
  const viewport = await page.locator('.board-viewport').boundingBox();
  if (!caja || !viewport) throw new Error('Sin cajas para centrar.');
  expect(Math.abs((caja.x + caja.width / 2) - (viewport.x + viewport.width / 2))).toBeLessThan(40);
  expect(Math.abs((caja.y + caja.height / 2) - (viewport.y + viewport.height / 2))).toBeLessThan(40);

  // Alcance proyecto: encuentra el otro tablero; alcance biblioteca: solo referentes.
  await page.keyboard.press('Meta+f');
  await buscador.fill('dos');
  await page.getByLabel('Alcance de búsqueda').selectOption('proyecto');
  await expect(page.getByTestId('search-count')).toHaveText('1 resultado');
  await page.keyboard.press('Enter');
  await expect(page.locator('#board-select')).toHaveValue('board-busqueda-b');
  await expect(page.locator('[data-card-id="b1"]')).toHaveClass(/selected/);
  await expect(page.getByTestId('board-undo-toast')).toHaveCount(0);

  await page.keyboard.press('Meta+f');
  await buscador.fill('alfa');
  await page.getByLabel('Alcance de búsqueda').selectOption('biblioteca');
  await expect(page.getByTestId('search-count')).toHaveText('1 resultado');
  await expect(page.getByRole('option', { name: /alfa referente/ })).toBeVisible();
  await page.screenshot({ path: path.join(CAPTURAS, 'H5-despues-busqueda-alcance.png') });
});
