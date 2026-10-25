/**
 * Sistemas de diseño por tablero.
 *
 * No son temas de color sueltos: cada entrada cambia el juego de tokens que
 * consumen el lienzo, las tarjetas y los portales. `forja` es el sistema base;
 * `irene` es una traducción propia del tono del Lienzo Archivo (papel blanco,
 * tinta negra, mono pequeña y líneas punteadas), no una copia de su web.
 */

export type DesignSystemId = 'forja' | 'irene';

export interface DesignSystemEntry {
  id: DesignSystemId;
  nombre: string;
  descripcion: string;
  /** Valores de muestra para el selector; no son la fuente de verdad de los tokens. */
  muestras: [string, string, string];
}

export const DESIGN_SYSTEMS: readonly DesignSystemEntry[] = [
  {
    id: 'forja',
    nombre: 'Forja 2',
    descripcion: 'Lienzo oscuro, papel cálido y acento de ascua. El sistema base del estudio.',
    muestras: ['#0f0f11', '#f7f3ea', '#ff8a52'],
  },
  {
    id: 'irene',
    nombre: 'Archivo Irene',
    descripcion: 'Papel blanco, tinta negra y mono pequeña. Inspirado en el archivo, no copiado de él.',
    muestras: ['#ffffff', '#111111', '#8a8a8a'],
  },
];

const IDS = new Set<DesignSystemId>(DESIGN_SYSTEMS.map((entry) => entry.id));

/** Un valor ausente o desconocido vuelve a Forja 2 sin perder el tablero. */
export function normalizeDesignSystem(value: unknown): DesignSystemId {
  return IDS.has(value as DesignSystemId) ? (value as DesignSystemId) : 'forja';
}

export function designSystemEntry(id: unknown): DesignSystemEntry {
  const normalized = normalizeDesignSystem(id);
  return DESIGN_SYSTEMS.find((entry) => entry.id === normalized) ?? DESIGN_SYSTEMS[0];
}
