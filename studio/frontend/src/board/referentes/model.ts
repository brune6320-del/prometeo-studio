import { MAX_MEDIA_DATA_URL_CHARS, isSafeExternalUrl, type BoardCard, type BoardMedia } from '../model';

export const REFERENTE_TIPO = 'referente';

/** Una lectura es una propuesta: no cambia nada hasta que Bruno la acepta. */
export interface Lectura {
  fecha: string;
  proyecto: string;
  ojos: string;
  texto: string;
  modelo: string;
  aceptada: boolean;
}

/**
 * Medio de la biblioteca. Puede ser una copia (`data:`) o una referencia a una
 * URL externa pegada por Bruno; en ese caso `fuente` y `fecha` dicen de dónde
 * salió y cuándo se añadió, sin descargarla.
 */
export interface MedioReferente extends BoardMedia {
  fuente?: string;
  fecha?: string;
}

/** Referente de la biblioteca. Vive en `card.datos` y la tarjeta guarda su id. */
export interface Referente {
  nombre: string;
  url: string;
  archivoOrigen: string;
  autor: string;
  anio: string;
  licencia: string;
  porQue: string;
  etiquetas: string[];
  /** Medios de la biblioteca; `imagenes[0]` es la imagen principal. */
  imagenes: MedioReferente[];
  vistoEn: string[];
  lecturas: Lectura[];
}

const MAX_NOMBRE = 200;
const MAX_URL = 2048;
const MAX_ARCHIVO = 500;
const MAX_AUTOR = 200;
const MAX_ANIO = 20;
const MAX_LICENCIA = 200;
const MAX_POR_QUE = 6000;
const MAX_ETIQUETAS = 40;
const MAX_ETIQUETA = 60;
const MAX_VISTO_EN = 400;
const MAX_LECTURAS = 200;
const MAX_TEXTO_LECTURA = 6000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function texto(value: unknown, fallback: string, limit: number): string {
  return (typeof value === 'string' ? value : fallback).slice(0, limit);
}

function listaTexto(value: unknown, limit: number, maxItems: number): string[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const result: string[] = [];
  for (const item of value) {
    if (typeof item !== 'string') continue;
    const limpio = item.trim().slice(0, limit);
    if (!limpio || seen.has(limpio)) continue;
    seen.add(limpio);
    result.push(limpio);
    if (result.length >= maxItems) break;
  }
  return result;
}

function normalizarImagen(value: unknown, index: number): MedioReferente | null {
  if (!isRecord(value)) return null;
  const source = typeof value.dataUrl === 'string' ? value.dataUrl : '';
  const mimeType = texto(value.mimeType, '', 100).trim().toLowerCase();
  if (!mimeType.startsWith('image/')) return null;

  const esCopia = source.startsWith(`data:${mimeType};base64,`);
  const esReferencia = isSafeExternalUrl(source);
  if (!esCopia && !esReferencia) return null;
  if (esCopia && source.length > MAX_MEDIA_DATA_URL_CHARS) return null;
  if (esReferencia && source.length > MAX_URL) return null;

  const imagen: MedioReferente = {
    name: texto(value.name, `imagen-${index + 1}`, 180) || `imagen-${index + 1}`,
    mimeType,
    dataUrl: esReferencia ? source.trim() : source,
    kind: 'image',
  };
  const fuente = texto(value.fuente, '', MAX_URL).trim();
  const fecha = texto(value.fecha, '', 40).trim();
  if (fuente && isSafeExternalUrl(fuente)) imagen.fuente = fuente;
  if (fecha) imagen.fecha = fecha;
  return imagen;
}

function normalizarLectura(value: unknown): Lectura | null {
  if (!isRecord(value)) return null;
  return {
    fecha: texto(value.fecha, '', 40),
    proyecto: texto(value.proyecto, '', 200),
    ojos: texto(value.ojos, '', 200),
    texto: texto(value.texto, '', MAX_TEXTO_LECTURA),
    modelo: texto(value.modelo, '', 200),
    aceptada: value.aceptada === true,
  };
}

export function referenteVacio(): Referente {
  return {
    nombre: '',
    url: '',
    archivoOrigen: '',
    autor: '',
    anio: '',
    licencia: '',
    porQue: '',
    etiquetas: [],
    imagenes: [],
    vistoEn: [],
    lecturas: [],
  };
}

/** Normaliza un referente venido de JSON o de una tarjeta sin fiarse de sus tipos. */
export function normalizarReferente(value: unknown): Referente {
  if (!isRecord(value)) return referenteVacio();
  const anio = typeof value.anio === 'number' && Number.isFinite(value.anio) ? String(value.anio) : value.anio;
  return {
    nombre: texto(value.nombre, '', MAX_NOMBRE).trim(),
    url: texto(value.url, '', MAX_URL).trim(),
    archivoOrigen: texto(value.archivoOrigen, '', MAX_ARCHIVO).trim(),
    autor: texto(value.autor, '', MAX_AUTOR).trim(),
    anio: texto(anio, '', MAX_ANIO).trim(),
    licencia: texto(value.licencia, '', MAX_LICENCIA).trim(),
    porQue: texto(value.porQue, '', MAX_POR_QUE),
    etiquetas: listaTexto(value.etiquetas, MAX_ETIQUETA, MAX_ETIQUETAS),
    imagenes: Array.isArray(value.imagenes)
      ? value.imagenes.map(normalizarImagen).filter((imagen): imagen is BoardMedia => Boolean(imagen))
      : [],
    vistoEn: listaTexto(value.vistoEn, 40, MAX_VISTO_EN),
    lecturas: Array.isArray(value.lecturas)
      ? value.lecturas.map(normalizarLectura).filter((lectura): lectura is Lectura => Boolean(lectura)).slice(0, MAX_LECTURAS)
      : [],
  };
}

export function isLectura(value: unknown): value is Lectura {
  return (
    isRecord(value) &&
    typeof value.fecha === 'string' &&
    typeof value.proyecto === 'string' &&
    typeof value.ojos === 'string' &&
    typeof value.texto === 'string' &&
    typeof value.modelo === 'string' &&
    typeof value.aceptada === 'boolean'
  );
}

export function isReferente(value: unknown): value is Referente {
  return (
    isRecord(value) &&
    typeof value.nombre === 'string' &&
    typeof value.url === 'string' &&
    typeof value.archivoOrigen === 'string' &&
    typeof value.autor === 'string' &&
    typeof value.anio === 'string' &&
    typeof value.licencia === 'string' &&
    typeof value.porQue === 'string' &&
    Array.isArray(value.etiquetas) &&
    value.etiquetas.every((item) => typeof item === 'string') &&
    Array.isArray(value.imagenes) &&
    Array.isArray(value.vistoEn) &&
    value.vistoEn.every((item) => typeof item === 'string') &&
    Array.isArray(value.lecturas) &&
    value.lecturas.every(isLectura)
  );
}

/** Una tarjeta es un referente cuando su tipo lo dice y sus datos tienen la forma esperada. */
export function esTarjetaReferente(value: unknown): value is BoardCard {
  return isRecord(value) && value.type === REFERENTE_TIPO && isReferente(value.datos);
}

/** Lee siempre un referente completo, aunque la tarjeta guardada sea parcial o vieja. */
export function leerReferente(card: unknown): Referente {
  if (isRecord(card) && isRecord(card.datos)) return normalizarReferente(card.datos);
  return referenteVacio();
}

function valorFecha(fecha: string): number {
  const time = Date.parse(fecha);
  return Number.isFinite(time) ? time : 0;
}

/** La última lectura es la de fecha más reciente; con fechas iguales o vacías, la última añadida. */
export function ultimaLectura(referente: Referente): Lectura | undefined {
  let ultima: Lectura | undefined;
  for (const lectura of referente.lecturas) {
    if (!ultima || valorFecha(lectura.fecha) >= valorFecha(ultima.fecha)) ultima = lectura;
  }
  return ultima;
}

function tituloMarkdown(value: string, fallback: string): string {
  return value.replace(/[\r\n]+/g, ' ').replace(/^#+\s*/, '').trim() || fallback;
}

/** Markdown de una tarjeta Referente, con enlace visible a la fuente declarada. */
export function referenteMarkdown(referente: Referente): string {
  const ref = normalizarReferente(referente);
  const lineas: string[] = [`## ${tituloMarkdown(ref.nombre, 'Referente sin nombre')}`, ''];

  if (ref.url && isSafeExternalUrl(ref.url)) lineas.push(`[Fuente](${ref.url})`, '');
  else if (ref.url) lineas.push(`Fuente: ${ref.url}`, '');

  const meta = [ref.archivoOrigen, ref.anio].filter(Boolean).join(' · ');
  if (meta) lineas.push(meta, '');
  if (ref.autor) lineas.push(`**Autor:** ${ref.autor}`);
  if (ref.licencia) lineas.push(`**Licencia:** ${ref.licencia}`);
  if (ref.etiquetas.length) lineas.push(`**Etiquetas:** ${ref.etiquetas.join(', ')}`);
  if (ref.porQue.trim()) lineas.push('', '**Por qué lo guardé**', '', ref.porQue.trim());

  const ultima = ultimaLectura(ref);
  if (ultima) {
    lineas.push('', '### Última lectura', '');
    const quien = [ultima.fecha, ultima.ojos, ultima.proyecto].filter(Boolean).join(' · ');
    if (quien) lineas.push(quien, '');
    if (ultima.texto.trim()) lineas.push(ultima.texto.trim());
  }

  return `${lineas.join('\n').trimEnd()}\n`;
}
