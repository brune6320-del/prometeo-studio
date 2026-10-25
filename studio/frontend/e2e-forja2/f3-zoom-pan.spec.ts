import { expect, test, type Page } from '@playwright/test';
import { abrirTableroCon, tarjeta } from './helpers';

function tablero300() {
  return Array.from({ length: 300 }, (_, i) => tarjeta({
    id: `c${i}`,
    type: 'note',
    title: `Tarjeta ${i + 1}`,
    body: i % 3 === 0 ? 'Una idea breve para medir el coste de pintar 300 tarjetas.' : '',
    x: (i % 20) * 300,
    y: Math.floor(i / 20) * 220,
    width: 260,
    color: ['paper', 'sand', 'sage', 'rose'][i % 4],
  }));
}

async function camara(page: Page) {
  return page.evaluate(() => {
    const stage = document.querySelector<HTMLElement>('.board-stage');
    if (!stage) throw new Error('Sin escenario');
    const matriz = new DOMMatrixReadOnly(getComputedStyle(stage).transform);
    return { zoom: matriz.a, x: matriz.e, y: matriz.f, lod: stage.dataset.lod ?? 'full' };
  });
}

async function puntoVacio(page: Page) {
  return page.evaluate(() => {
    const vp = document.querySelector<HTMLElement>('.board-viewport');
    if (!vp) throw new Error('Sin viewport');
    const caja = vp.getBoundingClientRect();
    for (let y = caja.top + 80; y < caja.bottom - 80; y += 12) {
      for (let x = caja.left + 80; x < caja.right - 80; x += 12) {
        const el = document.elementFromPoint(x, y);
        if (el && (el.classList.contains('board-viewport') || el.classList.contains('board-stage') || el.classList.contains('board-relations'))) return { x, y };
      }
    }
    return { x: caja.left + caja.width / 2, y: caja.top + caja.height / 2 };
  });
}

test('F3 · zoom hacia el cursor, LOD y 55 fps con 300 tarjetas', async ({ page }) => {
  await abrirTableroCon(page, tablero300());
  await page.waitForTimeout(900);
  await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
  await page.waitForTimeout(150);

  const inicial = await camara(page);
  expect(inicial.zoom).toBeLessThan(0.35);
  expect(inicial.lod).toBe('min');
  await expect(page.locator('.board-card .board-card-body').first()).toBeHidden();

  const caja = await page.locator('.board-viewport').boundingBox();
  if (!caja) throw new Error('Sin viewport');
  const foco = { x: Math.round(caja.x + caja.width * 0.62), y: Math.round(caja.y + caja.height * 0.4) };
  await page.mouse.move(foco.x, foco.y);
  const antes = await camara(page);
  const mundoAntes = { x: (foco.x - caja.x - antes.x) / antes.zoom, y: (foco.y - caja.y - antes.y) / antes.zoom };

  await page.keyboard.down('Control');
  for (let i = 0; i < 22; i += 1) await page.mouse.wheel(0, -100);
  await page.keyboard.up('Control');
  await page.waitForTimeout(350);

  const despues = await camara(page);
  const mundoDespues = { x: (foco.x - caja.x - despues.x) / despues.zoom, y: (foco.y - caja.y - despues.y) / despues.zoom };
  expect(despues.zoom).toBeGreaterThan(0.35);
  expect(despues.lod).toBe('full');
  expect(Math.abs(mundoDespues.x - mundoAntes.x) * despues.zoom).toBeLessThan(1);
  expect(Math.abs(mundoDespues.y - mundoAntes.y) * despues.zoom).toBeLessThan(1);

  await page.evaluate(() => {
    window.__forjaMetricas?.reiniciar();
    window.__medicion = { frames: 0, inicio: performance.now() };
    const loop = () => { if (!window.__medicion) return; window.__medicion.frames += 1; requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  });
  await page.keyboard.down('Control');
  for (let i = 0; i < 40; i += 1) await page.mouse.wheel(0, i % 2 ? 80 : -80);
  await page.keyboard.up('Control');
  await page.waitForTimeout(300);
  const rendimiento = await page.evaluate(() => {
    const m = window.__medicion;
    const fps = m.frames / ((performance.now() - m.inicio) / 1000);
    return { fps, renders: window.__forjaMetricas?.rendersTarjeta ?? 0 };
  });
  expect(rendimiento.renders).toBe(0);
  expect(rendimiento.fps).toBeGreaterThanOrEqual(55);
});

test('F3 · el pan tiene inercia y reduced-motion la apaga', async ({ page }) => {
  await abrirTableroCon(page, tablero300());
  await page.waitForTimeout(400);
  const vacio = await puntoVacio(page);
  await page.mouse.move(vacio.x, vacio.y);
  await page.mouse.down();
  for (let i = 0; i < 40; i += 1) await page.mouse.move(vacio.x + i * 8, vacio.y + i * 3);
  await page.mouse.up();
  const alSoltar = await camara(page);
  await page.waitForTimeout(260);
  const despues = await camara(page);
  expect(Math.hypot(despues.x - alSoltar.x, despues.y - alSoltar.y)).toBeGreaterThan(2);

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.mouse.move(vacio.x, vacio.y);
  await page.mouse.down();
  for (let i = 0; i < 40; i += 1) await page.mouse.move(vacio.x - i * 8, vacio.y - i * 3);
  await page.mouse.up();
  const quieto = await camara(page);
  await page.waitForTimeout(260);
  const trasEspera = await camara(page);
  expect(Math.hypot(trasEspera.x - quieto.x, trasEspera.y - quieto.y)).toBeLessThan(0.5);
});
