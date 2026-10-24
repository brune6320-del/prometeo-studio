import { createBoard, createCard, isSafeExternalUrl, type BoardCard, type BoardDocument } from '../model';
import { readFrameData } from '../frames';
import {
  leerReferente,
  normalizarReferente,
  referenteVacio,
  type MedioReferente,
  type Referente,
} from './model';
import { SEMILLA_REFERENTES, type ReferenteSemilla } from './semilla';

export const TITULO_BIBLIOTECA = 'Biblioteca';

const CARD_WIDTH = 320;
const CARD_HEIGHT = 400;
const COLUMNS = 4;
const INNER_GAP = 20;
const FRAME_PADDING = 24;
const FRAME_HEAD = 56;
const FRAME_GAP = 48;
const FRAME_X = 120;
const FRAME_Y = 120;
const FRAME_WIDTH = FRAME_PADDING * 2 + COLUMNS * CARD_WIDTH + (COLUMNS - 1) * INNER_GAP;

export interface ImportarBibliotecaOptions {
  /** Si se indica, solo se reutiliza una «Biblioteca» que ya pertenezca a ese proyecto. */
  projectId?: string;
  projectIdByBoardId?: ReadonlyMap<string, string>;
}

export interface ImportarBibliotecaResult {
  board: BoardDocument;
  created: boolean;
  referentes: number;
  marcos: number;
}

function slug(value: string): string {
  return value
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'sin-nombre';
}

/** El id de la tarjeta sale del id de la semilla: dos importaciones caen en la misma tarjeta. */
export function idTarjetaReferente(seedId: string): string {
  return `referente-${slug(seedId)}`;
}

/** El id del marco sale del vídeo de origen: media 11, media 13 y media 5. */
export function idMarcoVideo(video: string): string {
  return `marco-${slug(video)}`;
}

function etiquetasDeSemilla(item: ReferenteSemilla, base: readonly string[]): string[] {
  const etiquetas = base.filter((etiqueta) => etiqueta !== 'por verificar');
  if (item.verificar) etiquetas.push('por verificar');
  return etiquetas;
}

function actualizarReferente(base: Referente, item: ReferenteSemilla): Referente {
  return normalizarReferente({
    ...base,
    nombre: item.nombre,
    // Una URL ya verificada a mano no se borra porque la semilla la traiga a null.
    url: item.url ?? base.url,
    archivoOrigen: item.video,
    porQue: base.porQue.trim() ? base.porQue : item.que,
    etiquetas: etiquetasDeSemilla(item, base.etiquetas),
  });
}

function crearTarjetaReferente(item: ReferenteSemilla, x: number, y: number, existing?: BoardCard): BoardCard {
  const card = createCard('referente', existing?.x ?? x, existing?.y ?? y);
  card.id = idTarjetaReferente(item.id);
  card.title = item.nombre;
  card.body = item.que;
  card.width = existing?.width ?? CARD_WIDTH;
  card.color = existing?.color ?? 'paper';
  card.datos = {
    ...(existing?.datos ?? {}),
    ...actualizarReferente(existing ? leerReferente(existing) : referenteVacio(), item),
  };
  return card;
}

function crearMarco(
  video: string,
  x: number,
  y: number,
  alto: number,
  hijos: string[],
  existing?: BoardCard,
): BoardCard {
  const card = createCard('marco', existing?.x ?? x, existing?.y ?? y);
  card.id = idMarcoVideo(video);
  card.title = video;
  card.width = existing?.width ?? FRAME_WIDTH;
  card.datos = {
    ...(existing?.datos ?? {}),
    alto: existing ? readFrameData(existing).alto : alto,
    hijos,
    vista: existing ? readFrameData(existing).vista : 'libre',
  };
  return card;
}

function agruparPorVideo(semilla: readonly ReferenteSemilla[]): Array<{ video: string; items: ReferenteSemilla[] }> {
  const groups = new Map<string, ReferenteSemilla[]>();
  const seen = new Set<string>();
  for (const item of semilla) {
    if (!item.id || seen.has(item.id)) continue;
    seen.add(item.id);
    const list = groups.get(item.video) ?? [];
    list.push(item);
    groups.set(item.video, list);
  }
  return [...groups].map(([video, items]) => ({ video, items }));
}

function enProyecto(board: BoardDocument, options: ImportarBibliotecaOptions): boolean {
  if (!options.projectId || !options.projectIdByBoardId) return true;
  return options.projectIdByBoardId.get(board.id) === options.projectId;
}

/**
 * Crea o actualiza el tablero «Biblioteca» a partir de la semilla.
 *
 * - Una tarjeta Referente por archivo de la semilla, con id estable.
 * - Un marco por vídeo de origen (media 11, media 13, media 5) con sus hijos.
 * - Lo que Bruno ya editó (posiciones, imágenes pegadas, lecturas, visto en)
 *   se conserva: esto actualiza la ficha, no la pisa.
 */
export function importarBiblioteca(
  boards: readonly BoardDocument[],
  semilla: readonly ReferenteSemilla[] = SEMILLA_REFERENTES,
  options: ImportarBibliotecaOptions = {},
): ImportarBibliotecaResult {
  const existing = boards.find(
    (board) => board.title.trim().toLocaleLowerCase() === TITULO_BIBLIOTECA.toLocaleLowerCase() && enProyecto(board, options),
  );
  const base = existing ?? createBoard(TITULO_BIBLIOTECA);
  const existingById = new Map(base.cards.map((card) => [card.id, card]));
  const groups = agruparPorVideo(semilla);
  const frames: BoardCard[] = [];
  const referents: BoardCard[] = [];
  let cursorY = FRAME_Y;

  for (const group of groups) {
    const rows = Math.max(1, Math.ceil(group.items.length / COLUMNS));
    const alto = FRAME_HEAD + rows * CARD_HEIGHT + Math.max(0, rows - 1) * INNER_GAP + FRAME_PADDING;
    const frameId = idMarcoVideo(group.video);
    const groupCards = group.items.map((item, index) => {
      const column = index % COLUMNS;
      const row = Math.floor(index / COLUMNS);
      return crearTarjetaReferente(
        item,
        FRAME_X + FRAME_PADDING + column * (CARD_WIDTH + INNER_GAP),
        cursorY + FRAME_HEAD + row * (CARD_HEIGHT + INNER_GAP),
        existingById.get(idTarjetaReferente(item.id)),
      );
    });
    const childIds = groupCards.map((card) => card.id);
    const previousFrame = existingById.get(frameId);
    const extras = previousFrame
      ? readFrameData(previousFrame).hijos.filter((id) => id !== frameId && !childIds.includes(id))
      : [];
    const frame = crearMarco(group.video, FRAME_X, cursorY, alto, [...childIds, ...extras], previousFrame);
    frames.push(frame);
    referents.push(...groupCards);
    cursorY += readFrameData(frame).alto + FRAME_GAP;
  }

  const desiredIds = new Set([...frames, ...referents].map((card) => card.id));
  const preserved = base.cards.filter((card) => !desiredIds.has(card.id));
  const cards = [...frames, ...referents, ...preserved];
  const now = new Date().toISOString();
  const board: BoardDocument = {
    ...base,
    id: base.id,
    title: TITULO_BIBLIOTECA,
    createdAt: base.createdAt,
    updatedAt: now,
    cards,
  };

  return {
    board,
    created: !existing,
    referentes: referents.length,
    marcos: frames.length,
  };
}

const IMAGE_TYPES: Record<string, string> = {
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
  avif: 'image/avif',
  svg: 'image/svg+xml',
  bmp: 'image/bmp',
  tif: 'image/tiff',
  tiff: 'image/tiff',
};

export function tipoImagenDesdeUrl(url: string): string {
  try {
    const extension = new URL(url).pathname.split('.').pop()?.toLocaleLowerCase() ?? '';
    return IMAGE_TYPES[extension] ?? 'image/*';
  } catch {
    return 'image/*';
  }
}

function nombreDesdeUrl(url: string, fecha: string): string {
  try {
    const parts = new URL(url).pathname.split('/').filter(Boolean);
    const last = parts.length ? decodeURIComponent(parts[parts.length - 1]) : '';
    return (last || `imagen-${fecha || 'sin-fecha'}`).slice(0, 180);
  } catch {
    return `imagen-${fecha || 'sin-fecha'}`;
  }
}

/**
 * Pega una URL de imagen en un Referente: añade un medio que apunta a la fuente,
 * con la fecha de hoy. No descarga la imagen ni la convierte en copia.
 * Devuelve `null` si la URL no es http(s) segura.
 */
export function agregarImagenDesdeUrl(
  referente: Referente,
  url: string,
  fecha = new Date().toISOString().slice(0, 10),
): Referente | null {
  const limpia = url.trim();
  if (!limpia || !isSafeExternalUrl(limpia)) return null;
  const actual = normalizarReferente(referente);
  if (actual.imagenes.some((imagen) => imagen.dataUrl === limpia || imagen.fuente === limpia)) return actual;

  const medio: MedioReferente = {
    name: nombreDesdeUrl(limpia, fecha),
    mimeType: tipoImagenDesdeUrl(limpia),
    dataUrl: limpia,
    kind: 'image',
    fuente: limpia,
    fecha: fecha.slice(0, 40),
  };
  return normalizarReferente({ ...actual, imagenes: [...actual.imagenes, medio] });
}
