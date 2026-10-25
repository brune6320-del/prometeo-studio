import { expect, type Page, type Route } from '@playwright/test';

export const BOARD_DB = 'prometeo-studio-visual-board';

export async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

/** Motor PDF simulado: el tablero es local y no necesita el backend real. */
export async function mockBackend(page: Page) {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/health') return json(route, { ready: true, version: 'forja2', ocr_available: false, workspace: { writable: true } });
    if (path === '/api/samples') return json(route, { ok: true, samples: [] });
    return json(route, { ok: true });
  });
}

export interface SemillaTarjeta {
  id: string;
  type: string;
  title: string;
  body?: string;
  x: number;
  y: number;
  width?: number;
  color?: string;
  url?: string;
  datos?: Record<string, unknown>;
}

export function tarjeta(parcial: Partial<SemillaTarjeta> & Pick<SemillaTarjeta, 'id' | 'type' | 'x' | 'y'>): SemillaTarjeta {
  return {
    title: parcial.title ?? 'Tarjeta',
    body: parcial.body ?? '',
    width: parcial.width ?? 280,
    color: parcial.color ?? 'paper',
    ...parcial,
  } as SemillaTarjeta;
}

export function marco(id: string, x: number, y: number, extra: Partial<SemillaTarjeta> = {}): SemillaTarjeta {
  return {
    id,
    type: 'marco',
    title: extra.title ?? 'Marco de prueba',
    x,
    y,
    width: extra.width ?? 520,
    datos: { alto: 420, hijos: [], vista: 'libre', ...(extra.datos ?? {}) },
    ...extra,
  };
}

export async function sembrarTablero(page: Page, cards: SemillaTarjeta[], title = 'Tablero Forja 2') {
  await page.evaluate(async ({ db, cards: semilla, title: nombre }) => {
    const requestValue = <T,>(request: IDBRequest<T>) => new Promise<T>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const database = await requestValue(indexedDB.open(db, 1));
    const now = new Date().toISOString();
    const board = {
      schemaVersion: 1,
      id: 'board-forja2',
      title: nombre,
      createdAt: now,
      updatedAt: now,
      cards: semilla,
      relations: [],
    };
    const tx = database.transaction(['boards', 'meta'], 'readwrite');
    tx.objectStore('boards').put(board);
    tx.objectStore('meta').put({ key: 'active-board-id', value: board.id });
    await new Promise<void>((resolve, reject) => {
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
    database.close();
  }, { db: BOARD_DB, cards, title });
}

export async function abrirTablero(page: Page) {
  await page.goto('/');
  const tablero = page.getByRole('button', { name: /Tablero/ }).first();
  await expect(tablero).toBeVisible({ timeout: 20_000 });
  await tablero.click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.getByTestId('board-topbar')).toBeVisible();
}

export async function abrirTableroCon(page: Page, cards: SemillaTarjeta[], title?: string) {
  await mockBackend(page);
  await abrirTablero(page);
  await sembrarTablero(page, cards, title);
  await page.reload();
  await abrirTablero(page);
  await expect(page.locator('.board-card, .board-frame').first()).toBeVisible();
}

export async function centroDe(page: Page, selector: string) {
  const box = await page.locator(selector).first().boundingBox();
  if (!box) throw new Error(`Sin caja para ${selector}`);
  return { x: box.x + box.width / 2, y: box.y + box.height / 2, box };
}

export async function capturar(page: Page, path: string) {
  await page.screenshot({ path, animations: 'disabled' });
}
