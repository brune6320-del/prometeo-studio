import type { BoardDocument } from './model';

export interface BoardHistoryEntry {
  before: BoardDocument;
  after: BoardDocument;
  coalesceKey?: string;
  timestamp: number;
}

export interface BoardHistory {
  undo: BoardHistoryEntry[];
  redo: BoardDocument[];
}

export const MAX_BOARD_HISTORY = 100;
const COALESCE_WINDOW_MS = 900;

export function emptyBoardHistory(): BoardHistory {
  return { undo: [], redo: [] };
}

export function recordBoardChange(
  history: BoardHistory,
  before: BoardDocument,
  after: BoardDocument,
  coalesceKey?: string,
  timestamp = Date.now(),
): BoardHistory {
  const undo = [...history.undo];
  const last = undo[undo.length - 1];
  const canCoalesce = Boolean(
    coalesceKey && last?.coalesceKey === coalesceKey && timestamp - last.timestamp <= COALESCE_WINDOW_MS,
  );

  if (canCoalesce && last) {
    undo[undo.length - 1] = { ...last, after, timestamp };
  } else {
    undo.push({ before, after, coalesceKey, timestamp });
  }

  return { undo: undo.slice(-MAX_BOARD_HISTORY), redo: [] };
}

export function undoBoardChange(
  history: BoardHistory,
  current: BoardDocument,
): { history: BoardHistory; board: BoardDocument | null } {
  const entry = history.undo[history.undo.length - 1];
  if (!entry) return { history, board: null };
  return {
    board: { ...entry.before, updatedAt: new Date().toISOString() },
    history: { undo: history.undo.slice(0, -1), redo: [...history.redo, current] },
  };
}

export function redoBoardChange(
  history: BoardHistory,
  current: BoardDocument,
): { history: BoardHistory; board: BoardDocument | null } {
  const board = history.redo[history.redo.length - 1];
  if (!board) return { history, board: null };
  return {
    board: { ...board, updatedAt: new Date().toISOString() },
    history: {
      undo: [...history.undo, { before: current, after: board, timestamp: Date.now() }].slice(-MAX_BOARD_HISTORY),
      redo: history.redo.slice(0, -1),
    },
  };
}
