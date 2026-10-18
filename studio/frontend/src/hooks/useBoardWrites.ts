import { useSyncExternalStore } from 'react';
import { getBoardWriteStatus, subscribeBoardWrites, type BoardWriteStatus } from '../board/saveQueue';

/** Estado de las escrituras del tablero (pendientes y último error), siempre al día. */
export function useBoardWrites(): BoardWriteStatus {
  return useSyncExternalStore(subscribeBoardWrites, getBoardWriteStatus, getBoardWriteStatus);
}
