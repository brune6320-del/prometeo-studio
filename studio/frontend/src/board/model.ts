import { normalizeFrameData, readFrameData } from './frames';
import { normalizeColumnData } from './columnas';

export type BoardCardType = 'note' | 'link' | 'media' | (string & {});
export type BoardMediaKind = 'image' | 'video' | 'audio' | 'file';

export interface BoardMedia {
  name: string;
  mimeType: string;
  dataUrl: string;
  kind: BoardMediaKind;
}

export interface BoardCard {
  id: string;
  type: BoardCardType;
  title: string;
  body: string;
  x: number;
  y: number;
  width: number;
  /** Alto libre de una imagen o vídeo; las tarjetas de papel lo calculan solas. */
  height?: number;
  color: 'paper' | 'sand' | 'sage' | 'rose';
  url?: string;
  media?: BoardMedia;
  /** Una tarjeta bloqueada no se mueve, no se borra y no entra en una selección de arrastre. */
  locked?: boolean;
  /** Campos propios de una herramienta; se guardan acotados y sin interpretar. */
  datos?: Record<string, unknown>;
}

export type BoardRelationTone = 'ember' | 'sage' | 'sky' | 'rose';

export interface BoardRelation {
  id: string;
  from: string;
  to: string;
  /** Etiqueta opcional sobre la curva (doble clic en el conector). */
  label?: string;
  tone?: BoardRelationTone;
}

export interface BoardDocument {
  schemaVersion: 1;
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  cards: BoardCard[];
  relations: BoardRelation[];
}

export interface BoardExport {
  format: 'prometeo-studio-board';
  schemaVersion: 1;
  exportedAt: string;
  board: BoardDocument;
}

export const MAX_MEDIA_BYTES = 12 * 1024 * 1024;
export const MAX_MEDIA_DATA_URL_CHARS = Math.ceil(MAX_MEDIA_BYTES * 4 / 3) + 1024;

let fallbackId = 0;

export function newBoardId(prefix = 'board'): string {
  const random = globalThis.crypto?.randomUUID?.();
  return `${prefix}-${random ?? `${Date.now().toString(36)}-${++fallbackId}`}`;
}

export function createBoard(title = 'Mi tablero'): BoardDocument {
  const now = new Date().toISOString();
  return {
    schemaVersion: 1,
    id: newBoardId(),
    title,
    createdAt: now,
    updatedAt: now,
    cards: [],
    relations: [],
  };
}

export function createCard(type: BoardCardType, x: number, y: number): BoardCard {
  const common = {
    id: newBoardId('card'),
    type,
    title: type === 'note' ? 'Nueva nota' : type === 'link' ? 'Nuevo enlace' : 'Nuevo recurso',
    body: '',
    x,
    y,
    width: type === 'media' ? 290 : 260,
    color: 'paper' as const,
  };
  return type === 'link' ? { ...common, url: '' } : common;
}

export function createMediaCard(x: number, y: number, media: BoardMedia): BoardCard {
  return {
    ...createCard('media', x, y),
    title: media.name.replace(/\.[^.]+$/, '') || 'Recurso',
    media,
  };
}

export function isSafeExternalUrl(value: string): boolean {
  try {
    const url = new URL(value.trim());
    return url.protocol === 'https:' || url.protocol === 'http:';
  } catch {
    return false;
  }
}

export function makeBoardExport(board: BoardDocument): BoardExport {
  return {
    format: 'prometeo-studio-board',
    schemaVersion: 1,
    exportedAt: new Date().toISOString(),
    board,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function boundedText(value: unknown, fallback: string, limit: number): string {
  return (typeof value === 'string' ? value : fallback).slice(0, limit);
}

function boundedNumber(value: unknown, fallback: number, min: number, max: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : fallback;
}

const MAX_DATOS_BYTES = 120_000;

/** Copia acotada de los datos de una herramienta: sin funciones, sin ciclos y sin crecer sin freno. */
export function normalizeDatos(value: unknown): Record<string, unknown> | undefined {
  if (!isRecord(value)) return undefined;
  try {
    const serialized = JSON.stringify(value);
    if (serialized.length > MAX_DATOS_BYTES) return undefined;
    const copy = JSON.parse(serialized);
    return isRecord(copy) ? copy : undefined;
  } catch {
    return undefined;
  }
}

function normalizeMedia(value: unknown): BoardMedia | undefined {
  if (!isRecord(value)) return undefined;
  const dataUrl = typeof value.dataUrl === 'string' ? value.dataUrl : '';
  const mimeType = typeof value.mimeType === 'string' ? value.mimeType.slice(0, 100) : '';
  const name = boundedText(value.name, 'recurso', 180);
  if (!dataUrl.startsWith(`data:${mimeType};base64,`) || dataUrl.length > MAX_MEDIA_DATA_URL_CHARS) return undefined;
  const kind: BoardMediaKind = mimeType.startsWith('image/') ? 'image' : mimeType.startsWith('video/') ? 'video' : mimeType.startsWith('audio/') ? 'audio' : 'file';
  return { name, mimeType, dataUrl, kind };
}

export function normalizeBoard(value: unknown): BoardDocument | null {
  if (!isRecord(value) || !Array.isArray(value.cards) || !Array.isArray(value.relations)) return null;
  // Una versión posterior no se reinterpreta como v1: se rechaza para no sobrescribir datos que no entendemos.
  if (typeof value.schemaVersion === 'number' && value.schemaVersion > 1) return null;
  const usedIds = new Set<string>();
  const cards: BoardCard[] = [];

  for (const entry of value.cards) {
    if (!isRecord(entry)) continue;
    let id = boundedText(entry.id, '', 120).trim();
    if (!id || usedIds.has(id)) id = newBoardId('card');
    usedIds.add(id);
    const requestedType = boundedText(entry.type, 'note', 60).trim();
    // Un tipo que esta versión no conoce se conserva tal cual: la tarjeta se pinta como
    // «herramienta no instalada» y sus datos no se pierden al volver a guardar.
    const type: BoardCardType = requestedType || 'note';
    const knownType = type === 'note' || type === 'link' || type === 'media';
    const media = normalizeMedia(entry.media);
    const url = boundedText(entry.url, '', 2048).trim();
    const card: BoardCard = {
      id,
      type: type === 'media' && !media ? 'note' : type,
      title: boundedText(entry.title, 'Nueva tarjeta', 200),
      body: boundedText(entry.body, '', 12000),
      x: boundedNumber(entry.x, 120, -100000, 100000),
      y: boundedNumber(entry.y, 120, -100000, 100000),
      // Un marco puede ser más ancho que una tarjeta: su vista «Libre» contiene varias columnas.
      width: type === 'marco' || type === 'columna'
        ? boundedNumber(entry.width, 520, 210, 2400)
        : boundedNumber(entry.width, 260, 210, 440),
      color: entry.color === 'sand' || entry.color === 'sage' || entry.color === 'rose' ? entry.color : 'paper',
    };
    if (entry.locked === true) card.locked = true;
    const datos = normalizeDatos(entry.datos);
    if (datos) card.datos = datos;
    if (type === 'media' && (media?.kind === 'image' || media?.kind === 'video')) {
      card.width = boundedNumber(entry.width, 420, 120, 1200);
      card.height = boundedNumber(entry.height, Math.round(card.width * 0.75), 60, 2400);
    }
    if (type === 'link') card.url = isSafeExternalUrl(url) ? url : '';
    if (media && type === 'media') card.media = media;
    if (!knownType) {
      // Sin herramienta instalada no se interpreta el contenido: se guarda literal.
      if (url) card.url = url;
      if (media) card.media = media;
      const reserved = new Set(['id', 'type', 'title', 'body', 'x', 'y', 'width', 'height', 'color', 'url', 'media', 'datos', 'locked']);
      const extras = Object.fromEntries(Object.entries(entry).filter(([key]) => !reserved.has(key)));
      const propios = { ...(isRecord(card.datos) ? card.datos : {}), ...extras };
      if (Object.keys(propios).length > 0) card.datos = propios;
    }
    cards.push(card);
  }

  const cardIds = new Set(cards.map((card) => card.id));
  // Un marco guarda solo ids: al cargar se descartan los que ya no existen y se acota su alto.
  const normalizedCards = cards.map((card) => {
    const raw = isRecord(card.datos) ? card.datos : {};
    if (card.type === 'marco') return { ...card, datos: { ...raw, ...normalizeFrameData(raw, card.id, cardIds) } };
    if (card.type === 'columna') return { ...card, datos: { ...raw, ...normalizeColumnData(raw, card.id, cardIds) } };
    return card;
  });
  const relationIds = new Set<string>();
  const relations: BoardRelation[] = [];
  for (const entry of value.relations) {
    if (!isRecord(entry)) continue;
    const from = boundedText(entry.from, '', 120);
    const to = boundedText(entry.to, '', 120);
    if (!cardIds.has(from) || !cardIds.has(to) || from === to) continue;
    const key = [from, to].sort().join(':');
    if (relationIds.has(key)) continue;
    relationIds.add(key);
    const label = boundedText(entry.label, '', 160).trim();
    const tone = entry.tone === 'sage' || entry.tone === 'sky' || entry.tone === 'rose' ? entry.tone : 'ember';
    relations.push({
      id: boundedText(entry.id, '', 120) || newBoardId('relation'),
      from,
      to,
      ...(label ? { label } : {}),
      ...(tone !== 'ember' ? { tone } : {}),
    });
  }

  return {
    schemaVersion: 1,
    id: boundedText(value.id, '', 120) || newBoardId(),
    title: boundedText(value.title, 'Mi tablero', 120),
    createdAt: boundedText(value.createdAt, new Date().toISOString(), 80),
    updatedAt: boundedText(value.updatedAt, new Date().toISOString(), 80),
    cards: normalizedCards,
    relations,
  };
}

export function parseBoardImport(value: unknown): BoardDocument | null {
  if (!isRecord(value)) return null;
  if (value.format === 'prometeo-studio-board' && value.schemaVersion === 1) return normalizeBoard(value.board);
  return normalizeBoard(value);
}

export function cloneBoardForImport(board: BoardDocument): BoardDocument {
  const copy = normalizeBoard(board);
  if (!copy) return createBoard(`${board.title} (importado)`);
  const idMap = new Map(copy.cards.map((card) => [card.id, newBoardId('card')]));
  return {
    ...copy,
    id: newBoardId(),
    title: `${copy.title} (importado)`.slice(0, 120),
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    cards: copy.cards.map((card) => {
      const mapped = { ...card, id: idMap.get(card.id)! };
      if (card.type === 'marco') {
        const data = readFrameData(card);
        const raw = isRecord(card.datos) ? card.datos : {};
        mapped.datos = {
          ...raw,
          ...data,
          hijos: data.hijos.map((id) => idMap.get(id)).filter((id): id is string => Boolean(id)),
        };
      }
      return mapped;
    }),
    relations: copy.relations.map((relation) => ({
      id: newBoardId('relation'),
      from: idMap.get(relation.from)!,
      to: idMap.get(relation.to)!,
    })),
  };
}

/**
 * Copia tarjetas para Alt+arrastrar. Remapea ids, hijos de marcos y columnas,
 * y las relaciones internas del grupo; las externas se quedan fuera.
 */
export function duplicateCards(
  cards: BoardCard[],
  relations: BoardRelation[],
  ids: string[],
  offset: { x: number; y: number },
): { cards: BoardCard[]; relations: BoardRelation[]; idMap: Map<string, string>; newIds: string[] } {
  const selected = new Set(ids);
  const idMap = new Map<string, string>();
  for (const card of cards) {
    if (selected.has(card.id)) idMap.set(card.id, newBoardId('card'));
  }
  const copies = cards
    .filter((card) => selected.has(card.id))
    .map((card) => {
      const datos = normalizeDatos(card.datos);
      if (datos && Array.isArray(datos.hijos)) {
        datos.hijos = datos.hijos
          .map((id) => (typeof id === 'string' ? idMap.get(id) : undefined))
          .filter((id): id is string => Boolean(id));
      }
      return {
        ...card,
        id: idMap.get(card.id)!,
        x: card.x + offset.x,
        y: card.y + offset.y,
        locked: false,
        ...(datos ? { datos } : {}),
      };
    });
  const newIds = copies.map((card) => card.id);
  const internal = relations.filter((relation) => selected.has(relation.from) && selected.has(relation.to));
  return {
    cards: copies,
    newIds,
    idMap,
    relations: internal.map((relation) => ({
      ...relation,
      id: newBoardId('relation'),
      from: idMap.get(relation.from)!,
      to: idMap.get(relation.to)!,
    })),
  };
}

function cleanMarkdownHeading(value: string): string {
  return value.replace(/[\r\n]+/g, ' ').replace(/^#+\s*/, '').trim() || 'Sin título';
}

export interface BoardMarkdownOptions {
  /**
   * Una herramienta con exportador propio (p. ej. Referente) aporta su bloque.
   * Devolver `null` deja que se use el bloque genérico.
   */
  cardMarkdown?: (card: BoardCard) => string | null;
}

export function boardToMarkdown(board: BoardDocument, options: BoardMarkdownOptions = {}): string {
  const cardsById = new Map(board.cards.map((card) => [card.id, card]));
  const sections = board.cards.map((card) => {
    const propio = options.cardMarkdown?.(card);
    if (propio) return propio.trimEnd();
    const relations = board.relations
      .filter((relation) => relation.from === card.id || relation.to === card.id)
      .map((relation) => cardsById.get(relation.from === card.id ? relation.to : relation.from))
      .filter((target): target is BoardCard => Boolean(target));
    const content: string[] = [`## ${cleanMarkdownHeading(card.title)}`, ''];
    if (card.type === 'link' && card.url && isSafeExternalUrl(card.url)) content.push(`[Abrir enlace](${card.url})`, '');
    if (card.body.trim()) content.push(card.body.trim(), '');
    if (card.type === 'media' && card.media) content.push(`> Adjunto: ${card.media.name} (incluido en la exportación JSON del tablero).`, '');
    if (relations.length) {
      content.push('### Relaciones', ...relations.map((target) => `- [[${cleanMarkdownHeading(target.title)}]]`), '');
    }
    return content.join('\n').trimEnd();
  });
  return [
    '---',
    'prometeo_board: 1',
    `title: "${board.title.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/[\r\n]/g, ' ')}"`,
    '---',
    '',
    `# ${cleanMarkdownHeading(board.title)}`,
    '',
    ...sections,
    '',
  ].join('\n');
}

export function markdownToBoard(markdown: string): BoardDocument | null {
  const source = markdown.replace(/^---\r?\n[\s\S]*?\r?\n---\s*/m, '');
  const lines = source.split(/\r?\n/);
  const titleLine = lines.find((line) => /^#\s+/.test(line));
  const title = titleLine ? cleanMarkdownHeading(titleLine.replace(/^#\s+/, '')) : 'Tablero importado';
  const starts = lines.map((line, index) => ({ line, index })).filter(({ line }) => /^##\s+/.test(line));
  const board = createBoard(title);
  const linksByCard = new Map<string, string[]>();

  for (let i = 0; i < starts.length; i += 1) {
    const start = starts[i];
    const end = starts[i + 1]?.index ?? lines.length;
    const cardTitle = cleanMarkdownHeading(start.line.replace(/^##\s+/, ''));
    const block = lines.slice(start.index + 1, end);
    const relationHeading = block.findIndex((line) => /^###\s+Relaciones\s*$/i.test(line));
    const bodyLines = relationHeading < 0 ? block : block.slice(0, relationHeading);
    const body = bodyLines.filter((line) => !/^\s*<!--\s*prometeo:/i.test(line)).join('\n').trim();
    const linkMatch = body.match(/^\[Abrir enlace\]\((https?:\/\/[^\s)]+)\)$/m);
    const card = createCard(linkMatch && isSafeExternalUrl(linkMatch[1]) ? 'link' : 'note', 4200 + (i % 3) * 320, 4200 + Math.floor(i / 3) * 260);
    card.title = cardTitle;
    card.body = linkMatch ? body.replace(linkMatch[0], '').trim() : body;
    if (linkMatch) card.url = linkMatch[1];
    board.cards.push(card);
    const relationLines = relationHeading < 0 ? [] : block.slice(relationHeading + 1);
    linksByCard.set(card.id, relationLines.flatMap((line) => [...line.matchAll(/\[\[([^\]]+)\]\]/g)].map((match) => cleanMarkdownHeading(match[1]))));
  }

  for (const card of board.cards) {
    for (const titleRef of linksByCard.get(card.id) ?? []) {
      const target = board.cards.find((candidate) => candidate.id !== card.id && candidate.title.toLocaleLowerCase() === titleRef.toLocaleLowerCase());
      if (!target) continue;
      const key = [card.id, target.id].sort().join(':');
      if (!board.relations.some((relation) => [relation.from, relation.to].sort().join(':') === key)) {
        board.relations.push({ id: newBoardId('relation'), from: card.id, to: target.id });
      }
    }
  }
  return board;
}

export function boardFilename(title: string, extension: 'json' | 'md'): string {
  const safe = title.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-zA-Z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 64);
  return `${safe || 'prometeo-board'}.${extension}`;
}
