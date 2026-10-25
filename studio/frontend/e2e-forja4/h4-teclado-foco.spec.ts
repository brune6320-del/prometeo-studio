/**
 * H4 · teclado y foco.
 * Top 3 de A-1; debate D6; regla 15. Tab entra, Alt+flechas navegan,
 * Enter selecciona, Esc sale y los diálogos atrapan y devuelven el foco.
 */
import { expect, test, type Page } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { CAPTURAS, abrirTableroSembrado, leerTablero, mockReadyBackend, nota, tablero, type SeedCard } from './helpers';

function marco(id: string, x: number, y: number, hijos: string[] = []): SeedCard {
  return { id, type: 'marco', title: id, body: '', x, y, width: 420, color: 'paper', datos: { alto: 300, hijos, vista: 'libre' } };
}

function columna(id: string, x: number, y: number, hijos: string[] = []): SeedCard {
  return { id, type: 'columna', title: id, body: '', x, y, width: 300, color: 'paper', datos: { hijos, plegada: false } };
}

test('H4 · Tab entra, Alt+flechas navegan, Enter selecciona y Esc sale', async ({ page }) => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
  const board = tablero([
    nota('a', 100, 100, 'A'),
    nota('b', 520, 100, 'B'),
    nota('c', 940, 100, 'C'),
    marco('f1', 100, 480),
    columna('col1', 620, 480),
  ], 'board-h4', 'Teclado');
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, board);
  await page.screenshot({ path: path.join(CAPTURAS, 'H4-antes-teclado.png') });

  const activo = () => page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    return { tag: element?.tagName ?? null, cardId: element?.closest<HTMLElement>('[data-card-id]')?.dataset.cardId ?? null };
  });

  await page.locator('.board-viewport').focus();
  await page.keyboard.press('Tab');
  expect((await activo()).cardId).toBe('a');

  await page.keyboard.press('Alt+ArrowRight');
  expect((await activo()).cardId).toBe('b');
  await page.keyboard.press('Alt+ArrowRight');
  expect((await activo()).cardId).toBe('c');
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-card-id="c"]')).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByTestId('selection-live')).toHaveText('1 seleccionada');

  await page.keyboard.press('Escape');
  const trasEsc = await activo();
  expect(trasEsc.cardId).toBeNull();

  // Marcos y columnas también se seleccionan con Enter.
  await page.locator('[data-card-id="f1"]').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-card-id="f1"]')).toHaveAttribute('aria-selected', 'true');
  await page.locator('[data-card-id="col1"]').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('[data-card-id="col1"]')).toHaveAttribute('aria-selected', 'true');

  // ⌘+flecha redimensiona: nota (ancho) y marco (alto).
  await page.locator('[data-card-id="c"]').focus();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Meta+ArrowRight');
  await expect.poll(async () => (await leerTablero(page, 'board-h4'))?.cards.find((card) => card.id === 'c')?.width).toBe(270);
  await page.locator('[data-card-id="f1"]').focus();
  await page.keyboard.press('Enter');
  await page.keyboard.press('Meta+ArrowDown');
  await expect.poll(async () => {
    const guardado = await leerTablero(page, 'board-h4');
    return (guardado?.cards.find((card) => card.id === 'f1')?.datos as { alto?: number } | undefined)?.alto;
  }).toBe(310);
  await page.keyboard.press('Meta+ArrowRight');
  await expect.poll(async () => (await leerTablero(page, 'board-h4'))?.cards.find((card) => card.id === 'f1')?.width).toBe(430);

  // Tres seleccionadas: aria-selected y región viva.
  await page.keyboard.press('Meta+a');
  await expect(page.locator('[data-testid="selection-live"]')).toHaveText('5 seleccionadas');
  const aria = await page.locator('[data-card-id="a"]').getAttribute('aria-selected');
  expect(aria).toBe('true');
  await page.screenshot({ path: path.join(CAPTURAS, 'H4-despues-aria-seleccion.png') });
});

test('H4 · Tab no queda atrapado en Tareas y los diálogos atrapan y devuelven el foco', async ({ page }) => {
  const tareas: SeedCard = {
    id: 't1',
    type: 'tareas',
    title: 'Tareas',
    body: '',
    x: 120,
    y: 120,
    width: 320,
    color: 'paper',
    datos: { tareas: [
      { id: 'x1', texto: 'Primera', hecha: false, nivel: 0 },
      { id: 'x2', texto: 'Segunda', hecha: false, nivel: 0 },
    ] },
  };
  await mockReadyBackend(page);
  await abrirTableroSembrado(page, tablero([tareas], 'board-h4-tareas', 'Tareas'));

  const primerTexto = page.getByLabel('Texto de la tarea').first();
  await primerTexto.focus();
  await page.keyboard.press('Tab');
  const trasTab = await page.evaluate(() => {
    const element = document.activeElement as HTMLElement | null;
    return { etiqueta: element?.getAttribute('aria-label'), valor: (element as HTMLInputElement | null)?.value ?? null };
  });
  expect(trasTab.valor).not.toBe('Primera');
  await page.keyboard.press('Tab');
  await page.keyboard.press('Tab');
  await expect(page.getByLabel('Texto de la tarea').nth(1)).toBeFocused();

  // Diálogo de atajos: foco dentro, Tab cicla, Esc devuelve al disparador.
  const disparador = page.getByRole('button', { name: 'Atajos de teclado' });
  await disparador.click();
  const dialogo = page.getByRole('dialog', { name: 'Atajos del tablero' });
  await expect(dialogo).toBeVisible();
  await expect.poll(async () => page.evaluate(() => Boolean((document.activeElement as HTMLElement | null)?.closest('[role="dialog"]')))).toBe(true);
  for (let i = 0; i < 25; i += 1) await page.keyboard.press('Tab');
  expect(await page.evaluate(() => Boolean((document.activeElement as HTMLElement | null)?.closest('[role="dialog"]')))).toBe(true);
  await page.screenshot({ path: path.join(CAPTURAS, 'H4-despues-foco-dialogo.png') });
  await page.keyboard.press('Escape');
  await expect(dialogo).toHaveCount(0);
  await expect(disparador).toBeFocused();
});
