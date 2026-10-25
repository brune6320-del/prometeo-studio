/**
 * H3 · el lienzo se navega con el cuerpo.
 * Top 2 de A-1; debate D5; regla 16. Los eventos son sintéticos y
 * `pointerType: 'touch'`, igual que los entrega un iPad.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, mockReadyBackend, nota, tablero } from './helpers';

test.use({ hasTouch: true, isMobile: true, viewport: { width: 1024, height: 768 } });

async function puntero(page: Page, tipo: string, id: number, x: number, y: number) {
  await page.evaluate(({ tipo, id, x, y }) => {
    const element = document.querySelector('.board-viewport');
    if (!element) throw new Error('Sin viewport');
    element.dispatchEvent(new PointerEvent(tipo, {
      bubbles: true,
      cancelable: true,
      composed: true,
      pointerId: id,
      pointerType: 'touch',
      isPrimary: id === 1,
      clientX: x,
      clientY: y,
      button: 0,
      buttons: tipo === 'pointerup' || tipo === 'pointercancel' ? 0 : 1,
    }));
  }, { tipo, id, x, y });
}

async function transformada(page: Page) {
  return page.locator('.board-stage').evaluate((element) => (element as HTMLElement).style.transform);
}

test('H3 · un dedo dibuja marquesina, dos panean y el pellizco acerca', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  const board = tablero([nota('n1', 100, 100, 'Táctil')], 'board-h3', 'Táctil');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  const caja = await page.locator('.board-viewport').boundingBox();
  if (!caja) throw new Error('Sin viewport.');
  const antes = await transformada(page);

  // Un dedo en el fondo: marquesina, cámara inmóvil.
  await puntero(page, 'pointerdown', 1, caja.x + 240, caja.y + 200);
  await puntero(page, 'pointermove', 1, caja.x + 420, caja.y + 320);
  await expect(page.getByTestId('board-marquee')).toBeVisible();
  await page.screenshot({ path: path.join(CAPTURAS, 'H3-antes-un-dedo.png') });
  await puntero(page, 'pointerup', 1, caja.x + 420, caja.y + 320);
  expect(await transformada(page)).toBe(antes);

  // Dos dedos: paneo 1:1 sin inercia, sin seleccionar.
  await puntero(page, 'pointerdown', 1, caja.x + 300, caja.y + 260);
  await puntero(page, 'pointerdown', 2, caja.x + 500, caja.y + 260);
  for (let paso = 1; paso <= 8; paso += 1) {
    await puntero(page, 'pointermove', 1, caja.x + 300 + paso * 12, caja.y + 260);
    await puntero(page, 'pointermove', 2, caja.x + 500 + paso * 12, caja.y + 260);
  }
  await puntero(page, 'pointerup', 1, caja.x + 396, caja.y + 260);
  await puntero(page, 'pointerup', 2, caja.x + 596, caja.y + 260);
  const trasPaneo = await transformada(page);
  expect(trasPaneo).not.toBe(antes);
  expect(await page.locator('[data-card-id].selected').count()).toBe(0);
  await page.screenshot({ path: path.join(CAPTURAS, 'H3-despues-dos-dedos.png') });

  // Pellizco: los dedos se separan y el zoom aumenta en el punto medio.
  const zoomAntes = await page.locator('.board-zoom-value').textContent();
  await puntero(page, 'pointerdown', 3, caja.x + 400, caja.y + 300);
  await puntero(page, 'pointerdown', 4, caja.x + 600, caja.y + 300);
  for (let paso = 1; paso <= 6; paso += 1) {
    await puntero(page, 'pointermove', 3, caja.x + 400 - paso * 20, caja.y + 300);
    await puntero(page, 'pointermove', 4, caja.x + 600 + paso * 20, caja.y + 300);
  }
  await puntero(page, 'pointerup', 3, caja.x + 280, caja.y + 300);
  await puntero(page, 'pointerup', 4, caja.x + 720, caja.y + 300);
  await expect.poll(async () => Number((await page.locator('.board-zoom-value').textContent())?.replace('%', ''))).toBeGreaterThan(Number(zoomAntes?.replace('%', '')));

  // Botón Mano: un dedo mueve la cámara aunque el fondo también dibuje marquesina.
  await page.getByRole('button', { name: /^Mano/ }).click();
  const antesMano = await transformada(page);
  const z = await page.locator('.board-zoom-value').textContent();
  await puntero(page, 'pointerdown', 5, caja.x + 320, caja.y + 300);
  for (let paso = 1; paso <= 6; paso += 1) {
    await puntero(page, 'pointermove', 5, caja.x + 320 - paso * 10, caja.y + 300 + paso * 4);
  }
  await puntero(page, 'pointerup', 5, caja.x + 260, caja.y + 324);
  expect(await transformada(page)).not.toBe(antesMano);
  expect(await page.locator('.board-zoom-value').textContent()).toBe(z);
});

test('H3 · en táctil los controles llegan a 24 px y las asas a 44 px', async ({ page }) => {
  const board = tablero([
    nota('n1', 100, 100, 'Objetivos'),
    { id: 'm1', type: 'media', title: 'Imagen', body: '', x: 500, y: 100, width: 260, height: 180, color: 'paper', media: { name: 'x.png', mimeType: 'image/png', kind: 'image', dataUrl: 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==' } },
  ], 'board-h3-targets', 'Objetivos');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  expect(await page.evaluate(() => matchMedia('(pointer: coarse)').matches)).toBe(true);
  const tamano = async (selector: string) => page.locator(selector).first().evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
  });
  const swatch = await tamano('.board-color-swatch');
  expect(swatch.width).toBeGreaterThanOrEqual(24);
  expect(swatch.height).toBeGreaterThanOrEqual(24);
  const asa = await tamano('.board-free-media-handle');
  expect(asa.width).toBeGreaterThanOrEqual(44);
  expect(asa.height).toBeGreaterThanOrEqual(44);
});
