import { expect, type Page, type Route } from '@playwright/test';
import path from 'node:path';

export const CAPTURAS = path.resolve(process.cwd(), '../../REPORTES/capturas-forja4');
export const DB_NAME = 'prometeo-studio-visual-board';

export const mockSummary = {
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

export async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
}

/** Backend mínimo: el tablero no depende del motor PDF para existir. */
export async function mockReadyBackend(page: Page) {
  await page.route((url) => url.pathname.startsWith('/api/'), async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const endpoint = url.pathname;
    if (endpoint === '/api/health') return json(route, { ready: true, version: 'forja4-mock', ocr_available: false, workspace: { writable: true } });
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

export async function openBoard(page: Page) {
  await page.getByRole('button', { name: 'Tablero' }).click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
}

export interface SeedCard {
  id: string;
  type: string;
  title: string;
  body?: string;
  x: number;
  y: number;
  width?: number;
  height?: number;
  color?: string;
  url?: string;
  locked?: boolean;
  datos?: Record<string, unknown>;
}

export interface SeedBoard {
  schemaVersion: number;
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  cards: SeedCard[];
  relations: unknown[];
}

export function tablero(cards: SeedCard[], id = 'board-forja4', title = 'Forja 4'): SeedBoard {
  const ahora = new Date().toISOString();
  return { schemaVersion: 1, id, title, createdAt: ahora, updatedAt: ahora, cards, relations: [] };
}

export function nota(id: string, x: number, y: number, title = id, body = `cuerpo ${id}`, extra: Partial<SeedCard> = {}): SeedCard {
  return { id, type: 'note', title, body, x, y, width: 260, color: 'paper', ...extra };
}

/** Siembra IndexedDB antes de abrir el tablero (determinista y sin gestos). */
export async function sembrar(page: Page, board: SeedBoard) {
  await page.evaluate(async ({ board: valor, dbName }) => {
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
        tx.objectStore('boards').put(valor);
        tx.objectStore('meta').put({ key: 'active-board-id', value: valor.id });
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
    });
  }, { board, dbName: DB_NAME });
}

export async function leerTablero(page: Page, id: string): Promise<SeedBoard | null> {
  return page.evaluate(async ({ dbName, id: boardId }) => new Promise<SeedBoard | null>((resolve, reject) => {
    const request = indexedDB.open(dbName);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('boards')) { db.close(); resolve(null); return; }
      const tx = db.transaction('boards', 'readonly');
      const get = tx.objectStore('boards').get(boardId);
      get.onsuccess = () => { db.close(); resolve((get.result as SeedBoard | undefined) ?? null); };
      get.onerror = () => { db.close(); reject(get.error); };
    };
  }), { dbName: DB_NAME, id });
}

export async function abrirTableroSembrado(page: Page, board: SeedBoard) {
  await page.goto('/');
  await sembrar(page, board);
  await page.reload();
  await openBoard(page);
}
