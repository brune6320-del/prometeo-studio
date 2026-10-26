import { normalizeBoard, type BoardDocument } from './model';
import { marca, marcaFin } from './marcas';

const DATABASE_NAME = 'prometeo-studio-visual-board';
const DATABASE_VERSION = 1;
const BOARDS_STORE = 'boards';
const META_STORE = 'meta';
const ACTIVE_BOARD_KEY = 'active-board-id';

export interface BoardWorkspaceSnapshot {
  boards: BoardDocument[];
  activeBoardId: string | null;
  /** Registros que no se pudieron leer. Se quedan en IndexedDB sin tocar; nunca se sobrescriben. */
  skipped: { id: string; reason: string }[];
}

let databasePromise: Promise<IDBDatabase> | null = null;

function openDatabase(): Promise<IDBDatabase> {
  if (databasePromise) return databasePromise;
  databasePromise = new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) {
      reject(new Error('El almacenamiento local persistente no está disponible en este WebView.'));
      return;
    }
    const request = globalThis.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(BOARDS_STORE)) database.createObjectStore(BOARDS_STORE, { keyPath: 'id' });
      if (!database.objectStoreNames.contains(META_STORE)) database.createObjectStore(META_STORE, { keyPath: 'key' });
    };
    request.onsuccess = () => {
      const database = request.result;
      database.onversionchange = () => database.close();
      resolve(database);
    };
    request.onerror = () => {
      databasePromise = null;
      reject(request.error ?? new Error('No se pudo abrir el almacenamiento local.'));
    };
    request.onblocked = () => {
      databasePromise = null;
      reject(new Error('El almacenamiento local está ocupado por otra ventana de Prometeo.'));
    };
  });
  return databasePromise;
}

function transactionFinished(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error ?? new Error('La operación local se canceló.'));
    transaction.onerror = () => reject(transaction.error ?? new Error('No se pudo guardar en almacenamiento local.'));
  });
}

function recordId(value: unknown): string {
  return typeof value === 'object' && value !== null && typeof (value as { id?: unknown }).id === 'string'
    ? (value as { id: string }).id
    : '(sin identificador)';
}

export async function loadBoardWorkspace(): Promise<BoardWorkspaceSnapshot> {
  const database = await openDatabase();
  const transaction = database.transaction([BOARDS_STORE, META_STORE], 'readonly');
  const finished = transactionFinished(transaction);
  const boardRequest = transaction.objectStore(BOARDS_STORE).getAll();
  const activeRequest = transaction.objectStore(META_STORE).get(ACTIVE_BOARD_KEY);
  const [records, active] = await Promise.all([
    new Promise<unknown[]>((resolve, reject) => {
      boardRequest.onsuccess = () => resolve(boardRequest.result as unknown[]);
      boardRequest.onerror = () => reject(boardRequest.error ?? new Error('No se pudieron leer los tableros.'));
    }),
    new Promise<{ value: string } | undefined>((resolve, reject) => {
      activeRequest.onsuccess = () => resolve(activeRequest.result as { value: string } | undefined);
      activeRequest.onerror = () => reject(activeRequest.error ?? new Error('No se pudo leer el tablero activo.'));
    }),
  ]);
  await finished;

  const boards: BoardDocument[] = [];
  const skipped: { id: string; reason: string }[] = [];
  for (const record of records) {
    const version = typeof record === 'object' && record !== null ? (record as { schemaVersion?: unknown }).schemaVersion : undefined;
    if (typeof version === 'number' && version > 1) {
      skipped.push({ id: recordId(record), reason: 'Creado con una versión más nueva de Prometeo.' });
      continue;
    }
    const board = normalizeBoard(record);
    if (board) boards.push(board);
    else skipped.push({ id: recordId(record), reason: 'El formato no se reconoce.' });
  }
  const activeBoardId = active?.value && boards.some((board) => board.id === active.value) ? active.value : null;
  return { boards, activeBoardId, skipped };
}

export async function saveBoard(board: BoardDocument): Promise<void> {
  const database = await openDatabase();
  const transaction = database.transaction(BOARDS_STORE, 'readwrite');
  const inicio = marca('autosave:put', `${board.id} · ${board.cards.length} tarjetas · ${board.relations.length} relaciones`);
  transaction.objectStore(BOARDS_STORE).put(board);
  marcaFin('autosave:put:fin', inicio, board.id);
  await transactionFinished(transaction);
}

export async function saveActiveBoardId(id: string): Promise<void> {
  const database = await openDatabase();
  const transaction = database.transaction(META_STORE, 'readwrite');
  transaction.objectStore(META_STORE).put({ key: ACTIVE_BOARD_KEY, value: id });
  await transactionFinished(transaction);
}

export async function deleteBoard(id: string): Promise<void> {
  const database = await openDatabase();
  const transaction = database.transaction(BOARDS_STORE, 'readwrite');
  transaction.objectStore(BOARDS_STORE).delete(id);
  await transactionFinished(transaction);
}
