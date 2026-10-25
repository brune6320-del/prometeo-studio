/**
 * H7 · proyectos y zoom de inspección.
 * Top 13 y 14 de A-1; debates D13 y D14.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, DB_NAME, mockReadyBackend, nota, openBoard, tablero, type SeedBoard } from './helpers';

const PROJECT_DB = 'prometeo-studio-project-workspace';

async function sembrarProyectos(page: Page, projects: Array<{ id: string; name: string; archivado?: boolean }>, links: Array<{ boardId: string; projectId: string }>, activeProjectId: string, boards: SeedBoard[], activeBoardId: string) {
  await page.evaluate(async ({ projects: lista, links: enlaces, activeProjectId: activo, boards: tableros, activeBoardId: tableroActivo, projectDb, boardDb }) => {
    const ahora = new Date().toISOString();
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open(projectDb, 2);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('projects')) db.createObjectStore('projects', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('board-projects')) db.createObjectStore('board-projects', { keyPath: 'boardId' });
        if (!db.objectStoreNames.contains('pdf-references')) db.createObjectStore('pdf-references', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
      };
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction(['projects', 'board-projects', 'pdf-references', 'meta'], 'readwrite');
        for (const project of lista) tx.objectStore('projects').put({ schemaVersion: 2, createdAt: ahora, updatedAt: ahora, gustos: {}, plantillas: [], ...project });
        for (const link of enlaces) tx.objectStore('board-projects').put({ schemaVersion: 2, ...link });
        tx.objectStore('meta').put({ key: 'active-project-id', value: activo });
        tx.objectStore('meta').put({ key: 'workspace-schema-version', value: 2 });
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
    });
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open(boardDb);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains('boards')) db.createObjectStore('boards', { keyPath: 'id' });
        if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'key' });
      };
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction(['boards', 'meta'], 'readwrite');
        for (const board of tableros) tx.objectStore('boards').put(board);
        tx.objectStore('meta').put({ key: 'active-board-id', value: tableroActivo });
        tx.oncomplete = () => { db.close(); resolve(); };
        tx.onerror = () => reject(tx.error);
      };
    });
  }, { projects, links, activeProjectId, boards, activeBoardId, projectDb: PROJECT_DB, boardDb: DB_NAME });
}

async function leerProyectos(page: Page) {
  return page.evaluate(async (dbName) => new Promise<{ projects: Array<{ id: string; name: string; archivado?: boolean }>; links: Array<{ boardId: string; projectId: string }> }>((resolve) => {
    const request = indexedDB.open(dbName);
    request.onsuccess = () => {
      const db = request.result;
      const tx = db.transaction(['projects', 'board-projects'], 'readonly');
      const p = tx.objectStore('projects').getAll();
      const l = tx.objectStore('board-projects').getAll();
      tx.oncomplete = () => { db.close(); resolve({ projects: p.result, links: l.result }); };
      tx.onerror = () => { db.close(); resolve({ projects: [], links: [] }); };
    };
    request.onerror = () => resolve({ projects: [], links: [] });
  }), PROJECT_DB);
}

const alfa = tablero([nota('a1', 180, 180, 'Tablero Alfa')], 'board-alfa', 'Tablero Alfa');
const beta = tablero([nota('b1', 180, 180, 'Tablero Beta')], 'board-beta', 'Tablero Beta');

test('H7 · renombrar con F2, archivar, mover tablero y recuperar', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await mockReadyBackend(page);
  await page.goto('/');
  await sembrarProyectos(page,
    [{ id: 'project-alfa0001', name: 'Estudio Alfa' }, { id: 'project-beta0001', name: 'Estudio Beta' }],
    [{ boardId: 'board-alfa', projectId: 'project-alfa0001' }, { boardId: 'board-beta', projectId: 'project-beta0001' }],
    'project-alfa0001',
    [alfa, beta],
    'board-alfa',
  );
  await page.reload();
  await openBoard(page);
  await expect(page.locator('#project-select')).toHaveValue('project-alfa0001');

  await page.keyboard.press('F2');
  const editor = page.getByLabel('Nombre del proyecto');
  await expect(editor).toBeFocused();
  await editor.fill('Estudio Alfa renombrado');
  await editor.press('Enter');
  await expect.poll(async () => (await leerProyectos(page)).projects.find((project) => project.id === 'project-alfa0001')?.name).toBe('Estudio Alfa renombrado');

  // Archivar lo saca del selector pero lo deja en Archivo.
  await page.getByRole('button', { name: 'Menú del proyecto' }).click();
  await page.getByRole('menuitem', { name: 'Archivar proyecto' }).click();
  await expect(page.locator('#project-select')).not.toHaveValue('project-alfa0001');
  await page.getByRole('button', { name: 'Archivo y recientes borrados' }).click();
  const archivo = page.getByRole('dialog', { name: 'Archivo' });
  await expect(archivo.getByRole('heading', { name: 'Proyectos archivados' })).toBeVisible();
  await expect(archivo).toContainText('Estudio Alfa renombrado');
  await page.screenshot({ path: path.join(CAPTURAS, 'H7-antes-proyecto-archivado.png') });
  await archivo.getByRole('button', { name: 'Restaurar' }).first().click();
  await archivo.getByRole('button', { name: 'Cerrar', exact: true }).click();
  await expect.poll(async () => (await leerProyectos(page)).projects.find((project) => project.id === 'project-alfa0001')?.archivado ?? false).toBe(false);
  await expect(page.locator('#project-select option', { hasText: 'Estudio Alfa renombrado' })).toHaveCount(1);

  // Mover el tablero activo al otro proyecto.
  await page.locator('#project-select').selectOption('project-alfa0001');
  await page.getByRole('button', { name: 'Menú del proyecto' }).click();
  await page.getByRole('menuitem', { name: /Mover tablero a otro proyecto/ }).click();
  await page.getByLabel('Proyecto destino').selectOption('project-beta0001');
  await page.getByRole('button', { name: 'Mover tablero' }).click();
  await expect(page.locator('#project-select')).toHaveValue('project-beta0001');
  await expect.poll(async () => (await leerProyectos(page)).links.find((link) => link.boardId === 'board-alfa')?.projectId).toBe('project-beta0001');
  await page.screenshot({ path: path.join(CAPTURAS, 'H7-despues-mover-archivar.png') });
});

test('H7 · borrar un proyecto definitivamente exige el nombre y deja memoria de 30 días', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await sembrarProyectos(page,
    [{ id: 'project-alfa0001', name: 'Estudio Alfa' }, { id: 'project-beta0001', name: 'Estudio Beta' }],
    [{ boardId: 'board-alfa', projectId: 'project-alfa0001' }, { boardId: 'board-beta', projectId: 'project-beta0001' }],
    'project-beta0001',
    [alfa, beta],
    'board-beta',
  );
  await page.reload();
  await openBoard(page);
  await page.getByRole('button', { name: 'Archivo y recientes borrados' }).click();
  const archivo = page.getByRole('dialog', { name: 'Archivo' });
  await page.getByLabel('Proyecto a borrar definitivamente').selectOption('project-beta0001');
  const confirmar = page.getByLabel('Nombre del proyecto para confirmar el borrado');
  await confirmar.fill('Estudio equivocado');
  await page.getByRole('button', { name: 'Borrar definitivamente' }).click();
  await expect(archivo).toContainText('Escribe el nombre exacto');
  await confirmar.fill('Estudio Beta');
  await page.getByRole('button', { name: 'Borrar definitivamente' }).click();
  await expect.poll(async () => (await leerProyectos(page)).projects.some((project) => project.id === 'project-beta0001')).toBe(false);

  // La memoria de H1 lo conserva y permite recuperarlo.
  await expect(archivo).toContainText('Proyecto «Estudio Beta»');
  await archivo.getByRole('button', { name: 'Restaurar' }).last().click();
  await expect.poll(async () => (await leerProyectos(page)).projects.some((project) => project.id === 'project-beta0001')).toBe(true);
  await page.screenshot({ path: path.join(CAPTURAS, 'H7-despues-borrado-memoria.png') });
});

test('H7 · zoom del tablero 25-800 % con ⌘0, ⌘+/- y ⇧1/⇧2', async ({ page }) => {
  const board = tablero([nota('a', 0, 0, 'Izquierda'), nota('b', 2400, 0, 'Derecha')], 'board-h7-zoom', 'Zoom');
  await mockReadyBackend(page);
  await page.goto('/');
  await sembrarProyectos(page,
    [{ id: 'project-zoom0001', name: 'Zoom' }],
    [{ boardId: 'board-h7-zoom', projectId: 'project-zoom0001' }],
    'project-zoom0001',
    [board],
    'board-h7-zoom',
  );
  await page.reload();
  await openBoard(page);
  for (let i = 0; i < 24; i += 1) await page.keyboard.press('Meta+=');
  await expect(page.locator('.board-zoom-value')).toHaveText('800%');
  await page.keyboard.press('Meta+0');
  await expect(page.locator('.board-zoom-value')).toHaveText('100%');
  await page.keyboard.press('Shift+1');
  const ajustado = Number((await page.locator('.board-zoom-value').textContent())?.replace('%', ''));
  expect(ajustado).toBeLessThan(100);
  await page.locator('[data-card-id="a"]').click();
  await page.keyboard.press('Shift+2');
  const aSeleccion = Number((await page.locator('.board-zoom-value').textContent())?.replace('%', ''));
  expect(aSeleccion).toBeGreaterThan(100);
  for (let i = 0; i < 30; i += 1) await page.keyboard.press('Meta+-');
  await expect(page.locator('.board-zoom-value')).toHaveText('25%');
  await page.screenshot({ path: path.join(CAPTURAS, 'H7-despues-zoom-800.png') });
});

test('H7 · el PDF también llega a 800 % y vuelve con ⌘0', async ({ page }) => {
  await mockReadyBackend(page);
  await page.goto('/');
  await page.locator('[data-sample="mock_three_pages"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('tres-paginas.pdf');
  for (let i = 0; i < 20; i += 1) await page.keyboard.press('Meta+=');
  await expect(page.locator('.zoom-value')).toContainText('800%');
  await page.keyboard.press('Meta+0');
  await expect(page.locator('.zoom-value')).toContainText('100%');
  for (let i = 0; i < 20; i += 1) await page.keyboard.press('Meta+-');
  await expect(page.locator('.zoom-value')).toContainText('25%');
});
