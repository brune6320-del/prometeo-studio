import { expect, test, type Page } from '@playwright/test';
import { abrirTableroCon, capturar, marco, tarjeta } from './helpers';

function tableroMixto() {
  return [
    tarjeta({ id: 'g1-nota-a', type: 'note', title: 'Nota A', body: 'Primera idea del tablero.', x: 220, y: 180, width: 300 }),
    tarjeta({ id: 'g1-nota-b', type: 'note', title: 'Nota B', body: 'Segunda idea, alineada.', x: 620, y: 180, width: 300, color: 'sand' }),
    tarjeta({ id: 'g1-nota-c', type: 'note', title: 'Nota C', body: 'Tercera idea.', x: 1020, y: 180, width: 300, color: 'sage' }),
    tarjeta({ id: 'g1-enlace', type: 'link', title: 'Enlace', body: '', url: 'https://example.com', x: 220, y: 560, width: 300 }),
    marco('g1-marco', 620, 540, { title: 'Marco G1', datos: { alto: 380, hijos: [], vista: 'libre' } }),
  ];
}

async function camara(page: Page) {
  return page.evaluate(() => {
    const stage = document.querySelector<HTMLElement>('.board-stage');
    if (!stage) throw new Error('Sin escenario');
    const matriz = new DOMMatrixReadOnly(getComputedStyle(stage).transform);
    return { zoom: matriz.a, x: matriz.e, y: matriz.f };
  });
}

async function estadoLimpio(page: Page) {
  const panneando = await page.locator('.board-viewport.panning').count();
  const arrastrando = await page.locator('.board-card.dragging, .board-frame.dragging').count();
  expect(panneando).toBe(0);
  expect(arrastrando).toBe(0);
}

async function puntoVacio(page: Page) {
  return page.evaluate(() => {
    const vp = document.querySelector<HTMLElement>('.board-viewport');
    if (!vp) throw new Error('Sin viewport');
    const caja = vp.getBoundingClientRect();
    for (let y = caja.top + 80; y < caja.bottom - 80; y += 14) {
      for (let x = caja.left + 80; x < caja.right - 80; x += 14) {
        const el = document.elementFromPoint(x, y);
        if (el && (el.classList.contains('board-viewport') || el.classList.contains('board-stage') || el.classList.contains('board-relations'))) return { x, y };
      }
    }
    return { x: caja.left + caja.width / 2, y: caja.top + caja.height / 2 };
  });
}

async function guardado(page: Page) {
  await page.waitForFunction(() => document.querySelector('.board-save-state')?.textContent === 'Guardado', null, { timeout: 10_000 });
}

async function rueda(page: Page, dx: number, dy: number, ctrl = false) {
  if (ctrl) await page.keyboard.down('Control');
  await page.mouse.wheel(dx, dy);
  if (ctrl) await page.keyboard.up('Control');
}

test.describe('G1 · trackpad acoplado', () => {
  test.setTimeout(180_000);

  test('200 gestos mezclados no dejan el lienzo sordo ni capturas colgadas', async ({ page }) => {
    await abrirTableroCon(page, tableroMixto());
    await page.waitForTimeout(500);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    // Segundo tablero para probar que cambiar de documento no pierde la rueda ni el puntero.
    const tableroOriginal = await page.locator('#board-select').inputValue();
    await page.getByRole('button', { name: 'Crear tablero' }).click();
    await guardado(page);
    await page.waitForTimeout(150);
    const opciones = await page.locator('#board-select option').count();
    expect(opciones).toBeGreaterThanOrEqual(2);
    const ids = await page.locator('#board-select option').evaluateAll((options) => options.map((o) => (o as HTMLOptionElement).value));
    const tableroVacio = ids.find((id) => id !== tableroOriginal) ?? tableroOriginal;
    await page.selectOption('#board-select', tableroOriginal);
    await expect(page.locator('#board-select')).toHaveValue(tableroOriginal);
    await page.waitForTimeout(250);

    const vacio = await puntoVacio(page);
    const caja = await page.locator('.board-viewport').boundingBox();
    if (!caja) throw new Error('Sin viewport');
    const mapa = { pinchIn: 0, pinchOut: 0, dosDedos: 0, fondo: 0, tarjeta: 0, doble: 0, vista: 0, tablero: 0 };

    for (let i = 0; i < 200; i += 1) {
      const tipo = i % 8;
      if (tipo === 0) {
        await page.mouse.move(vacio.x, vacio.y + (i % 7) * 12);
        await rueda(page, 0, 90, true);
        mapa.pinchIn += 1;
      } else if (tipo === 1) {
        await page.mouse.move(vacio.x, vacio.y + (i % 5) * 10);
        await rueda(page, 0, -90, true);
        mapa.pinchOut += 1;
      } else if (tipo === 2) {
        await page.mouse.move(vacio.x, vacio.y);
        await rueda(page, 30, 20);
        mapa.dosDedos += 1;
      } else if (tipo === 3) {
        await page.mouse.move(vacio.x, vacio.y);
        await page.mouse.down();
        await page.mouse.move(vacio.x + 18, vacio.y + 12, { steps: 3 });
        await page.mouse.up();
        mapa.fondo += 1;
      } else if (tipo === 4) {
        const cabeza = page.locator('[data-card-id="g1-nota-a"] .board-card-head');
        const c = await cabeza.boundingBox();
        if (c) {
          await page.mouse.move(c.x + c.width / 2, c.y + c.height / 2);
          await page.mouse.down();
          await page.mouse.move(c.x + c.width / 2 + 24, c.y + c.height / 2 + 10, { steps: 2 });
          await page.mouse.move(c.x + c.width / 2, c.y + c.height / 2, { steps: 2 });
          await page.mouse.up();
        }
        mapa.tarjeta += 1;
      } else if (tipo === 5) {
        const titulo = page.locator('[data-card-id="g1-nota-b"] .board-card-title');
        const c = await titulo.boundingBox();
        if (c) {
          await page.mouse.dblclick(c.x + c.width / 2, c.y + c.height / 2);
          await page.keyboard.press('Escape');
        }
        mapa.doble += 1;
      } else if (tipo === 6) {
        const selector = page.locator('.board-frame-view select').first();
        const vistas = ['archivo', 'muro', 'mesa', 'libre'];
        await selector.selectOption(vistas[Math.floor(i / 8) % 4]);
        mapa.vista += 1;
      } else {
        await guardado(page);
        await page.selectOption('#board-select', tableroVacio);
        await page.waitForTimeout(40);
        await guardado(page);
        await page.selectOption('#board-select', tableroOriginal);
        await page.waitForTimeout(40);
        mapa.tablero += 1;
      }

      if (i % 10 === 9) {
        await page.waitForTimeout(15);
        await estadoLimpio(page);
        const antes = await camara(page);
        await page.mouse.move(vacio.x, vacio.y);
        await rueda(page, 0, 40);
        await page.waitForTimeout(35);
        const despues = await camara(page);
        expect(Math.hypot(despues.x - antes.x, despues.y - antes.y)).toBeGreaterThan(0.5);
        const tapado = await page.evaluate(({ x, y }) => {
          const el = document.elementFromPoint(x, y);
          return Boolean(el?.closest('.board-add-backdrop, .board-dialog-backdrop, .board-archive-fullscreen'));
        }, vacio);
        expect(tapado).toBe(false);
      }
      if (i % 40 === 39) {
        await page.locator('.board-zoom-value').click();
        await page.waitForTimeout(60);
      }
    }

    expect(mapa).toEqual({ pinchIn: 25, pinchOut: 25, dosDedos: 25, fondo: 25, tarjeta: 25, doble: 25, vista: 25, tablero: 25 });
    await estadoLimpio(page);
    const antesFinal = await camara(page);
    await page.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2);
    await rueda(page, 0, 60);
    await page.waitForTimeout(80);
    const despuesFinal = await camara(page);
    expect(Math.hypot(despuesFinal.x - antesFinal.x, despuesFinal.y - antesFinal.y)).toBeGreaterThan(0.5);

    await capturar(page, '../../REPORTES/capturas-forja3/g1-despues.png');
  });

  test('hover, inclinación, guías y asentado viven y respetan reduced motion', async ({ page }) => {
    await abrirTableroCon(page, tableroMixto());
    await page.waitForTimeout(500);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    await page.locator('.board-zoom-value').click();
    await page.waitForTimeout(200);

    const tarjetaA = page.locator('[data-card-id="g1-nota-a"]');
    const cajaA = await tarjetaA.boundingBox();
    if (!cajaA) throw new Error('Sin tarjeta A');
    await page.mouse.move(cajaA.x + cajaA.width / 2, cajaA.y + cajaA.height / 2);
    await page.waitForTimeout(180);
    const subida = await tarjetaA.evaluate((el) => getComputedStyle(el).transform);
    expect(subida).not.toBe('none');

    const cabeza = page.locator('[data-card-id="g1-nota-a"] .board-card-head');
    const c = await cabeza.boundingBox();
    const b = await page.locator('[data-card-id="g1-nota-b"]').boundingBox();
    if (!c || !b) throw new Error('Sin cabecera o tarjeta B');
    const destinoX = c.x + c.width / 2 + (b.x - cajaA.x) + 3;
    const destinoY = c.y + c.height / 2 + (b.y - cajaA.y) + 2;
    await page.mouse.move(c.x + c.width / 2, c.y + c.height / 2);
    await page.mouse.down();
    await page.mouse.move(destinoX, destinoY, { steps: 18 });
    const inclinacion = await page.locator('.board-viewport').evaluate((el) => getComputedStyle(el).getPropertyValue('--drag-tilt'));
    expect(inclinacion.trim()).not.toBe('');
    const guiaVisible = await page.locator('.board-guide').count();
    expect(guiaVisible).toBeGreaterThan(0);
    await page.mouse.up();
    await page.waitForTimeout(40);
    const asentando = await page.locator('.board-card.settling').count();
    expect(asentando).toBeGreaterThan(0);
    await page.waitForTimeout(320);
    await estadoLimpio(page);

    await page.emulateMedia({ reducedMotion: 'reduce' });
    const c2 = await cabeza.boundingBox();
    if (!c2) throw new Error('Sin cabecera');
    await page.mouse.move(c2.x + c2.width / 2, c2.y + c2.height / 2);
    await page.mouse.down();
    for (let i = 0; i < 12; i += 1) await page.mouse.move(c2.x + c2.width / 2 - i * 10, c2.y + c2.height / 2 + i * 2);
    const sinInclinacion = await page.locator('.board-viewport').evaluate((el) => getComputedStyle(el).getPropertyValue('--drag-tilt'));
    expect(sinInclinacion.trim()).toBe('');
    await page.mouse.up();
    await page.waitForTimeout(60);
    expect(await page.locator('.board-card.settling').count()).toBe(0);
    await estadoLimpio(page);
  });

  test('los gestos de WebKit y rAF mantienen el zoom y el ritmo', async ({ page }) => {
    await abrirTableroCon(page, tableroMixto());
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const antes = await camara(page);
    const emitirGesto = (tipo: string, scale: number) => page.evaluate(({ tipo, scale }) => {
      const el = document.querySelector<HTMLElement>('.board-viewport');
      if (!el) return false;
      const caja = el.getBoundingClientRect();
      const evento = new Event(tipo, { bubbles: true, cancelable: true });
      Object.defineProperties(evento, {
        scale: { value: scale },
        clientX: { value: caja.left + caja.width / 2 },
        clientY: { value: caja.top + caja.height / 2 },
      });
      el.dispatchEvent(evento);
      return true;
    }, { tipo, scale });
    expect(await emitirGesto('gesturestart', 1)).toBe(true);
    expect(await emitirGesto('gesturechange', 1.3)).toBe(true);
    await page.waitForTimeout(80);
    const durante = await camara(page);
    expect(durante.zoom).toBeGreaterThan(antes.zoom + 0.01);
    await emitirGesto('gestureend', 1.3);
    await page.waitForTimeout(250);

    const fps = await page.evaluate(() => new Promise<number>((resolve) => {
      let frames = 0;
      const inicio = performance.now();
      const paso = (ahora: number) => {
        frames += 1;
        if (ahora - inicio < 1000) requestAnimationFrame(paso);
        else resolve((frames * 1000) / (ahora - inicio));
      };
      requestAnimationFrame(paso);
    }));
    console.log(`G1 rAF: ${fps.toFixed(1)} fps en este entorno`);
    expect(fps).toBeGreaterThan(20);
  });
});
