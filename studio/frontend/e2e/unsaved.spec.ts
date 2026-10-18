/**
 * PROMETEO Studio · E2E de la guarda de trabajo sin guardar (CAMP-002 · F1/F2), contra el motor real.
 * Cubre lo que el arnés nativo no puede pulsar: Cancelar, Esc, foco, Descartar, Guardar (descarga),
 * aviso del navegador al cerrar la pestaña y recuperación de la sesión tras recargar.
 */
import { expect, test, type Page } from '@playwright/test';

async function openSampleAndStage(page: Page) {
  await page.goto('/');
  await page.locator('[data-sample="case_a"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('case_a.pdf');
  await page.getByRole('button', { name: /Contratado: Juan Perez/ }).first().click();
  await page.getByLabel('Texto nuevo').fill('Contratado: Ana Ruiz');
  await page.getByRole('button', { name: 'Preparar cambio' }).click();
  await expect(page.getByText('1 cambio preparado')).toBeVisible();
}

async function verifyCopy(page: Page) {
  await page.locator('#verify-button').click();
  await expect(page.getByRole('heading', { name: 'Copia verificada' })).toBeVisible({ timeout: 90_000 });
}

/** Intenta abrir el ejemplo escaneado desde la barra superior (acción protegida por la guarda). */
async function tryOpenOtherSample(page: Page) {
  await page.locator('#sample-select').selectOption('case_b_scan');
}

test('cambios preparados: abrir otro documento pregunta; Cancelar y Esc conservan el trabajo', async ({ page }) => {
  await openSampleAndStage(page);
  await tryOpenOtherSample(page);
  const dialog = page.getByRole('alertdialog');
  await expect(dialog).toBeVisible();
  await expect(dialog).toContainText('Tienes cambios sin verificar');
  await expect(dialog).toContainText('Tu original no cambia');
  // Sin copia aprobada no se ofrece «Guardar».
  await expect(dialog.getByTestId('unsaved-save')).toHaveCount(0);
  // El foco empieza en Cancelar (la opción que no pierde nada).
  await expect(dialog.getByRole('button', { name: 'Cancelar' })).toBeFocused();
  await dialog.getByRole('button', { name: 'Cancelar' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('#open-file-name')).toHaveText('case_a.pdf');
  await expect(page.getByText('1 cambio preparado')).toBeVisible();

  await tryOpenOtherSample(page);
  await expect(page.getByRole('alertdialog')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
  await expect(page.getByText('1 cambio preparado')).toBeVisible();
});

test('con el diálogo abierto: foco atrapado, fondo inerte y ⌘F no abre el buscador', async ({ page }) => {
  await openSampleAndStage(page);
  await tryOpenOtherSample(page);
  const dialog = page.getByRole('alertdialog');
  await expect(dialog).toBeVisible();
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press('Tab');
    const inside = await page.evaluate(() => !!document.activeElement?.closest('[role="alertdialog"]'));
    expect(inside).toBe(true);
  }
  await page.keyboard.press('Meta+f');
  await page.keyboard.press('Control+f');
  await expect(page.getByRole('dialog', { name: /Buscar/ })).toHaveCount(0);
  expect(await page.locator('.app').getAttribute('inert')).not.toBeNull();
});

test('Descartar y abrir: se pierde lo preparado (decisión de la persona) y se abre el otro documento', async ({ page }) => {
  await openSampleAndStage(page);
  await tryOpenOtherSample(page);
  await page.getByTestId('unsaved-discard').click();
  await expect(page.locator('#open-file-name')).toHaveText('case_b_scan.pdf', { timeout: 60_000 });
  await expect(page.getByText('No hay cambios preparados')).toBeVisible();
});

test('copia verificada sin guardar: «Guardar y continuar» descarga la copia y después abre el otro documento', async ({ page }) => {
  await openSampleAndStage(page);
  await verifyCopy(page);
  await tryOpenOtherSample(page);
  const dialog = page.getByRole('alertdialog');
  await expect(dialog).toContainText('La copia verificada no está guardada');
  const download = page.waitForEvent('download');
  await dialog.getByTestId('unsaved-save').click();
  const file = await download;
  expect(file.suggestedFilename()).toMatch(/\.pdf$/);
  await expect(page.locator('#open-file-name')).toHaveText('case_b_scan.pdf', { timeout: 60_000 });
});

test('cerrar la pestaña con trabajo sin guardar dispara el aviso del navegador', async ({ page }) => {
  await openSampleAndStage(page);
  const seen = new Promise<string>((resolve) => page.once('dialog', async (d) => {
    resolve(d.type());
    await d.dismiss();
  }));
  await page.close({ runBeforeUnload: true });
  expect(await seen).toBe('beforeunload');
});

test('sin trabajo pendiente no hay diálogo al abrir otro documento', async ({ page }) => {
  await page.goto('/');
  await page.locator('[data-sample="case_a"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('case_a.pdf');
  await tryOpenOtherSample(page);
  await expect(page.getByRole('alertdialog')).toHaveCount(0);
  await expect(page.locator('#open-file-name')).toHaveText('case_b_scan.pdf', { timeout: 60_000 });
});

test('recargar la interfaz recupera la sesión con sus cambios', async ({ page }) => {
  test.setTimeout(120_000);
  await openSampleAndStage(page);
  page.once('dialog', (d) => d.accept()); // aviso de beforeunload: aceptar recargar
  await page.reload();
  await expect(page.getByText('Sesión recuperada')).toBeVisible({ timeout: 30_000 });
  await expect(page.locator('#open-file-name')).toHaveText('case_a.pdf');
  await expect(page.getByText('1 cambio preparado')).toBeVisible();
});
