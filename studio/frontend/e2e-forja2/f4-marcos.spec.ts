import { expect, test, type Page } from '@playwright/test';
import { abrirTableroCon, marco, tarjeta } from './helpers';

const HIJOS = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6'];

function tablero() {
  const hijos = HIJOS.map((id, i) => tarjeta({
    id,
    type: 'note',
    title: `Hija ${i + 1}`,
    body: 'Dentro del marco.',
    x: 140 + (i % 3) * 150,
    y: 150 + Math.floor(i / 3) * 150,
    width: 120,
  }));
  return [
    marco('f1', 100, 100, { title: 'Marco con seis', width: 500, datos: { alto: 400, hijos: HIJOS, vista: 'libre' } }),
    ...hijos,
    tarjeta({ id: 'fuera', type: 'note', title: 'Fuera del marco', x: 620, y: 160, width: 120 }),
    tarjeta({ id: 'suelta', type: 'note', title: 'Para soltar', x: 900, y: 650, width: 140 }),
  ];
}

async function cajaDe(page: Page, selector: string) {
  const caja = await page.locator(selector).first().boundingBox();
  if (!caja) throw new Error(`Sin caja para ${selector}`);
  return caja;
}

test('F4 · mover el marco mueve sus 6 hijas, Deshacer lo devuelve y redimensionar recalcula', async ({ page }) => {
  await abrirTableroCon(page, tablero());
  await page.waitForTimeout(400);

  const cabecera = await cajaDe(page, '.board-frame-head');
  const marcoAntes = await cajaDe(page, '.board-frame');
  const hija = await cajaDe(page, '[data-card-id="h1"]');
  await page.mouse.move(cabecera.x + 12, cabecera.y + 12);
  await page.mouse.down();
  for (let i = 1; i <= 12; i += 1) await page.mouse.move(cabecera.x + 12 + (300 * i) / 12, cabecera.y + 12);
  await page.mouse.up();
  await page.waitForTimeout(320);

  const marcoMovido = await cajaDe(page, '.board-frame');
  const hijaMovida = await cajaDe(page, '[data-card-id="h1"]');
  expect(Math.abs((marcoMovido.x - marcoAntes.x) - 300)).toBeLessThan(2);
  expect(Math.abs((hija.x + 300) - hijaMovida.x)).toBeLessThan(2);
  expect(Math.abs((hija.x + 300) - hijaMovida.x)).toBeLessThan(2);
  expect(Math.abs((hija.y) - hijaMovida.y)).toBeLessThan(2);

  await page.getByTestId('board-topbar').getByRole('button', { name: 'Deshacer' }).click();
  await page.waitForTimeout(250);
  const hijaDeshecha = await cajaDe(page, '[data-card-id="h1"]');
  expect(Math.abs(hijaDeshecha.x - hija.x)).toBeLessThan(2);
  expect(Math.abs(hijaDeshecha.y - hija.y)).toBeLessThan(2);

  const antesResize = await cajaDe(page, '.board-frame');
  const handle = await cajaDe(page, '.board-frame-resize');
  await page.mouse.move(handle.x + handle.width / 2, handle.y + handle.height / 2);
  await page.mouse.down();
  for (let i = 1; i <= 12; i += 1) await page.mouse.move(handle.x + handle.width / 2 + (250 * i) / 12, handle.y + handle.height / 2 + (40 * i) / 12);
  await page.mouse.up();
  await page.waitForTimeout(320);
  const despuesResize = await cajaDe(page, '.board-frame');
  expect(despuesResize.width).toBeGreaterThan(antesResize.width + 200);
  await expect(page.locator('.board-frame-meta')).toHaveText(/7 tarjetas dentro/);

  const suelta = await cajaDe(page, '[data-card-id="suelta"]');
  const destino = await cajaDe(page, '.board-frame');
  await page.mouse.move(suelta.x + 12, suelta.y + 12);
  await page.mouse.down();
  for (let i = 1; i <= 12; i += 1) {
    await page.mouse.move(
      suelta.x + 12 + ((destino.x + destino.width / 2) - (suelta.x + 12)) * (i / 12),
      suelta.y + 12 + ((destino.y + destino.height / 2) - (suelta.y + 12)) * (i / 12),
    );
  }
  await expect(page.locator('.board-card.dragging')).toHaveCount(1);
  await expect(page.locator('.board-frame.drop-target')).toHaveCount(1);
  await page.mouse.up();
  await page.waitForTimeout(100);
  await expect(page.locator('.board-frame-meta')).toHaveText(/8 tarjetas dentro/);
});
