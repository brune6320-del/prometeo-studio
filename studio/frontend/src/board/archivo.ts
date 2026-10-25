import type { BoardCard } from './model';

/**
 * Lectura pura de los hijos de un marco en la vista «Archivo».
 *
 * Reglas de autoría (sin campos nuevos obligatorios):
 * - La primera nota hija es la NOTA FIJA de la columna izquierda.
 * - Una etiqueta justo antes de un grupo de medios aporta `código` (su cuerpo) y
 *   `estado` (su título) al bloque siguiente.
 * - Cada grupo de medios consecutivos es un bloque con carrusel.
 * - Una nota después de un bloque aporta el texto largo de ese bloque.
 * - Un enlace después del bloque o del texto se muestra como enlace del bloque.
 * - El resto de hijos se pinta como bloque de solo texto, sin perder nada.
 *
 * `datos.codigo`, `datos.estado` y `datos.texto` en la primera pieza del bloque
 * tienen prioridad (los escribe una versión futura; aquí se leen si existen).
 */

export interface ArchiveBlock {
  /** Id estable derivado de la primera pieza del bloque. */
  id: string;
  code: string;
  title: string;
  status: string;
  text: string;
  /** Enlace opcional del bloque (tarjeta de tipo link). */
  url: string;
  /** Diapositivas del carrusel; vacío en bloques de solo texto. */
  items: BoardCard[];
}

export interface ArchiveLayout {
  note: BoardCard | null;
  blocks: ArchiveBlock[];
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function dataString(card: BoardCard, key: string): string {
  const raw = card.datos;
  if (typeof raw !== 'object' || raw === null) return '';
  return text((raw as Record<string, unknown>)[key]);
}

function joinText(left: string, right: string): string {
  if (!left) return right;
  if (!right) return left;
  return `${left}\n\n${right}`;
}

/** Construye nota fija y bloques del feed a partir de los ids de hijos, en su orden. */
export function buildArchive(cards: readonly BoardCard[], childIds: readonly string[]): ArchiveLayout {
  const byId = new Map(cards.map((card) => [card.id, card]));
  const children = childIds
    .map((id) => byId.get(id))
    .filter((card): card is BoardCard => Boolean(card));

  let note: BoardCard | null = null;
  let pendingCode = '';
  let pendingStatus = '';
  let current: ArchiveBlock | null = null;
  let currentClosed = true;
  const blocks: ArchiveBlock[] = [];

  const openBlock = (card: BoardCard): ArchiveBlock => {
    const block: ArchiveBlock = {
      id: `archivo-${card.id}`,
      code: pendingCode || dataString(card, 'codigo'),
      title: text(card.title) || text(card.media?.name),
      status: pendingStatus || dataString(card, 'estado'),
      text: dataString(card, 'texto'),
      url: '',
      items: [],
    };
    pendingCode = '';
    pendingStatus = '';
    currentClosed = false;
    blocks.push(block);
    return block;
  };

  for (const card of children) {
    if (card.type === 'media') {
      if (!current || currentClosed || current.items.length === 0) current = openBlock(card);
      current.items.push(card);
      continue;
    }

    if (card.type === 'note') {
      // La primera nota es siempre la fija, aunque aparezca después de un medio.
      if (!note) {
        note = card;
        continue;
      }
      if (current && !currentClosed && current.items.length > 0) {
        current.text = joinText(current.text, text(card.body));
        currentClosed = true;
        continue;
      }
      blocks.push({
        id: `archivo-${card.id}`,
        code: '',
        title: text(card.title),
        status: '',
        text: text(card.body),
        url: '',
        items: [],
      });
      continue;
    }

    if (card.type === 'etiqueta') {
      // Etiqueta = código (cuerpo) + estado (título) del siguiente grupo de medios.
      pendingCode = text(card.body) || dataString(card, 'codigo');
      pendingStatus = text(card.title);
      current = null;
      currentClosed = true;
      continue;
    }

    if (card.type === 'link') {
      if (current && current.items.length > 0 && !current.url) {
        current.url = text(card.url);
        currentClosed = true;
        continue;
      }
      blocks.push({
        id: `archivo-${card.id}`,
        code: '',
        title: text(card.title),
        status: '',
        text: text(card.body),
        url: text(card.url),
        items: [],
      });
      current = null;
      currentClosed = true;
      continue;
    }

    // Una herramienta desconocida no se descarta: se muestra como bloque de texto.
    blocks.push({
      id: `archivo-${card.id}`,
      code: '',
      title: text(card.title),
      status: '',
      text: text(card.body),
      url: '',
      items: [],
    });
    current = null;
    currentClosed = true;
  }

  for (const block of blocks) {
    if (!block.text && block.items.length > 0) {
      block.text = block.items.map((item) => text(item.body)).filter(Boolean).join('\n\n');
    }
  }

  return { note, blocks };
}

/** Índice del carrusel circular: con 0 elementos siempre 0; con n, envuelve en ambos sentidos. */
export function slideIndex(current: number, length: number, delta: number): number {
  if (!Number.isFinite(length) || length <= 0) return 0;
  const size = Math.trunc(length);
  const start = Number.isFinite(current) ? Math.trunc(current) : 0;
  return ((start + (Number.isFinite(delta) ? Math.trunc(delta) : 0)) % size + size) % size;
}

/** Contador legible del carrusel: «1 / 3»; con lista vacía, «0 / 0». */
export function slideCounter(current: number, length: number): string {
  if (!Number.isFinite(length) || length <= 0) return '0 / 0';
  const size = Math.trunc(length);
  const start = Number.isFinite(current) ? Math.trunc(current) : 0;
  const safe = Math.min(size - 1, Math.max(0, start));
  return `${safe + 1} / ${size}`;
}

function yearFromValue(value: unknown): number | null {
  if (typeof value === 'number' && Number.isInteger(value) && value >= 1900 && value <= 2100) return value;
  if (typeof value !== 'string') return null;
  const match = value.match(/\b(19\d{2}|20\d{2}|2100)\b/);
  if (!match) return null;
  const year = Number(match[1]);
  return year >= 1900 && year <= 2100 ? year : null;
}

/**
 * Año del bloque: primero `datos.año`/`datos.ano`/`datos.year` de sus piezas,
 * después el primer año de cuatro cifras en código, título o texto.
 * Si no hay dato, devuelve null; no se inventa una fecha.
 */
export function blockYear(block: ArchiveBlock): number | null {
  for (const item of block.items) {
    const raw = item.datos;
    if (typeof raw !== 'object' || raw === null) continue;
    for (const key of ['año', 'ano', 'year']) {
      const year = yearFromValue((raw as Record<string, unknown>)[key]);
      if (year !== null) return year;
    }
  }
  for (const value of [block.code, block.title, block.text]) {
    const year = yearFromValue(value);
    if (year !== null) return year;
  }
  return null;
}

export interface YearRow {
  year: number | null;
  label: string;
  blocks: ArchiveBlock[];
}

/**
 * Filas por año, de más reciente a más antiguo y «Sin año» al final.
 * Solo entran bloques con medios: un bloque de solo texto no tiene tira que enseñar.
 */
export function groupBlocksByYear(blocks: readonly ArchiveBlock[]): YearRow[] {
  const rows = new Map<number | null, ArchiveBlock[]>();
  for (const block of blocks) {
    if (block.items.length === 0) continue;
    const year = blockYear(block);
    const list = rows.get(year) ?? [];
    list.push(block);
    rows.set(year, list);
  }
  return [...rows.entries()]
    .sort(([left], [right]) => {
      if (left === null) return 1;
      if (right === null) return -1;
      return right - left;
    })
    .map(([year, list]) => ({ year, label: year === null ? 'Sin año' : String(year), blocks: list }));
}

/** Reloj vivo en formato HH:MM:SS, sin depender del locale del sistema. */
export function formatClock(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

/** Parte el texto en párrafos por líneas en blanco, para pintar el feed como la referencia. */
export function paragraphs(value: string): string[] {
  return value
    .split(/\n\s*\n/)
    .map((part) => part.trim())
    .filter(Boolean);
}
