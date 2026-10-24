import { describe, expect, it } from 'vitest';
import type { BoardCard } from '../board/model';
import { cloneBoardForImport, normalizeBoard } from '../board/model';
import {
  cardsInsideFrame,
  detachCardFromFrames,
  moveFrameWithChildren,
  readFrameData,
  removeFrameKeepingChildren,
  type FrameRect,
} from '../board/frames';

function card(id: string, x: number, y: number, width = 260): BoardCard {
  return { id, type: 'note', title: id, body: '', x, y, width, color: 'paper' };
}

function frame(id: string, x: number, y: number, width: number, alto: number, hijos: string[]): BoardCard {
  return {
    id,
    type: 'marco',
    title: id,
    body: '',
    x,
    y,
    width,
    color: 'paper',
    datos: { alto, hijos, vista: 'libre' },
  };
}

const RECT: FrameRect = { x: 100, y: 100, width: 600, height: 400 };

describe('marco: hijos, movimiento y borrado', () => {
  it('elige como hijos las tarjetas cuyo centro cae dentro, sin anidar marcos', () => {
    const cards = [
      card('centro-dentro', 500, 150),
      card('fuera', 710, 150),
      frame('otro-marco', 150, 150, 100, 100, []),
    ];
    expect(cardsInsideFrame(cards, RECT)).toEqual(['centro-dentro']);
  });

  it('mueve el marco y sus hijos en bloque sin tocar al resto', () => {
    const cards = [frame('marco', 100, 100, 600, 400, ['a', 'b']), card('a', 200, 150), card('b', 300, 300), card('fuera', 900, 900)];
    const moved = moveFrameWithChildren(cards, 'marco', 50, -20);
    expect(moved.find((item) => item.id === 'marco')).toMatchObject({ x: 150, y: 80 });
    expect(moved.find((item) => item.id === 'a')).toMatchObject({ x: 250, y: 130 });
    expect(moved.find((item) => item.id === 'b')).toMatchObject({ x: 350, y: 280 });
    expect(moved.find((item) => item.id === 'fuera')).toMatchObject({ x: 900, y: 900 });
    expect(cards.find((item) => item.id === 'a')).toMatchObject({ x: 200, y: 150 });
  });

  it('borra el marco y deja a los hijos en la pizarra', () => {
    const cards = [frame('marco', 100, 100, 600, 400, ['a', 'b']), card('a', 200, 150), card('b', 300, 300)];
    const remaining = removeFrameKeepingChildren(cards, 'marco');
    expect(remaining.map((item) => item.id)).toEqual(['a', 'b']);
    expect(remaining[0]).toMatchObject({ x: 200, y: 150 });
    expect(remaining[1]).toMatchObject({ x: 300, y: 300 });
  });

  it('al borrar un hijo se quita su id del marco y los demás siguen dentro', () => {
    const cards = [frame('marco', 100, 100, 600, 400, ['a', 'b']), card('a', 200, 150)];
    const remaining = detachCardFromFrames(cards, 'a');
    expect(readFrameData(remaining.find((item) => item.id === 'marco')!).hijos).toEqual(['b']);
  });

  it('al cargar descarta hijos inexistentes y conserva el alto del marco', () => {
    const loaded = normalizeBoard({
      schemaVersion: 1,
      id: 'b',
      title: 'Marco',
      cards: [
        frame('marco', 100, 100, 600, 320, ['a', 'fantasma', 'marco']),
        card('a', 200, 150),
      ],
      relations: [],
    });
    const marco = loaded?.cards.find((item) => item.type === 'marco');
    expect(marco?.datos).toMatchObject({ alto: 320, hijos: ['a'], vista: 'libre' });
  });

  it('al importar una copia remapea los ids de los hijos del marco', () => {
    const original = normalizeBoard({
      schemaVersion: 1,
      id: 'b',
      title: 'Marco',
      cards: [frame('marco', 100, 100, 600, 400, ['a']), card('a', 200, 150)],
      relations: [],
    })!;
    const copy = cloneBoardForImport(original);
    const marco = copy.cards.find((item) => item.type === 'marco')!;
    const childId = readFrameData(marco).hijos[0];
    expect(copy.cards.some((item) => item.id === childId)).toBe(true);
    expect(childId).not.toBe('a');
  });
});
