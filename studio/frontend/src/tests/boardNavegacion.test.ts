import { describe, expect, it } from 'vitest';
import { createBoard, createCard } from '../board/model';
import { vecinoGeometrico } from '../board/navegacion';

function tableroCon(posiciones: Array<[string, number, number]>) {
  const board = createBoard('navegación');
  board.cards = posiciones.map(([id, x, y]) => ({ ...createCard('note', x, y), id }));
  return board;
}

describe('H4 · vecino geométrico para Alt+flecha', () => {
  it('recorre una fila en línea recta y prefiere el eje de la flecha', () => {
    const board = tableroCon([['a', 0, 0], ['b', 300, 20], ['c', 600, 0], ['abajo', 20, 300]]);
    expect(vecinoGeometrico(board.cards, 'a', 'derecha')).toBe('b');
    expect(vecinoGeometrico(board.cards, 'b', 'derecha')).toBe('c');
    expect(vecinoGeometrico(board.cards, 'b', 'izquierda')).toBe('a');
    expect(vecinoGeometrico(board.cards, 'a', 'abajo')).toBe('abajo');
    expect(vecinoGeometrico(board.cards, 'a', 'arriba')).toBeNull();
  });

  it('devuelve null sin vecino en esa dirección', () => {
    const board = tableroCon([['a', 0, 0], ['b', 300, 0]]);
    expect(vecinoGeometrico(board.cards, 'b', 'derecha')).toBeNull();
    expect(vecinoGeometrico(board.cards, 'inexistente', 'derecha')).toBeNull();
  });
});
