/**
 * Memoria de Prometeo (Forja 4 · H1).
 *
 * No es una papelera visible: es una memoria de 30 días para lo que se borra
 * (tableros, referencias PDF, tarjetas y proyectos) y un almacén del historial
 * de deshacer para que recargar no lo borre. Vive en su propia base para no
 * tocar el formato de los tableros ni invalidar los registros existentes.
 */
import type { BoardDocument } from './model';
import type { BoardHistory } from './history';
import type { PdfReference } from './projectModel';

const DATABASE_NAME = 'prometeo-studio-memoria';
const DATABASE_VERSION = 1;
const BORRADOS_STORE = 'borrados';
const HISTORIAL_STORE = 'historial';

/** 30 días, tal como los pide la auditoría A-1 (D3). */
export const MEMORIA_TTL_MS = 30 * 24 * 60 * 60 * 1000;

export type BorradoKind = 'board' | 'reference' | 'cards' | 'project';

export interface BorradoPayload {
  board?: BoardDocument;
  projectId?: string;
  reference?: PdfReference;
  cards?: { boardId: string; cards: BoardDocument['cards']; relations: BoardDocument['relations'] };
  project?: { name: string };
}

export interface BorradoEntry {
  id: string;
  kind: BorradoKind;
  label: string;
  deletedAt: string;
  expiresAt: string;
  payload: BorradoPayload;
}

export interface NuevaMemoria {
  kind: BorradoKind;
  label: string;
  payload: BorradoPayload;
}

let databasePromise: Promise<IDBDatabase> | null = null;

function openDatabase(): Promise<IDBDatabase> {
  if (databasePromise) return databasePromise;
  databasePromise = new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) {
      reject(new Error('La memoria local no está disponible en este WebView.'));
      return;
    }
    const request = globalThis.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(BORRADOS_STORE)) {
        const store = database.createObjectStore(BORRADOS_STORE, { keyPath: 'id' });
        store.createIndex('deletedAt', 'deletedAt');
      }
      if (!database.objectStoreNames.contains(HISTORIAL_STORE)) {
        database.createObjectStore(HISTORIAL_STORE, { keyPath: 'boardId' });
      }
    };
    request.onsuccess = () => {
      const database = request.result;
      database.onversionchange = () => database.close();
      resolve(database);
    };
    request.onerror = () => {
      databasePromise = null;
      reject(request.error ?? new Error('No se pudo abrir la memoria local.'));
    };
    request.onblocked = () => {
      databasePromise = null;
      reject(new Error('La memoria local está ocupada por otra ventana de Prometeo.'));
    };
  });
  return databasePromise;
}

function transactionFinished(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error ?? new Error('La memoria local canceló la operación.'));
    transaction.onerror = () => reject(transaction.error ?? new Error('No se pudo escribir en la memoria local.'));
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function normalizeEntry(value: unknown): BorradoEntry | null {
  if (!isRecord(value)) return null;
  const kind = value.kind;
  if (kind !== 'board' && kind !== 'reference' && kind !== 'cards' && kind !== 'project') return null;
  if (typeof value.id !== 'string' || typeof value.label !== 'string') return null;
  if (typeof value.deletedAt !== 'string' || typeof value.expiresAt !== 'string') return null;
  return {
    id: value.id,
    kind,
    label: value.label.slice(0, 240),
    deletedAt: value.deletedAt,
    expiresAt: value.expiresAt,
    payload: isRecord(value.payload) ? (value.payload as BorradoPayload) : {},
  };
}

export function memoriaId(): string {
  const random = globalThis.crypto?.randomUUID?.();
  return `mem-${random ?? `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`}`;
}

/** Guarda una entrada; devuelve null si la memoria no está disponible (el borrado sigue siendo válido). */
export async function recordarBorrado(entrada: NuevaMemoria): Promise<BorradoEntry | null> {
  const ahora = new Date();
  const entry: BorradoEntry = {
    id: memoriaId(),
    kind: entrada.kind,
    label: entrada.label.slice(0, 240),
    deletedAt: ahora.toISOString(),
    expiresAt: new Date(ahora.getTime() + MEMORIA_TTL_MS).toISOString(),
    payload: entrada.payload,
  };
  try {
    const database = await openDatabase();
    const transaction = database.transaction(BORRADOS_STORE, 'readwrite');
    transaction.objectStore(BORRADOS_STORE).put(entry);
    await transactionFinished(transaction);
    return entry;
  } catch (error) {
    console.warn('No se pudo recordar el borrado en la memoria de 30 días.', error);
    return null;
  }
}

function expirado(entry: BorradoEntry, ahora = Date.now()): boolean {
  const expires = Date.parse(entry.expiresAt);
  return !Number.isFinite(expires) || expires <= ahora;
}

/** Lista lo recuperable, purgando lo que ya cumplió 30 días. */
export async function listarBorrados(): Promise<BorradoEntry[]> {
  try {
    const database = await openDatabase();
    const transaction = database.transaction(BORRADOS_STORE, 'readwrite');
    const store = transaction.objectStore(BORRADOS_STORE);
    const request = store.getAll();
    const records = await new Promise<unknown[]>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result as unknown[]);
      request.onerror = () => reject(request.error);
    });
    const ahora = Date.now();
    const vigentes: BorradoEntry[] = [];
    for (const record of records) {
      const entry = normalizeEntry(record);
      if (!entry) continue;
      if (expirado(entry, ahora)) store.delete(entry.id);
      else vigentes.push(entry);
    }
    await transactionFinished(transaction);
    return vigentes.sort((a, b) => b.deletedAt.localeCompare(a.deletedAt));
  } catch (error) {
    console.warn('No se pudo leer la memoria de borrados.', error);
    return [];
  }
}

/** Devuelve la entrada y la retira de la memoria: restaurar es un acto explícito. */
export async function tomarBorrado(id: string): Promise<BorradoEntry | null> {
  try {
    const database = await openDatabase();
    const transaction = database.transaction(BORRADOS_STORE, 'readwrite');
    const store = transaction.objectStore(BORRADOS_STORE);
    const request = store.get(id);
    const record = await new Promise<unknown>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
    const entry = normalizeEntry(record);
    if (entry) store.delete(id);
    await transactionFinished(transaction);
    return entry && !expirado(entry) ? entry : null;
  } catch (error) {
    console.warn('No se pudo recuperar el borrado.', error);
    return null;
  }
}

export async function olvidarBorrado(id: string): Promise<void> {
  try {
    const database = await openDatabase();
    const transaction = database.transaction(BORRADOS_STORE, 'readwrite');
    transaction.objectStore(BORRADOS_STORE).delete(id);
    await transactionFinished(transaction);
  } catch (error) {
    console.warn('No se pudo olvidar el borrado.', error);
  }
}

/** Historial de deshacer por tablero. Se guarda acotado para no reventar la cuota. */
const MAX_HISTORIAL_BYTES = 3_500_000;

function compactar(history: BoardHistory): BoardHistory {
  const intento = (undo: BoardHistory['undo']): BoardHistory => ({ undo, redo: history.redo });
  let candidate = intento(history.undo);
  if (JSON.stringify(candidate).length <= MAX_HISTORIAL_BYTES) return candidate;
  for (const limite of [20, 8, 3, 1]) {
    candidate = intento(history.undo.slice(-limite));
    if (JSON.stringify(candidate).length <= MAX_HISTORIAL_BYTES) return candidate;
  }
  return intento(history.undo.slice(-1));
}

export async function guardarHistorial(boardId: string, history: BoardHistory): Promise<void> {
  try {
    const database = await openDatabase();
    const transaction = database.transaction(HISTORIAL_STORE, 'readwrite');
    transaction.objectStore(HISTORIAL_STORE).put({ boardId, history: compactar(history), savedAt: new Date().toISOString() });
    await transactionFinished(transaction);
  } catch (error) {
    console.warn('No se pudo guardar el historial del tablero.', error);
  }
}

export async function leerHistoriales(): Promise<Record<string, BoardHistory>> {
  try {
    const database = await openDatabase();
    const transaction = database.transaction(HISTORIAL_STORE, 'readonly');
    const request = transaction.objectStore(HISTORIAL_STORE).getAll();
    const records = await new Promise<unknown[]>((resolve, reject) => {
      request.onsuccess = () => resolve(request.result as unknown[]);
      request.onerror = () => reject(request.error);
    });
    await transactionFinished(transaction);
    const result: Record<string, BoardHistory> = {};
    for (const record of records) {
      if (!isRecord(record) || typeof record.boardId !== 'string' || !isRecord(record.history)) continue;
      const undo = Array.isArray(record.history.undo) ? record.history.undo : [];
      const redo = Array.isArray(record.history.redo) ? record.history.redo : [];
      result[record.boardId] = { undo: undo as BoardHistory['undo'], redo: redo as BoardHistory['redo'] };
    }
    return result;
  } catch (error) {
    console.warn('No se pudo leer el historial guardado.', error);
    return {};
  }
}

export async function borrarHistorial(boardId: string): Promise<void> {
  try {
    const database = await openDatabase();
    const transaction = database.transaction(HISTORIAL_STORE, 'readwrite');
    transaction.objectStore(HISTORIAL_STORE).delete(boardId);
    await transactionFinished(transaction);
  } catch (error) {
    console.warn('No se pudo borrar el historial guardado.', error);
  }
}

/** Solo pruebas: olvida la conexión para que un contexto nuevo empiece limpio. */
export function resetMemoriaForTests(): void {
  databasePromise = null;
}
