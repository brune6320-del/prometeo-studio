import { expect, test, type Page } from '@playwright/test';
import { abrirTablero, abrirTableroCon, marco, tarjeta } from './helpers';
import fs from 'node:fs';
import path from 'node:path';

const IMAGEN = path.resolve('e2e-forja3/fixtures/imagen-1920.png');

function imagen(id: string) {
  const base64 = fs.readFileSync(IMAGEN).toString('base64');
  return {
    id, type: 'media', title: id, body: '', x: 700, y: 700, width: 260, color: 'paper',
    media: { name: `${id}.png`, mimeType: 'image/png', dataUrl: `data:image/png;base64,${base64}`, kind: 'image' },
  };
}

async function guardado(page: Page) {
  await page.waitForFunction(() => document.querySelector('.board-save-state')?.textContent === 'Guardado', null, { timeout: 15_000 });
}

test.describe('G8 · soak', () => {
  test.skip(process.env.PROMETEO_SOAK !== '1', 'Soak de 15 min: ejecutar con PROMETEO_SOAK=1');
  test.setTimeout(960_000);

  test('15 minutos de uso continuo con recargas y cambios de vista', async ({ page }) => {
    test.slow();
    page.setDefaultTimeout(8_000);
    const errores: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errores.push(message.text()); });
    page.on('pageerror', (error) => errores.push(`${error.name}: ${error.message}`));

    await abrirTableroCon(page, [
      tarjeta({ id: 'g8s-nota', type: 'note', title: 'Base', body: 'Soak', x: 240, y: 200, width: 300 }),
      tarjeta({ id: 'g8s-t', type: 'etiqueta', title: 'IN EXHIBITION', body: 'DE-P01.01', x: 240, y: 560, width: 220 }),
      imagen('g8s-m1'),
      imagen('g8s-m2'),
      marco('g8s-marco', 240, 520, {
        title: 'BARATTOLO',
        width: 840,
        datos: { alto: 420, hijos: ['g8s-t', 'g8s-m1', 'g8s-m2'], vista: 'archivo' },
      }),
    ]);
    await page.waitForTimeout(500);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    const marcoEl = page.locator('[data-card-id="g8s-marco"]');
    const vista = marcoEl.locator('select[aria-label^="Ver como"]');
    const inicio = Date.now();
    let ciclos = 0;
    let peorFps = 240;
    let recargas = 0;

    while (Date.now() - inicio < 900_000) {
      ciclos += 1;

      // Herramienta: añadir una nota y borrarla.
      await page.getByRole('button', { name: 'Más herramientas' }).click();
      await page.getByRole('searchbox', { name: 'Buscar herramienta' }).fill('nota');
      await page.getByRole('button', { name: 'Añadir al tablero' }).click();
      const nueva = page.locator('.board-card.selected');
      await expect(nueva).toHaveCount(1);
      page.once('dialog', (dialog) => void dialog.accept());
      await nueva.locator('.board-card-delete').click();
      await expect(nueva).toHaveCount(0);

      // Vistas.
      await vista.selectOption('archivo');
      await page.waitForTimeout(80);
      if (ciclos % 3 === 0) {
        await marcoEl.locator('.archivo-block').first().dblclick();
        await page.keyboard.press('ArrowRight');
        await page.keyboard.press('Escape');
      }
      await vista.selectOption('muro');
      await page.waitForTimeout(80);
      if (ciclos % 4 === 0) {
        await marcoEl.locator('.muro-thumb').first().click();
        await page.keyboard.press('ArrowRight');
        await page.keyboard.press('Escape');
      }
      await vista.selectOption('mesa');
      await page.waitForTimeout(80);
      if (ciclos % 5 === 0) {
        await marcoEl.getByRole('button', { name: 'Por año' }).click();
        await marcoEl.locator('.mesa-year-more').first().click();
        await page.keyboard.press('Escape');
      }
      await vista.selectOption('libre');

      // Atajos.
      if (ciclos % 7 === 0) {
        await page.keyboard.press('Shift+Slash');
        await page.keyboard.press('Escape');
      }

      // Pan y marquesina.
      if (ciclos % 6 === 0) {
        await page.keyboard.down('Space');
        await page.mouse.move(500, 600);
        await page.mouse.down();
        await page.mouse.move(560, 640, { steps: 6 });
        await page.mouse.up();
        await page.keyboard.up('Space');
      }

      // Sistema de diseño.
      if (ciclos % 9 === 0) {
        const sistema = page.getByLabel('Sistema de diseño del tablero');
        await sistema.selectOption(ciclos % 18 === 0 ? 'forja' : 'irene');
      }

      // Ritmo.
      if (ciclos % 20 === 0) {
        const fps = await page.evaluate(() => new Promise<number>((resolve) => {
          let frames = 0;
          const start = performance.now();
          const step = () => {
            frames += 1;
            if (performance.now() - start > 400) resolve(Math.round((frames * 1000) / (performance.now() - start)));
            else requestAnimationFrame(step);
          };
          requestAnimationFrame(step);
        }));
        peorFps = Math.min(peorFps, fps);
      }

      // Recarga y recuperación.
      if (Date.now() - inicio > (recargas + 1) * 60_000) {
        await guardado(page);
        await page.reload();
        await abrirTablero(page);
        recargas += 1;
      }
      await page.waitForTimeout(120);
    }

    console.log(JSON.stringify({ segundos: Math.round((Date.now() - inicio) / 1000), ciclos, recargas, peorFps, errores }, null, 2));
    expect(errores).toEqual([]);
    expect(peorFps).toBeGreaterThanOrEqual(30);
  });
});
