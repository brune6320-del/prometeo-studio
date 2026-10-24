import type { BoardCard } from './model';
import { DEFAULT_CARD_LAYOUT_HEIGHT, type CardSize } from './geometry';

/**
 * Un marco contiene tarjetas por id, no las copia. Mover el marco mueve a sus hijos
 * y borrar el marco los deja donde están (skill prometeo-herramientas).
 * Las vistas solo cambian cómo se pintan esos hijos: nunca su posición ni sus datos.
 */
export type FrameView = 'libre' | 'archivo' | 'muro' | 'mesa';

const FRAME_VIEWS: readonly FrameView[] = ['libre', 'archivo', 'muro', 'mesa'];

export function normalizeFrameView(value: unknown): FrameView {
  return FRAME_VIEWS.includes(value as FrameView) ? (value as FrameView) : 'libre';
}

export interface FrameData {
  alto: number;
  hijos: string[];
  vista: FrameView;
}

export interface FrameRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export const DEFAULT_FRAME_WIDTH = 520;
export const DEFAULT_FRAME_HEIGHT = 360;
export const FRAME_MIN_SIZE = 80;
export const MAX_FRAME_CHILDREN = 500;

export function isFrameCard(card: BoardCard): boolean {
  return card.type === 'marco';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/** Lee los datos del marco con valores seguros, sin confiar en lo que venga del almacenamiento. */
export function readFrameData(card: BoardCard): FrameData {
  const raw = isRecord(card.datos) ? card.datos : {};
  const alto = typeof raw.alto === 'number' && Number.isFinite(raw.alto)
    ? Math.max(FRAME_MIN_SIZE, raw.alto)
    : DEFAULT_FRAME_HEIGHT;
  const hijos = Array.isArray(raw.hijos)
    ? [...new Set(raw.hijos.filter((id): id is string => typeof id === 'string' && id.length > 0))].slice(0, MAX_FRAME_CHILDREN)
    : [];
  return { alto, hijos, vista: normalizeFrameView(raw.vista) };
}

/** Valida y acota los datos de un marco al cargar; los hijos deben existir en el tablero. */
export function normalizeFrameData(value: unknown, selfId: string, cardIds: ReadonlySet<string>): FrameData {
  const raw = isRecord(value) ? value : {};
  const alto = typeof raw.alto === 'number' && Number.isFinite(raw.alto)
    ? Math.min(100000, Math.max(FRAME_MIN_SIZE, raw.alto))
    : DEFAULT_FRAME_HEIGHT;
  const hijos = Array.isArray(raw.hijos)
    ? [...new Set(raw.hijos.filter(
      (id): id is string => typeof id === 'string' && id !== selfId && cardIds.has(id),
    ))].slice(0, MAX_FRAME_CHILDREN)
    : [];
  return { alto, hijos, vista: normalizeFrameView(raw.vista) };
}

/** Cambia solo la vista del marco; posiciones, hijos y datos de las demás tarjetas no se tocan. */
export function setFrameView(cards: BoardCard[], frameId: string, vista: FrameView): BoardCard[] {
  let changed = false;
  const next = cards.map((card) => {
    if (card.id !== frameId || !isFrameCard(card)) return card;
    const data = readFrameData(card);
    if (data.vista === vista) return card;
    changed = true;
    return { ...card, datos: { ...card.datos, ...data, vista } };
  });
  return changed ? next : cards;
}

export function frameRect(card: BoardCard): FrameRect {
  return { x: card.x, y: card.y, width: card.width, height: readFrameData(card).alto };
}

export function rectFromPoints(a: { x: number; y: number }, b: { x: number; y: number }): FrameRect {
  return {
    x: Math.min(a.x, b.x),
    y: Math.min(a.y, b.y),
    width: Math.abs(b.x - a.x),
    height: Math.abs(b.y - a.y),
  };
}

function sizeOf(card: BoardCard, sizes?: ReadonlyMap<string, CardSize>): CardSize {
  const measured = sizes?.get(card.id);
  return {
    width: measured?.width ?? card.width,
    height: measured?.height ?? DEFAULT_CARD_LAYOUT_HEIGHT,
  };
}

/**
 * Hijos por geometría: una tarjeta queda dentro cuando su centro cae en el rectángulo.
 * Los marcos no se anidan como hijos de otro marco.
 */
export function cardsInsideFrame(
  cards: BoardCard[],
  rect: FrameRect,
  sizes?: ReadonlyMap<string, CardSize>,
): string[] {
  const left = Math.min(rect.x, rect.x + rect.width);
  const right = Math.max(rect.x, rect.x + rect.width);
  const top = Math.min(rect.y, rect.y + rect.height);
  const bottom = Math.max(rect.y, rect.y + rect.height);
  return cards
    .filter((card) => !isFrameCard(card))
    .filter((card) => {
      const size = sizeOf(card, sizes);
      const centerX = card.x + size.width / 2;
      const centerY = card.y + size.height / 2;
      return centerX >= left && centerX <= right && centerY >= top && centerY <= bottom;
    })
    .map((card) => card.id);
}

/** Mueve el marco y sus hijos en bloque, sin mutar el array original. */
export function moveFrameWithChildren(cards: BoardCard[], frameId: string, dx: number, dy: number): BoardCard[] {
  const frame = cards.find((card) => card.id === frameId && isFrameCard(card));
  if (!frame) return cards;
  const ids = new Set([frameId, ...readFrameData(frame).hijos]);
  return cards.map((card) => (ids.has(card.id) ? { ...card, x: card.x + dx, y: card.y + dy } : card));
}

/** Borra solo el marco: las tarjetas que contenía siguen en la pizarra. */
export function removeFrameKeepingChildren(cards: BoardCard[], frameId: string): BoardCard[] {
  return cards.filter((card) => card.id !== frameId);
}

/** Al borrar una tarjeta, se quita su id de todos los marcos sin tocar nada más. */
export function detachCardFromFrames(cards: BoardCard[], cardId: string): BoardCard[] {
  let changed = false;
  const next = cards.map((card) => {
    if (!isFrameCard(card)) return card;
    const data = readFrameData(card);
    if (!data.hijos.includes(cardId)) return card;
    changed = true;
    return { ...card, datos: { ...card.datos, ...data, hijos: data.hijos.filter((id) => id !== cardId) } };
  });
  return changed ? next : cards;
}
