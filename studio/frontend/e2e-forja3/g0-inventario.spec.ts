import { expect, test } from '@playwright/test';
import { abrirTableroCon, capturar, marco, tarjeta } from './helpers';

test('G0 · captura de referencia del tablero actual', async ({ page }) => {
  await abrirTableroCon(page, [
    tarjeta({ id: 'g0-nota', type: 'note', title: 'Una idea que se queda', body: 'El tablero tiene que parecer un taller, no un panel.', x: 120, y: 120, width: 300 }),
    tarjeta({ id: 'g0-enlace', type: 'link', title: 'Referente', body: 'Una fuente para volver.', url: 'https://example.com', x: 460, y: 140, width: 280, color: 'sand' }),
    marco('g0-marco', 800, 120, { title: 'Marco de trabajo', datos: { alto: 360, hijos: [], vista: 'libre' } }),
  ]);
  await page.waitForTimeout(400);
  await expect(page.locator('.board-card').first()).toBeVisible();
  await capturar(page, '../../REPORTES/capturas-forja3/g0-antes.png');
  await capturar(page, '../../REPORTES/capturas-forja3/g0-despues.png');
});
