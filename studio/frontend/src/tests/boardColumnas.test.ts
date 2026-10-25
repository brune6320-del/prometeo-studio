import { describe, expect, it } from 'vitest';
import { createBoard, createCard } from '../board/model';
import { normalizeColumnData, quitarHijoDeColumna, readColumnData, reordenarHijoDeColumna } from '../board/columnas';

function columna(hijos: string[], extra: Record<string, unknown> = {}) {
  return {
    ...createCard('columna', 100, 100),
    id: 'col',
    datos: { hijos, plegada: false, ...extra },
  };
}

describe('H6 · columnas con orden explícito', () => {
  it('reordena dentro de datos.hijos y marca el orden como explícito', () => {
    const board = createBoard('columnas');
    board.cards = [columna(['a', 'b', 'c'], { auto: true })];
    const despues = reordenarHijoDeColumna(board.cards, 'col', 'c', 'a');
    const datos = readColumnData(despues[0]);
    expect(datos.hijos).toEqual(['c', 'a', 'b']);
    expect(datos.ordenExplicito).toBe(true);
  });

  it('sacar un hijo no borra la tarjeta ni toca el orden de los demás', () => {
    const board = createBoard('columnas');
    board.cards = [columna(['a', 'b', 'c']), { ...createCard('note', 0, 0), id: 'b' }];
    const despues = quitarHijoDeColumna(board.cards, 'col', 'b');
    expect(readColumnData(despues[0]).hijos).toEqual(['a', 'c']);
    expect(despues.some((card) => card.id === 'b')).toBe(true);
  });

  it('normaliza alto y orden al cargar', () => {
    const datos = normalizeColumnData({ hijos: ['a'], alto: 40, ordenExplicito: true }, 'col', new Set(['a']));
    expect(datos.alto).toBe(150);
    expect(datos.ordenExplicito).toBe(true);
    const sinOrden = normalizeColumnData({ hijos: ['a'] }, 'col', new Set(['a']));
    expect(sinOrden.ordenExplicito).toBe(false);
    expect(sinOrden.alto).toBeUndefined();
  });
});
