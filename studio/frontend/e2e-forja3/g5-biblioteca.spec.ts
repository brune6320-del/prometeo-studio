import { expect, test, type Page } from '@playwright/test';
import { abrirTablero, abrirTableroCon, capturar, tarjeta } from './helpers';

async function abrirBiblioteca(page: Page) {
  await page.getByRole('button', { name: 'Más herramientas' }).click();
  await expect(page.locator('.board-library')).toBeVisible();
}

async function guardado(page: Page) {
  await page.waitForFunction(() => document.querySelector('.board-save-state')?.textContent === 'Guardado', null, { timeout: 10_000 });
}

test.describe('G5 · biblioteca y sistemas de diseño', () => {
  test.setTimeout(150_000);

  test('«+ Más» busca, filtra por categoría, previsualiza y añade', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta({ id: 'g5-n1', type: 'note', title: 'Una idea', body: 'Antes de la biblioteca.', x: 180, y: 160 }),
    ]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});
    await abrirBiblioteca(page);

    const buscar = page.getByRole('searchbox', { name: 'Buscar herramienta' });
    await expect(buscar).toBeFocused();
    await expect(page.locator('.board-library-item')).toHaveCount(10);

    await buscar.fill('enlace');
    await expect(page.locator('.board-library-item')).toHaveCount(1);
    await expect(page.locator('.board-library-item')).toContainText('Enlace');
    await expect(page.locator('.board-library-preview')).toContainText('vista previa');

    await capturar(page, '../../REPORTES/capturas-forja3/g5-despues-mas.png');

    await page.getByRole('button', { name: 'Añadir al tablero' }).click();
    await expect(page.locator('.board-library')).toHaveCount(0);
    await expect(page.locator('.board-card')).toHaveCount(2);

    await abrirBiblioteca(page);
    await page.getByRole('button', { name: 'Referencias', exact: true }).click();
    await expect(page.locator('.board-library-item')).toHaveCount(2);
    await expect(page.locator('.board-library-chip[aria-pressed="true"]')).toHaveText('Referencias');

    await page.getByRole('searchbox', { name: 'Buscar herramienta' }).fill('zzzz');
    await expect(page.locator('.board-library-empty').first()).toBeVisible();
    await expect(page.locator('.board-library-item')).toHaveCount(0);
  });

  test('sistema de diseño por tablero: Irene, Forja y persistencia', async ({ page }) => {
    await abrirTableroCon(page, [
      tarjeta({ id: 'g5-n1', type: 'note', title: 'Una idea', body: 'El sistema cambia los tokens.', x: 220, y: 180, width: 300 }),
      {
        id: 'g5-marco',
        type: 'marco',
        title: 'BARATTOLO',
        x: 620,
        y: 180,
        width: 520,
        datos: { alto: 380, hijos: [], vista: 'libre' },
      },
    ]);
    await page.waitForTimeout(400);
    await page.locator('.board-toast button').click({ timeout: 1000 }).catch(() => {});

    const selector = page.getByLabel('Sistema de diseño del tablero');
    await expect(selector).toHaveValue('forja');
    await expect(page.locator('html')).toHaveAttribute('data-design-system', 'forja');
    const forja = await page.locator('.board-viewport').evaluate((element) => getComputedStyle(element).backgroundColor);
    expect(forja).toBe('rgb(15, 15, 17)');

    await selector.selectOption('irene');
    await expect(page.locator('html')).toHaveAttribute('data-design-system', 'irene');
    await expect.poll(() => page.locator('.board-viewport').evaluate((element) => getComputedStyle(element).backgroundColor))
      .toBe('rgb(244, 243, 239)');
    const irene = await page.locator('.board-workspace').evaluate((element) => ({
      familia: getComputedStyle(element).fontFamily.toLowerCase(),
      radio: getComputedStyle(element).getPropertyValue('--radius-lg').trim(),
      tinta: getComputedStyle(element).getPropertyValue('--fg-1').trim(),
      marco: getComputedStyle(document.querySelector<HTMLElement>('.board-frame')!).borderStyle,
    }));
    expect(irene.familia).toMatch(/mono/);
    expect(irene.radio).toBe('2px');
    expect(irene.tinta).toBe('#111111');
    expect(irene.marco).toBe('dashed');

    await capturar(page, '../../REPORTES/capturas-forja3/g5-despues-irene.png');
    await guardado(page);

    // Otro tablero nace en Forja 2; al volver, el primero conserva Irene.
    await page.getByRole('button', { name: 'Crear tablero' }).click();
    await expect(page.getByLabel('Sistema de diseño del tablero')).toHaveValue('forja');
    await expect(page.locator('html')).toHaveAttribute('data-design-system', 'forja');

    const primerTablero = await page.evaluate(() => {
      const select = document.querySelector<HTMLSelectElement>('#board-select');
      return select ? [...select.options].map((option) => `${option.value}|${option.textContent}`) : [];
    });
    const idIrene = primerTablero.find((item) => item.endsWith('|Tablero Forja 2'))?.split('|')[0];
    expect(idIrene).toBeTruthy();
    await page.locator('#board-select').selectOption(idIrene!);
    await expect(page.getByLabel('Sistema de diseño del tablero')).toHaveValue('irene');
    await expect(page.locator('html')).toHaveAttribute('data-design-system', 'irene');
    await guardado(page);

    // Recargar conserva el sistema del tablero.
    await page.reload();
    await abrirTablero(page);
    await expect(page.getByLabel('Sistema de diseño del tablero')).toHaveValue('irene');
    await expect(page.locator('html')).toHaveAttribute('data-design-system', 'irene');

    await page.getByLabel('Sistema de diseño del tablero').selectOption('forja');
    await expect(page.locator('html')).toHaveAttribute('data-design-system', 'forja');
    await expect.poll(() => page.locator('.board-viewport').evaluate((element) => getComputedStyle(element).backgroundColor))
      .toBe('rgb(15, 15, 17)');
  });
});
