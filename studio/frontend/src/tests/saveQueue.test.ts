import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createBoard, type BoardDocument } from '../board/model';
import {
  enqueueBoardSave,
  flushBoardWrites,
  getBoardWriteStatus,
  removeBoardFromStore,
  resetBoardWritesForTests,
} from '../board/saveQueue';
import { deleteBoard, saveBoard } from '../board/storage';

vi.mock('../board/storage', () => ({
  saveBoard: vi.fn(),
  saveActiveBoardId: vi.fn(),
  deleteBoard: vi.fn(),
}));

const saveMock = vi.mocked(saveBoard);
const deleteMock = vi.mocked(deleteBoard);

function withTitle(board: BoardDocument, title: string): BoardDocument {
  return { ...board, title };
}

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe('cola de escritura del tablero (Visual V1 · L1)', () => {
  beforeEach(() => {
    saveMock.mockReset();
    deleteMock.mockReset();
    saveMock.mockResolvedValue(undefined);
    deleteMock.mockResolvedValue(undefined);
    resetBoardWritesForTests();
  });

  afterEach(() => {
    resetBoardWritesForTests();
  });

  it('escribe sólo la revisión más reciente cuando hay varias pendientes', async () => {
    const base = createBoard('Tablero');
    enqueueBoardSave(withTitle(base, 'v1'));
    enqueueBoardSave(withTitle(base, 'v2'));
    enqueueBoardSave(withTitle(base, 'v3'));

    expect(await flushBoardWrites()).toBe(true);
    expect(saveMock).toHaveBeenCalledTimes(1);
    expect(saveMock.mock.calls[0][0].title).toBe('v3');
    expect(getBoardWriteStatus()).toEqual({ pending: 0, error: null });
  });

  it('una escritura antigua nunca termina después de una nueva y nunca hay dos a la vez', async () => {
    const base = createBoard('Tablero');
    const order: string[] = [];
    let inFlight = 0;
    let maxInFlight = 0;
    const gate = deferred();
    saveMock.mockImplementation(async (board) => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      if (board.title === 'v1') await gate.promise;
      order.push(board.title);
      inFlight -= 1;
    });

    enqueueBoardSave(withTitle(base, 'v1'));
    const flushing = flushBoardWrites();
    // Llega una revisión nueva mientras la primera aún no se ha confirmado.
    enqueueBoardSave(withTitle(base, 'v2'));
    gate.resolve();

    expect(await flushing).toBe(true);
    expect(order).toEqual(['v1', 'v2']);
    expect(maxInFlight).toBe(1);
    expect(saveMock.mock.calls.at(-1)?.[0].title).toBe('v2');
  });

  it('un error conserva la copia, no marca guardado y el reintento la escribe', async () => {
    const base = createBoard('Tablero');
    saveMock.mockRejectedValueOnce(new Error('disco lleno'));
    enqueueBoardSave(withTitle(base, 'importante'));

    expect(await flushBoardWrites()).toBe(false);
    expect(getBoardWriteStatus()).toEqual({ pending: 1, error: 'disco lleno' });

    expect(await flushBoardWrites()).toBe(true);
    expect(getBoardWriteStatus()).toEqual({ pending: 0, error: null });
    expect(saveMock.mock.calls.at(-1)?.[0].title).toBe('importante');
  });

  it('un fallo no se oculta porque otro tablero se guarde después; se retira al confirmar todo', async () => {
    const a = createBoard('A');
    const b = createBoard('B');
    let failA = true;
    saveMock.mockImplementation(async (board) => {
      if (board.id === a.id && failA) throw new Error('fallo A');
    });

    enqueueBoardSave(a);
    expect(await flushBoardWrites()).toBe(false);
    enqueueBoardSave(b);
    expect(await flushBoardWrites()).toBe(false);
    expect(getBoardWriteStatus()).toEqual({ pending: 2, error: 'fallo A' });

    failA = false;
    expect(await flushBoardWrites()).toBe(true);
    expect(getBoardWriteStatus()).toEqual({ pending: 0, error: null });
  });

  it('un tablero borrado no vuelve a escribirse con sus cambios pendientes', async () => {
    const base = createBoard('Tablero');
    enqueueBoardSave(withTitle(base, 'pendiente'));
    await removeBoardFromStore(base.id);

    expect(deleteMock).toHaveBeenCalledWith(base.id);
    expect(await flushBoardWrites()).toBe(true);
    expect(saveMock).not.toHaveBeenCalled();
  });
});
