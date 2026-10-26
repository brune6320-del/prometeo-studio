/**
 * I4 · el engranaje de cada tarjeta: cambios en vivo y sin «Aplicar».
 */
import { expect, test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, mockReadyBackend, nota, tablero } from './helpers';

/**
 * Los range se mueven con el teclado: es el gesto real y no depende del value
 * tracker de React. Home lleva al mínimo; cada flecha suma un paso.
 */
async function moverRango(locator: import('@playwright/test').Locator, pasos: number) {
  await locator.focus();
  await locator.press('Home');
  for (let i = 0; i < pasos; i += 1) await locator.press('ArrowRight');
}

test.beforeEach(async ({ page }) => {
  await mockReadyBackend(page);
});

test('I4 · el engranaje edita la tarjeta en vivo y convierte el tipo', async ({ page }) => {
  await abrirTableroSembrado(page, tablero([nota('n1', 200, 200, 'Ajustable', 'texto')], 'board-super4-ajustes', 'Ajustes'));
  const tarjeta = page.locator('[data-card-id="n1"]');
  await tarjeta.click();
  const engranaje = tarjeta.getByRole('button', { name: /Ajustes de/ });
  await expect(engranaje).toBeVisible();
  await engranaje.click();
  const panel = page.getByRole('dialog', { name: 'Ajustes de la tarjeta' });
  await expect(panel).toBeVisible();
  await expect(panel.getByRole('button', { name: /Aplicar/ })).toHaveCount(0);

  await moverRango(panel.locator('label').filter({ hasText: 'Opacidad' }).locator('input[type="range"]'), 8);
  await expect(tarjeta).toHaveCSS('opacity', '0.5');
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await page.screenshot({ path: path.join(CAPTURAS, 'I4-despues-ajustes.png') });

  await moverRango(panel.locator('label').filter({ hasText: 'Tamaño de texto' }).locator('input[type="range"]'), 18);
  await expect(tarjeta).toHaveCSS('font-size', '28px');

  await panel.getByLabel('Convertir en').selectOption('columna');
  await expect(page.locator('[data-card-id="n1"].board-column')).toBeVisible();
});

test('I4 · con varias seleccionadas el engranaje edita todas', async ({ page }) => {
  await abrirTableroSembrado(page, tablero([
    nota('n1', 160, 180, 'Una', 'texto'),
    nota('n2', 520, 180, 'Dos', 'texto'),
  ], 'board-super4-ajustes-multi', 'Ajustes múltiples'));
  await page.locator('[data-card-id="n1"]').click();
  await page.locator('[data-card-id="n2"]').click({ modifiers: ['Shift'] });
  await expect(page.locator('.board-card.selected')).toHaveCount(2);
  await page.locator('[data-card-id="n1"]').getByRole('button', { name: /Ajustes de/ }).click();
  const panel = page.getByRole('dialog', { name: 'Ajustes de la tarjeta' });
  await expect(panel).toContainText('2 tarjetas');
  await moverRango(panel.locator('label').filter({ hasText: 'Opacidad' }).locator('input[type="range"]'), 6);
  await expect(page.locator('[data-card-id="n1"]')).toHaveCSS('opacity', '0.4');
  await expect(page.locator('[data-card-id="n2"]')).toHaveCSS('opacity', '0.4');
});
