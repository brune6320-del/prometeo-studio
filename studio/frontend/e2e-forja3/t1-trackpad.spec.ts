import { expect, test, type Page } from '@playwright/test';
import { abrirTableroCon, marco, tarjeta } from './helpers';

/**
 * T-1 · trackpad real.
 * La rueda y el pellizco (ctrl + rueda) escriben la cámara en el mismo frame:
 * sin muelle, sin lerp, sin inercia propia y sin setState por evento.
 */

function tablero() {
  return [
    tarjeta({ id: 't1-nota-a', type: 'note', title: 'Nota A', body: 'Una idea.', x: 220, y: 180, width: 300 }),
    tarjeta({ id: 't1-nota-b', type: 'note', title: 'Nota B', body: 'Otra idea.', x: 620, y: 200, width: 300, color: 'sand' }),
    marco('t1-marco', 980, 180, { title: 'Marco T1', datos: { alto: 380, hijos: [], vista: 'libre' } }),
  ];
}

interface Camara {
  zoom: number;
  x: number;
  y: number;
}

async function camara(page: Page): Promise<Camara> {
  return page.evaluate(() => {
    const stage = document.querySelector<HTMLElement>('.board-stage');
    if (!stage) throw new Error('Sin escenario');
    const matriz = new DOMMatrixReadOnly(getComputedStyle(stage).transform);
    return { zoom: matriz.a, x: matriz.e, y: matriz.f };
  });
}

/** Punto del mundo bajo un punto de pantalla, con la cámara actual. */
async function mundoBajo(page: Page, punto: { x: number; y: number }) {
  return page.evaluate(({ x, y }) => {
    const vp = document.querySelector<HTMLElement>('.board-viewport');
    const stage = document.querySelector<HTMLElement>('.board-stage');
    if (!vp || !stage) throw new Error('Sin viewport o escenario');
    const caja = vp.getBoundingClientRect();
    const matriz = new DOMMatrixReadOnly(getComputedStyle(stage).transform);
    return {
      x: (x - caja.left - matriz.e) / matriz.a,
      y: (y - caja.top - matriz.f) / matriz.a,
    };
  }, punto);
}

/** Muestrea 500 ms de rAF y cuenta si el transform del mundo volvió a cambiar. */
async function colaDeAnimacion(page: Page) {
  return page.evaluate(() => new Promise<{ cambios: number; frames: number; maxGap: number }>((resolve) => {
    const stage = document.querySelector<HTMLElement>('.board-stage');
    if (!stage) throw new Error('Sin escenario');
    const inicial = getComputedStyle(stage).transform;
    let cambios = 0;
    let frames = 0;
    let maxGap = 0;
    let ultimo = performance.now();
    const inicio = ultimo;
    const tick = (ahora: number) => {
      frames += 1;
      maxGap = Math.max(maxGap, ahora - ultimo);
      ultimo = ahora;
      if (getComputedStyle(stage).transform !== inicial) cambios += 1;
      if (ahora - inicio < 500) requestAnimationFrame(tick);
      else resolve({ cambios, frames, maxGap });
    };
    requestAnimationFrame(tick);
  }));
}

test.describe('T-1 · trackpad 1:1', () => {
  test.setTimeout(120_000);

  test('20 pellizcos ctrl+rueda: el punto bajo el cursor no se mueve y no queda cola de animación', async ({ page }) => {
    await abrirTableroCon(page, tablero());
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const caja = await page.locator('.board-viewport').boundingBox();
    if (!caja) throw new Error('Sin viewport');
    const cursor = { x: caja.x + caja.width * 0.72, y: caja.y + caja.height * 0.42 };
    await page.mouse.move(cursor.x, cursor.y);

    const antes = await camara(page);
    const mundoAntes = await mundoBajo(page, cursor);

    await page.keyboard.down('Control');
    for (let i = 0; i < 20; i += 1) await page.mouse.wheel(0, -3);
    await page.keyboard.up('Control');

    // (a) Tras el último evento la cámara ya no se mueve ni un frame.
    const cola = await colaDeAnimacion(page);
    console.log(`T-1 cola tras el gesto: ${cola.cambios} cambios en ${cola.frames} frames, hueco máximo ${cola.maxGap.toFixed(1)} ms`);
    expect(cola.cambios).toBe(0);
    expect(cola.maxGap).toBeLessThan(32);

    // (b) El mundo bajo el cursor queda clavado (zoom hacia el cursor).
    const despues = await camara(page);
    const mundoDespues = await mundoBajo(page, cursor);
    expect(despues.zoom).toBeGreaterThan(antes.zoom + 0.01);
    expect(Math.hypot(mundoDespues.x - mundoAntes.x, mundoDespues.y - mundoAntes.y)).toBeLessThan(0.75);
  });

  test('wheel de dos dedos aplica el delta 1:1 y para en el acto', async ({ page }) => {
    await abrirTableroCon(page, tablero());
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const caja = await page.locator('.board-viewport').boundingBox();
    if (!caja) throw new Error('Sin viewport');
    await page.mouse.move(caja.x + caja.width / 2, caja.y + caja.height / 2);

    const antes = await camara(page);
    await page.mouse.wheel(0, 120);
    const siguiente = await page.evaluate(() => new Promise<Camara>((resolve) => {
      requestAnimationFrame(() => {
        const stage = document.querySelector<HTMLElement>('.board-stage');
        if (!stage) throw new Error('Sin escenario');
        const matriz = new DOMMatrixReadOnly(getComputedStyle(stage).transform);
        resolve({ zoom: matriz.a, x: matriz.e, y: matriz.f });
      });
    }));
    // Un evento = 120 px de mundo, en el mismo frame. Sin inercia sumada después.
    expect(siguiente.x).toBeCloseTo(antes.x, 1);
    expect(siguiente.y).toBeCloseTo(antes.y - 120, 1);

    const cola = await colaDeAnimacion(page);
    expect(cola.cambios).toBe(0);
    expect(cola.maxGap).toBeLessThan(32);
  });

  test('durante el gesto no hay transición de transform ni re-render de tarjetas', async ({ page }) => {
    await abrirTableroCon(page, tablero());
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const caja = await page.locator('.board-viewport').boundingBox();
    if (!caja) throw new Error('Sin viewport');
    const cursor = { x: caja.x + caja.width * 0.62, y: caja.y + caja.height * 0.38 };

    // Gestión en el mismo task: así se mide lo que ocurre DURANTE el gesto,
    // antes del debounce de 150 ms que sincroniza React.
    const durante = await page.evaluate(({ x, y }) => {
      const metricas = (window as unknown as { __forjaMetricas: { rendersTarjeta: number; reiniciar: () => void } }).__forjaMetricas;
      const vp = document.querySelector<HTMLElement>('.board-viewport');
      const stage = document.querySelector<HTMLElement>('.board-stage');
      const card = document.querySelector<HTMLElement>('.board-card');
      if (!metricas || !vp || !stage || !card) throw new Error('Sin instrumentación');
      metricas.reiniciar();
      const antes = getComputedStyle(stage).transform;
      const rendersAntes = metricas.rendersTarjeta;
      for (let i = 0; i < 20; i += 1) {
        vp.dispatchEvent(new WheelEvent('wheel', {
          deltaY: -3,
          ctrlKey: true,
          clientX: x,
          clientY: y,
          bubbles: true,
          cancelable: true,
        }));
      }
      return {
        renders: metricas.rendersTarjeta - rendersAntes,
        gestoActivo: vp.classList.contains('gesto-activo'),
        transicion: getComputedStyle(card).transitionProperty,
        transformo: getComputedStyle(stage).transform !== antes,
      };
    }, cursor);

    // (c) Cero re-renders de tarjeta y cero transición de transform durante el gesto.
    expect(durante.renders).toBe(0);
    expect(durante.gestoActivo).toBe(true);
    expect(durante.transicion).toBe('none');
    expect(durante.transformo).toBe(true);

    await page.waitForTimeout(260);
    const despues = await page.evaluate(() => {
      const vp = document.querySelector<HTMLElement>('.board-viewport');
      const card = document.querySelector<HTMLElement>('.board-card');
      if (!vp || !card) throw new Error('Sin viewport o tarjeta');
      return { gestoActivo: vp.classList.contains('gesto-activo'), transicion: getComputedStyle(card).transitionProperty };
    });
    expect(despues.gestoActivo).toBe(false);
    expect(despues.transicion).not.toBe('none');
  });

  test('los tiradores de estirado tienen zona de agarre de al menos 12 px', async ({ page }) => {
    await abrirTableroCon(page, tablero());
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const tirador = page.locator('.board-frame-resize').first();
    const caja = await tirador.boundingBox();
    if (!caja) throw new Error('Sin tirador de marco');
    expect(caja.width).toBeGreaterThanOrEqual(12);
    expect(caja.height).toBeGreaterThanOrEqual(12);

    // El tirador de una pieza libre también reserva 22×22 aunque el punto visible sea menor.
    const regla = await page.evaluate(() => {
      for (const hoja of Array.from(document.styleSheets)) {
        let reglas: CSSRuleList;
        try { reglas = hoja.cssRules; } catch { continue; }
        for (const regla of Array.from(reglas)) {
          if (regla instanceof CSSStyleRule && regla.selectorText === '.board-free-media-handle') {
            return { ancho: regla.style.width, alto: regla.style.height };
          }
        }
      }
      return null;
    });
    expect(regla).toEqual({ ancho: '22px', alto: '22px' });
  });
});
