/**
 * T-3 · prueba de regresión: un autosave con 500 tarjetas no puede producir un
 * longtask de más de 200 ms.
 *
 * Se siembra un historial de deshacer de 100 pasos completos (el tope real de
 * H1) para que la escritura del historial no quede fuera de la prueba: es el
 * sospechoso más caro (serializar 100 copias del tablero).
 */
import { expect, test } from '@playwright/test';
import { abrirTableroSembrado, mockReadyBackend, nota, tablero } from './helpers';

const DB_MEMORIA = 'prometeo-studio-memoria';

test('T-3 · autosave con 500 tarjetas sin longtask > 200 ms', async ({ page }) => {
  test.setTimeout(120_000);
  const cartas = Array.from({ length: 500 }, (_, indice) => nota(
    `n${indice}`,
    (indice % 25) * 280,
    Math.floor(indice / 25) * 210,
    `Tarjeta ${indice}`,
    `cuerpo ${indice}`,
  ));
  const tableroSoak = tablero(cartas, 'board-autosave', 'Autosave 500');

  await mockReadyBackend(page);
  await page.goto('/');

  // Historial de 100 pasos del tope, con el tablero completo en cada uno.
  await page.evaluate(async ({ board, dbName }) => {
    const database = await new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(dbName, 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('borrados')) db.createObjectStore('borrados', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('historial')) db.createObjectStore('historial', { keyPath: 'boardId' });
      };
      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
    });
    const undo = Array.from({ length: 100 }, (_, paso) => ({
      before: board,
      after: board,
      coalesceKey: `paso-${paso}`,
      timestamp: Date.now() - (100 - paso) * 1000,
    }));
    await new Promise<void>((resolve, reject) => {
      const transaction = database.transaction('historial', 'readwrite');
      transaction.objectStore('historial').put({ boardId: board.id, history: { undo, redo: [] }, savedAt: new Date().toISOString() });
      transaction.oncomplete = () => { database.close(); resolve(); };
      transaction.onerror = () => reject(transaction.error);
    });
  }, { board: tableroSoak, dbName: DB_MEMORIA });

  await abrirTableroSembrado(page, tableroSoak);
  await expect(page.locator('[data-card-id]')).toHaveCount(500);
  await expect(page.getByTestId('history-status')).toContainText('historial restaurado');

  await page.evaluate(() => {
    const registro = { activo: true, marcas: [], longtasks: [], loaf: [] };
    (window as unknown as { __prometeoT3: typeof registro }).__prometeoT3 = registro;
    new PerformanceObserver((lista) => {
      for (const entrada of lista.getEntries()) {
        registro.longtasks.push({ startTime: entrada.startTime, duration: entrada.duration });
      }
    }).observe({ type: 'longtask' });
    new PerformanceObserver((lista) => {
      for (const entrada of lista.getEntries() as Array<PerformanceEntry & { scripts?: Array<Record<string, unknown>> }>) {
        registro.loaf.push({
          startTime: entrada.startTime,
          duration: entrada.duration,
          scripts: (entrada.scripts ?? []).map((script) => ({ url: script.sourceURL, fn: script.sourceFunctionName, duracion: script.duration })),
        });
      }
    }).observe({ type: 'long-animation-frame' });
  });

  // Un gesto real: seleccionar una tarjeta y moverla. Dispara historial + autosave.
  const tarjeta = page.locator('[data-card-id="n0"]');
  await tarjeta.click();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(2500);

  const datos = await page.evaluate(() => (window as unknown as {
    __prometeoT3: {
      longtasks: Array<{ startTime: number; duration: number }>;
      loaf: Array<{ startTime: number; duration: number; scripts: Array<{ url?: string; fn?: string; duracion?: number }> }>;
      marcas: Array<{ nombre: string; detalle?: string; dur?: number }>;
    };
  }).__prometeoT3);

  const culpables = datos.longtasks.filter((tarea) => tarea.duration > 200);
  const escrituras = datos.marcas.filter((marca) => marca.nombre.startsWith('autosave') || marca.nombre.startsWith('historial'));
  console.log(`T-3 autosave · longtasks: ${datos.longtasks.map((tarea) => tarea.duration.toFixed(0)).join(', ') || 'ninguna'}`);
  console.log(`T-3 autosave · marcas: ${escrituras.map((marca) => `${marca.nombre}${marca.dur != null ? ` ${marca.dur.toFixed(0)} ms` : ''}`).join(' · ')}`);

  expect(culpables, `longtasks > 200 ms: ${JSON.stringify(culpables)}`).toEqual([]);
});
