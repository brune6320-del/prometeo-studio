/**
 * Cola de escritura del tablero (Visual V1 · L1).
 *
 * - Un solo escritor a la vez: una escritura antigua nunca termina después de una nueva.
 * - Para cada tablero se escribe siempre la revisión más reciente; las intermedias se descartan.
 * - «Guardado» sólo cuando IndexedDB confirmó la revisión vigente.
 * - Un error conserva la copia en memoria: no se descarta nada y reintentar vuelve a encolarla.
 */
import type { BoardDocument } from './model';
import { deleteBoard, saveActiveBoardId, saveBoard } from './storage';

const DEBOUNCE_MS = 400;

export interface BoardWriteStatus {
  /** Número de tableros con una revisión aún no confirmada por el almacenamiento. */
  pending: number;
  /** Último error de escritura; null cuando la última escritura se confirmó. */
  error: string | null;
}

interface PendingBoard {
  board: BoardDocument;
  revision: number;
}

let revisionCounter = 0;
const pending = new Map<string, PendingBoard>();
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setTimeout> | null = null;
let draining: Promise<boolean> | null = null;
let activeQueue: Promise<void> = Promise.resolve();
let lastError: string | null = null;
let status: BoardWriteStatus = { pending: 0, error: null };

function publish(): void {
  const next: BoardWriteStatus = { pending: pending.size, error: lastError };
  if (next.pending === status.pending && next.error === status.error) return;
  status = next;
  listeners.forEach((listener) => listener());
}

function messageOf(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

/** Suscripción para `useSyncExternalStore`. */
export function subscribeBoardWrites(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** Estado instantáneo; la referencia cambia sólo cuando cambia el contenido. */
export function getBoardWriteStatus(): BoardWriteStatus {
  return status;
}

async function drainOnce(): Promise<boolean> {
  while (pending.size > 0) {
    const [id, entry] = pending.entries().next().value as [string, PendingBoard];
    try {
      await saveBoard(entry.board);
    } catch (error) {
      lastError = messageOf(error, 'No se pudo guardar este tablero.');
      publish();
      return false;
    }
    // Si durante la escritura llegó una revisión más nueva, se conserva y se escribirá en la siguiente vuelta.
    if (pending.get(id)?.revision === entry.revision) pending.delete(id);
    publish();
  }
  // El error sólo se retira cuando no queda nada pendiente: un tablero guardado no oculta el fallo de otro.
  lastError = null;
  publish();
  return true;
}

function drain(): Promise<boolean> {
  if (!draining) {
    draining = drainOnce().finally(() => {
      draining = null;
      publish();
    });
  }
  return draining;
}

/**
 * Encola la revisión actual del tablero. La escritura llega tras una pausa corta
 * (o de inmediato con `immediate`); cada nueva revisión reinicia la pausa.
 */
export function enqueueBoardSave(board: BoardDocument, options: { immediate?: boolean } = {}): void {
  revisionCounter += 1;
  pending.set(board.id, { board, revision: revisionCounter });
  publish();
  if (timer !== null) globalThis.clearTimeout(timer);
  timer = globalThis.setTimeout(() => {
    timer = null;
    void drain().catch(() => undefined);
  }, options.immediate ? 0 : DEBOUNCE_MS);
}

/**
 * Resuelve cuando no queda ninguna revisión pendiente. Devuelve false si alguna escritura falló:
 * en ese caso la copia sigue en memoria y no debe considerarse guardada.
 */
export async function flushBoardWrites(): Promise<boolean> {
  if (timer !== null) {
    globalThis.clearTimeout(timer);
    timer = null;
  }
  while (pending.size > 0) {
    const ok = await drain();
    if (!ok) return false;
  }
  return lastError === null;
}

/** Quita el tablero de la cola (sin escribirlo) y lo borra del almacenamiento tras cualquier escritura en curso. */
export async function removeBoardFromStore(id: string): Promise<void> {
  pending.delete(id);
  publish();
  if (draining) await draining.catch(() => false);
  await deleteBoard(id);
}

/**
 * Recuerda el tablero activo. Es una preferencia de navegación, no contenido: si falla no bloquea
 * salir del tablero ni se muestra como error de guardado.
 */
export function rememberActiveBoard(id: string): void {
  activeQueue = activeQueue
    .then(() => saveActiveBoardId(id))
    .catch((error: unknown) => {
      console.warn('No se pudo recordar el tablero activo.', messageOf(error, ''));
    });
}

/** Solo para pruebas: reinicia el estado del módulo. */
export function resetBoardWritesForTests(): void {
  pending.clear();
  lastError = null;
  revisionCounter = 0;
  if (timer !== null) globalThis.clearTimeout(timer);
  timer = null;
  draining = null;
  activeQueue = Promise.resolve();
  status = { pending: 0, error: null };
  listeners.clear();
}
