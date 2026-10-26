/**
 * I2 · mover desde cualquier parte y mover toda la selección.
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, leerTablero, mockReadyBackend, nota, tablero } from './helpers';

test.beforeEach(async ({ page }) => {
  await mockReadyBackend(page);
});

test('I2 · arrastrar desde el cuerpo mueve; doble clic escribe; la selección se mueve junta', async ({ page }) => {
  const board = tablero([
    nota('n1', 160, 180, 'Primera', 'cuerpo de la primera nota'),
    nota('n2', 520, 180, 'Segunda', 'cuerpo de la segunda nota'),
    nota('n3', 160, 430, 'Tercera', 'cuerpo de la tercera nota'),
  ], 'board-super4-mover', 'Mover');
  await abrirTableroSembrado(page, board);

  const n1 = page.locator('[data-card-id="n1"]');
  const caja = await n1.boundingBox();
  if (!caja) throw new Error('Sin caja para n1');
  const centro = { x: caja.x + caja.width / 2, y: caja.y + caja.height / 2 };
  await page.mouse.move(centro.x, centro.y);
  await page.mouse.down();
  await page.mouse.move(centro.x + 90, centro.y + 55, { steps: 8 });
  await page.mouse.up();

  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-super4-mover');
    return guardado?.cards.find((card) => card.id === 'n1')?.x ?? 0;
  }).toBeGreaterThan(200);

  // Doble clic en el cuerpo entra a escribir (no mueve).
  await n1.locator('.board-note-read').dblclick();
  const editor = n1.locator('.board-card-text-editor');
  await expect(editor).toBeVisible();
  await expect(editor).toBeFocused();
  await editor.press('Escape');

  // La selección de tres se mueve al arrastrar una de ellas.
  await n1.click();
  await page.keyboard.press('Meta+a');
  await expect(page.locator('.board-card.selected')).toHaveCount(3);
  const antes = await leerTablero(page, 'board-super4-mover');
  const caja2 = await n1.boundingBox();
  if (!caja2) throw new Error('Sin caja para n1 tras seleccionar');
  await page.mouse.move(caja2.x + caja2.width / 2, caja2.y + caja2.height / 2);
  await page.mouse.down();
  await page.mouse.move(caja2.x + caja2.width / 2 + 60, caja2.y + caja2.height / 2 + 30, { steps: 8 });
  await page.mouse.up();

  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-super4-mover');
    const desplazados = ['n1', 'n2', 'n3'].filter((id) => {
      const a = antes?.cards.find((card) => card.id === id);
      const b = guardado?.cards.find((card) => card.id === id);
      return a && b && (Math.abs(b.x - a.x) > 20 || Math.abs(b.y - a.y) > 20);
    });
    return desplazados.length;
  }).toBe(3);
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.screenshot({ path: path.join(CAPTURAS, 'I2-despues-mover-seleccion.png') });
});
