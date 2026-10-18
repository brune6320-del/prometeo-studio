import type { BoardCard } from './model';

export const DEFAULT_CARD_LAYOUT_HEIGHT = 210;

export interface CardSize {
  width: number;
  height: number;
}

export type Alignment = 'left' | 'center-x' | 'right' | 'top' | 'center-y' | 'bottom';
export type DistributionAxis = 'horizontal' | 'vertical';

function cardSize(card: BoardCard, sizes?: ReadonlyMap<string, CardSize>): CardSize {
  const measured = sizes?.get(card.id);
  return {
    width: measured?.width ?? card.width,
    height: measured?.height ?? DEFAULT_CARD_LAYOUT_HEIGHT,
  };
}

export function alignCards(
  cards: BoardCard[],
  selectedIds: string[],
  alignment: Alignment,
  sizes?: ReadonlyMap<string, CardSize>,
): BoardCard[] {
  const selected = cards.filter((card) => selectedIds.includes(card.id));
  if (selected.length < 2) return cards;

  const bounds = selected.map((card) => {
    const size = cardSize(card, sizes);
    return { card, right: card.x + size.width, bottom: card.y + size.height };
  });
  const left = Math.min(...bounds.map(({ card }) => card.x));
  const right = Math.max(...bounds.map((bound) => bound.right));
  const top = Math.min(...bounds.map(({ card }) => card.y));
  const bottom = Math.max(...bounds.map((bound) => bound.bottom));
  const centerX = (left + right) / 2;
  const centerY = (top + bottom) / 2;
  const positions = new Map<string, { x: number; y: number }>();

  for (const { card } of bounds) {
    const size = cardSize(card, sizes);
    let x = card.x;
    let y = card.y;
    if (alignment === 'left') x = left;
    else if (alignment === 'center-x') x = centerX - size.width / 2;
    else if (alignment === 'right') x = right - size.width;
    else if (alignment === 'top') y = top;
    else if (alignment === 'center-y') y = centerY - size.height / 2;
    else if (alignment === 'bottom') y = bottom - size.height;
    positions.set(card.id, { x, y });
  }

  return cards.map((card) => {
    const position = positions.get(card.id);
    return position ? { ...card, ...position } : card;
  });
}

export function distributeCards(
  cards: BoardCard[],
  selectedIds: string[],
  axis: DistributionAxis,
  sizes?: ReadonlyMap<string, CardSize>,
): BoardCard[] {
  const selected = cards.filter((card) => selectedIds.includes(card.id));
  if (selected.length < 3) return cards;

  const isHorizontal = axis === 'horizontal';
  const ordered = [...selected].sort((a, b) => {
    const primary = isHorizontal ? a.x - b.x : a.y - b.y;
    return primary || a.id.localeCompare(b.id);
  });
  const sizesById = new Map(ordered.map((card) => [card.id, cardSize(card, sizes)]));
  const start = isHorizontal ? ordered[0].x : ordered[0].y;
  const last = ordered[ordered.length - 1];
  const lastSize = sizesById.get(last.id)!;
  const end = isHorizontal ? last.x + lastSize.width : last.y + lastSize.height;
  const totalSize = ordered.reduce((total, card) => {
    const size = sizesById.get(card.id)!;
    return total + (isHorizontal ? size.width : size.height);
  }, 0);
  const gap = (end - start - totalSize) / (ordered.length - 1);
  const positions = new Map<string, { x: number; y: number }>();
  let cursor = start;

  for (const card of ordered) {
    positions.set(card.id, isHorizontal ? { x: cursor, y: card.y } : { x: card.x, y: cursor });
    const size = sizesById.get(card.id)!;
    cursor += (isHorizontal ? size.width : size.height) + gap;
  }

  return cards.map((card) => {
    const position = positions.get(card.id);
    return position ? { ...card, ...position } : card;
  });
}

export function snapPosition(value: number, gridSize = 24): number {
  return Math.round(value / gridSize) * gridSize;
}
