import { expect, test } from '@playwright/test';
import { abrirTablero, abrirTableroCon, marco, tarjeta } from './helpers';

const CARDS = [
  tarjeta({ id: 'n1', type: 'note', title: 'Nota', body: 'Texto inicial', x: 80, y: 80, width: 280 }),
  tarjeta({
    id: 'r1', type: 'referente', title: 'Irene Guerra', x: 420, y: 80, width: 320,
    datos: {
      nombre: 'Irene Guerra', url: 'https://ireneguerra.xyz', archivoOrigen: 'portfolio', anio: '2026',
      autor: 'Irene Guerra', licencia: '©', porQue: 'Una jerarquía seca.', etiquetas: ['tipografía'],
      vistoEn: ['2026-10-24'], imagenes: [], lecturas: [],
    },
  }),
  marco('f1', 80, 420, { title: 'Marco inicial', width: 520, datos: { alto: 360, hijos: [], vista: 'libre' } }),
];

test('F5 · doble clic edita en el sitio, Enter/clic fuera guarda y Escape cancela', async ({ page }) => {
  await abrirTableroCon(page, CARDS);
  await page.waitForTimeout(500);

  await page.locator('.board-frame-title').dblclick();
  const tituloMarco = page.locator('input.board-frame-title.board-inline-input');
  await expect(tituloMarco).toBeVisible();
  await tituloMarco.fill('Marco editado');
  await tituloMarco.press('Enter');
  await expect(page.locator('.board-frame-title')).toHaveText('Marco editado');

  await page.locator('.board-referente-nombre').dblclick();
  const tituloReferente = page.locator('input.board-referente-nombre.board-inline-input');
  await expect(tituloReferente).toBeVisible();
  await tituloReferente.fill('Referente editado');
  await tituloReferente.press('Enter');
  await expect(page.locator('.board-referente-nombre')).toHaveText('Referente editado');

  const cuerpo = page.locator('[data-card-id="n1"] .board-card-text');
  await cuerpo.dblclick();
  const editor = page.locator('[data-card-id="n1"] .board-card-text-editor');
  await expect(editor).toBeVisible();
  await editor.fill('Nota guardada');
  await page.keyboard.type('n');
  await expect(page.locator('.board-add-backdrop')).toHaveCount(0);
  await editor.fill('Nota guardada');
  await editor.press('Enter');
  await expect(cuerpo).toHaveText('Nota guardada');

  await cuerpo.dblclick();
  await editor.fill('No debe quedar');
  await editor.press('Escape');
  await expect(cuerpo).toHaveText('Nota guardada');

  await cuerpo.dblclick();
  await editor.fill('Nota por clic fuera');
  await page.locator('.board-viewport').click({ position: { x: 1100, y: 600 } });
  await expect(cuerpo).toHaveText('Nota por clic fuera');

  await page.getByTestId('board-topbar').getByRole('button', { name: 'Deshacer' }).click();
  await expect(cuerpo).toHaveText('Nota guardada');
  await page.getByTestId('board-topbar').getByRole('button', { name: 'Rehacer' }).click();
  await expect(cuerpo).toHaveText('Nota por clic fuera');

  const pista = page.locator('.board-referente-hint');
  await expect(pista).toHaveCSS('opacity', '0');
  await page.locator('[data-card-id="r1"]').hover();
  await expect(pista).toHaveCSS('opacity', '1');

  await page.waitForTimeout(600);
  await page.reload();
  await abrirTablero(page);
  await expect(page.locator('.board-frame-title')).toHaveText('Marco editado');
  await expect(page.locator('.board-referente-nombre')).toHaveText('Referente editado');
  await expect(page.locator('[data-card-id="n1"] .board-card-text')).toHaveText('Nota por clic fuera');
});
