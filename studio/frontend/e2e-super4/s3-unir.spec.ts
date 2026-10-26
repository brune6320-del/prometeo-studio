/**
 * I3 · unir con un gesto: puntos en el borde, arrastre y vacío sin relación.
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, leerTablero, mockReadyBackend, nota, tablero } from './helpers';

test.beforeEach(async ({ page }) => {
  await mockReadyBackend(page);
});

test('I3 · los puntos aparecen al borde, arrastrar une y Cmd+Z lo deshace', async ({ page }) => {
  const board = tablero([
    nota('a', 160, 180, 'Origen'),
    nota('b', 560, 180, 'Destino'),
  ], 'board-super4-unir', 'Unir');
  await abrirTableroSembrado(page, board);

  const a = page.locator('[data-card-id="a"]');
  const b = page.locator('[data-card-id="b"]');
  const cajaA = await a.boundingBox();
  const cajaB = await b.boundingBox();
  if (!cajaA || !cajaB) throw new Error('Sin cajas');

  // A 12 px del borde derecho aparecen los cuatro puntos, con su pulso.
  await page.mouse.move(cajaA.x + cajaA.width - 2, cajaA.y + cajaA.height / 2);
  const punto = a.locator('.board-connect-dot.dot-e');
  await expect(punto).toHaveCSS('opacity', '1');
  await expect(a.locator('.board-connect-dot')).toHaveCount(4);
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.screenshot({ path: path.join(CAPTURAS, 'I3-antes-arrastrar-punto.png') });

  const cajaPunto = await punto.boundingBox();
  if (!cajaPunto) throw new Error('Sin punto de unión');
  await page.mouse.move(cajaPunto.x + cajaPunto.width / 2, cajaPunto.y + cajaPunto.height / 2);
  await page.mouse.down();
  await page.mouse.move(cajaB.x + cajaB.width / 2, cajaB.y + cajaB.height / 2, { steps: 12 });
  await page.mouse.up();

  await expect.poll(async () => (await leerTablero(page, 'board-super4-unir'))?.relations?.length ?? 0).toBe(1);
  await page.screenshot({ path: path.join(CAPTURAS, 'I3-despues-union.png') });

  await page.keyboard.press('Meta+z');
  await expect.poll(async () => (await leerTablero(page, 'board-super4-unir'))?.relations?.length ?? 0).toBe(0);

  // Soltar en el vacío no crea nada.
  await page.mouse.move(cajaA.x + cajaA.width - 2, cajaA.y + cajaA.height / 2);
  const punto2 = await a.locator('.board-connect-dot.dot-e').boundingBox();
  if (!punto2) throw new Error('Sin punto de unión (2)');
  await page.mouse.move(punto2.x + punto2.width / 2, punto2.y + punto2.height / 2);
  await page.mouse.down();
  await page.mouse.move(cajaA.x + 60, cajaA.y + cajaA.height + 180, { steps: 10 });
  await page.mouse.up();
  await page.waitForTimeout(300);
  expect((await leerTablero(page, 'board-super4-unir'))?.relations?.length ?? 0).toBe(0);
});
