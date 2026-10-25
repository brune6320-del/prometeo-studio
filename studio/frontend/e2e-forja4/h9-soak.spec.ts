/**
 * H9 · soak de 15 minutos sobre el build de producción.
 * Se miden fotogramas con rAF, errores de consola y errores de página.
 * La consola y el frame máximo se imprimen para el reporte.
 */
import { expect, test } from '@playwright/test';
import { abrirTableroSembrado, mockReadyBackend, nota, tablero } from './helpers';

test('H9 · 15 minutos con 500 tarjetas: cero errores y fotogramas medidos', async ({ page }) => {
  test.setTimeout(16 * 60 * 1000);
  const errores: string[] = [];
  page.on('console', (message) => { if (message.type() === 'error') errores.push(`console: ${message.text()}`); });
  page.on('pageerror', (error) => errores.push(`pageerror: ${error.message}`));

  const cartas = Array.from({ length: 500 }, (_, indice) => nota(`n${indice}`, (indice % 25) * 280, Math.floor(indice / 25) * 210, `Tarjeta ${indice}`, `cuerpo ${indice}`));
  await mockReadyBackend(page);
  await page.goto('/');
  await abrirTableroSembrado(page, tablero(cartas, 'board-soak', 'Soak 500'));
  await expect(page.locator('[data-card-id]')).toHaveCount(500);

  await page.evaluate(() => {
    const estado = { max: 0, suma: 0, cuenta: 0, sobre33: 0, ultimo: performance.now() };
    (window as unknown as { __soak: typeof estado }).__soak = estado;
    const tick = (ahora: number) => {
      const delta = ahora - estado.ultimo;
      estado.ultimo = ahora;
      estado.max = Math.max(estado.max, delta);
      estado.suma += delta;
      estado.cuenta += 1;
      if (delta > 33.4) estado.sobre33 += 1;
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  });

  const viewport = await page.locator('.board-viewport').boundingBox();
  if (!viewport) throw new Error('Sin viewport.');
  const centro = { x: viewport.x + viewport.width / 2, y: viewport.y + viewport.height / 2 };
  const inicio = Date.now();
  let iteracion = 0;
  while (Date.now() - inicio < 15 * 60 * 1000) {
    iteracion += 1;
    await page.mouse.move(centro.x + (iteracion % 7) * 20, centro.y + (iteracion % 5) * 16);
    await page.mouse.wheel(0, iteracion % 2 === 0 ? 48 : -32);

    if (iteracion % 6 === 0) {
      for (let i = 0; i < 3; i += 1) await page.keyboard.press('Meta+=');
      for (let i = 0; i < 3; i += 1) await page.keyboard.press('Meta+-');
    }
    if (iteracion % 10 === 0) {
      await page.keyboard.press('l');
      await page.getByLabel('Buscar en el índice').fill(`Tarjeta ${iteracion % 500}`);
      await page.waitForTimeout(40);
      await page.keyboard.press('Escape');
    }
    if (iteracion % 12 === 0) {
      await page.keyboard.press('Meta+f');
      const buscador = page.getByLabel('Buscar tarjetas');
      await buscador.fill(`${iteracion % 500}`);
      await page.waitForTimeout(40);
      await page.keyboard.press('Escape');
    }
    if (iteracion % 15 === 0) {
      await page.mouse.move(viewport.x + 160, viewport.y + 160);
      await page.mouse.down();
      await page.mouse.move(viewport.x + 360, viewport.y + 300, { steps: 4 });
      await page.mouse.up();
      await page.keyboard.press('Escape');
    }
    if (iteracion % 20 === 0) {
      await page.keyboard.press('Meta+a');
      await page.waitForTimeout(60);
      await page.keyboard.press('Escape');
    }
    await page.waitForTimeout(1600);
  }

  const metricas = await page.evaluate(() => {
    const estado = (window as unknown as { __soak: { max: number; suma: number; cuenta: number; sobre33: number } }).__soak;
    return { ...estado, fps: estado.cuenta ? 1000 / (estado.suma / estado.cuenta) : 0 };
  });
  console.log(`H9 · soak: ${iteracion} iteraciones · frame máximo ${metricas.max.toFixed(1)} ms · FPS medio ${metricas.fps.toFixed(1)} · frames > 33 ms ${metricas.sobre33}/${metricas.cuenta}`);
  expect(errores, errores.join('\n')).toEqual([]);
  expect(metricas.fps).toBeGreaterThan(20);
  expect(metricas.max).toBeLessThan(1500);
});
