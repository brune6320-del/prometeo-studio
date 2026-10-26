/**
 * I6 · guías casi invisibles por defecto y tablero configurable por tablero.
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, mockReadyBackend, nota, tablero } from './helpers';

test.beforeEach(async ({ page }) => {
  await mockReadyBackend(page);
});

async function arrastrarParaGuia(page: import('@playwright/test').Page) {
  const a = page.locator('[data-card-id="a"]');
  const b = page.locator('[data-card-id="b"]');
  const cajaA = await a.boundingBox();
  const cajaB = await b.boundingBox();
  if (!cajaA || !cajaB) throw new Error('Sin cajas');
  await page.mouse.move(cajaA.x + cajaA.width / 2, cajaA.y + cajaA.height / 2);
  await page.mouse.down();
  await page.mouse.move(cajaA.x + cajaA.width / 2 + (cajaB.x - cajaA.x), cajaA.y + cajaA.height / 2 + 80, { steps: 12 });
}

test('I6 · guías sutiles, apagables, y fondo/cursor guardados por tablero', async ({ page }) => {
  await abrirTableroSembrado(page, tablero([
    nota('a', 160, 180, 'A'),
    nota('b', 552, 180, 'B'),
  ], 'board-super4-guias', 'Guías'));

  await arrastrarParaGuia(page);
  const guia = page.locator('[data-testid="board-guide-x"]');
  await expect(guia).toBeVisible();
  await expect(guia).toHaveCSS('opacity', '0.25');
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.mouse.up();

  await page.getByRole('button', { name: 'Ajustes de este tablero' }).click();
  const panel = page.getByRole('dialog', { name: 'Este tablero' });
  await expect(panel).toBeVisible();
  await panel.getByLabel('Guías de alineación').selectOption('apagadas');

  await arrastrarParaGuia(page);
  await expect(page.locator('[data-testid="board-guide-x"]')).toHaveCount(0);
  await page.mouse.up();

  await panel.getByLabel('Color del fondo').evaluate((elemento) => {
    const input = elemento as HTMLInputElement;
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set;
    setter?.call(input, '#223344');
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
  await expect(page.locator('.board-viewport')).toHaveCSS('background-color', 'rgb(34, 51, 68)');
  await panel.getByLabel('Cursor sobre el lienzo').selectOption('mano');
  await page.screenshot({ path: path.join(CAPTURAS, 'I6-despues-tablero.png') });
  await expect(page.locator('.board-viewport')).toHaveClass(/cursor-mano/);

  await page.waitForTimeout(700);
  await page.reload();
  await page.getByRole('button', { name: 'Tablero' }).click();
  await expect(page.locator('.board-workspace')).toBeVisible();
  await expect(page.locator('.board-viewport')).toHaveCSS('background-color', 'rgb(34, 51, 68)');
  await page.getByRole('button', { name: 'Ajustes de este tablero' }).click();
  await expect(page.getByRole('dialog', { name: 'Este tablero' }).getByLabel('Guías de alineación')).toHaveValue('apagadas');
});
