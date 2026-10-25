import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const PUERTO = 5199;
const APP_URL = `http://localhost:${PUERTO}`;
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

async function esperarUrl(url, intentos = 80) {
  for (let i = 0; i < intentos; i += 1) {
    try { if ((await fetch(url)).ok) return; } catch { /* arrancando */ }
    await esperar(250);
  }
  throw new Error('Vite no arrancó');
}

function tablero300() {
  const ahora = new Date().toISOString();
  const cards = [];
  for (let i = 0; i < 300; i += 1) {
    cards.push({
      id: `c${i}`, type: 'note', title: `Tarjeta ${String(i + 1).padStart(3, '0')}`,
      body: i % 3 === 0 ? 'Una idea breve para medir el coste de pintar 300 tarjetas.' : '',
      x: (i % 20) * 300, y: Math.floor(i / 20) * 220, width: 260, color: ['paper', 'sand', 'sage', 'rose'][i % 4],
    });
  }
  return { schemaVersion: 1, id: 'board-forja2-300', title: '300 tarjetas', createdAt: ahora, updatedAt: ahora, cards, relations: [] };
}

async function sembrar(page) {
  await page.evaluate(async (board) => {
    const abrir = (r) => new Promise((res, rej) => { r.onsuccess = () => res(r.result); r.onerror = () => rej(r.error); });
    const db = await abrir(indexedDB.open('prometeo-studio-visual-board', 1));
    const tx = db.transaction(['boards', 'meta'], 'readwrite');
    tx.objectStore('boards').put(board);
    tx.objectStore('meta').put({ key: 'active-board-id', value: board.id });
    await new Promise((res, rej) => { tx.oncomplete = res; tx.onerror = () => rej(tx.error); });
    db.close();
  }, tablero300());
}

async function medirFps(page, accion) {
  await page.evaluate(() => {
    window.__forjaMetricas?.reiniciar();
    window.__medicion = { frames: 0, inicio: performance.now(), fin: 0 };
    const loop = () => {
      if (!window.__medicion) return;
      window.__medicion.frames += 1;
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  });
  const antes = await page.evaluate(() => window.__forjaMetricas?.rendersTarjeta ?? 0);
  await accion();
  await page.waitForTimeout(250);
  return await page.evaluate((antes) => {
    const m = window.__medicion;
    m.fin = performance.now();
    const fps = m.frames / ((m.fin - m.inicio) / 1000);
    const renders = (window.__forjaMetricas?.rendersTarjeta ?? 0) - antes;
    return { fps: Math.round(fps * 10) / 10, renders };
  }, antes);
}

const servidor = spawn('npx', ['vite', '--port', String(PUERTO), '--strictPort'], { cwd: path.resolve(AQUI, '..'), stdio: 'ignore' });
let navegador;
try {
  await esperarUrl(APP_URL);
  navegador = await chromium.launch({ executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser' });
  const contexto = await navegador.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await contexto.newPage();
  await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
    const r = new URL(route.request().url()).pathname;
    if (r === '/api/health') return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ready":true}' });
    if (r === '/api/samples') return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true,"samples":[]}' });
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' });
  });
  await page.goto(APP_URL);
  await page.getByRole('button', { name: /Tablero/ }).first().click();
  await page.locator('.board-workspace').waitFor();
  await sembrar(page);
  await page.reload();
  await page.getByRole('button', { name: /Tablero/ }).first().click();
  await page.locator('.board-workspace').waitFor();
  await page.waitForTimeout(1200);
  const caja = await page.locator('.board-viewport').boundingBox();
  if (!caja) throw new Error('Sin viewport');

  const zoom = await medirFps(page, async () => {
    await page.keyboard.down('Control');
    for (let i = 0; i < 40; i += 1) await page.mouse.wheel(0, i % 2 ? 80 : -80);
    await page.keyboard.up('Control');
  });

  const vacio = await page.evaluate(() => {
    const vp = document.querySelector('.board-viewport');
    const caja = vp.getBoundingClientRect();
    for (let y = caja.top + 90; y < caja.bottom - 90; y += 12) {
      for (let x = caja.left + 90; x < caja.right - 90; x += 12) {
        const el = document.elementFromPoint(x, y);
        if (el && (el.classList.contains('board-viewport') || el.classList.contains('board-stage') || el.classList.contains('board-relations'))) return { x, y };
      }
    }
    return { x: caja.left + caja.width / 2, y: caja.top + caja.height / 2 };
  });
  await page.mouse.move(vacio.x, vacio.y);
  const pan = await medirFps(page, async () => {
    await page.mouse.down();
    for (let i = 0; i < 40; i += 1) await page.mouse.move(vacio.x + i * 4, vacio.y + i * 2);
    await page.mouse.up();
  });

  console.log(JSON.stringify({
    tarjetas: 300,
    zoom: { ...zoom, eventos: 40, rendersPorEvento: Math.round((zoom.renders / 40) * 10) / 10 },
    pan: { ...pan, eventos: 40, rendersPorEvento: Math.round((pan.renders / 40) * 10) / 10 },
  }, null, 2));
} finally {
  await navegador?.close();
  servidor.kill('SIGTERM');
}
