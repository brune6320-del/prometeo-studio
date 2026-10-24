import type { BoardCard } from '../model';
import { buildArchive } from '../archivo';
import { DEFAULT_CARD_LAYOUT_HEIGHT } from '../geometry';

/**
 * Lectura pura de un marco en la vista «Muro».
 *
 * El muro es una hoja de contactos: solo miniaturas de medios, en columnas, con
 * el código que ya aporta la etiqueta anterior (mismo criterio que «Archivo»).
 * No escribe nada en las tarjetas ni en el marco; sus posiciones no se tocan.
 */

export interface MuroItem {
  id: string;
  card: BoardCard;
  /** Código del bloque al que pertenece la pieza (etiqueta o `datos.codigo`). */
  code: string;
  title: string;
  /** Relación ancho/alto usada para equilibrar las columnas. */
  aspect: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function dataString(card: BoardCard, key: string): string {
  const raw = card.datos;
  if (!isRecord(raw)) return '';
  const value = raw[key];
  return typeof value === 'string' ? value.trim() : '';
}

/** Aspecto declarado por la tarjeta si existe; si no, el de su caja actual. */
export function cardAspect(card: BoardCard): number {
  const raw = card.datos;
  if (isRecord(raw)) {
    for (const key of ['aspecto', 'aspect', 'ratio']) {
      const value = raw[key];
      if (typeof value === 'number' && Number.isFinite(value) && value > 0.05 && value < 20) return value;
    }
  }
  return Math.max(0.2, card.width / DEFAULT_CARD_LAYOUT_HEIGHT);
}

/** Piezas del muro: medios del marco, en el orden de sus ids, con el código del bloque. */
export function buildMuro(cards: readonly BoardCard[], childIds: readonly string[]): MuroItem[] {
  const byId = new Map(cards.map((card) => [card.id, card]));
  const codeByItem = new Map<string, string>();
  for (const block of buildArchive(cards, childIds).blocks) {
    for (const item of block.items) {
      codeByItem.set(item.id, block.code || dataString(item, 'codigo'));
    }
  }

  return childIds
    .map((id) => byId.get(id))
    .filter((card): card is BoardCard => Boolean(card))
    .filter((card) => card.type === 'media' || Boolean(card.media))
    .map((card) => ({
      id: card.id,
      card,
      code: codeByItem.get(card.id) || dataString(card, 'codigo'),
      title: card.title.trim() || card.media?.name || 'Sin título',
      aspect: cardAspect(card),
    }));
}

/**
 * Reparto estable por columnas: cada pieza cae en la columna más corta hasta ese
 * momento. Con la misma lista y el mismo número de columnas el resultado es idéntico.
 */
export function distributeMuroColumns(items: readonly MuroItem[], columnCount: number): MuroItem[][] {
  const count = Math.max(1, Math.min(12, Math.trunc(columnCount) || 1));
  const columns: MuroItem[][] = Array.from({ length: count }, () => []);
  const heights = new Array<number>(count).fill(0);

  for (const item of items) {
    let target = 0;
    for (let index = 1; index < count; index += 1) {
      if (heights[index] < heights[target]) target = index;
    }
    columns[target].push(item);
    heights[target] += 1 / Math.max(0.2, item.aspect) + 0.22;
  }

  return columns;
}

/** Número de columnas razonable para el ancho disponible del marco. */
export function muroColumnCount(width: number): number {
  if (!Number.isFinite(width) || width <= 0) return 3;
  return Math.max(2, Math.min(5, Math.floor(width / 110)));
}

/** Orden de lectura del muro: se recorre columna a columna, de arriba abajo. */
export function muroOrder(columns: readonly MuroItem[][]): MuroItem[] {
  return columns.flat();
}

/** Índice circular para la caja de luz: con 0 elementos devuelve -1. */
export function stepIndex(current: number, length: number, delta: number): number {
  if (!Number.isFinite(length) || length <= 0) return -1;
  const size = Math.trunc(length);
  const start = Number.isFinite(current) ? Math.trunc(current) : 0;
  const jump = Number.isFinite(delta) ? Math.trunc(delta) : 0;
  return ((start + jump) % size + size) % size;
}
