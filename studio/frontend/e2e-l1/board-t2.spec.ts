import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * T-2 · selección y borrado. Se siembra IndexedDB para tener tableros
 * deterministas (incluidos marcos y relaciones) sin depender de gestos.
 */

const DB_NAME = 'prometeo-studio-visual-board';

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

async function mockReadyBackend(page: Page) {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/health') return json(route, { ready: true, version: 't2', ocr_available: false, workspace: { writable: true } });
    if (path === '/api/samples') return json(route, { ok: true, samples: [] });
    return json(route, { ok: true });
  });
}

interface TableroSembrado {
  schemaVersion: number;
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  cards: Array<Record<string, unknown>>;
  relations: Array<Record<string, unknown>>;
}

function tablero(cards: Array<Record<string, unknown>>, relations: Array<Record<string, unknown>> = []): TableroSembrado {
  const ahora = new Date().toISOString();
  return { schemaVersion: 1, id: 'board-t2', title: 'T-2', createdAt: ahora, updatedAt: ahora, cards, relations };
}

function nota(id: string, x: number, y: number, body = `cuerpo ${id}`) {
  return { id, type: 'note', title: id, body, x, y, width: 260, color: 'paper' };
}

async function sembrar(page: Page, board: TableroSembrado) {
  await page.evaluate(async ({ board, dbName }) => {
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open(dbName, 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('boards')) db.createObjectStore('boards', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
      };
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction(['boards', 'meta'], 'readwrite');
        tx.objectStore('boards').put(board);
        tx.objectStore('meta').put({ key: 'active-board-id', value: board.id });
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
    });
  }, { board, dbName: DB_NAME });
}

async function abrirTablero(page: Page) {
  await page.getByRole('button', { name: 'Tablero' }).click();
  await expect(page.locator('.board-workspace')).toBeVisible();
}

async function leerTablero(page: Page, id: string): Promise<TableroSembrado | null> {
  return page.evaluate(async ({ dbName, id }) => new Promise<TableroSembrado | null>((resolve, reject) => {
    const request = indexedDB.open(dbName, 1);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction('boards', 'readonly');
      const get = tx.objectStore('boards').get(id);
      get.onsuccess = () => { db.close(); resolve((get.result as TableroSembrado | undefined) ?? null); };
      get.onerror = () => { db.close(); reject(get.error); };
    };
  }), { dbName: DB_NAME, id });
}

test('Cmd+A + Supr vacía el tablero sin confirm y Cmd+Z lo devuelve idéntico', async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __confirms: number }).__confirms = 0;
    window.confirm = () => {
      (window as unknown as { __confirms: number }).__confirms += 1;
      return true;
    };
  });
  await mockReadyBackend(page);
  const board = tablero([
    nota('n1', 120, 120),
    nota('n2', 460, 120),
    nota('n3', 800, 120),
    { id: 'f1', type: 'marco', title: 'Marco', body: '', x: 60, y: 60, width: 1000, color: 'paper', datos: { alto: 420, hijos: ['n2'], vista: 'libre' } },
  ], [{ id: 'r1', from: 'n1', to: 'n2' }]);
  await page.goto('/');
  await sembrar(page, board);
  await abrirTablero(page);
  await expect(page.locator('[data-card-id]')).toHaveCount(4);

  const antes = await leerTablero(page, board.id);
  expect(antes?.cards).toHaveLength(4);

  await page.keyboard.press('Meta+a');
  await expect(page.locator('.board-selection-bar')).toContainText('4 seleccionadas');
  await page.keyboard.press('Delete');

  await expect(page.locator('[data-card-id]')).toHaveCount(0);
  const aviso = page.getByTestId('board-undo-toast');
  await expect(aviso).toBeVisible();
  await expect(aviso).toContainText('4 tarjetas eliminadas');
  await expect(aviso.getByRole('button', { name: 'Deshacer' })).toBeVisible();
  expect(await page.evaluate(() => (window as unknown as { __confirms: number }).__confirms)).toBe(0);

  // El botón usa el mismo historial que Cmd+Z.
  await aviso.getByRole('button', { name: 'Deshacer' }).click();
  await expect(page.locator('[data-card-id]')).toHaveCount(4);
  await expect(aviso).toHaveCount(0);
  await expect.poll(async () => (await leerTablero(page, board.id))?.cards.length).toBe(4);
  const restaurado = await leerTablero(page, board.id);
  expect(restaurado?.cards).toEqual(antes?.cards);
  expect(restaurado?.relations).toEqual(antes?.relations);

  // Y Cmd+Z repite la misma operación.
  await page.keyboard.press('Meta+a');
  await page.keyboard.press('Delete');
  await expect(page.locator('[data-card-id]')).toHaveCount(0);
  await page.keyboard.press('Meta+z');
  await expect(page.locator('[data-card-id]')).toHaveCount(4);
  await expect(aviso).toHaveCount(0);

  await expect.poll(async () => (await leerTablero(page, board.id))?.cards.length).toBe(4);
  const despues = await leerTablero(page, board.id);
  expect(despues?.cards).toEqual(antes?.cards);
  expect(despues?.relations).toEqual(antes?.relations);
  const marco = despues?.cards.find((card) => card.id === 'f1');
  expect((marco?.datos as { hijos?: string[] } | undefined)?.hijos).toEqual(['n2']);
});

test('Supr dentro de una nota en edición borra texto, no la tarjeta', async ({ page }) => {
  await page.addInitScript(() => {
    (window as unknown as { __confirms: number }).__confirms = 0;
    window.confirm = () => {
      (window as unknown as { __confirms: number }).__confirms += 1;
      return true;
    };
  });
  await mockReadyBackend(page);
  const board = tablero([{ ...nota('n1', 200, 200, 'Hola mundo'), body: 'Hola mundo' }]);
  await page.goto('/');
  await sembrar(page, board);
  await abrirTablero(page);

  await page.locator('.board-note-read').dblclick();
  const editor = page.getByLabel('Contenido de la nota con formato');
  await editor.focus();
  await expect(editor).toHaveValue('Hola mundo');
  await page.keyboard.press('Meta+a');
  await page.keyboard.press('Backspace');
  await expect(editor).toHaveValue('');
  await expect(page.locator('[data-card-id="n1"]')).toHaveCount(1);
  await expect(page.getByTestId('board-undo-toast')).toHaveCount(0);
  expect(await page.evaluate(() => (window as unknown as { __confirms: number }).__confirms)).toBe(0);

  await editor.press('Meta+Enter');
  await expect.poll(async () => {
    const saved = await leerTablero(page, board.id);
    return saved?.cards.find((card) => card.id === 'n1')?.body;
  }).toBe('');
});

test('diez pulsaciones de flecha son un solo paso de historial', async ({ page }) => {
  await mockReadyBackend(page);
  const board = tablero([nota('n1', 100, 100)]);
  await page.goto('/');
  await sembrar(page, board);
  await abrirTablero(page);

  const carta = page.locator('[data-card-id="n1"]');
  await carta.click();
  for (let i = 0; i < 10; i += 1) await page.keyboard.press('ArrowRight');
  await expect(carta).toHaveCSS('left', '110px');

  await page.keyboard.press('Meta+z');
  await expect(carta).toHaveCSS('left', '100px');
});

test('el título en el sitio se edita con doble clic después de quitar sus efectos', async ({ page }) => {
  await mockReadyBackend(page);
  const board = tablero([nota('n1', 200, 200)]);
  await page.goto('/');
  await sembrar(page, board);
  await abrirTablero(page);

  await page.locator('.board-card-title').dblclick();
  const editor = page.getByLabel('Título de tarjeta');
  await expect(editor).toBeFocused();
  await editor.fill('Título nuevo');
  await editor.press('Enter');
  await expect(page.locator('.board-card-title')).toHaveText('Título nuevo');
  await expect.poll(async () => {
    const saved = await leerTablero(page, board.id);
    return saved?.cards.find((card) => card.id === 'n1')?.title;
  }).toBe('Título nuevo');
});

test('duplicar, copiar, cortar y pegar tarjetas dentro de Prometeo', async ({ page }) => {
  await mockReadyBackend(page);
  const board = tablero([nota('n1', 200, 200), nota('n2', 500, 200)], [{ id: 'r1', from: 'n1', to: 'n2' }]);
  await page.goto('/');
  await sembrar(page, board);
  await abrirTablero(page);
  await expect(page.locator('[data-card-id]')).toHaveCount(2);

  await page.locator('[data-card-id="n1"]').click();
  await page.keyboard.press('Meta+d');
  await expect(page.locator('[data-card-id]')).toHaveCount(3);

  await page.keyboard.press('Meta+a');
  await expect(page.locator('[data-card-id].selected')).toHaveCount(3);
  await page.keyboard.press('Meta+c');
  await page.keyboard.press('Meta+v');
  await expect(page.locator('[data-card-id]')).toHaveCount(6);

  await page.locator('[data-card-id]').last().click();
  await page.keyboard.press('Meta+x');
  await expect(page.locator('[data-card-id]')).toHaveCount(5);
  await expect(page.getByTestId('board-undo-toast')).toContainText('1 tarjeta eliminada');
  await page.keyboard.press('Meta+v');
  await expect(page.locator('[data-card-id]')).toHaveCount(6);
});

test('borrar 500 tarjetas con Cmd+A + Supr: tiempo y fotogramas medidos', async ({ page }) => {
  test.setTimeout(120_000);
  const produccion = test.info().project.name === 'produccion';
  await mockReadyBackend(page);
  const cards = Array.from({ length: 500 }, (_, indice) => nota(`n${indice}`, (indice % 25) * 280, Math.floor(indice / 25) * 200));
  const board = tablero(cards);
  await page.goto('/');
  await sembrar(page, board);
  await abrirTablero(page);
  await expect(page.locator('[data-card-id]')).toHaveCount(500);

  const mediciones: Array<{ seleccionadas: number; milisegundos: number; primerFotograma: number; fotogramaMaximo: number; restantes: number }> = [];
  const repeticiones = produccion ? 3 : 1;
  for (let vuelta = 0; vuelta < repeticiones; vuelta += 1) {
    await page.keyboard.press('Meta+a');
    await expect(page.locator('[data-card-id].selected')).toHaveCount(500);

    const medicion = await page.evaluate(async () => {
      const siguienteFotograma = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));
      await siguienteFotograma();
      const seleccionadas = document.querySelectorAll('[data-card-id].selected').length;

      const inicio = performance.now();
      window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Delete', bubbles: true }));
      const despacho = performance.now() - inicio;
      const fotogramas: number[] = [];
      let primerFotograma = 0;
      await new Promise<void>((resolve) => {
        let ultimo = performance.now();
        let cuenta = 0;
        const tick = () => {
          const ahora = performance.now();
          if (cuenta === 0) primerFotograma = ahora - inicio;
          cuenta += 1;
          fotogramas.push(ahora - ultimo);
          ultimo = ahora;
          if (ahora - inicio >= 200) resolve();
          else requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
      });
      return {
        seleccionadas,
        milisegundos: despacho,
        primerFotograma,
        fotogramaMaximo: Math.max(...fotogramas),
        restantes: document.querySelectorAll('[data-card-id]').length,
      };
    });
    mediciones.push(medicion);
    expect(medicion.seleccionadas).toBe(500);
    expect(medicion.restantes).toBe(0);
    expect(medicion.milisegundos).toBeLessThan(100);
    expect(medicion.primerFotograma).toBeLessThan(100);

    if (vuelta < repeticiones - 1) {
      await page.keyboard.press('Meta+z');
      await expect(page.locator('[data-card-id]')).toHaveCount(500);
    }
  }

  const maximos = mediciones.map((medicion) => medicion.fotogramaMaximo).sort((a, b) => a - b);
  const mediana = maximos[Math.floor(maximos.length / 2)];
  console.log(`T-2 · 500 tarjetas (${produccion ? 'build de producción' : 'dev'}): despacho ${mediciones[0].milisegundos.toFixed(1)} ms · primer fotograma ${mediciones[0].primerFotograma.toFixed(1)} ms · fotogramas ${maximos.map((valor) => valor.toFixed(1)).join(' / ')} ms`);
  // En dev el árbol de React añade trabajo; el presupuesto se exige al build de producción.
  if (produccion) expect(mediana).toBeLessThan(32);
  else expect(mediana).toBeLessThan(100);
});
