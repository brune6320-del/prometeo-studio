/// <reference types="node" />
import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const TOKENS = join(RAIZ, 'styles/tokens.css');

function css(desde: string): string[] {
  return readdirSync(desde).flatMap((entrada) => {
    const ruta = join(desde, entrada);
    if (statSync(ruta).isDirectory()) return css(ruta);
    return ruta.endsWith('.css') ? [ruta] : [];
  });
}

const FUERA_DE_TOKENS = css(RAIZ)
  .filter((ruta) => ruta !== TOKENS)
  .map((ruta) => [ruta, readFileSync(ruta, 'utf8')] as const);

/** Excepciones deliberadas: CSS autónomo del sitio publicado (no es chrome de la app). */
const EXCEPCIONES = new Set<string>();

describe('Forja 2 · tokens', () => {
  it('no quedan colores hexadecimales sueltos fuera de tokens.css', () => {
    const sueltos = FUERA_DE_TOKENS.flatMap(([ruta, texto]) => {
      if (EXCEPCIONES.has(ruta)) return [];
      return Array.from(texto.matchAll(/#[0-9a-fA-F]{3,8}\b/g)).map((m) => `${ruta}: ${m[0]}`);
    });
    expect(sueltos).toEqual([]);
  });

  it('el azul heredado no sobrevive en CSS', () => {
    for (const [, texto] of FUERA_DE_TOKENS) {
      expect(texto.toLowerCase()).not.toContain('#315c7c');
    }
  });

  it('ningún texto baja de 12 px', () => {
    const pequenos = FUERA_DE_TOKENS.flatMap(([ruta, texto]) =>
      Array.from(texto.matchAll(/font-size:\s*(\d+)px/g))
        .filter((m) => Number(m[1]) < 12)
        .map((m) => `${ruta}: ${m[1]}px`),
    );
    expect(pequenos).toEqual([]);
  });

  it('tokens.css define la escala, ambos temas y el movimiento heredado', () => {
    const texto = readFileSync(TOKENS, 'utf8');
    for (const token of [
      '--surface-0', '--surface-1', '--surface-2', '--surface-3',
      '--fg-1', '--fg-2', '--fg-3', '--accent', '--accent-soft', '--on-accent',
      '--space-1', '--space-4', '--space-8', '--radius-lg', '--radius-pill',
      '--shadow-1', '--shadow-3', '--state-focus-ring', '--state-selected-ring',
      '--duration-fast', '--duration-slow', '--ease-out', '--motion-tau-seco',
      '--font-size-caption', '--font-size-body', '--board-lod-zoom',
    ]) {
      expect(texto).toContain(`${token}:`);
    }
    expect(texto).toContain("[data-theme='light']");
    expect(texto).toContain('prefers-reduced-motion: reduce');
  });

  it('index.css importa los tokens una sola vez y no duplica la raíz', () => {
    const index = readFileSync(join(RAIZ, 'index.css'), 'utf8');
    expect(index.match(/@import '\.\/styles\/tokens\.css';/g)).toHaveLength(1);
    expect(index).not.toContain(':root {');
  });
});
