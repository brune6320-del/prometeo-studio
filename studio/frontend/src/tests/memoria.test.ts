import { describe, expect, it } from 'vitest';
import { compactarHistorial } from '../board/memoria';
import type { BoardHistory } from '../board/history';
import { createBoard, type BoardDocument } from '../board/model';

function tableroConCuerpo(cuerpo: string): BoardDocument {
  const board = createBoard('Prueba');
  return {
    ...board,
    cards: [{ id: 'n0', type: 'note', title: 'Nota', body: cuerpo, x: 0, y: 0, width: 260, color: 'paper' }],
  };
}

function historialDe(pasos: number, bytes: number): BoardHistory {
  const board = tableroConCuerpo('x'.repeat(bytes));
  return {
    undo: Array.from({ length: pasos }, (_, indice) => ({
      before: board,
      after: board,
      coalesceKey: `paso-${indice}`,
      timestamp: indice,
    })),
    redo: [board],
  };
}

describe('historial de 30 días (T-3)', () => {
  it('conserva los pasos más recientes cuando no cabe todo', () => {
    const history = historialDe(100, 2000);
    const compacto = compactarHistorial(history, 20_000);
    expect(compacto.undo.length).toBeGreaterThan(0);
    expect(compacto.undo.length).toBeLessThan(100);
    expect(compacto.undo.at(-1)?.coalesceKey).toBe('paso-99');
    expect(compacto.undo[0]?.coalesceKey).toBe(`paso-${100 - compacto.undo.length}`);
  });

  it('no muta el historial original y conserva redo', () => {
    const history = historialDe(10, 100);
    const compacto = compactarHistorial(history, 100_000);
    expect(compacto.undo).toHaveLength(10);
    expect(compacto.redo).toHaveLength(1);
    expect(history.undo).toHaveLength(10);
  });

  it('siempre conserva al menos el paso más reciente aunque exceda el presupuesto', () => {
    const compacto = compactarHistorial(historialDe(3, 50_000), 1000);
    expect(compacto.undo).toHaveLength(1);
    expect(compacto.undo[0].coalesceKey).toBe('paso-2');
  });

  it('medir desde la caché da el mismo recorte que la primera pasada', () => {
    const history = historialDe(100, 2000);
    const primera = compactarHistorial(history, 20_000);
    const segunda = compactarHistorial(history, 20_000);
    expect(segunda.undo.map((entry) => entry.coalesceKey)).toEqual(primera.undo.map((entry) => entry.coalesceKey));
  });
});
