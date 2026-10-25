import type { BoardCard } from './model';

export interface ColumnData {
  hijos: string[];
  plegada: boolean;
  /** Alto fijo opcional; sin él, la columna crece con su lista. */
  alto?: number;
  /** Si se ha reordenado o soltado dentro, manda `hijos`; si no, se hereda el orden por `y`. */
  ordenExplicito: boolean;
}

export const COLUMN_WIDTH = 300;
export const COLUMN_MIN_HEIGHT = 150;
export const MAX_COLUMN_CHILDREN = 200;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function esColumna(card: BoardCard): boolean {
  return card.type === 'columna';
}

export function readColumnData(card: BoardCard): ColumnData {
  const raw = isRecord(card.datos) ? card.datos : {};
  const alto = typeof raw.alto === 'number' && Number.isFinite(raw.alto) ? Math.max(COLUMN_MIN_HEIGHT, raw.alto) : undefined;
  return {
    hijos: Array.isArray(raw.hijos)
      ? [...new Set(raw.hijos.filter((id): id is string => typeof id === 'string' && id.length > 0))].slice(0, MAX_COLUMN_CHILDREN)
      : [],
    plegada: raw.plegada === true,
    ...(alto !== undefined ? { alto } : {}),
    ordenExplicito: raw.ordenExplicito === true,
  };
}

export function normalizeColumnData(value: unknown, selfId: string, cardIds: ReadonlySet<string>): ColumnData {
  const raw = isRecord(value) ? value : {};
  const alto = typeof raw.alto === 'number' && Number.isFinite(raw.alto) ? Math.min(100000, Math.max(COLUMN_MIN_HEIGHT, raw.alto)) : undefined;
  return {
    hijos: Array.isArray(raw.hijos)
      ? [...new Set(raw.hijos.filter((id): id is string => typeof id === 'string' && id !== selfId && cardIds.has(id)))].slice(0, MAX_COLUMN_CHILDREN)
      : [],
    plegada: raw.plegada === true,
    ...(alto !== undefined ? { alto } : {}),
    ordenExplicito: raw.ordenExplicito === true,
  };
}

export function setColumnFolded(cards: BoardCard[], cardId: string, plegada: boolean): BoardCard[] {
  let changed = false;
  const next = cards.map((card) => {
    if (card.id !== cardId || !esColumna(card)) return card;
    const data = readColumnData(card);
    if (data.plegada === plegada) return card;
    changed = true;
    return { ...card, datos: { ...card.datos, ...data, plegada } };
  });
  return changed ? next : cards;
}

export function setColumnChildren(cards: BoardCard[], cardId: string, hijos: string[]): BoardCard[] {
  return cards.map((card) => {
    if (card.id !== cardId || !esColumna(card)) return card;
    const data = readColumnData(card);
    return { ...card, datos: { ...card.datos, ...data, hijos: [...new Set(hijos)], ordenExplicito: true } };
  });
}

/** Reordena un hijo dentro de la columna; el orden queda explícito en `datos.hijos`. */
export function reordenarHijoDeColumna(cards: BoardCard[], cardId: string, hijoId: string, destinoId: string): BoardCard[] {
  return cards.map((card) => {
    if (card.id !== cardId || !esColumna(card)) return card;
    const data = readColumnData(card);
    const actual = data.hijos.filter((id) => id !== hijoId);
    const indice = actual.indexOf(destinoId);
    if (indice < 0) return card;
    actual.splice(indice, 0, hijoId);
    return { ...card, datos: { ...card.datos, ...data, hijos: actual, ordenExplicito: true } };
  });
}

/** Quita un hijo de la columna sin borrar la tarjeta. */
export function quitarHijoDeColumna(cards: BoardCard[], cardId: string, hijoId: string): BoardCard[] {
  return cards.map((card) => {
    if (card.id !== cardId || !esColumna(card)) return card;
    const data = readColumnData(card);
    if (!data.hijos.includes(hijoId)) return card;
    return { ...card, datos: { ...card.datos, ...data, hijos: data.hijos.filter((id) => id !== hijoId), ordenExplicito: true } };
  });
}

/** Ids de tarjetas que ya se pintan dentro de alguna columna (no se dibujan en el lienzo). */
export function columnChildIds(cards: BoardCard[]): Set<string> {
  const ids = new Set<string>();
  for (const card of cards) {
    if (!esColumna(card)) continue;
    for (const id of readColumnData(card).hijos) ids.add(id);
  }
  return ids;
}
