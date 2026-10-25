import { chromium } from '@playwright/test';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(AQUI, '../../..');
const PUERTO = 5198;
const APP_URL = `http://localhost:${PUERTO}`;
const DURACION_MS = Number(process.env.FORJA2_SOAK_MS ?? 15 * 60 * 1000);
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

async function esperarUrl(url, intentos = 100) {
  for (let i = 0; i < intentos; i += 1) {
    try { if ((await fetch(url)).ok) return; } catch { /* arrancando */ }
    await esperar(250);
  }
  throw new Error('Vite no arrancó');
}

let accionActual = 'inicio';
const resumen = {
  inicio: new Date().toISOString(),
  duracionObjetivoMs: DURACION_MS,
  ciclos: 0,
  erroresConsola: [],
  erroresPagina: [],
  longTasks: [],
  latencias: [],
  memoria: [],
  fallosDeCiclo: [],
};

const servidor = spawn('npx', ['vite', '--port', String(PUERTO), '--strictPort'], { cwd: path.resolve(AQUI, '..'), stdio: 'ignore' });
let navegador;
try {
  await esperarUrl(APP_URL);
  navegador = await chromium.launch({ executablePath: '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser' });
  const contexto = await navegador.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
  const page = await contexto.newPage();
  await page.exposeFunction('reportarLongTask', (ms) => { resumen.longTasks.push({ ms, accion: accionActual, cuando: Date.now() }); });
  await page.addInitScript(() => {
    try {
      new PerformanceObserver((lista) => {
        for (const entrada of lista.getEntries()) {
          const w = window;
          if (typeof w.reportarLongTask === 'function') w.reportarLongTask(Math.round(entrada.duration));
        }
      }).observe({ entryTypes: ['longtask'] });
    } catch { /* sin soporte */ }
  });
  page.on('console', (msg) => { if (msg.type() === 'error') resumen.erroresConsola.push({ texto: msg.text(), cuando: Date.now() }); });
  page.on('pageerror', (err) => resumen.erroresPagina.push({ texto: err.message, cuando: Date.now() }));
  page.on('dialog', (dialog) => void dialog.accept());
  await page.route((url) => url.pathname.startsWith('/api/'), (route) => {
    const r = new URL(route.request().url()).pathname;
    if (r === '/api/health') return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ready":true}' });
    if (r === '/api/samples') return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true,"samples":[]}' });
    return route.fulfill({ status: 200, contentType: 'application/json', body: '{"ok":true}' });
  });

  const abrir = async () => {
    await page.goto(APP_URL);
    await page.getByRole('button', { name: /Tablero/ }).first().click();
    await page.locator('.board-workspace').waitFor();
    await page.waitForTimeout(350);
    const cerrar = page.locator('.board-toast button');
    if (await cerrar.count()) await cerrar.first().click().catch(() => {});
  };

  const medir = async (nombre, accion) => {
    const t0 = Date.now();
    accionActual = nombre;
    try { await accion(); } catch (error) { resumen.fallosDeCiclo.push({ ciclo: resumen.ciclos, accion: nombre, error: String(error).slice(0, 300) }); }
    resumen.latencias.push({ ciclo: resumen.ciclos, accion: nombre, ms: Date.now() - t0 });
    accionActual = 'espera';
  };

  const svg = Buffer.from('<svg xmlns="http://www.w3.org/2000/svg" width="240" height="160"><rect width="240" height="160" fill="#c9b391"/><circle cx="160" cy="70" r="42" fill="#9d5c3a"/></svg>');

  while (Date.now() - Date.parse(resumen.inicio) < DURACION_MS) {
    resumen.ciclos += 1;
    await abrir();
    await medir('nota', async () => {
      await page.getByRole('button', { name: 'Nueva nota' }).click();
      await page.locator('[data-card-type="note"]').last().waitFor();
    });
    await medir('enlace', async () => {
      await page.getByRole('button', { name: 'Añadir enlace' }).click();
      await page.getByLabel('Título').fill(`Fuente ${resumen.ciclos}`);
      await page.getByLabel('Dirección web').fill(`https://example.com/${resumen.ciclos}`);
      await page.getByRole('button', { name: 'Agregar enlace' }).click();
    });
    await medir('imagen', async () => {
      await page.locator('input[accept*="image/*"]').setInputFiles({ name: `pieza-${resumen.ciclos}.svg`, mimeType: 'image/svg+xml', buffer: svg });
    });
    await medir('referente', async () => {
      await page.getByRole('button', { name: 'Añadir referente' }).click();
    });
    await medir('mas', async () => {
      await page.getByRole('button', { name: 'Más herramientas' }).click();
      await page.getByRole('menuitem', { name: 'Etiqueta' }).click();
    });
    await medir('entropia', async () => {
      await page.getByRole('button', { name: 'Añadir entropía' }).click();
    });
    await medir('marco', async () => {
      await page.getByRole('button', { name: 'Dibujar marco' }).click();
      const vp = await page.locator('.board-viewport').boundingBox();
      if (!vp) return;
      const x = vp.x + vp.width * 0.62;
      const y = vp.y + vp.height * 0.28;
      await page.mouse.move(x, y);
      await page.mouse.down();
      for (let i = 1; i <= 8; i += 1) await page.mouse.move(x + i * 22, y + i * 16);
      await page.mouse.up();
    });
    await medir('editar', async () => {
      const nota = page.locator('[data-card-type="note"]').last();
      await nota.locator('.board-card-text').dispatchEvent('dblclick');
      await nota.locator('.board-card-text-editor').fill(`Nota de caza ${resumen.ciclos}`);
      await nota.locator('.board-card-text-editor').press('Enter');
    });
    await medir('mover', async () => {
      const nota = page.locator('[data-card-type="note"]').last();
      const caja = await nota.boundingBox();
      if (!caja) return;
      await page.mouse.move(caja.x + 20, caja.y + 20);
      await page.mouse.down();
      for (let i = 1; i <= 6; i += 1) await page.mouse.move(caja.x + 20 + i * 14, caja.y + 20 + i * 8);
      await page.mouse.up();
    });
    await medir('borrar-y-deshacer', async () => {
      const enlace = page.locator('[data-card-type="link"]').last();
      await enlace.focus();
      await page.keyboard.press('Enter');
      await enlace.locator('.board-card-delete').dispatchEvent('click');
      await page.getByTestId('board-topbar').getByRole('button', { name: 'Deshacer' }).click();
    });
    await medir('ver-como', async () => {
      const marco = page.locator('.board-frame').last();
      await marco.focus();
      await page.keyboard.press('Enter');
      const selector = marco.locator('.board-frame-view select');
      await selector.selectOption('archivo', { force: true });
      await selector.selectOption('muro', { force: true });
      await selector.selectOption('mesa', { force: true });
      await selector.selectOption('archivo', { force: true });
    });
    await medir('publicar', async () => {
      const marco = page.locator('.board-frame').last();
      const descarga = page.waitForEvent('download', { timeout: 15_000 }).catch(() => null);
      await marco.getByRole('button', { name: /Publicar/ }).dispatchEvent('click');
      const archivo = await descarga;
      await archivo?.delete();
    });
    await medir('recargar', async () => {
      await page.waitForTimeout(250);
      await abrir();
    });
    const memoria = await page.evaluate(() => (performance).memory ? Math.round((performance).memory.usedJSHeapSize / 1048576) : null).catch(() => null);
    resumen.memoria.push({ ciclo: resumen.ciclos, mb: memoria });
    await esperar(600);
  }
} catch (error) {
  resumen.fallosDeCiclo.push({ ciclo: resumen.ciclos, accion: 'global', error: String(error).slice(0, 500) });
} finally {
  resumen.fin = new Date().toISOString();
  resumen.duracionRealMs = Date.parse(resumen.fin) - Date.parse(resumen.inicio);
  await mkdir(path.join(REPO, 'REPORTES/capturas-forja2'), { recursive: true });
  await writeFile(path.join(REPO, 'REPORTES/capturas-forja2/f7-soak.json'), JSON.stringify(resumen, null, 2));
  await navegador?.close();
  servidor.kill('SIGTERM');
  console.log(JSON.stringify({ ciclos: resumen.ciclos, errores: resumen.erroresConsola.length + resumen.erroresPagina.length, longTasks: resumen.longTasks.length, fallos: resumen.fallosDeCiclo.length }));
}
