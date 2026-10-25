import { describe, expect, it } from 'vitest';
import { createBoard } from '../board/model';
import { emptyBoardHistory, recordBoardChange, undoBoardChange } from '../board/history';

describe('historial del tablero: un gesto es un paso (Visual V1 · L1)', () => {
  it('dos gestos rápidos con claves distintas son dos pasos de deshacer', () => {
    const b0 = createBoard('t');
    const b1 = { ...b0, title: 'uno' };
    const b2 = { ...b0, title: 'dos' };
    let history = recordBoardChange(emptyBoardHistory(), b0, b1, 'move:g1', 0);
    history = recordBoardChange(history, b1, b2, 'move:g2', 100);

    expect(history.undo).toHaveLength(2);
    const first = undoBoardChange(history, b2);
    expect(first.board?.title).toBe('uno');
    const second = undoBoardChange(first.history, first.board!);
    expect(second.board?.title).toBe('t');
  });

  it('escribir en el mismo campo dentro de la ventana es un solo paso', () => {
    const b0 = createBoard('t');
    const b1 = { ...b0, title: 'a' };
    const b2 = { ...b0, title: 'ab' };
    let history = recordBoardChange(emptyBoardHistory(), b0, b1, 'card:x:title:1', 0);
    history = recordBoardChange(history, b1, b2, 'card:x:title:1', 200);
    expect(history.undo).toHaveLength(1);
  });

  it('salir del campo cierra el grupo: la siguiente escritura es otro paso', () => {
    const b0 = createBoard('t');
    const b1 = { ...b0, title: 'a' };
    const b2 = { ...b0, title: 'ab' };
    let history = recordBoardChange(emptyBoardHistory(), b0, b1, 'card:x:title:1', 0);
    history = recordBoardChange(history, b1, b2, 'card:x:title:2', 200);
    expect(history.undo).toHaveLength(2);
  });

  it('150 gestos conservan los 100 pasos más recientes (A-1 · Top 1)', () => {
    let board = createBoard('t');
    let history = emptyBoardHistory();
    for (let index = 0; index < 150; index += 1) {
      const next = { ...board, title: `paso ${index}` };
      history = recordBoardChange(history, board, next, `gesto-${index}`, index * 1000);
      board = next;
    }
    expect(history.undo).toHaveLength(100);
    expect(history.undo[0].after.title).toBe('paso 50');
    expect(history.undo[99].after.title).toBe('paso 149');
  });
});
