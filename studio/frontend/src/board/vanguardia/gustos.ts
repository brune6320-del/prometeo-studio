import type { Combinacion } from './combinador';

/**
 * Memoria de gusto de la vanguardia. Vive en el proyecto (campo `gustos`),
 * nunca en localStorage. `gustos.json` es su forma exportable.
 */
export interface Gustos {
  version: 1;
  referentes: Record<string, number>;
  reglas: Record<string, number>;
  herramientas: Record<string, number>;
  /** Peso por par de referentes; la clave ordena los dos ids: «a|b». */
  pares: Record<string, number>;
}

export const PESO_MINIMO = 0.2;
export const PESO_MAXIMO = 5;
export const PESO_INICIAL = 1;
export const ARCHIVO_GUSTOS = 'gustos.json';

export function gustosVacios(): Gustos {
  return { version: 1, referentes: {}, reglas: {}, herramientas: {}, pares: {} };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function recortarPeso(value: number): number {
  if (!Number.isFinite(value)) return PESO_INICIAL;
  return Math.min(PESO_MAXIMO, Math.max(PESO_MINIMO, value));
}

function normalizarMapa(value: unknown): Record<string, number> {
  if (!isRecord(value)) return {};
  const result: Record<string, number> = {};
  for (const [clave, peso] of Object.entries(value)) {
    if (!clave.trim() || typeof peso !== 'number' || !Number.isFinite(peso)) continue;
    result[clave] = recortarPeso(peso);
  }
  return result;
}

/** Acepta JSON viejo o parcial y devuelve siempre gustos utilizables. */
export function normalizarGustos(value: unknown): Gustos {
  if (!isRecord(value)) return gustosVacios();
  return {
    version: 1,
    referentes: normalizarMapa(value.referentes),
    reglas: normalizarMapa(value.reglas),
    herramientas: normalizarMapa(value.herramientas),
    pares: normalizarMapa(value.pares),
  };
}

/** Peso efectivo: lo no guardado pesa 1. */
export function pesoDe(mapa: Readonly<Record<string, number>>, id: string): number {
  const peso = mapa[id];
  return typeof peso === 'number' && Number.isFinite(peso) ? recortarPeso(peso) : PESO_INICIAL;
}

/** Clave estable de un par, sin depender del orden en que se eligieron. */
export function clavePar(a: string, b: string): string {
  return [a, b].sort().join('|');
}

function sumar(
  mapa: Readonly<Record<string, number>>,
  ids: readonly string[],
  delta: number,
): Record<string, number> {
  const result: Record<string, number> = { ...mapa };
  for (const id of ids) {
    if (!id) continue;
    result[id] = recortarPeso(pesoDe(result, id) + delta);
  }
  return result;
}

function ajustar(gustos: Gustos, combinacion: Combinacion, delta: number): Gustos {
  const actual = normalizarGustos(gustos);
  const referentes = [...new Set(combinacion.referentes.filter(Boolean))];
  const pares: string[] = [];
  for (let i = 0; i < referentes.length; i += 1) {
    for (let j = i + 1; j < referentes.length; j += 1) {
      pares.push(clavePar(referentes[i], referentes[j]));
    }
  }

  return {
    version: 1,
    referentes: sumar(actual.referentes, referentes, delta),
    reglas: sumar(actual.reglas, [combinacion.regla], delta),
    herramientas: sumar(actual.herramientas, [combinacion.herramienta], delta),
    pares: sumar(actual.pares, pares, delta),
  };
}

/** ♥ suma 1 a referentes, regla, herramienta y cada par; recorta a [0.2, 5]. */
export function like(gustos: Gustos, combinacion: Combinacion): Gustos {
  return ajustar(gustos, combinacion, 1);
}

/** ✕ resta 1 con el mismo alcance y el mismo recorte. */
export function nope(gustos: Gustos, combinacion: Combinacion): Gustos {
  return ajustar(gustos, combinacion, -1);
}

/** Guarda los gustos dentro del proyecto; no toca localStorage. */
export function conGustos<T extends object>(proyecto: T, gustos: Gustos): T & { gustos: Gustos } {
  return { ...proyecto, gustos: normalizarGustos(gustos) };
}

/** Lee los gustos del proyecto; si no existen, devuelve memoria vacía. */
export function gustosDeProyecto(proyecto: unknown): Gustos {
  if (isRecord(proyecto) && 'gustos' in proyecto) return normalizarGustos(proyecto.gustos);
  return gustosVacios();
}

/** Contenido de `gustos.json`, estable y legible. */
export function gustosAJson(gustos: Gustos): string {
  return `${JSON.stringify(normalizarGustos(gustos), null, 2)}\n`;
}

/** Reverso de `gustosAJson`; `null` solo si el texto no es JSON válido. */
export function gustosDesdeJson(texto: string): Gustos | null {
  try {
    const value: unknown = JSON.parse(texto);
    return isRecord(value) ? normalizarGustos(value) : null;
  } catch {
    return null;
  }
}
