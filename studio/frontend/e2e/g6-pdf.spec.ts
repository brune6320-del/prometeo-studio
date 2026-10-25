/**
 * G6 · editor PDF contra el motor real y las muestras del repositorio.
 * Requiere el Python empaquetado:
 *   PROMETEO_PYTHON=…/studio-desktop/resources/runtime/bin/python3 \
 *     npx playwright test -c playwright.config.ts g6-pdf.spec.ts
 */
import { expect, test, type Page } from '@playwright/test';

async function abrirMuestra(page: Page, key: string) {
  await page.goto('/');
  await page.locator(`[data-sample="${key}"]`).click();
  await expect(page.locator('#open-file-name')).toHaveText(`${key}.pdf`, { timeout: 60_000 });
  await expect(page.getByRole('img', { name: /Página 1/ })).toBeVisible({ timeout: 60_000 });
}

async function prepararObservacion(page: Page, id = 'ocr_p0_w4') {
  const capa = page.getByRole('button', { name: /Capa OCR/ });
  if ((await capa.getAttribute('aria-pressed')) !== 'true') await capa.click();
  const overlay = page.locator(`[data-ocr-id="${id}"]`);
  await expect(overlay).toBeVisible({ timeout: 30_000 });
  await overlay.click();
  await expect(page.getByText('Sí: fondo uniforme, edición verificable')).toBeVisible({ timeout: 30_000 });
}

test.describe('G6 · editor PDF', () => {
  test.setTimeout(180_000);

  test('reintentar un parche raster reutiliza la preparación y no falla', async ({ page }) => {
    await abrirMuestra(page, 'case_b_scan');
    await prepararObservacion(page);

    await page.locator('#raster-edit-input').fill('CONTRATO2');
    await page.getByRole('button', { name: 'Preparar parche' }).click();
    await expect(page.locator('.notice-title').filter({ hasText: 'Parche preparado' })).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('.tray-item')).toHaveCount(1);

    await page.locator('#raster-edit-input').fill('CONTRATO3');
    await expect(page.getByRole('button', { name: 'Actualizar parche preparado' })).toBeEnabled();
    await page.getByRole('button', { name: 'Actualizar parche preparado' }).click();

    await expect(page.getByText(/ya ha sido preparada/i)).toHaveCount(0);
    await expect(page.locator('.tray-item')).toHaveCount(1);
    await expect(page.locator('.tray-item .text-new')).toHaveText('CONTRATO3');
    await page.screenshot({ path: '../../REPORTES/capturas-forja3/g6-despues-reintento.png', animations: 'disabled' });
  });

  test('la verificación fallida dice qué comprobación falló, esperado y obtenido', async ({ page }) => {
    await abrirMuestra(page, 'case_b_scan');
    await prepararObservacion(page);

    await page.locator('#raster-edit-input').fill('ZZZZZZZZ');
    await page.getByRole('button', { name: 'Preparar parche' }).click();
    await expect(page.locator('.tray-item')).toHaveCount(1);

    await page.locator('#verify-button').click();
    await expect(page.getByRole('heading', { name: 'La copia no superó la verificación' })).toBeVisible({ timeout: 120_000 });

    await expect(page.getByRole('heading', { name: 'Qué falló' })).toBeVisible();
    const fila = page.locator('.failure-table tbody tr').filter({ hasText: 'El texto nuevo se lee en la copia' });
    await expect(fila).toBeVisible();
    await expect(fila.locator('td').first()).toHaveText('ZZZZZZZZ');
    const obtenido = await fila.locator('td').last().textContent();
    expect(obtenido?.trim().length).toBeGreaterThan(0);

    await page.screenshot({ path: '../../REPORTES/capturas-forja3/g6-despues-fallo.png', animations: 'disabled' });
  });

  test('ventana estrecha: sin desbordamiento, visor visible y paneles plegables', async ({ page }) => {
    await abrirMuestra(page, 'case_a');

    await page.setViewportSize({ width: 760, height: 700 });
    await page.waitForTimeout(600);
    const ancho760 = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      ventana: window.innerWidth,
      visor: document.querySelector('.viewport')?.getBoundingClientRect().width ?? 0,
    }));
    expect(ancho760.scroll).toBeLessThanOrEqual(ancho760.ventana + 1);
    expect(ancho760.visor).toBeGreaterThan(700);

    await page.getByRole('button', { name: 'Mostrar el panel Inspector' }).click();
    const inspector = page.locator('.inspector-panel');
    await expect(inspector).toBeVisible();
    const cajaInspector = await inspector.boundingBox();
    expect(cajaInspector?.width ?? 0).toBeGreaterThan(280);
    expect((cajaInspector?.x ?? 0) + (cajaInspector?.width ?? 0)).toBeLessThanOrEqual(760);
    await page.screenshot({ path: '../../REPORTES/capturas-forja3/g6-despues-760.png', animations: 'disabled' });

    await page.getByRole('button', { name: 'Ocultar el panel Inspector' }).click();
    await expect(inspector).toBeHidden();

    await page.setViewportSize({ width: 520, height: 700 });
    await page.waitForTimeout(600);
    const ancho520 = await page.evaluate(() => ({
      scroll: document.documentElement.scrollWidth,
      ventana: window.innerWidth,
      visor: document.querySelector('.viewport')?.getBoundingClientRect().width ?? 0,
    }));
    expect(ancho520.scroll).toBeLessThanOrEqual(ancho520.ventana + 1);
    expect(ancho520.visor).toBeGreaterThan(500);

    await page.getByRole('button', { name: 'Mostrar el panel Contenido' }).click();
    await expect(page.locator('.outliner-panel')).toBeVisible();
    await page.screenshot({ path: '../../REPORTES/capturas-forja3/g6-despues-520.png', animations: 'disabled' });
    await page.getByRole('button', { name: 'Ocultar el panel Contenido' }).click();
    await expect(page.locator('.outliner-panel')).toBeHidden();
    await expect(page.getByRole('img', { name: /Página 1/ })).toBeVisible();
  });
});
