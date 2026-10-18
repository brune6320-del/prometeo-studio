/**
 * PROMETEO Studio · accesibilidad básica en navegador (CAMP-002). No sustituye a VoiceOver ni a
 * una auditoría WCAG: comprueba nombres accesibles de los controles y que «reducir movimiento»
 * desactiva las animaciones.
 */
import { expect, test, type Page } from '@playwright/test';

async function unnamedControls(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const textOf = (id: string) => document.getElementById(id)?.textContent?.trim() ?? '';
    const name = (el: Element): string => {
      const h = el as HTMLElement;
      const labelledby = h.getAttribute('aria-labelledby');
      if (labelledby) return labelledby.split(/\s+/).map(textOf).join(' ').trim();
      const aria = h.getAttribute('aria-label');
      if (aria) return aria.trim();
      if (h.id) {
        const lab = document.querySelector(`label[for="${h.id}"]`);
        if (lab?.textContent?.trim()) return lab.textContent.trim();
      }
      const imgAlt = Array.from(h.querySelectorAll('img[alt]')).map((i) => i.getAttribute('alt')).join(' ');
      return (h.innerText || h.getAttribute('title') || imgAlt || '').trim();
    };
    const visible = (el: Element) => {
      const r = (el as HTMLElement).getBoundingClientRect();
      return r.width > 0 && r.height > 0 && !(el as HTMLElement).closest('[hidden]');
    };
    return Array.from(document.querySelectorAll('button, input:not([type=hidden]), select, textarea, [role=button], a[href]'))
      .filter(visible)
      .filter((el) => !name(el))
      .map((el) => el.outerHTML.slice(0, 140));
  });
}

test('todos los controles visibles tienen nombre accesible (bienvenida, documento, diálogo)', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Edita PDFs sin poner en riesgo el original' })).toBeVisible();
  expect(await unnamedControls(page)).toEqual([]);

  await page.locator('[data-sample="case_a"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('case_a.pdf');
  await page.getByRole('button', { name: /Contratado: Juan Perez/ }).first().click();
  expect(await unnamedControls(page)).toEqual([]);

  await page.getByLabel('Texto nuevo').fill('Contratado: Ana Ruiz');
  await page.getByRole('button', { name: 'Preparar cambio' }).click();
  await page.locator('#sample-select').selectOption('case_b_scan');
  await expect(page.getByRole('alertdialog')).toBeVisible();
  expect(await unnamedControls(page)).toEqual([]);
});

test('con «reducir movimiento» las animaciones quedan desactivadas', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await page.locator('[data-sample="case_a"]').click();
  await expect(page.locator('#open-file-name')).toHaveText('case_a.pdf');
  const durations = await page.evaluate(() =>
    Array.from(document.querySelectorAll('*'))
      .map((el) => getComputedStyle(el).animationDuration)
      .filter((d) => d && d !== '0s')
      .map((d) => parseFloat(d) * (d.endsWith('ms') ? 1 : 1000)),
  );
  // 0,01 ms por regla global; ninguna animación perceptible (> 1 ms).
  expect(durations.filter((ms) => ms > 1)).toEqual([]);
});
