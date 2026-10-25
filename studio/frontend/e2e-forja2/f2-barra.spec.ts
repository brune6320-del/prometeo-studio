import { expect, test } from '@playwright/test';
import { abrirTableroCon, tarjeta } from './helpers';

const CARDS = [
  tarjeta({ id: 'a', type: 'note', title: 'Primera', body: 'Una', x: 80, y: 80 }),
  tarjeta({ id: 'b', type: 'note', title: 'Segunda', body: 'Dos', x: 420, y: 80 }),
  tarjeta({ id: 'c', type: 'note', title: 'Tercera', body: 'Tres', x: 760, y: 80 }),
];

test('F2 · la barra fina, el rail y los menús conservan todas las acciones', async ({ page }) => {
    await abrirTableroCon(page, CARDS);

  const topbar = page.getByTestId('board-topbar');
  await expect(topbar.getByLabel('Elegir proyecto')).toBeVisible();
  await expect(topbar.getByLabel('Elegir tablero')).toBeVisible();
  await expect(topbar.getByLabel('Buscar tarjetas')).toBeVisible();
  await expect(topbar.getByRole('button', { name: 'Deshacer' })).toBeVisible();
  await expect(topbar.getByRole('button', { name: 'Rehacer' })).toBeVisible();
  await expect(topbar.getByRole('button', { name: /Zoom/ })).toBeVisible();
  await expect(topbar.getByRole('button', { name: 'Crear proyecto' })).toBeVisible();
  await expect(topbar.getByRole('button', { name: 'Crear tablero' })).toBeVisible();
  await expect(topbar.getByRole('button', { name: 'Importar tablero' })).toBeVisible();
  await expect(topbar.getByRole('button', { name: 'Renombrar tablero' })).toBeVisible();
  await expect(topbar.getByRole('button', { name: 'Eliminar tablero' })).toBeVisible();

  for (const nombre of ['Nueva nota', 'Añadir enlace', 'Añadir imagen', 'Añadir referente', 'Dibujar marco', 'Añadir entropía', 'Más herramientas']) {
    await expect(page.getByRole('button', { name: nombre })).toHaveCount(1);
  }

  await topbar.getByRole('button', { name: /Exportar/ }).click();
  const exportar = page.getByRole('menu', { name: 'Exportar' });
  for (const item of ['JSON del tablero', 'Markdown', 'Obsidian del proyecto', 'Referentes a Obsidian', 'Publicar marco seleccionado']) {
    await expect(exportar.getByRole('menuitem', { name: item })).toBeVisible();
  }
  await page.keyboard.press('Escape');
  await expect(exportar).toHaveCount(0);

  await topbar.getByRole('button', { name: /Biblioteca/ }).click();
  const biblioteca = page.getByRole('menu', { name: 'Biblioteca' });
  for (const item of ['Volver a mirar', 'Manifiesto de la semana', 'Importar referentes', 'Importar gustos']) {
    await expect(biblioteca.getByRole('menuitem', { name: item })).toBeVisible();
  }
  await expect(biblioteca.getByRole('menuitem', { name: /Referenciar página PDF/ })).toBeVisible();
  await expect(biblioteca.getByRole('menuitem', { name: /Referencias PDF/ })).toBeVisible();
  await page.keyboard.press('Escape');

  await expect(page.locator('.board-selection-bar')).toHaveCount(0);
  const tarjetas = page.locator('.board-card');
  await tarjetas.nth(0).click({ position: { x: 30, y: 24 } });
  await tarjetas.nth(1).click({ position: { x: 30, y: 24 }, modifiers: ['Shift'] });
  const barra = page.locator('.board-selection-bar');
  await expect(barra).toBeVisible();
  await expect(barra.getByRole('button', { name: 'Alinear a la izquierda' })).toBeVisible();
  await expect(barra.getByRole('button', { name: 'Distribuir horizontalmente' })).toBeDisabled();
  await tarjetas.nth(2).click({ position: { x: 30, y: 24 }, modifiers: ['Shift'] });
  await expect(barra.getByRole('button', { name: 'Distribuir horizontalmente' })).toBeEnabled();

  const antes = await page.locator('.board-card').count();
  await page.getByRole('button', { name: 'Nueva nota' }).dragTo(page.locator('.board-viewport'), { targetPosition: { x: 900, y: 600 } });
  await expect(page.locator('.board-card')).toHaveCount(antes + 1);
});
