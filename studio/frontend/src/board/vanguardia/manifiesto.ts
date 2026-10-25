import { studioApi } from '../../api/client';
import { leerReferente } from '../referentes/model';
import {
  newBoardId,
  type BoardCard,
  type BoardDocument,
} from '../model';
import { leerEntropia, type EntropiaDatos, type FuenteEntropia } from './entropia';import { PESO_INICIAL, type Gustos } from './gustos';
import type { ManifiestoRequest } from '../../types';

export const DIAS_SEMANA = 7;
export const MAX_COLLAGES_MANIFIESTO = 9;
export const MAX_LINEAS_MANIFIESTO = 12;
export const MAX_PESOS_MANIFIESTO = 5;

export interface CollageSemana {
  boardId: string;
  cardId: string;
  titulo: string;
  semilla: string;
  regla: string;
  reglaNombre: string;
  restriccion: string;
  creado: string;
  fuentes: string[];
  datos: EntropiaDatos;
}

export interface LecturaSemana {
  boardId: string;
  cardId: string;
  referente: string;
  fecha: string;
  proyecto: string;
  ojos: string;
  texto: string;
}

export interface PesoSemana {
  tipo: 'referente' | 'regla' | 'herramienta' | 'par';
  clave: string;
  etiqueta: string;
  peso: number;
  subida: number;
}

export interface SeleccionManifiesto {
  desde: string;
  hasta: string;
  collages: CollageSemana[];
  lecturas: LecturaSemana[];
  pesos: PesoSemana[];
}

const DIA_MS = 24 * 60 * 60 * 1000;

function esDiaSolo(fecha: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(fecha.trim());
}

function momento(fecha: string): number {
  const valor = Date.parse(fecha);
  return Number.isFinite(valor) ? valor : Number.NaN;
}

/** Una fecha sin hora se considera todo el día: si es hoy, entra en la semana. */
function dentroDeLaSemana(fecha: string, desde: number, hasta: number): boolean {
  const inicio = momento(fecha);
  if (!Number.isFinite(inicio)) return false;
  const fin = esDiaSolo(fecha) ? inicio + DIA_MS - 1 : inicio;
  return fin >= desde && inicio <= hasta;
}

function collagesDe(boards: readonly BoardDocument[]): CollageSemana[] {
  const collages: CollageSemana[] = [];
  for (const board of boards) {
    for (const card of board.cards) {
      const datos = leerEntropia(card);
      if (!datos || !datos.guardado) continue;
      collages.push({
        boardId: board.id,
        cardId: card.id,
        titulo: card.title || `Collage · ${datos.reglaNombre || datos.regla}`,
        semilla: datos.semilla,
        regla: datos.regla,
        reglaNombre: datos.reglaNombre,
        restriccion: datos.restriccion,
        creado: datos.creado,
        fuentes: datos.fuentes,
        datos,
      });
    }
  }
  return collages;
}

function lecturasDe(boards: readonly BoardDocument[]): LecturaSemana[] {
  const lecturas: LecturaSemana[] = [];
  for (const board of boards) {
    for (const card of board.cards) {
      if (card.type !== 'referente') continue;
      const referente = leerReferente(card);
      for (const lectura of referente.lecturas) {
        if (!lectura.aceptada || !lectura.texto.trim()) continue;
        lecturas.push({
          boardId: board.id,
          cardId: card.id,
          referente: referente.nombre || card.title || 'Referente sin nombre',
          fecha: lectura.fecha,
          proyecto: lectura.proyecto,
          ojos: lectura.ojos,
          texto: lectura.texto.trim(),
        });
      }
    }
  }
  return lecturas;
}

function pesosDe(gustos: Gustos): PesoSemana[] {
  const pesos: PesoSemana[] = [];
  const añadir = (tipo: PesoSemana['tipo'], clave: string, peso: number, etiqueta = clave) => {
    if (!clave || !Number.isFinite(peso)) return;
    const subida = peso - PESO_INICIAL;
    if (subida <= 0) return;
    pesos.push({ tipo, clave, etiqueta, peso, subida });
  };
  for (const [clave, peso] of Object.entries(gustos.referentes)) añadir('referente', clave, peso);
  for (const [clave, peso] of Object.entries(gustos.reglas)) añadir('regla', clave, peso);
  for (const [clave, peso] of Object.entries(gustos.herramientas)) añadir('herramienta', clave, peso);
  for (const [clave, peso] of Object.entries(gustos.pares)) añadir('par', clave, peso, clave.replace('|', ' ↔ '));
  return pesos.sort((a, b) => b.subida - a.subida || b.peso - a.peso || a.clave.localeCompare(b.clave));
}

/**
 * Reúne lo que de verdad pasó en los últimos siete días: collages guardados
 * con ♥, lecturas aceptadas y los pesos que subieron por encima del inicial.
 */
export function seleccionarSemana(
  boards: readonly BoardDocument[],
  opciones: { ahora?: Date; gustos?: Gustos } = {},
): SeleccionManifiesto {
  const ahora = opciones.ahora ?? new Date();
  const hasta = ahora.getTime();
  const desde = hasta - DIAS_SEMANA * DIA_MS;

  const collages = collagesDe(boards)
    .filter((collage) => dentroDeLaSemana(collage.creado, desde, hasta))
    .sort((a, b) => momento(b.creado) - momento(a.creado) || a.cardId.localeCompare(b.cardId))
    .slice(0, MAX_COLLAGES_MANIFIESTO);

  const lecturas = lecturasDe(boards)
    .filter((lectura) => dentroDeLaSemana(lectura.fecha, desde, hasta))
    .sort((a, b) => momento(b.fecha) - momento(a.fecha) || a.cardId.localeCompare(b.cardId));

  return {
    desde: new Date(desde).toISOString(),
    hasta: new Date(hasta).toISOString(),
    collages,
    lecturas,
    pesos: pesosDe(opciones.gustos ?? {
      version: 1,
      referentes: {},
      reglas: {},
      herramientas: {},
      pares: {},
    }).slice(0, MAX_PESOS_MANIFIESTO),
  };
}

/** Plantilla de 12 líneas vacías para escribir a mano. */
export function plantillaManifiesto(cantidad = MAX_LINEAS_MANIFIESTO): string[] {
  return Array.from({ length: cantidad }, (_, indice) => `${indice + 1}.`);
}

/**
 * Normaliza la respuesta del modelo: quita vallas, viñetas y numeración vieja,
 * parte párrafos en frases y deja como máximo 12 líneas numeradas.
 */
export function normalizarLineasManifiesto(valor: string | readonly string[] | null | undefined): string[] {
  const bruto = Array.isArray(valor) ? valor.join('\n') : typeof valor === 'string' ? valor : '';
  const limpio = bruto
    .replace(/\r\n/g, '\n')
    .replace(/^```[a-zA-Z0-9_-]*\n?/m, '')
    .replace(/\n?```\s*$/m, '')
    .trim();
  const lineas = limpio
    .split('\n')
    .map((linea) => linea
      .trim()
      .replace(/^#{1,6}\s*/, '')
      .replace(/\*\*(.+?)\*\*/g, '$1')
      .replace(/__(.+?)__/g, '$1')
      .replace(/^(?:\d+[.)]|[-*•])\s*/, '')
      .replace(/sk-[A-Za-z0-9_-]{8,}/g, '[clave oculta]')
      .replace(/Bearer\s+\S+/gi, 'Bearer [oculto]')
      .trim())
    .filter(Boolean);

  let definitivas = lineas;
  if (definitivas.length <= 1 && definitivas[0]) {
    definitivas = definitivas[0].split(/(?<=[.!?…])\s+/).map((linea) => linea.trim()).filter(Boolean);
  }
  return definitivas.slice(0, MAX_LINEAS_MANIFIESTO).map((linea, indice) => `${indice + 1}. ${linea}`);
}

export function pedidoDeSeleccion(seleccion: SeleccionManifiesto, proyecto: string): ManifiestoRequest {
  return {
    proyecto,
    collages: seleccion.collages.map((collage) => {
      const regla = collage.reglaNombre || collage.regla;
      return `${collage.titulo} · ${regla}${collage.restriccion ? ` · ${collage.restriccion}` : ''} · semilla ${collage.semilla}`;
    }),
    lecturas: seleccion.lecturas.map((lectura) => {
      const quien = [lectura.referente, lectura.ojos, lectura.proyecto].filter(Boolean).join(' · ');
      return `${quien}: ${lectura.texto}`;
    }),
    pesos: seleccion.pesos.map((peso) => `${peso.tipo} ${peso.etiqueta}: ${peso.peso.toFixed(1)}`),
  };
}

export interface ResultadoManifiesto {
  disponible: boolean;
  motivo: string;
  modelo: string;
  lineas: string[];
}

/** Pide el manifiesto al motor local. Sin clave o sin red devuelve la plantilla vacía. */
export async function pedirManifiesto(
  seleccion: SeleccionManifiesto,
  proyecto: string,
): Promise<ResultadoManifiesto> {
  try {
    const respuesta = await studioApi.escribirManifiesto(pedidoDeSeleccion(seleccion, proyecto));
    const lineas = normalizarLineasManifiesto(respuesta.lineas ?? []);
    if (respuesta.disponible === false || lineas.length === 0) {
      return {
        disponible: false,
        motivo: respuesta.motivo || 'El manifiesto salió vacío. Escribe las líneas a mano.',
        modelo: '',
        lineas: plantillaManifiesto(),
      };
    }
    return {
      disponible: true,
      motivo: '',
      modelo: respuesta.modelo || '',
      lineas,
    };
  } catch {
    return {
      disponible: false,
      motivo: 'Sin conexión con el motor local. El manifiesto sigue en blanco para escribirlo a mano.',
      modelo: '',
      lineas: plantillaManifiesto(),
    };
  }
}

function escapeXml(valor: string): string {
  return valor.replace(/[&<>"']/g, (caracter) => {
    if (caracter === '&') return '&amp;';
    if (caracter === '<') return '&lt;';
    if (caracter === '>') return '&gt;';
    if (caracter === '"') return '&quot;';
    return '&#39;';
  });
}

function base64Utf8(texto: string): string {
  const bytes = new TextEncoder().encode(texto);
  let binario = '';
  for (let indice = 0; indice < bytes.length; indice += 0x8000) {
    binario += String.fromCharCode(...bytes.subarray(indice, indice + 0x8000));
  }
  return btoa(binario);
}

function recorteValido(valor: unknown): { x: number; y: number; w: number; h: number } {
  if (typeof valor !== 'object' || valor === null) return { x: 0, y: 0, w: 1, h: 1 };
  const recorte = valor as Record<string, unknown>;
  const numero = (dato: unknown, fallback: number) => typeof dato === 'number' && Number.isFinite(dato) ? dato : fallback;
  return {
    x: numero(recorte.x, 0),
    y: numero(recorte.y, 0),
    w: Math.max(0.0001, numero(recorte.w, 1)),
    h: Math.max(0.0001, numero(recorte.h, 1)),
  };
}

/**
 * Convierte una tirada en un SVG autocontenido. Solo incrusta imágenes locales
 * (`data:`); una fuente sin imagen se pinta como bloque tipográfico.
 */
export function collageASvg(
  datos: EntropiaDatos,
  fuentes: readonly FuenteEntropia[],
  fondo = '#faf8f3',
): string {
  const porId = new Map(fuentes.map((fuente) => [fuente.id, fuente]));
  const ancho = Math.max(1, datos.ancho);
  const alto = Math.max(1, datos.alto);
  const defs: string[] = [];
  const cuerpo: string[] = [];
  const piezas = [...datos.disposicion].sort((a, b) => a.z - b.z);

  piezas.forEach((pieza, indice) => {
    const fuente = porId.get(pieza.id);
    const recorte = recorteValido(pieza.recorte);
    const rotacion = Number.isFinite(pieza.rot) ? pieza.rot : 0;
    const clipId = `c${indice}`;
    const src = fuente?.imagen?.src ?? '';
    const esImagen = /^data:image\/[a-z0-9.+-]+;base64,/i.test(src);

    cuerpo.push(`<g transform="translate(${pieza.x} ${pieza.y}) rotate(${rotacion} ${pieza.w / 2} ${pieza.h / 2})">`);
    if (esImagen) {
      defs.push(`<clipPath id="${clipId}"><rect width="${pieza.w}" height="${pieza.h}"/></clipPath>`);
      cuerpo.push(`<g clip-path="url(#${clipId})">`);
      cuerpo.push(
        `<image href="${escapeXml(src)}" x="${-recorte.x / recorte.w * pieza.w}" y="${-recorte.y / recorte.h * pieza.h}"`
        + ` width="${pieza.w / recorte.w}" height="${pieza.h / recorte.h}" preserveAspectRatio="none"/>`,
      );
      cuerpo.push('</g>');
    } else {
      const nombre = escapeXml((fuente?.nombre || pieza.id).slice(0, 28));
      cuerpo.push(`<rect width="${pieza.w}" height="${pieza.h}" fill="#e9e5dc"/>`);
      cuerpo.push(
        `<text x="${pieza.w / 2}" y="${pieza.h / 2}" text-anchor="middle" dominant-baseline="middle"`
        + ` font-family="ui-monospace, monospace" font-size="${Math.max(9, Math.min(18, pieza.h / 5))}" fill="#111">${nombre}</text>`,
      );
    }
    cuerpo.push('</g>');
  });

  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${ancho} ${alto}" width="${ancho}" height="${alto}">`
    + `<rect width="${ancho}" height="${alto}" fill="${escapeXml(fondo)}"/>`
    + (defs.length ? `<defs>${defs.join('')}</defs>` : '')
    + cuerpo.join('')
    + '</svg>';
}

export function collageADataUrl(
  datos: EntropiaDatos,
  fuentes: readonly FuenteEntropia[],
): string {
  return `data:image/svg+xml;base64,${base64Utf8(collageASvg(datos, fuentes))}`;
}

export interface MarcoManifiesto {
  frame: BoardCard;
  cards: BoardCard[];
}

export interface OpcionesMarcoManifiesto {
  x: number;
  y: number;
  fuentes: readonly FuenteEntropia[];
  ancho?: number;
  alto?: number;
  ahora?: Date;
}

function fechaCorta(fecha: Date): string {
  return fecha.toISOString().slice(0, 10);
}

/**
 * Crea el marco nuevo en vista Archivo: una nota fija con el manifiesto y un
 * bloque por collage. La etiqueta de cada bloque conserva el código de la semilla.
 */
export function crearMarcoManifiesto(
  seleccion: SeleccionManifiesto,
  lineas: readonly string[],
  opciones: OpcionesMarcoManifiesto,
): MarcoManifiesto {
  const fecha = fechaCorta(opciones.ahora ?? new Date());
  const ancho = opciones.ancho ?? 620;
  const alto = opciones.alto ?? 460;

  const nota: BoardCard = {
    id: newBoardId('card'),
    type: 'note',
    title: `Manifiesto semanal · ${fecha}`,
    body: lineas.join('\n'),
    x: opciones.x + 20,
    y: opciones.y + 20,
    width: 280,
    color: 'paper',
  };

  const hijos: string[] = [nota.id];
  const cards: BoardCard[] = [nota];

  seleccion.collages.forEach((collage, indice) => {
    const etiqueta: BoardCard = {
      id: newBoardId('card'),
      type: 'etiqueta',
      title: `Collage ${String(indice + 1).padStart(2, '0')}`,
      body: `semilla ${collage.semilla}`,
      x: opciones.x + 20,
      y: opciones.y + 20,
      width: 240,
      color: 'sand',
    };
    const media: BoardCard = {
      id: newBoardId('card'),
      type: 'media',
      title: collage.titulo,
      body: [collage.reglaNombre || collage.regla, collage.restriccion].filter(Boolean).join(' · '),
      x: opciones.x + 20,
      y: opciones.y + 20,
      width: 290,
      color: 'paper',
      media: {
        name: `manifiesto-${String(indice + 1).padStart(2, '0')}-${collage.semilla}.svg`,
        mimeType: 'image/svg+xml',
        dataUrl: collageADataUrl(collage.datos, opciones.fuentes),
        kind: 'image',
      },
    };
    hijos.push(etiqueta.id, media.id);
    cards.push(etiqueta, media);
  });

  const frame: BoardCard = {
    id: newBoardId('card'),
    type: 'marco',
    title: `Manifiesto · ${fecha}${seleccion.collages.length ? ` · ${seleccion.collages.length} collages` : ''}`,
    body: '',
    x: opciones.x,
    y: opciones.y,
    width: ancho,
    color: 'paper',
    datos: { alto, hijos, vista: 'archivo' },
  };

  return { frame, cards: [...cards, frame] };
}
