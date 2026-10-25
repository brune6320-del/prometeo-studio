import { readFile } from 'node:fs/promises';
import { expect, test, type Page, type Route } from '@playwright/test';

const BOARD_DB = 'prometeo-studio-visual-board';
const PROJECT_DB = 'prometeo-studio-project-workspace';
const SOURCE_SHA = 'a'.repeat(64);

const mockSummary = {
  document_id: 'doc_mock',
  source_sha256: SOURCE_SHA,
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
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/health') return json(route, { ready: true, version: 'l2-mock', ocr_available: false, workspace: { writable: true } });
    if (path === '/api/samples') return json(route, { ok: true, samples: [{ key: 'mock_three_pages', description: 'PDF de tres páginas' }] });
    if (path === '/api/sessions/open_sample') return json(route, { ok: true, session_id: 'studio_sess_abcdef', filename: 'tres-paginas.pdf', summary: mockSummary });
    if (path.endsWith('/nodes')) return json(route, { nodes: [] });
    if (path.endsWith('/transaction')) return json(route, { staged_operations: [], transaction_state: 'READY' });
    if (path.includes('/render')) {
      const pageNumber = Number(path.match(/page\/(\d+)/)?.[1] ?? 0);
      const svg = encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="612" height="792"><rect width="100%" height="100%" fill="white"/></svg>');
      return json(route, { page: { page_number: pageNumber, width_pt: 612, height_pt: 792, image_data_url: 'data:image/svg+xml,' + svg } });
    }
    return json(route, { ok: true });
  });
}

async function seedLegacyWorkspace(page: Page) {
  await page.evaluate(async ({ boardDb, projectDb }) => {
    const open = (name: string, version: number, upgrade: (database: IDBDatabase) => void) => new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(name, version);
      request.onupgradeneeded = () => upgrade(request.result);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const complete = (transaction: IDBTransaction) => new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
      transaction.onabort = () => reject(transaction.error);
    });
    const now = '2026-10-17T12:00:00.000Z';
    const board = {
      schemaVersion: 1,
      id: 'board legacy:001',
      title: 'Tablero heredado',
      createdAt: now,
      updatedAt: now,
      cards: [{ id: 'card-legacy-001', type: 'note', title: 'Idea conservada', body: 'Contenido previo', x: 120, y: 140, width: 260, color: 'paper' }],
      relations: [],
    };
    const boards = await open(boardDb, 1, (database) => {
      database.createObjectStore('boards', { keyPath: 'id' });
      database.createObjectStore('meta', { keyPath: 'key' });
    });
    const boardTx = boards.transaction(['boards', 'meta'], 'readwrite');
    boardTx.objectStore('boards').put(board);
    boardTx.objectStore('meta').put({ key: 'active-board-id', value: board.id });
    await complete(boardTx);
    boards.close();

    const projects = await open(projectDb, 1, (database) => {
      database.createObjectStore('projects', { keyPath: 'id' });
      database.createObjectStore('board-projects', { keyPath: 'boardId' });
    });
    const projectTx = projects.transaction('projects', 'readwrite');
    projectTx.objectStore('projects').put({ id: 'project-legacy-0001', name: 'Proyecto legado', createdAt: now, updatedAt: now });
    await complete(projectTx);
    projects.close();
  }, { boardDb: BOARD_DB, projectDb: PROJECT_DB });
}

async function renombrarTablero(page: Page, nombre: string) {
  page.once('dialog', (dialog) => dialog.accept(nombre));
  await page.getByRole('button', { name: 'Renombrar tablero' }).click();
}

async function openBoard(page: Page) {
  await page.getByRole('button', { name: 'Tablero' }).click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
  await expect(page.getByLabel('Elegir proyecto')).toBeEnabled();
}

test('migra el espacio legado a proyectos sin reescribir el tablero ni el proyecto previos', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await seedLegacyWorkspace(page);
  await openBoard(page);

  await expect(page.getByLabel('Elegir proyecto')).toHaveValue('project-legacy-0001');
  await expect(page.locator('#board-select option:checked')).toHaveText('Tablero heredado');
  await expect(page.locator('.board-card-title')).toHaveText('Idea conservada');

  const state = await page.evaluate(async ({ boardDb, projectDb }) => {
    const requestValue = <T,>(request: IDBRequest<T>) => new Promise<T>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const open = (name: string) => requestValue(indexedDB.open(name));
    const boards = await open(boardDb);
    const boardTx = boards.transaction('boards', 'readonly');
    const board = await requestValue(boardTx.objectStore('boards').get('board legacy:001'));
    boards.close();
    const projects = await open(projectDb);
    const tx = projects.transaction(['projects', 'board-projects', 'meta'], 'readonly');
    const project = await requestValue(tx.objectStore('projects').get('project-legacy-0001'));
    const link = await requestValue(tx.objectStore('board-projects').get('board legacy:001'));
    const schema = await requestValue(tx.objectStore('meta').get('workspace-schema-version'));
    const version = projects.version;
    projects.close();
    return { board, project, link, schema, version };
  }, { boardDb: BOARD_DB, projectDb: PROJECT_DB });

  expect(state.version).toBe(2);
  expect(state.schema).toEqual({ key: 'workspace-schema-version', value: 2 });
  expect(state.board).toEqual({
    schemaVersion: 1,
    id: 'board legacy:001',
    title: 'Tablero heredado',
    createdAt: '2026-10-17T12:00:00.000Z',
    updatedAt: '2026-10-17T12:00:00.000Z',
    cards: [{ id: 'card-legacy-001', type: 'note', title: 'Idea conservada', body: 'Contenido previo', x: 120, y: 140, width: 260, color: 'paper' }],
    relations: [],
  });
  expect(state.project).toEqual({
    id: 'project-legacy-0001',
    name: 'Proyecto legado',
    createdAt: '2026-10-17T12:00:00.000Z',
    updatedAt: '2026-10-17T12:00:00.000Z',
  });
  expect(state.link).toEqual({ schemaVersion: 2, boardId: 'board legacy:001', projectId: 'project-legacy-0001' });
});

test('crea proyectos separados y recupera su tablero activo después de recargar', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await openBoard(page);

  await renombrarTablero(page, 'Tablero general');
  await expect(page.getByText('Guardando…', { exact: true })).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Crear proyecto' }).click();
  const dialog = page.getByRole('dialog', { name: 'Crear proyecto' });
  await dialog.getByLabel('Nombre del proyecto').fill('Investigación PDF');
  await dialog.getByRole('button', { name: 'Crear proyecto' }).click();
  await expect(page.getByLabel('Elegir proyecto')).toHaveValue(/project-/);
  await expect(page.locator('#board-select option:checked')).toHaveText('Mi tablero');
  await renombrarTablero(page, 'Tablero de investigación');
  await expect(page.getByText('Guardando…', { exact: true })).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();

  await page.getByLabel('Elegir proyecto').selectOption({ label: 'Proyecto general' });
  await expect(page.locator('#board-select option:checked')).toHaveText('Tablero general');
  await page.getByLabel('Elegir proyecto').selectOption({ label: 'Investigación PDF' });
  await expect(page.locator('#board-select option:checked')).toHaveText('Tablero de investigación');

  await page.reload();
  await openBoard(page);
  await expect(page.getByLabel('Elegir proyecto')).toHaveValue(/project-/);
  await expect(page.getByLabel('Elegir proyecto').locator('option')).toHaveCount(2);
  await expect(page.getByLabel('Elegir proyecto').locator('option:checked')).toHaveText('Investigación PDF');
  await expect(page.locator('#board-select option:checked')).toHaveText('Tablero de investigación');
});

test('guarda referencias de página, vuelve al PDF exacto y exporta Markdown para Obsidian', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await page.locator('[data-sample="mock_three_pages"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('tres-paginas.pdf');
  await page.getByRole('button', { name: 'Página siguiente' }).click();
  await expect(page.locator('#page-jump')).toHaveValue('2');
  await openBoard(page);

  await page.getByRole('button', { name: /^Biblioteca/ }).click();
  await page.getByRole('menuitem', { name: /Referenciar página PDF/ }).click();
  const dialog = page.getByRole('dialog', { name: 'Referenciar página PDF' });
  await dialog.getByLabel('Cita o fragmento').fill('Fragmento verificable');
  await dialog.getByLabel('Nota').fill('Conectar con el marco teórico');
  await dialog.getByRole('button', { name: 'Guardar referencia' }).click();
  const references = page.getByRole('complementary', { name: /Referencias PDF de/ });
  await expect(references).toContainText('tres-paginas.pdf');
  await expect(references).toContainText('Página 2');
  await expect(references).toContainText('Fragmento verificable');

  await page.locator('.board-topbar-actions').getByRole('button', { name: /^Exportar/ }).click();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('menuitem', { name: 'Obsidian del proyecto' }).click(),
  ]);
  const downloadPath = await download.path();
  expect(downloadPath).not.toBeNull();
  const markdown = await readFile(downloadPath!, 'utf8');
  expect(markdown).toContain('## Referencias PDF');
  expect(markdown).toContain('tres-paginas.pdf — página 2');
  expect(markdown).toContain('SHA-256: ' + SOURCE_SHA);
  expect(markdown).toContain('Fragmento verificable');
  expect(markdown).not.toContain('/Users/');

  await references.getByRole('button', { name: 'Abrir página' }).click();
  await expect(page.locator('.board-workspace')).toHaveCount(0);
  await expect(page.locator('#page-jump')).toHaveValue('2');
});

test('rechaza una base futura, conserva sus datos y mantiene operativos los tableros', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await page.evaluate(async ({ boardDb, projectDb }) => {
    const open = (name: string, version: number, upgrade: (database: IDBDatabase) => void) => new Promise<IDBDatabase>((resolve, reject) => {
      const request = indexedDB.open(name, version);
      request.onupgradeneeded = () => upgrade(request.result);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const complete = (transaction: IDBTransaction) => new Promise<void>((resolve, reject) => {
      transaction.oncomplete = () => resolve();
      transaction.onerror = () => reject(transaction.error);
    });
    const now = '2026-10-17T12:00:00.000Z';
    const boards = await open(boardDb, 1, (database) => {
      database.createObjectStore('boards', { keyPath: 'id' });
      database.createObjectStore('meta', { keyPath: 'key' });
    });
    const boardTx = boards.transaction('boards', 'readwrite');
    boardTx.objectStore('boards').put({ schemaVersion: 1, id: 'board-safe-001', title: 'Tablero seguro', createdAt: now, updatedAt: now, cards: [], relations: [] });
    await complete(boardTx);
    boards.close();
    const future = await open(projectDb, 3, (database) => database.createObjectStore('future-data', { keyPath: 'id' }));
    const futureTx = future.transaction('future-data', 'readwrite');
    futureTx.objectStore('future-data').put({ id: 'marker', payload: 'conservar-exacto' });
    await complete(futureTx);
    future.close();
  }, { boardDb: BOARD_DB, projectDb: PROJECT_DB });

  await page.getByRole('button', { name: 'Tablero' }).click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.getByRole('alert')).toContainText('versión más nueva');
  await expect(page.locator('#board-select option:checked')).toHaveText('Tablero seguro');
  await page.getByRole('button', { name: 'Nueva nota' }).click();
  await page.locator('.board-card-title').last().dblclick();
  await page.getByLabel('Título de tarjeta').fill('Trabajo local conservado');
  await page.getByLabel('Título de tarjeta').press('Enter');
  await expect(page.getByText('Guardando…', { exact: true })).toBeVisible();
  await expect(page.getByText('Guardado', { exact: true })).toBeVisible();

  const state = await page.evaluate(async ({ boardDb, projectDb }) => {
    const value = <T,>(request: IDBRequest<T>) => new Promise<T>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const future = await value(indexedDB.open(projectDb));
    const marker = await value(future.transaction('future-data', 'readonly').objectStore('future-data').get('marker'));
    const version = future.version;
    future.close();
    const boards = await value(indexedDB.open(boardDb));
    const board = await value(boards.transaction('boards', 'readonly').objectStore('boards').get('board-safe-001'));
    boards.close();
    return { marker, version, board };
  }, { boardDb: BOARD_DB, projectDb: PROJECT_DB });
  expect(state.version).toBe(3);
  expect(state.marker).toEqual({ id: 'marker', payload: 'conservar-exacto' });
  expect(state.board.cards).toHaveLength(1);
  expect(state.board.cards[0].title).toBe('Trabajo local conservado');
});
