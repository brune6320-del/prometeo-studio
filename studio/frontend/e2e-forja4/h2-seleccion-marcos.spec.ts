/**
 * H2 · selección que reemplaza, marcos que contienen y desagrupan.
 * Top 4 y 6 de A-1; debates D1 y D2; reglas 13 y 14.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, leerTablero, mockReadyBackend, nota, tablero, type SeedCard } from './helpers';

async function marquesina(page: Page, desde: { x: number; y: number }, hasta: { x: number; y: number }, teclas: string[] = []) {
  for (const tecla of teclas) await page.keyboard.down(tecla);
  await page.mouse.move(desde.x, desde.y);
  await page.mouse.down();
  await page.mouse.move(hasta.x, hasta.y, { steps: 12 });
  await page.mouse.up();
  for (const tecla of [...teclas].reverse()) await page.keyboard.up(tecla);
}

function marco(id: string, x: number, y: number, hijos: string[], extra: Partial<SeedCard> = {}): SeedCard {
  return {
    id,
    type: 'marco',
    title: id,
    body: '',
    x,
    y,
    width: 520,
    color: 'paper',
    datos: { alto: 360, hijos, vista: 'libre' },
    ...extra,
  };
}

test('H2 · la marquesina reemplaza, ⇧ suma y ⌥ resta; ⇧+clic alterna', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  const board = tablero([
    nota('a', 120, 120, 'A'),
    nota('b', 660, 120, 'B'),
  ], 'board-h2-sel', 'Selección');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  const a = page.locator('[data-card-id="a"]');
  const b = page.locator('[data-card-id="b"]');
  const cajaB = await b.boundingBox();
  if (!cajaB) throw new Error('Sin caja para B.');

  // A seleccionada + marquesina sobre B = solo B.
  await a.click();
  await expect(page.locator('[data-card-id].selected')).toHaveCount(1);
  await marquesina(page, { x: cajaB.x - 24, y: cajaB.y - 24 }, { x: cajaB.x + cajaB.width + 16, y: cajaB.y + cajaB.height + 16 });
  await expect(page.locator('[data-card-id].selected')).toHaveCount(1);
  await expect(b).toHaveClass(/selected/);
  await expect(a).not.toHaveClass(/selected/);
  await page.screenshot({ path: path.join(CAPTURAS, 'H2-antes-marquesina-suma.png') });

  // ⇧+clic alterna: quita B, vuelve a ponerla.
  await b.click({ modifiers: ['Shift'] });
  await expect(page.locator('[data-card-id].selected')).toHaveCount(0);
  await b.click({ modifiers: ['Shift'] });
  await expect(page.locator('[data-card-id].selected')).toHaveCount(1);
  await a.click({ modifiers: ['Shift'] });
  await expect(page.locator('[data-card-id].selected')).toHaveCount(2);

  // ⌥ + marquesina resta B y deja A.
  await marquesina(page, { x: cajaB.x - 24, y: cajaB.y - 24 }, { x: cajaB.x + cajaB.width + 16, y: cajaB.y + cajaB.height + 16 }, ['Alt']);
  await expect(page.locator('[data-card-id].selected')).toHaveCount(1);
  await expect(a).toHaveClass(/selected/);
  await page.screenshot({ path: path.join(CAPTURAS, 'H2-despues-seleccion-contrato.png') });
});

test('H2 · sacar un hijo lo desvincula, ⌘G agrupa y ⌘⇧G desagrupa sin mover', async ({ page }) => {
  const n1 = nota('n1', 260, 240, 'Hija uno');
  const n2 = nota('n2', 300, 520, 'Hija dos');
  const board = tablero([marco('f1', 200, 200, ['n1']), n1, n2], 'board-h2-marco', 'Marcos');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  const viewport = await page.locator('.board-viewport').boundingBox();
  const hija = await page.locator('[data-card-id="n1"] .board-card-head').boundingBox();
  if (!viewport || !hija) throw new Error('Sin cajas para arrastrar.');

  // Arrastrar la hija al vacío: `hijos` deja de contenerla en el mismo gesto.
  await page.mouse.move(hija.x + 20, hija.y + 10);
  await page.mouse.down();
  await page.mouse.move(viewport.x + viewport.width - 120, viewport.y + viewport.height - 100, { steps: 16 });
  await page.mouse.up();
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h2-marco');
    const frame = guardado?.cards.find((card) => card.id === 'f1');
    return (frame?.datos as { hijos?: string[] } | undefined)?.hijos ?? [];
  }).not.toContain('n1');

  // Un solo ⌘Z devuelve el arrastre y la adopción anterior.
  await page.keyboard.press('Meta+z');
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h2-marco');
    const frame = guardado?.cards.find((card) => card.id === 'f1');
    return (frame?.datos as { hijos?: string[] } | undefined)?.hijos ?? [];
  }).toContain('n1');

  // ⌘G agrupa n1 y n2 sin moverlas.
  const posiciones = await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>('[data-card-id]')).map((el) => ({ id: el.dataset.cardId, left: el.style.left, top: el.style.top })));
  await page.locator('[data-card-id="n1"]').click();
  await page.locator('[data-card-id="n2"]').click({ modifiers: ['Shift'] });
  await page.keyboard.press('Meta+g');
  await expect(page.locator('.board-frame')).toHaveCount(2);
  await expect.poll(async () => {
    const trasAgrupar = await leerTablero(page, 'board-h2-marco');
    const grupo = trasAgrupar?.cards.find((card) => card.title === 'Grupo');
    return (grupo?.datos as { hijos?: string[] } | undefined)?.hijos ?? [];
  }).toEqual(expect.arrayContaining(['n1', 'n2']));
  const trasAgrupar = await leerTablero(page, 'board-h2-marco');
  const grupo = trasAgrupar?.cards.find((card) => card.title === 'Grupo');
  expect((grupo?.datos as { hijos?: string[] } | undefined)?.hijos).toEqual(expect.arrayContaining(['n1', 'n2']));
  const posicionesDespues = await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>('[data-card-id]')).map((el) => ({ id: el.dataset.cardId, left: el.style.left, top: el.style.top })));
  expect(posicionesDespues.filter((item) => item.id === 'n1' || item.id === 'n2')).toEqual(posiciones.filter((item) => item.id === 'n1' || item.id === 'n2'));

  // ⌘⇧G quita el marco y deja las posiciones intactas.
  await page.locator('.board-frame').last().locator('.board-frame-head').click({ position: { x: 40, y: 8 } });
  await page.keyboard.press('Meta+Shift+g');
  await expect.poll(async () => (await leerTablero(page, 'board-h2-marco'))?.cards.some((card) => card.title === 'Grupo')).toBe(false);
  const posicionesFinales = await page.evaluate(() => Array.from(document.querySelectorAll<HTMLElement>('[data-card-id]')).map((el) => ({ id: el.dataset.cardId, left: el.style.left, top: el.style.top })));
  expect(posicionesFinales.filter((item) => item.id === 'n1' || item.id === 'n2')).toEqual(posiciones.filter((item) => item.id === 'n1' || item.id === 'n2'));

  // El marco tiene candado y cambiar de vista no mueve nada.
  await page.locator('.board-frame').first().locator('.board-frame-head').click({ position: { x: 40, y: 8 } });
  await page.getByRole('button', { name: 'Bloquear marco' }).click();
  await expect(page.locator('.board-frame').first()).toHaveClass(/is-locked/);
  await expect(page.getByRole('button', { name: 'Eliminar marco' })).toBeDisabled();
  const antesVista = await leerTablero(page, 'board-h2-marco');
  await page.getByLabel(/Ver como/).first().selectOption('archivo');
  const despuesVista = await leerTablero(page, 'board-h2-marco');
  expect(despuesVista?.cards.map((card) => [card.id, card.x, card.y])).toEqual(antesVista?.cards.map((card) => [card.id, card.x, card.y]));
});
