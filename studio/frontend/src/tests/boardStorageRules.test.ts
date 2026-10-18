import { describe, expect, it } from 'vitest';
import { createBoard, normalizeBoard, parseBoardImport } from '../board/model';
import { describeBoardUnsaved, unsavedCopy } from '../state/unsaved';

describe('reglas de datos del tablero (Visual V1 · L1)', () => {
  it('una versión posterior no se reinterpreta como v1', () => {
    const future = { ...createBoard('futuro'), schemaVersion: 2 };
    expect(normalizeBoard(future)).toBeNull();
  });

  it('una importación de formato futuro se rechaza', () => {
    const exported = { format: 'prometeo-studio-board', schemaVersion: 2, exportedAt: 'x', board: createBoard('x') };
    expect(parseBoardImport(exported)).toBeNull();
  });

  it('un tablero v1 válido se normaliza sin cambiar su identidad', () => {
    const board = createBoard('ok');
    expect(normalizeBoard(board)?.id).toBe(board.id);
  });

  it('cambios del tablero pendientes son trabajo sin guardar con acción de guardado', () => {
    expect(describeBoardUnsaved(0)).toBeNull();
    const work = describeBoardUnsaved(2);
    expect(work).toEqual({ kind: 'board_unsaved', count: 2 });
    const copy = unsavedCopy(work!, 'close', 'Descargas');
    expect(copy.canSave).toBe(true);
    expect(copy.saveLabel).toBe('Guardar tablero y cerrar');
  });
});
