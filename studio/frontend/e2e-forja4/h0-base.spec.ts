/**
 * H0 · suite en verde y contrato visual del lienzo.
 * La captura «antes» reproduce el recorte de `contain: paint` que R-10 destapó:
 * una tarjeta en coordenadas locales negativas se pintaba solo a medias.
 */
import { expect, test } from '@playwright/test';
import { CAPTURAS, mockReadyBackend, openBoard } from './helpers';
import fs from 'node:fs';
import path from 'node:path';

test('H0: una tarjeta en coordenadas negativas se pinta entera', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  await mockReadyBackend(page);
  await page.goto('/');
  await openBoard(page);
  await page.getByRole('button', { name: 'Nueva nota' }).click();
  await expect(page.locator('.board-card')).toHaveCount(1);

  // Antes: el `contain: paint` del escenario recortaba la pieza.
  await page.addStyleTag({ content: '.board-stage { contain: layout style paint !important; }' });
  await page.waitForTimeout(150);
  await page.screenshot({ path: path.join(CAPTURAS, 'H0-antes-tarjeta-recortada.png') });
  await page.addStyleTag({ content: '.board-stage { contain: layout style !important; }' });

  const card = page.locator('.board-card');
  const box = await card.boundingBox();
  if (!box) throw new Error('La tarjeta no tiene caja.');
  const hit = await page.evaluate(({ x, y }) => {
    const element = document.elementFromPoint(x, y);
    return element?.closest('.board-card') !== null;
  }, { x: box.x + 8, y: box.y + 8 });
  expect(hit).toBe(true);
  await page.screenshot({ path: path.join(CAPTURAS, 'H0-despues-tarjeta-entera.png') });
});
