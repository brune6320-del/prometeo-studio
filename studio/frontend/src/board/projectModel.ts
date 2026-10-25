import { boardFilename, type BoardDocument } from './model';
import { gustosVacios, normalizarGustos, type Gustos } from './vanguardia/gustos';

export const PROJECT_WORKSPACE_SCHEMA_VERSION = 2 as const;

export interface BoardProject {
  schemaVersion: typeof PROJECT_WORKSPACE_SCHEMA_VERSION;
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  /** Memoria de gusto de la vanguardia (♥/✕). Vive en el proyecto, no en localStorage. */
  gustos: Gustos;
}

export interface BoardProjectLink {
  schemaVersion: typeof PROJECT_WORKSPACE_SCHEMA_VERSION;
  boardId: string;
  projectId: string;
}

export interface PdfReference {
  schemaVersion: typeof PROJECT_WORKSPACE_SCHEMA_VERSION;
  id: string;
  projectId: string;
  boardId: string;
  sourceName: string;
  sourceSha256: string;
  page: number;
  quote: string;
  note: string;
  createdAt: string;
  updatedAt: string;
}

export interface PdfReferenceSource {
  filename: string;
  sha256: string;
  page: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function normalizeBoardIdentifier(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  // Los tableros L1 aceptaban identificadores de texto más amplios. Se conserva el valor exacto
  // para que la capa de proyectos nunca vuelva invisible un tablero legado válido.
  if (!value || value.length > 120 || Array.from(value).some((character) => {
    const code = character.charCodeAt(0);
    return code <= 31 || code === 127;
  })) return null;
  return value;
}

function safeProjectId(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const result = value.trim();
  return /^project-[A-Za-z0-9-]{8,100}$/.test(result) ? result : null;
}

function safePdfReferenceId(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const result = value.trim();
  return /^pdfref-[A-Za-z0-9-]{8,100}$/.test(result) ? result : null;
}

/** Los registros nuevos se rechazan sin reinterpretarlos ni sobrescribirlos. */
export function hasFutureProjectSchema(value: unknown): boolean {
  if (!isRecord(value)) return false;
  return typeof value.schemaVersion === 'number' && value.schemaVersion > PROJECT_WORKSPACE_SCHEMA_VERSION;
}

function cleanSingleLine(value: unknown, fallback: string, limit: number): string {
  if (typeof value !== 'string') return fallback;
  return Array.from(value, (character) => {
    const code = character.charCodeAt(0);
    return code <= 31 || code === 127 ? ' ' : character;
  }).join('').trim().slice(0, limit) || fallback;
}

function cleanContent(value: unknown, limit: number): string {
  if (typeof value !== 'string') return '';
  return Array.from(value.replace(/\r\n?/g, '\n'))
    .filter((character) => {
      const code = character.charCodeAt(0);
      return !(code <= 8 || code === 11 || code === 12 || (code >= 14 && code <= 31) || code === 127);
    })
    .join('')
    .slice(0, limit);
}

function cleanSourceName(value: unknown): string {
  if (typeof value !== 'string') return '';
  const basename = value.replace(/\\/g, '/').split('/').pop() ?? '';
  return cleanSingleLine(basename, '', 180);
}

function validTimestamp(value: unknown): string {
  if (typeof value === 'string' && Number.isFinite(Date.parse(value))) return value.slice(0, 80);
  return new Date().toISOString();
}

export function newProjectId(): string {
  const random = globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36) + Math.random().toString(36).slice(2);
  return 'project-' + random;
}

export function newPdfReferenceId(): string {
  const random = globalThis.crypto?.randomUUID?.() ?? Date.now().toString(36) + Math.random().toString(36).slice(2);
  return 'pdfref-' + random;
}

export function createBoardProject(name: string): BoardProject {
  const now = new Date().toISOString();
  return {
    schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION,
    id: newProjectId(),
    name: cleanSingleLine(name, 'Proyecto nuevo', 120),
    createdAt: now,
    updatedAt: now,
    gustos: gustosVacios(),
  };
}

export function normalizeBoardProject(value: unknown): BoardProject | null {
  if (!isRecord(value) || hasFutureProjectSchema(value)) return null;
  const id = safeProjectId(value.id);
  if (!id || typeof value.name !== 'string') return null;
  return {
    schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION,
    id,
    name: cleanSingleLine(value.name, 'Proyecto sin nombre', 120),
    createdAt: validTimestamp(value.createdAt),
    updatedAt: validTimestamp(value.updatedAt),
    gustos: normalizarGustos(value.gustos),
  };
}

export function normalizeBoardProjectLink(value: unknown): BoardProjectLink | null {
  if (!isRecord(value) || hasFutureProjectSchema(value)) return null;
  const boardId = normalizeBoardIdentifier(value.boardId);
  const projectId = safeProjectId(value.projectId);
  return boardId && projectId ? { schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION, boardId, projectId } : null;
}

export function normalizePdfReference(value: unknown): PdfReference | null {
  if (!isRecord(value) || hasFutureProjectSchema(value)) return null;
  const id = safePdfReferenceId(value.id);
  const projectId = safeProjectId(value.projectId);
  const boardId = normalizeBoardIdentifier(value.boardId);
  const sourceName = cleanSourceName(value.sourceName);
  const sourceSha256 = typeof value.sourceSha256 === 'string' ? value.sourceSha256.toLowerCase() : '';
  const page = value.page;
  if (!id || !projectId || !boardId || !sourceName) return null;
  if (!/^[a-f0-9]{64}$/.test(sourceSha256)) return null;
  if (typeof page !== 'number' || !Number.isInteger(page) || page < 1 || page > 100000) return null;
  return {
    schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION,
    id,
    projectId,
    boardId,
    sourceName,
    sourceSha256,
    page,
    quote: cleanContent(value.quote, 2000),
    note: cleanContent(value.note, 3000),
    createdAt: validTimestamp(value.createdAt),
    updatedAt: validTimestamp(value.updatedAt),
  };
}

export function createPdfReference(input: {
  projectId: string;
  boardId: string;
  source: PdfReferenceSource;
  quote: string;
  note: string;
}): PdfReference | null {
  return normalizePdfReference({
    schemaVersion: PROJECT_WORKSPACE_SCHEMA_VERSION,
    id: newPdfReferenceId(),
    projectId: input.projectId,
    boardId: input.boardId,
    sourceName: input.source.filename,
    sourceSha256: input.source.sha256,
    page: input.source.page,
    quote: input.quote,
    note: input.note,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
}

function escapePlainMarkdown(value: string): string {
  return value.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function cleanHeading(value: string): string {
  const syntax = new Set(['`', '*', '_', '{', '}', '[', ']']);
  return Array.from(escapePlainMarkdown(value.replace(/[\r\n]+/g, ' ').replace(/^#+\s*/, '').trim() || 'Sin título'))
    .map((character) => syntax.has(character) ? '\\' + character : character)
    .join('');
}

function quoteLines(value: string): string[] {
  const escaped = escapePlainMarkdown(value).replace(/([\\`*_[\]{}()#+\-.!|>])/g, '\\$1');
  return escaped.split('\n').map((line) => '> ' + line);
}

export function projectToMarkdown(project: BoardProject, boards: BoardDocument[], references: PdfReference[]): string {
  const title = project.name.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/[\r\n]/g, ' ');
  const lines = [
    '---',
    'prometeo_project: 1',
    'title: "' + title + '"',
    '---',
    '',
    '# ' + cleanHeading(project.name),
    '',
    '## Tableros',
    '',
  ];

  for (const board of boards) {
    const noteName = boardFilename(board.title, 'md').replace(/\.md$/i, '');
    lines.push('- [[' + noteName + ']]');
  }

  lines.push('', '## Referencias PDF', '');
  for (const reference of references) {
    lines.push('### ' + cleanHeading(reference.sourceName) + ' — página ' + reference.page, '');
    if (reference.quote) lines.push(...quoteLines(reference.quote), '');
    if (reference.note) lines.push(...quoteLines(reference.note), '');
    lines.push('> SHA-256: ' + reference.sourceSha256, '');
  }
  return lines.join('\n');
}
