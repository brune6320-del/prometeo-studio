import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(AQUI, '../../..');
const SALIDA = path.join(REPO, 'REPORTES/capturas-forja2');
const PUERTO = 5199;
const APP_URL = `http://localhost:${PUERTO}`;
const fase = process.argv[2] ?? 'f0';
const momento = process.argv[3] ?? 'antes';
const lod = process.argv[4] === 'lod';

const esperar = async (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function esperarUrl(url, intentos = 80) {
  for (let i = 0; i < intentos; i += 1) {
    try {
      const res = await fetch(url);
      if (res.ok) return;
    } catch {
      /* el servidor aún arranca */
    }
    await esperar(250);
  }
  throw new Error(`No arrancó ${url}`);
}

const imagen = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="480" height="360"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e7d8bd"/><stop offset="1" stop-color="#b7c3b4"/></linearGradient></defs><rect width="480" height="360" fill="url(#g)"/><circle cx="310" cy="130" r="80" fill="#c07a4c" opacity=".62"/><rect x="60" y="220" width="240" height="18" fill="#24221f" opacity=".55"/></svg>')}`;

function demo() {
  const ahora = new Date().toISOString();
  const hijos = ['n1', 'n2', 'n3', 'n4', 'l1', 'r1'];
  return {
    schemaVersion: 1,
    id: 'board-forja2-demo',
    title: 'Biblioteca · Forja 2',
    createdAt: ahora,
    updatedAt: ahora,
    relations: [],
    cards: [
      { id: 'n1', type: 'note', title: 'El archivo como material', body: 'Trabajar con lo que ya existe: recortar, desplazar y volver a mirar.', x: 80, y: 80, width: 300, color: 'paper' },
      { id: 'n2', type: 'note', title: 'Regla de la semana', body: 'Una imagen no entra si no cambia la lectura de las otras.', x: 420, y: 80, width: 280, color: 'sand' },
      { id: 'n3', type: 'link', title: 'Letterform Archive', body: 'Tipografía y archivo.', url: 'https://letterformarchive.org', x: 80, y: 320, width: 300, color: 'sage' },
      { id: 'n4', type: 'media', title: 'Prueba de mesa', body: '', media: { name: 'mesa.svg', mimeType: 'image/svg+xml', dataUrl: imagen, kind: 'image' }, x: 420, y: 320, width: 280, color: 'rose' },
      {
        id: 'r1', type: 'referente', title: 'Irene Guerra', x: 760, y: 80, width: 320, color: 'paper',
        datos: { nombre: 'Irene Guerra', url: 'https://ireneguerra.xyz', archivoOrigen: 'portfolio', anio: '2026', autor: 'Irene Guerra', licencia: '©', porQue: 'Monument y Diatype con una jerarquía muy seca.', etiquetas: ['tipografía', 'archivo'], vistoEn: ['2026-10-24'], imagenes: [{ name: 'obra.svg', mimeType: 'image/svg+xml', dataUrl: imagen, kind: 'image' }], lecturas: [] },
      },
      {
        id: 'l1', type: 'marco', title: 'Sala de lectura', x: 80, y: 600, width: 1000,
        datos: { alto: 420, hijos, vista: 'libre' },
      },
    ],
  };
}

async function sembrar(page) {
  await page.evaluate(async (board) => {
    const requestValue = (request) => new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const db = await requestValue(indexedDB.open('prometeo-studio-visual-board', 1));
    const tx = db.transaction(['boards', 'meta'], 'readwrite');
    tx.objectStore('boards').put(board);
    tx.objectStore('meta').put({ key: 'active-board-id', value: board.id });
    await new Promise((resolve, reject) => {
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
    db.close();
  }, demo());
}

const servidor = spawn('npx', ['vite', '--port', String(PUERTO), '--strictPort'], {
  cwd: path.resolve(AQUI, '..'),
  stdio: 'ignore',
});
let navegador;
try {
  await esperarUrl(APP_URL);
  navegador = await chromium.launch({ executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser' });
  const contexto = await navegador.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
  const page = await contexto.newPage();
  await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
    const ruta = new URL(route.request().url()).pathname;
    if (ruta === '/api/health') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ready: true, version: 'forja2', ocr_available: false }) });
    if (ruta === '/api/samples') return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ ok: true, samples: [] }) });
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' });
  });
  await page.goto(APP_URL);
  await page.getByRole('button', { name: /Tablero/ }).first().click();
  await page.locator('.board-workspace').waitFor();
  await sembrar(page);
  await page.reload();
  await page.getByRole('button', { name: /Tablero/ }).first().click();
  await page.locator('.board-workspace').waitFor();
  await page.waitForTimeout(900);
  if (lod) {
    const caja = await page.locator('.board-viewport').boundingBox();
    if (caja) await page.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2);
    await page.keyboard.down('Control');
    for (let i = 0; i < 40; i += 1) await page.mouse.wheel(0, 120);
    await page.keyboard.up('Control');
    await page.waitForTimeout(700);
  }
  await mkdir(SALIDA, { recursive: true });
  const destino = path.join(SALIDA, `${fase}-${momento}.png`);
  await page.screenshot({ path: destino, animations: 'disabled' });
  console.log(destino);
} finally {
  await navegador?.close();
  servidor.kill('SIGTERM');
}
