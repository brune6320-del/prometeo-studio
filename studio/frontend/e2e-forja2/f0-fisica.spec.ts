import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { abrirTablero, mockBackend } from './helpers';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const REPO = path.resolve(AQUI, '../../..');
const SKILL = path.join(REPO, '.agents/skills/prometeo-fisica/SKILL.md');
const MUELLE = path.join(REPO, 'studio/frontend/src/motion/muelle.ts');

test('F0 · la skill de física es corta, cita Sala Oscura y enlaza el módulo', () => {
  const skill = readFileSync(SKILL, 'utf8');
  const lineas = skill.split('\n').length;
  expect(lineas).toBeLessThanOrEqual(80);
  expect(skill).toContain('sala-oscura.html:8878');
  expect(skill).toContain('rubber-band');
  expect(skill).toContain('prefers-reduced-motion');
  expect(readFileSync(MUELLE, 'utf8')).toContain('export function pasoMuelle');
});

test('F0 · el tablero abre con reduced motion y sin errores de consola', async ({ page }) => {
  const errores: string[] = [];
  page.on('console', (msg) => { if (msg.type() === 'error') errores.push(msg.text()); });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await mockBackend(page);
  await abrirTablero(page);
  await expect(page.locator('.board-header')).toBeVisible();
  expect(errores).toEqual([]);
});
