import { expect, test } from '@playwright/test';
import { abrirTablero, mockBackend } from './helpers';

test('F1 · los tokens Forja 2 mandan y no queda texto por debajo de 12 px', async ({ page }) => {
  await mockBackend(page);
  await abrirTablero(page);

  const raiz = await page.evaluate(() => {
    const estilo = getComputedStyle(document.documentElement);
    return {
      accent: estilo.getPropertyValue('--accent').trim(),
      surface0: estilo.getPropertyValue('--surface-0').trim(),
      caption: estilo.getPropertyValue('--font-size-caption').trim(),
      lod: estilo.getPropertyValue('--board-lod-zoom').trim(),
    };
  });
  expect(raiz.accent).toBe('#ff8a52');
  expect(raiz.surface0).toBe('#0f0f11');
  expect(raiz.caption).toBe('12px');
  expect(Number(raiz.lod)).toBeGreaterThan(0);

  const pequenos = await page.evaluate(() => {
    const vistos: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>('body *'))) {
      const caja = el.getBoundingClientRect();
      if (caja.width === 0 || caja.height === 0) continue;
      if (el.closest('[aria-hidden="true"]')) continue;
      if (!el.textContent?.trim()) continue;
      if (el.children.length > 0 && Array.from(el.children).some((hijo) => (hijo.textContent ?? '').trim())) continue;
      const tamano = Number.parseFloat(getComputedStyle(el).fontSize);
      if (Number.isFinite(tamano) && tamano < 12) vistos.push(`${el.className || el.tagName}: ${tamano}px`);
    }
    return vistos;
  });
  expect(pequenos).toEqual([]);
});
