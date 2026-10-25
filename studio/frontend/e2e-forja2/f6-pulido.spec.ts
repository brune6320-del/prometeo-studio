import { expect, test } from '@playwright/test';
import { abrirTableroCon, marco, tarjeta } from './helpers';

const CARDS = [
  tarjeta({ id: 'n1', type: 'note', title: 'Nota', body: 'Texto', x: 80, y: 80, width: 280 }),
  tarjeta({
    id: 'r1', type: 'referente', title: 'Referente', x: 420, y: 80, width: 320,
    datos: { nombre: 'Referente', url: '', archivoOrigen: 'archivo', anio: '2026', autor: '', licencia: '', porQue: '', etiquetas: [], vistoEn: [], imagenes: [], lecturas: [] },
  }),
  marco('f1', 80, 440, { title: 'Marco', width: 520, datos: { alto: 320, hijos: [], vista: 'libre' } }),
];

test('F6 · estados con tokens, chrome discreto, foco y reduced-motion', async ({ page }) => {
  await abrirTableroCon(page, CARDS);
  await page.waitForTimeout(500);

  const marcoEl = page.locator('.board-frame');
  const estiloMarco = await marcoEl.evaluate((el) => {
    const s = getComputedStyle(el);
    return { fondo: s.backgroundColor, borde: s.borderTopColor };
  });
  expect(estiloMarco.fondo).toBe('rgba(0, 0, 0, 0)');
  expect(estiloMarco.borde).toBe('rgb(44, 44, 51)');
  await expect(page.locator('.board-frame-view')).toHaveCSS('opacity', '0');
  await marcoEl.hover();
  await expect(page.locator('.board-frame-view')).toHaveCSS('opacity', '1');

  const nota = page.locator('[data-card-id="n1"]');
  await expect(nota.locator('.board-card-delete')).toHaveCSS('opacity', '0');
  await expect(nota.locator('.board-card-color-row')).toHaveCSS('opacity', '0');
  await expect(nota.locator('.board-drag-grip')).toHaveCSS('opacity', '0.25');
  await nota.hover();
  await expect(nota.locator('.board-card-color-row')).toHaveCSS('opacity', '1');
  await expect(nota.locator('.board-card-delete')).toHaveCSS('opacity', '0.75');

  await nota.click({ position: { x: 30, y: 24 } });
  await expect(nota).toHaveClass(/selected/);
  await expect(nota).toHaveCSS('outline-style', 'solid');
  await expect(nota).toHaveCSS('outline-color', 'rgb(255, 138, 82)');

  const otra = page.locator('[data-card-id="r1"]');
  await page.locator('.board-viewport').click({ position: { x: 1100, y: 600 } });
  for (let i = 0; i < 80; i += 1) {
    await page.keyboard.press('Tab');
    const activo = await page.evaluate(() => document.activeElement?.getAttribute('data-card-id'));
    if (activo === 'r1') break;
  }
  await page.waitForTimeout(250);
  const foco = await otra.evaluate((el) => ({
    visible: el.matches(':focus-visible'),
    contorno: getComputedStyle(el).outlineStyle,
    sombra: getComputedStyle(el).boxShadow,
  }));
  expect(foco.visible).toBe(true);
  expect(foco.contorno).toBe('none');
  expect(foco.sombra).toContain('rgb(255, 138, 82)');

  await expect(page.locator('[data-card-type="referente"] .board-card-title')).toBeHidden();
  await expect(page.locator('.board-referente-noimg')).toBeVisible();

  await page.getByTestId('board-topbar').getByRole('button', { name: /Exportar/ }).click();
  const menu = page.locator('.board-menu');
  await expect(menu).toBeVisible();
  expect(await menu.evaluate((el) => getComputedStyle(el).animationName)).toBe('board-entrada-suave');
  await page.keyboard.press('Escape');

  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.getByTestId('board-topbar').getByRole('button', { name: /Exportar/ }).click();
  expect(await page.locator('.board-menu').evaluate((el) => getComputedStyle(el).animationName)).toBe('none');
});
