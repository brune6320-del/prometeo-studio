/**
 * T-4 · el escenario no puede recortar las tarjetas que salen de su caja.
 *
 * T-3 había dejado `contain: paint` + `will-change` en `.board-stage`: el DOM
 * tenía las 500 tarjetas, pero solo se pintaban las primeras columnas. Contar
 * nodos no lo detectaba; esta prueba pregunta al navegador qué hay en el píxel
 * de una tarjeta del extremo del tablero.
 */
import { expect, test } from '@playwright/test';
import { abrirTableroSembrado, mockReadyBackend, nota, tablero } from './helpers';

test('T-4 · una tarjeta del extremo del tablero se pinta dentro del viewport', async ({ page }) => {
  const cartas = Array.from({ length: 500 }, (_, indice) => nota(
    `n${indice}`,
    (indice % 25) * 280,
    Math.floor(indice / 25) * 210,
    `Tarjeta ${indice}`,
    `cuerpo ${indice}`,
  ));
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, tablero(cartas, 'board-t4-escenario', 'Escenario 500'));
  await expect(page.locator('[data-card-id]')).toHaveCount(500);

  const pintada = await page.evaluate(() => {
    const card = document.querySelector<HTMLElement>('[data-card-id="n24"]');
    if (!card) return { ok: false, motivo: 'sin tarjeta' };
    const rect = card.getBoundingClientRect();
    const x = rect.x + rect.width / 2;
    const y = rect.y + rect.height / 2;
    if (x < 0 || y < 0 || x > window.innerWidth || y > window.innerHeight) return { ok: false, motivo: `fuera de pantalla ${x},${y}` };
    const arriba = document.elementFromPoint(x, y);
    return { ok: arriba === card || card.contains(arriba), motivo: arriba?.className ?? 'nada', x, y };
  });

  expect(pintada.ok, `n24 no se pinta en ${pintada.x},${pintada.y}: ${pintada.motivo}`).toBe(true);
});
