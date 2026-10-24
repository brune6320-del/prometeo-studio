import type { BoardCard } from '../model';
import { buildMuro, type MuroItem } from './muro';

/**
 * Lectura pura de un marco en la vista «Mesa de luz».
 *
 * Las piezas son las mismas del muro, vistas desde arriba: giro leve derivado de
 * una semilla fija, sombra suave y, si se pide, filas justificadas que respetan
 * el aspecto de cada pieza. Todo se calcula para pintar; las tarjetas del
 * tablero no cambian de posición.
 */

export interface MesaPiece extends MuroItem {
  /** Giro leve en grados, entre -max y +max. */
  rotation: number;
  /** Desplazamiento de mesa en píxeles, solo visual. */
  offsetX: number;
  offsetY: number;
}

export interface JustifiedItem {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface JustifiedRow {
  y: number;
  width: number;
  height: number;
  items: JustifiedItem[];
}

export interface JustifiedLayout {
  width: number;
  height: number;
  rows: JustifiedRow[];
}

/** Hash FNV-1a: barato, estable y suficiente para sembrar un giro. */
export function hashString(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

/** Valor [0, 1) estable para una pieza y una semilla. */
export function seededUnit(id: string, seed: number): number {
  return hashString(`${Math.trunc(seed) || 0}:${id}`) / 4294967296;
}

/** Giro leve y simétrico; la misma semilla da siempre el mismo ángulo. */
export function seededRotation(id: string, seed: number, amplitude = 3.4): number {
  const span = Math.max(0, amplitude);
  return (seededUnit(id, seed) * 2 - 1) * span;
}

/** Piezas de la mesa con su giro y desplazamiento visual derivados de la semilla. */
export function buildMesaPieces(
  cards: readonly BoardCard[],
  childIds: readonly string[],
  seed = 1,
): MesaPiece[] {
  return buildMuro(cards, childIds).map((item) => ({
    ...item,
    rotation: Number(seededRotation(item.id, seed).toFixed(2)),
    offsetX: Number(((seededUnit(`${item.id}:x`, seed) * 2 - 1) * 4).toFixed(2)),
    offsetY: Number(((seededUnit(`${item.id}:y`, seed) * 2 - 1) * 4).toFixed(2)),
  }));
}

/**
 * Filas justificadas: se agrupan piezas a una altura objetivo y cada fila se
 * estira hasta el ancho disponible conservando el aspecto. La última fila también
 * se justifica si no obliga a una altura desmedida; una sola pieza se deja a la
 * altura objetivo para no deformarla.
 */
export function layoutJustifiedRows(
  pieces: readonly Pick<MesaPiece, 'id' | 'aspect'>[],
  width: number,
  rowHeight = 118,
  gap = 8,
): JustifiedLayout {
  const safeWidth = Math.max(1, Number.isFinite(width) ? width : 1);
  const target = Math.max(24, Number.isFinite(rowHeight) ? rowHeight : 118);
  const spacing = Math.max(0, Number.isFinite(gap) ? gap : 0);
  const rows: JustifiedRow[] = [];
  let y = 0;
  let row: Array<Pick<MesaPiece, 'id' | 'aspect'>> = [];
  let rowAspect = 0;

  const closeRow = (current: Array<Pick<MesaPiece, 'id' | 'aspect'>>, last: boolean) => {
    if (current.length === 0) return;
    const available = Math.max(1, safeWidth - spacing * (current.length - 1));
    const justifiedHeight = available / Math.max(0.01, rowAspect);
    const canJustifyLast = current.length > 1 && justifiedHeight <= target * 2.2;
    const height = last && !canJustifyLast ? Math.min(target, justifiedHeight) : justifiedHeight;
    let x = 0;
    const items = current.map((piece) => {
      const itemWidth = Math.max(1, piece.aspect * height);
      const item: JustifiedItem = { id: piece.id, x, y, width: itemWidth, height };
      x += itemWidth + spacing;
      return item;
    });
    rows.push({ y, width: Math.max(0, x - spacing), height, items });
    y += height + spacing;
  };

  for (const piece of pieces) {
    const aspect = Math.max(0.05, Number.isFinite(piece.aspect) ? piece.aspect : 1);
    const nextWidth = aspect * target;
    if (row.length > 0 && rowAspect * target + spacing * row.length + nextWidth > safeWidth) {
      closeRow(row, false);
      row = [];
      rowAspect = 0;
    }
    row.push({ id: piece.id, aspect });
    rowAspect += aspect;
  }
  closeRow(row, true);

  return { width: safeWidth, height: rows.length > 0 ? y - spacing : 0, rows };
}
