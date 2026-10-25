import {
  createBoardProject,
  hasFutureProjectSchema,
  normalizeBoardIdentifier,
  normalizeBoardProject,
  normalizeBoardProjectLink,
  normalizePdfReference,
  PROJECT_WORKSPACE_SCHEMA_VERSION,
  type BoardProject,
  type BoardProjectLink,
  type PdfReference,
} from './projectModel';
import { normalizarGustos, type Gustos } from './vanguardia/gustos';

const DATABASE_NAME = 'prometeo-studio-project-workspace';
const DATABASE_VERSION = 2;
const PROJECTS_STORE = 'projects';
const BOARD_PROJECTS_STORE = 'board-projects';
const PDF_REFERENCES_STORE = 'pdf-references';
const META_STORE = 'meta';
const ACTIVE_PROJECT_KEY = 'active-project-id';
const SCHEMA_VERSION_KEY = 'workspace-schema-version';
const MAX_PROJECTS = 200;
const MAX_PDF_REFERENCES = 5000;

export interface ProjectWorkspaceSnapshot {
  projects: BoardProject[];
  projectIdByBoardId: Map<string, string>;
  activeProjectId: string;
  references: PdfReference[];
  /** Registros desconocidos que siguen intactos en IndexedDB. */
  skipped: Array<{ kind: 'project' | 'board-link' | 'pdf-reference'; id: string; reason: string }>;
  migration: {
    fromVersion: number;
    toVersion: typeof PROJECT_WORKSPACE_SCHEMA_VERSION;
    createdDefaultProject: boolean;
    linkedExistingBoards: number;
  };
}

let databasePromise: Promise<IDBDatabase> | null = null;

function openDatabase(): Promise<IDBDatabase> {
  if (databasePromise) return databasePromise;
  databasePromise = new Promise((resolve, reject) => {
    if (!globalThis.indexedDB) {
      reject(new Error('El almacenamiento local de proyectos no está disponible.'));
      databasePromise = null;
      return;
    }
    const request = globalThis.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      if (!database.objectStoreNames.contains(PROJECTS_STORE)) database.createObjectStore(PROJECTS_STORE, { keyPath: 'id' });
      if (!database.objectStoreNames.contains(BOARD_PROJECTS_STORE)) database.createObjectStore(BOARD_PROJECTS_STORE, { keyPath: 'boardId' });
      const references = database.objectStoreNames.contains(PDF_REFERENCES_STORE)
        ? request.transaction!.objectStore(PDF_REFERENCES_STORE)
        : database.createObjectStore(PDF_REFERENCES_STORE, { keyPath: 'id' });
      if (!references.indexNames.contains('projectId')) references.createIndex('projectId', 'projectId', { unique: false });
      if (!database.objectStoreNames.contains(META_STORE)) database.createObjectStore(META_STORE, { keyPath: 'key' });
    };
    let rejected = false;
    request.onsuccess = () => {
      const database = request.result;
      if (rejected) {
        database.close();
        return;
      }
      database.onversionchange = () => database.close();
      resolve(database);
    };
    request.onerror = () => {
      databasePromise = null;
      const error = request.error;
      if (error?.name === 'VersionError') {
        reject(new Error('Los proyectos fueron creados con una versión más nueva de Prometeo. Se conservan intactos y no se abrirán con esta versión.'));
      } else {
        reject(error ?? new Error('No se pudo abrir el almacenamiento local de proyectos.'));
      }
    };
    request.onblocked = () => {
      rejected = true;
      databasePromise = null;
      reject(new Error('El almacenamiento local de proyectos está ocupado por otra ventana de Prometeo.'));
    };
  });
  return databasePromise;
}

function transactionFinished(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onabort = () => reject(transaction.error ?? new Error('La operación local de proyectos se canceló.'));
    transaction.onerror = () => reject(transaction.error ?? new Error('No se pudo guardar en el espacio de proyectos.'));
  });
}

function recordId(value: unknown, fallback: string): string {
  if (typeof value !== 'object' || value === null) return fallback;
  for (const key of ['id', 'boardId']) {
    const candidate = (value as Record<string, unknown>)[key];
    if (typeof candidate === 'string' && candidate.trim()) return candidate.slice(0, 120);
  }
  return fallback;
}

function schemaVersionFromMeta(value: unknown): number {
  if (value === undefined) return 1;
  if (typeof value !== 'object' || value === null || !('value' in value)) {
    throw new Error('La versión del espacio de proyectos no se reconoce. Los datos se conservan sin cambios.');
  }
  const version = (value as { value?: unknown }).value;
  if (typeof version !== 'number' || !Number.isInteger(version) || version < 1) {
    throw new Error('La versión del espacio de proyectos no se reconoce. Los datos se conservan sin cambios.');
  }
  if (version > PROJECT_WORKSPACE_SCHEMA_VERSION) {
    throw new Error('Los proyectos fueron creados con una versión más nueva de Prometeo. Se conservan intactos y no se abrirán con esta versión.');
  }
  return version;
}

export async function loadProjectWorkspace(boardIds: string[]): Promise<ProjectWorkspaceSnapshot> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction([PROJECTS_STORE, BOARD_PROJECTS_STORE, PDF_REFERENCES_STORE, META_STORE], 'readwrite');
    const finished = transactionFinished(transaction);
    const projectsRequest = transaction.objectStore(PROJECTS_STORE).getAll(undefined, MAX_PROJECTS + 1);
    const linksRequest = transaction.objectStore(BOARD_PROJECTS_STORE).getAll();
    const referencesRequest = transaction.objectStore(PDF_REFERENCES_STORE).getAll(undefined, MAX_PDF_REFERENCES + 1);
    const activeRequest = transaction.objectStore(META_STORE).get(ACTIVE_PROJECT_KEY);
    const schemaRequest = transaction.objectStore(META_STORE).get(SCHEMA_VERSION_KEY);
    let projectValues: unknown[] | null = null;
    let linkValues: unknown[] | null = null;
    let referenceValues: unknown[] | null = null;
    let activeValue: unknown = null;
    let schemaValue: unknown = undefined;
    let received = 0;
    let snapshot: ProjectWorkspaceSnapshot | null = null;
    let settled = false;

    const fail = (error: unknown) => {
      if (settled) return;
      settled = true;
      reject(error instanceof Error ? error : new Error('No se pudo cargar el espacio de proyectos.'));
    };

    const maybePrepare = () => {
      received += 1;
      if (received !== 5) return;
      try {
        const sourceSchemaVersion = schemaVersionFromMeta(schemaValue);
        if ((projectValues ?? []).length > MAX_PROJECTS) {
          throw new Error(`El espacio contiene más de ${MAX_PROJECTS} proyectos. Se conservan todos; no se han modificado.`);
        }
        if ((referenceValues ?? []).length > MAX_PDF_REFERENCES) {
          throw new Error(`El espacio contiene más de ${MAX_PDF_REFERENCES} referencias PDF. Se conservan todas; no se han modificado.`);
        }
        const everyRecord = [...(projectValues ?? []), ...(linkValues ?? []), ...(referenceValues ?? [])];
        if (everyRecord.some(hasFutureProjectSchema)) {
          throw new Error('Hay datos de proyectos creados con una versión más nueva de Prometeo. Se conservan intactos y no se abrirán con esta versión.');
        }
        const skipped: ProjectWorkspaceSnapshot['skipped'] = [];
        const projects = new Map<string, BoardProject>();
        for (const value of projectValues ?? []) {
          const project = normalizeBoardProject(value);
          if (project && !projects.has(project.id)) {
            projects.set(project.id, project);
          } else {
            skipped.push({ kind: 'project', id: recordId(value, '(proyecto sin identificador)'), reason: 'Formato no reconocido o identificador duplicado.' });
          }
        }
        let createdDefaultProject = false;
        if (projects.size === 0) {
          const fallback = createBoardProject('Proyecto general');
          projects.set(fallback.id, fallback);
          transaction.objectStore(PROJECTS_STORE).put(fallback);
          createdDefaultProject = true;
        }

        const projectIdByBoardId = new Map<string, string>();
        for (const value of linkValues ?? []) {
          const link = normalizeBoardProjectLink(value);
          if (link && projects.has(link.projectId) && !projectIdByBoardId.has(link.boardId)) {
            projectIdByBoardId.set(link.boardId, link.projectId);
          } else {
            skipped.push({ kind: 'board-link', id: recordId(value, '(vínculo sin identificador)'), reason: 'Formato no reconocido, proyecto ausente o vínculo duplicado.' });
          }
        }
        const defaultProjectId = projects.keys().next().value as string;
        let linkedExistingBoards = 0;
        for (const rawId of boardIds) {
          const boardId = normalizeBoardIdentifier(rawId);
          if (!boardId || projectIdByBoardId.has(boardId)) continue;
          const link: BoardProjectLink = { schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION, boardId, projectId: defaultProjectId };
          projectIdByBoardId.set(boardId, defaultProjectId);
          transaction.objectStore(BOARD_PROJECTS_STORE).put(link);
          linkedExistingBoards += 1;
        }

        const savedProjectId =
          typeof activeValue === 'object' && activeValue !== null && 'value' in activeValue
            ? (activeValue as { value?: unknown }).value
            : null;
        const activeProjectId = typeof savedProjectId === 'string' && projects.has(savedProjectId) ? savedProjectId : defaultProjectId;
        if (activeProjectId !== savedProjectId) {
          transaction.objectStore(META_STORE).put({ key: ACTIVE_PROJECT_KEY, value: activeProjectId });
        }

        const references: PdfReference[] = [];
        for (const value of referenceValues ?? []) {
          const reference = normalizePdfReference(value);
          if (reference && projects.has(reference.projectId)) {
            references.push(reference);
          } else {
            skipped.push({ kind: 'pdf-reference', id: recordId(value, '(referencia sin identificador)'), reason: 'Formato no reconocido o proyecto ausente.' });
          }
        }
        if (sourceSchemaVersion < PROJECT_WORKSPACE_SCHEMA_VERSION) {
          transaction.objectStore(META_STORE).put({ key: SCHEMA_VERSION_KEY, value: PROJECT_WORKSPACE_SCHEMA_VERSION });
        }
        snapshot = {
          projects: Array.from(projects.values()),
          projectIdByBoardId,
          activeProjectId,
          references,
          skipped,
          migration: {
            fromVersion: sourceSchemaVersion,
            toVersion: PROJECT_WORKSPACE_SCHEMA_VERSION,
            createdDefaultProject,
            linkedExistingBoards,
          },
        };
      } catch (error) {
        try { transaction.abort(); } catch { /* transaction already closed */ }
        fail(error);
      }
    };

    projectsRequest.onsuccess = () => { projectValues = projectsRequest.result as unknown[]; maybePrepare(); };
    linksRequest.onsuccess = () => { linkValues = linksRequest.result as unknown[]; maybePrepare(); };
    referencesRequest.onsuccess = () => { referenceValues = referencesRequest.result as unknown[]; maybePrepare(); };
    activeRequest.onsuccess = () => { activeValue = activeRequest.result; maybePrepare(); };
    schemaRequest.onsuccess = () => { schemaValue = schemaRequest.result; maybePrepare(); };
    projectsRequest.onerror = () => fail(projectsRequest.error);
    linksRequest.onerror = () => fail(linksRequest.error);
    referencesRequest.onerror = () => fail(referencesRequest.error);
    activeRequest.onerror = () => fail(activeRequest.error);
    schemaRequest.onerror = () => fail(schemaRequest.error);

    void finished.then(() => {
      if (!settled && snapshot) {
        settled = true;
        resolve(snapshot);
      } else if (!settled) {
        fail(new Error('La carga del espacio de proyectos quedó incompleta.'));
      }
    }).catch(fail);
  });
}

export async function createProject(name: string): Promise<BoardProject> {
  const project = createBoardProject(name);
  const database = await openDatabase();
  const transaction = database.transaction(PROJECTS_STORE, 'readwrite');
  const finished = transactionFinished(transaction);
  const store = transaction.objectStore(PROJECTS_STORE);
  const countRequest = store.count();
  let tooMany = false;
  countRequest.onsuccess = () => {
    if (countRequest.result >= MAX_PROJECTS) {
      tooMany = true;
      try { transaction.abort(); } catch { /* transaction already closed */ }
      return;
    }
    store.add(project);
  };
  try {
    await finished;
  } catch (error) {
    if (tooMany) throw new Error(`Se alcanzó el límite local de ${MAX_PROJECTS} proyectos.`);
    throw error;
  }
  return project;
}

export async function saveProjectGustos(projectId: string, gustos: Gustos): Promise<void> {
  const database = await openDatabase();
  const transaction = database.transaction(PROJECTS_STORE, 'readwrite');
  const finished = transactionFinished(transaction);
  const store = transaction.objectStore(PROJECTS_STORE);
  const request = store.get(projectId);
  let missing = false;
  request.onsuccess = () => {
    const project = normalizeBoardProject(request.result);
    if (!project) {
      missing = true;
      try { transaction.abort(); } catch { /* transaction already closed */ }
      return;
    }
    store.put({
      ...project,
      gustos: normalizarGustos(gustos),
      updatedAt: new Date().toISOString(),
    } satisfies BoardProject);
  };
  try {
    await finished;
  } catch (error) {
    if (missing) throw new Error('El proyecto ya no existe en el almacenamiento local.');
    throw error;
  }
}

export async function setActiveProject(projectId: string): Promise<void> {
  const database = await openDatabase();
  const transaction = database.transaction([PROJECTS_STORE, META_STORE], 'readwrite');
  const finished = transactionFinished(transaction);
  const request = transaction.objectStore(PROJECTS_STORE).get(projectId);
  let missing = false;
  request.onsuccess = () => {
    const project = normalizeBoardProject(request.result);
    if (!project) {
      missing = true;
      try { transaction.abort(); } catch { /* transaction already closed */ }
      return;
    }
    transaction.objectStore(META_STORE).put({ key: ACTIVE_PROJECT_KEY, value: project.id });
  };
  try {
    await finished;
  } catch (error) {
    if (missing) throw new Error('El proyecto ya no existe en el almacenamiento local.');
    throw error;
  }
}

export async function assignBoardToProject(boardId: string, projectId: string): Promise<void> {
  const safeId = normalizeBoardIdentifier(boardId);
  if (!safeId) throw new Error('El identificador del tablero no es válido.');
  const database = await openDatabase();
  const transaction = database.transaction([PROJECTS_STORE, BOARD_PROJECTS_STORE], 'readwrite');
  const finished = transactionFinished(transaction);
  const request = transaction.objectStore(PROJECTS_STORE).get(projectId);
  let missing = false;
  request.onsuccess = () => {
    const project = normalizeBoardProject(request.result);
    if (!project) {
      missing = true;
      try { transaction.abort(); } catch { /* transaction already closed */ }
      return;
    }
    transaction.objectStore(BOARD_PROJECTS_STORE).put({
      schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION,
      boardId: safeId,
      projectId: project.id,
    } satisfies BoardProjectLink);
  };
  try {
    await finished;
  } catch (error) {
    if (missing) throw new Error('El proyecto ya no existe en el almacenamiento local.');
    throw error;
  }
}

export async function removeBoardProjectLink(boardId: string): Promise<void> {
  const safeId = normalizeBoardIdentifier(boardId);
  if (!safeId) return;
  const database = await openDatabase();
  const transaction = database.transaction(BOARD_PROJECTS_STORE, 'readwrite');
  const finished = transactionFinished(transaction);
  transaction.objectStore(BOARD_PROJECTS_STORE).delete(safeId);
  await finished;
}

export async function savePdfReference(reference: PdfReference): Promise<void> {
  const normalized = normalizePdfReference(reference);
  if (!normalized) throw new Error('La referencia PDF no tiene un formato válido.');
  const database = await openDatabase();
  const transaction = database.transaction([PROJECTS_STORE, BOARD_PROJECTS_STORE, PDF_REFERENCES_STORE], 'readwrite');
  const finished = transactionFinished(transaction);
  const projects = transaction.objectStore(PROJECTS_STORE);
  const links = transaction.objectStore(BOARD_PROJECTS_STORE);
  const references = transaction.objectStore(PDF_REFERENCES_STORE);
  const projectRequest = projects.get(normalized.projectId);
  const linkRequest = links.get(normalized.boardId);
  const existingRequest = references.get(normalized.id);
  const countRequest = references.count();
  let remaining = 4;
  let invalid = '';
  const maybeSave = () => {
    remaining -= 1;
    if (remaining !== 0) return;
    if (!normalizeBoardProject(projectRequest.result)) invalid = 'El proyecto ya no existe en el almacenamiento local.';
    const link = normalizeBoardProjectLink(linkRequest.result);
    if (!link || link.projectId !== normalized.projectId) invalid = 'El tablero ya no pertenece a este proyecto.';
    const current = normalizePdfReference(existingRequest.result);
    if (!current && countRequest.result >= MAX_PDF_REFERENCES) {
      invalid = `Se alcanzó el límite local de ${MAX_PDF_REFERENCES} referencias PDF.`;
    }
    if (invalid) {
      try { transaction.abort(); } catch { /* transaction already closed */ }
      return;
    }
    references.put(normalized);
  };
  for (const request of [projectRequest, linkRequest, existingRequest, countRequest]) {
    request.onsuccess = maybeSave;
    request.onerror = () => {
      invalid = 'No se pudieron validar el proyecto y el tablero.';
      try { transaction.abort(); } catch { /* transaction already closed */ }
    };
  }
  try {
    await finished;
  } catch (error) {
    if (invalid) throw new Error(invalid);
    throw error;
  }
}

export async function deletePdfReference(id: string): Promise<void> {
  if (typeof id !== 'string' || !/^pdfref-[A-Za-z0-9-]{8,100}$/.test(id)) return;
  const database = await openDatabase();
  const transaction = database.transaction(PDF_REFERENCES_STORE, 'readwrite');
  const finished = transactionFinished(transaction);
  transaction.objectStore(PDF_REFERENCES_STORE).delete(id);
  await finished;
}
