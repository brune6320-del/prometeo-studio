import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { abrirTablero, abrirTableroCon, capturar, marco, tarjeta } from './helpers';

const IMAGEN = path.resolve('e2e-forja3/fixtures/imagen-1920.png');

function imagen(id: string, title: string, x: number, y: number) {
  const base64 = fs.readFileSync(IMAGEN).toString('base64');
  return {
    id,
    type: 'media',
    title,
    body: '',
    x,
    y,
    width: 260,
    color: 'paper',
    media: { name: `${id}.png`, mimeType: 'image/png', dataUrl: `data:image/png;base64,${base64}`, kind: 'image' },
  };
}

async function guardado(page: Page) {
  await page.waitForFunction(() => document.querySelector('.board-save-state')?.textContent === 'Guardado', null, { timeout: 15_000 });
}

test.describe('G8 · caza de errores', () => {
  test.setTimeout(300_000);

  test('recorrido de 15 minutos como Bruno: herramientas, vistas, diseño, plantillas y recarga', async ({ page }) => {
    const inicio = Date.now();
    const errores: string[] = [];
    const fallosRed: string[] = [];
    page.on('console', (message) => { if (message.type() === 'error') errores.push(message.text()); });
    page.on('pageerror', (error) => errores.push(`${error.name}: ${error.message}`));
    page.on('requestfailed', (request) => fallosRed.push(`${request.method()} ${request.url()} · ${request.failure()?.errorText ?? ''}`));

    await abrirTableroCon(page, [
      tarjeta({ id: 'g8-nota', type: 'note', title: 'Nota A', body: 'Una idea con **negrita** y una lista:', x: 220, y: 180, width: 300 }),
      tarjeta({ id: 'g8-link', type: 'link', title: 'Enlace', body: '', url: 'https://example.com', x: 620, y: 200, width: 300 }),
      tarjeta({ id: 'g8-tareas', type: 'tareas', title: 'Tareas', x: 220, y: 500, width: 280, datos: { tareas: [{ id: 't1', texto: 'Revisar', hecha: false, nivel: 0 }] } }),
      tarjeta({ id: 'g8-col', type: 'columna', title: 'Columna', x: 980, y: 200, width: 300, datos: { hijos: [], plegada: false } }),
      tarjeta({ id: 'g8-e1', type: 'etiqueta', title: 'IN EXHIBITION', body: 'DE-P01.01', x: 620, y: 620, width: 220 }),
      imagen('g8-m1', 'Pareidolìa 01', 620, 680),
      imagen('g8-m2', 'Pareidolìa 02', 620, 760),
      tarjeta({ id: 'g8-t1', type: 'note', title: 'Texto', body: 'Un dispositivo especulativo.\n\nSegundo párrafo.', x: 620, y: 840, width: 300 }),
      marco('g8-marco', 620, 600, {
        title: 'BARATTOLO',
        width: 840,
        datos: { alto: 460, hijos: ['g8-e1', 'g8-m1', 'g8-m2', 'g8-t1'], vista: 'archivo' },
      }),
    ]);
    await page.waitForTimeout(600);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    await guardado(page);

    await page.setDefaultTimeout(6_000);

    // Atajos
    await page.keyboard.press('Shift+Slash');
    await expect(page.getByRole('dialog', { name: 'Atajos del tablero' })).toBeVisible();
    await page.keyboard.press('Escape');

    // Renombrar nota y URL
    const titulo = page.locator('[data-card-id="g8-nota"] .board-card-title');
    await titulo.dblclick();
    await page.locator('[data-card-id="g8-nota"] .board-inline-input').fill('Nota renombrada');
    await page.keyboard.press('Enter');
    await expect(page.locator('[data-card-id="g8-nota"] .board-card-title')).toContainText('Nota renombrada');
    const url = page.locator('[data-card-id="g8-link"] .board-link-url-text');
    await url.dblclick();
    await page.locator('[data-card-id="g8-link"] .board-url-edit input').fill('https://example.org/caza');
    await page.keyboard.press('Enter');
    await guardado(page);

    // Marco con hijos: Archivo → pliego → Esc
    const marcoEl = page.locator('[data-card-id="g8-marco"]');
    const selectVista = marcoEl.locator('select[aria-label^="Ver como"]');
    await selectVista.selectOption('archivo');
    await page.waitForTimeout(500);
    await expect(marcoEl.locator('.archivo-counter')).toHaveText('1 / 2');
    await marcoEl.locator('.archivo-zone.next').click({ position: { x: 30, y: 30 }, timeout: 4_000 });
    await expect(marcoEl.locator('.archivo-counter')).toHaveText('2 / 2');
    await marcoEl.locator('.archivo-block').first().dblclick();
    const pliego = page.locator('.archivo-spread');
    await expect(pliego).toBeVisible();
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Escape');
    await expect(pliego).toHaveCount(0);

    // Muro y caja de luz
    await selectVista.selectOption('muro');
    await page.waitForTimeout(400);
    await marcoEl.locator('.muro-thumb').first().click();
    const caja = page.locator('.board-muro-lightbox');
    await expect(caja).toBeVisible();
    await caja.locator('.muro-lightbox-zone.next').click({ position: { x: 15, y: 20 } });
    await page.keyboard.press('Escape');
    await expect(caja).toHaveCount(0);

    // Mesa y filas por año
    await selectVista.selectOption('mesa');
    await page.waitForTimeout(400);
    await marcoEl.getByRole('button', { name: 'Por año' }).click();
    const filas = marcoEl.locator('.mesa-year');
    expect(await filas.count()).toBeGreaterThan(0);
    await marcoEl.locator('.mesa-year-more').first().click();
    await expect(page.locator('.archivo-spread')).toBeVisible();
    await page.keyboard.press('Escape');
    await selectVista.selectOption('libre');

    // Marquesina simple y espacio + pan
    const nota = await page.locator('[data-card-id="g8-nota"]').boundingBox();
    if (!nota) throw new Error('Sin nota');
    await page.mouse.move(Math.max(16, nota.x - 50), Math.max(110, nota.y - 50));
    await page.mouse.down();
    await page.mouse.move(nota.x + nota.width + 40, nota.y + nota.height + 40, { steps: 12 });
    await page.mouse.up();
    await expect(page.locator('.board-card.selected')).toHaveCount(1);
    const etapa = page.locator('.board-stage');
    const antes = await etapa.evaluate((element) => new DOMMatrixReadOnly(getComputedStyle(element).transform).e);
    await page.keyboard.down('Space');
    await page.mouse.move(500, 600);
    await page.mouse.down();
    await page.mouse.move(620, 680, { steps: 10 });
    await page.mouse.up();
    await page.keyboard.up('Space');
    const despues = await etapa.evaluate((element) => new DOMMatrixReadOnly(getComputedStyle(element).transform).e);
    expect(Math.abs(despues - antes)).toBeGreaterThan(60);

    // Sistema de diseño
    await page.getByLabel('Sistema de diseño del tablero').selectOption('irene');
    await expect(page.locator('html')).toHaveAttribute('data-design-system', 'irene');
    await guardado(page);

    // Plantillas: guardar y reabrir
    await page.getByRole('button', { name: 'Plantillas de tablero' }).click();
    const plantillas = page.getByRole('dialog', { name: 'Plantillas de tablero' });
    await plantillas.getByRole('button', { name: 'Guardar este tablero como plantilla' }).click();
    await expect(plantillas.locator('.board-template-card').filter({ hasText: 'Tablero Forja 2' })).toHaveCount(1);
    await plantillas.getByRole('button', { name: 'Cerrar' }).last().click();

    // Biblioteca: categorías, búsqueda y todas las herramientas
    await page.getByRole('button', { name: 'Más herramientas' }).click();
    for (const categoria of ['Escribir', 'Medios', 'Estructura', 'Referencias', 'Collage']) {
      await page.getByRole('button', { name: categoria, exact: true }).click();
      await page.waitForTimeout(40);
    }
    await page.getByRole('button', { name: 'Todas', exact: true }).click();
    await page.getByRole('searchbox', { name: 'Buscar herramienta' }).fill('tareas');
    await page.getByRole('button', { name: 'Añadir al tablero' }).click();
    await guardado(page);
    await page.getByRole('button', { name: 'Más herramientas' }).click();
    await page.getByRole('searchbox', { name: 'Buscar herramienta' }).fill('referente');
    await page.getByRole('button', { name: 'Añadir al tablero' }).click();
    await page.waitForTimeout(500);
    await page.getByRole('button', { name: 'Más herramientas' }).click();
    await page.getByRole('searchbox', { name: 'Buscar herramienta' }).fill('entropía');
    await page.getByRole('button', { name: 'Añadir al tablero' }).click();
    await page.waitForTimeout(300);
    await page.getByRole('button', { name: 'Más herramientas' }).click();
    await page.getByRole('searchbox', { name: 'Buscar herramienta' }).fill('tablero');
    await page.getByRole('button', { name: 'Añadir al tablero' }).click();
    const anidar = page.getByRole('dialog', { name: 'Anidar un tablero' });
    await expect(anidar).toBeVisible();
    await anidar.locator('.board-template-card').first().click();
    await page.waitForTimeout(400);
    await guardado(page);

    // Recarga: sistema, plantilla y URL siguen
    await page.reload();
    await abrirTablero(page);
    await expect(page.getByLabel('Sistema de diseño del tablero')).toHaveValue('irene');
    await expect(page.locator('[data-card-id="g8-link"] a[aria-label="Abrir el enlace"]')).toHaveAttribute('href', 'https://example.org/caza');
    await page.getByRole('button', { name: 'Plantillas de tablero' }).click();
    await expect(page.getByRole('dialog', { name: 'Plantillas de tablero' }).locator('.board-template-card').filter({ hasText: 'Tablero Forja 2' })).toHaveCount(1);
    await page.keyboard.press('Escape');
    await page.getByLabel('Sistema de diseño del tablero').selectOption('forja');

    // Medida de ritmo con rAF
    const fps = await page.evaluate(() => new Promise<number>((resolve) => {
      let frames = 0;
      const start = performance.now();
      const step = () => {
        frames += 1;
        if (performance.now() - start > 1500) resolve(Math.round((frames * 1000) / (performance.now() - start)));
        else requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    }));
    await capturar(page, '../../REPORTES/capturas-forja3/g8-despues.png');

    const duracion = Math.round((Date.now() - inicio) / 1000);
    console.log(JSON.stringify({ duracion_s: duracion, fps, errores, fallosRed }, null, 2));
    expect(errores).toEqual([]);
    expect(fallosRed.filter((item) => !item.includes('favicon') && !item.includes('net::ERR_ABORTED'))).toEqual([]);
    expect(fps).toBeGreaterThanOrEqual(30);
  });
});
