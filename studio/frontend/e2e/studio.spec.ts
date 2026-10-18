/**
 * PROMETEO Studio · E2E de navegador (CLAUDE-REMEDIATION-001).
 * Flujo humano mínimo contra el motor real: bienvenida → ejemplo → seleccionar → preparar →
 * verificar → comparar. Proyectos: chromium y webkit (el motor de la app de escritorio).
 * Requiere los navegadores de Playwright instalados (npx playwright install chromium webkit).
 */
import { expect, test } from '@playwright/test';

test('flujo completo: abrir, preparar, verificar y comparar', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Edita PDFs sin poner en riesgo el original' })).toBeVisible();

  await page.locator('[data-sample="case_a"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('case_a.pdf');
  await expect(page.getByRole('img', { name: /Página 1/ })).toBeVisible();

  await page.getByRole('button', { name: /Contratado: Juan Perez/ }).click();
  const field = page.getByLabel('Texto nuevo');
  await field.fill('Contratado: Ana Ruiz');
  await page.getByRole('button', { name: 'Preparar cambio' }).click();
  await expect(page.getByText('1 cambio preparado')).toBeVisible();

  await page.locator('#verify-button').click();
  await expect(page.getByRole('heading', { name: 'Copia verificada' })).toBeVisible({ timeout: 60_000 });
  await expect(page.getByText(/Tu original no cambió/)).toBeVisible();
  await expect(page.getByText('Copia verificada', { exact: true }).first()).toBeVisible();
});

test('motor caído: el error se explica, no se muestra "Load failed"', async ({ page }) => {
  await page.route('**/api/samples', (route) => route.abort('connectionrefused'));
  await page.goto('/');
  // La lista de ejemplos falla: debe verse un aviso explicado con «Reintentar» (antes era silencioso).
  const notice = page.getByTestId('samples-error');
  await expect(notice).toBeVisible({ timeout: 20_000 });
  await expect(notice.getByRole('button', { name: /Reintentar/ })).toBeVisible();
  await expect(page.getByText('Load failed')).toHaveCount(0);
  await expect(page.getByText('Failed to fetch')).toHaveCount(0);
  // Al recuperarse el motor, «Reintentar» trae los ejemplos.
  await page.unroute('**/api/samples');
  await notice.getByRole('button', { name: /Reintentar/ }).click();
  await expect(page.locator('[data-sample="case_a"]')).toBeVisible({ timeout: 20_000 });
});
