import type { BoardCard } from './model';

export interface ColumnData {
  hijos: string[];
  plegada: boolean;
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
  return {
    hijos: Array.isArray(raw.hijos)
      ? [...new Set(raw.hijos.filter((id): id is string => typeof id === 'string' && id.length > 0))].slice(0, MAX_COLUMN_CHILDREN)
      : [],
    plegada: raw.plegada === true,
  };
}

export function normalizeColumnData(value: unknown, selfId: string, cardIds: ReadonlySet<string>): ColumnData {
  const raw = isRecord(value) ? value : {};
  return {
    hijos: Array.isArray(raw.hijos)
      ? [...new Set(raw.hijos.filter((id): id is string => typeof id === 'string' && id !== selfId && cardIds.has(id)))].slice(0, MAX_COLUMN_CHILDREN)
      : [],
    plegada: raw.plegada === true,
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
    return { ...card, datos: { ...card.datos, ...data, hijos: [...new Set(hijos)] } };
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
