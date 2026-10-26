/**
 * I5 · «N» y un clic añade. La explicación espera al puntero; nada de «Añadir».
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, mockReadyBackend, tablero } from './helpers';

const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
  'base64',
);

test.beforeEach(async ({ page }) => {
  await mockReadyBackend(page);
});

test('I5 · una nota se añade con un clic y queda seleccionada', async ({ page }) => {
  await abrirTableroSembrado(page, tablero([], 'board-super4-biblioteca', 'Biblioteca'));
  await page.evaluate(() => {
    (window as unknown as { __clics: number }).__clics = 0;
    window.addEventListener('pointerdown', () => { (window as unknown as { __clics: number }).__clics += 1; }, true);
  });
  await page.keyboard.press('n');
  await expect(page.getByText('Biblioteca de herramientas')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Añadir al tablero' })).toHaveCount(0);
  await page.getByRole('option', { name: /^Nota/ }).click();
  await expect(page.locator('.board-card[data-card-type="note"]')).toHaveCount(1);
  await expect(page.locator('.board-card.selected')).toHaveCount(1);
  expect(await page.evaluate(() => (window as unknown as { __clics: number }).__clics)).toBe(1);
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.screenshot({ path: path.join(CAPTURAS, 'I5-despues-un-clic.png') });
});

test('I5 · imagen abre el selector directamente; enlace abre su diálogo', async ({ page }) => {
  await abrirTableroSembrado(page, tablero([], 'board-super4-biblioteca-medios', 'Medios'));
  await page.keyboard.press('n');
  const selector = page.waitForEvent('filechooser');
  await page.getByRole('option', { name: /^Imagen o vídeo/ }).click();
  const eleccion = await selector;
  await eleccion.setFiles({ name: 'pieza.png', mimeType: 'image/png', buffer: PNG });
  await expect(page.locator('.board-free-media')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Añadir al tablero' })).toHaveCount(0);

  await page.keyboard.press('n');
  await page.getByRole('option', { name: /^Enlace/ }).click();
  await expect(page.getByRole('dialog', { name: 'Añadir enlace' })).toBeVisible();
});

test('I5 · tabla de clics: nota, imagen, enlace, columna y marco no pasan de dos', async ({ page }) => {
  await abrirTableroSembrado(page, tablero([], 'board-super4-clics', 'Clics'));
  await page.evaluate(() => {
    (window as unknown as { __clics: number }).__clics = 0;
    window.addEventListener('pointerdown', () => { (window as unknown as { __clics: number }).__clics += 1; }, true);
  });
  const reiniciar = () => page.evaluate(() => { (window as unknown as { __clics: number }).__clics = 0; });
  const clics = () => page.evaluate(() => (window as unknown as { __clics: number }).__clics);

  await reiniciar();
  await page.keyboard.press('n');
  await page.getByRole('option', { name: /^Nota/ }).click();
  expect(await clics()).toBe(1);

  await reiniciar();
  await page.keyboard.press('n');
  const selector = page.waitForEvent('filechooser');
  await page.getByRole('option', { name: /^Imagen o vídeo/ }).click();
  const eleccion = await selector;
  await eleccion.setFiles({ name: 'clic.png', mimeType: 'image/png', buffer: PNG });
  await expect(page.locator('.board-free-media')).toHaveCount(1);
  expect(await clics()).toBe(1);

  await reiniciar();
  await page.keyboard.press('n');
  await page.getByRole('option', { name: /^Enlace/ }).click();
  const dialogo = page.getByRole('dialog', { name: 'Añadir enlace' });
  await dialogo.getByLabel('Dirección web').fill('https://example.com');
  await dialogo.getByRole('button', { name: 'Agregar enlace' }).click();
  await expect(page.locator('.board-card[data-card-type="link"]')).toHaveCount(1);
  expect(await clics()).toBe(2);

  await reiniciar();
  await page.keyboard.press('n');
  await page.getByLabel('Buscar herramienta').fill('Columna');
  await page.getByRole('option', { name: /^Columna/ }).click();
  await expect(page.locator('.board-column')).toHaveCount(1);
  expect(await clics()).toBe(1);

  await reiniciar();
  await page.keyboard.press('n');
  await page.getByLabel('Buscar herramienta').fill('Marco');
  await page.getByRole('option', { name: /^Marco/ }).click();
  await expect(page.locator('.board-frame')).toHaveCount(1);
  expect(await clics()).toBe(1);
});

test('I5 · arrastrar una herramienta desde la biblioteca la suelta donde se suelta', async ({ page }) => {
  await abrirTableroSembrado(page, tablero([], 'board-super4-biblioteca-drag', 'Arrastrar'));
  await page.keyboard.press('n');
  const destino = await page.locator('.board-viewport').boundingBox();
  if (!destino) throw new Error('Sin lienzo');
  await page.evaluate(({ x, y }) => {
    const datos = new DataTransfer();
    datos.setData('application/x-prometeo-tool', 'note');
    const fondo = document.querySelector('.board-add-backdrop');
    fondo?.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: datos, clientX: x, clientY: y }));
  }, { x: destino.x + 420, y: destino.y + 260 });
  await expect(page.locator('.board-card[data-card-type="note"]')).toHaveCount(1);
  const caja = await page.locator('.board-card[data-card-type="note"]').boundingBox();
  expect(Math.abs((caja?.x ?? 0) + (caja?.width ?? 0) / 2 - (destino.x + 420))).toBeLessThan(220);
});
