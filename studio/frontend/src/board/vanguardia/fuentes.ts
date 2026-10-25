import { leerReferente } from '../referentes/model';
import type { FuenteEntropia } from './entropia';

/** De dónde salió la imagen que se pintó en una pieza del collage. */
export type ProcedenciaImagen = 'referente' | 'marco' | 'tablero' | 'tipografico';

export interface TableroEntropia {
  id: string;
  title: string;
  /** Tarjetas sin normalizar: el export JSON es la fuente y puede venir de otra versión. */
  cards: readonly unknown[];
}

export interface FuentesProyecto {
  fuentes: FuenteEntropia[];
  /** Procedencia de la imagen de cada fuente, por id de tarjeta. */
  procedencia: Record<string, ProcedenciaImagen>;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function texto(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

function esImagenLocal(value: unknown): value is string {
  return typeof value === 'string' && /^data:image\/[a-z0-9.+-]+;base64,/i.test(value);
}

interface TarjetaImagen {
  id: string;
  src: string;
  nombre: string;
}

/** Una tarjeta media con imagen incrustada; no se descarga nada de la red. */
function tarjetaImagen(card: unknown): TarjetaImagen | null {
  if (!isRecord(card) || card.type !== 'media' || !isRecord(card.media)) return null;
  const id = texto(card.id);
  const src = card.media.dataUrl;
  if (!id || !esImagenLocal(src)) return null;
  const mime = texto(card.media.mimeType).toLocaleLowerCase();
  if (mime && !mime.startsWith('image/')) return null;
  return {
    id,
    src,
    nombre: texto(card.media.name) || texto(card.title) || id,
  };
}

function hijosDeMarco(card: unknown): string[] {
  if (!isRecord(card) || card.type !== 'marco' || !isRecord(card.datos)) return [];
  const hijos = card.datos.hijos;
  if (!Array.isArray(hijos)) return [];
  return hijos.filter((id): id is string => typeof id === 'string' && id.length > 0);
}

function indiceLocal(ref: ReturnType<typeof leerReferente>): string | null {
  for (const imagen of ref.imagenes) {
    if (esImagenLocal(imagen.dataUrl)) return imagen.dataUrl;
  }
  return null;
}

/**
 * Convierte las tarjetas de un export en fuentes de Entropía.
 *
 * Orden de imagen, tal como pidió V-4:
 * 1. la imagen del propio referente;
 * 2. una tarjeta de imagen del mismo marco;
 * 3. una tarjeta de imagen del mismo tablero;
 * 4. bloque tipográfico.
 *
 * Solo acepta `data:image/...;base64`: no se descarga nada de internet.
 * Los ids repetidos entre tableros se quedan con la primera aparición.
 */
export function fuentesDeProyecto(tableros: readonly TableroEntropia[]): FuentesProyecto {
  const vistas = new Set<string>();
  const fuentes: FuenteEntropia[] = [];
  const procedencia: Record<string, ProcedenciaImagen> = {};

  for (const tablero of tableros) {
    const imagenes = tablero.cards.map(tarjetaImagen).filter((item): item is TarjetaImagen => Boolean(item));
    const marcoDe = new Map<string, string>();
    const hijosPorMarco = new Map<string, Set<string>>();
    for (const card of tablero.cards) {
      if (!isRecord(card) || card.type !== 'marco') continue;
      const marcoId = texto(card.id);
      if (!marcoId) continue;
      const hijos = new Set(hijosDeMarco(card));
      hijosPorMarco.set(marcoId, hijos);
      for (const hijo of hijos) {
        if (!marcoDe.has(hijo)) marcoDe.set(hijo, marcoId);
      }
    }

    const usadasEnMarco = new Map<string, number>();
    let usadasEnTablero = 0;

    for (const card of tablero.cards) {
      if (!isRecord(card) || card.type !== 'referente') continue;
      const id = texto(card.id);
      if (!id || vistas.has(id)) continue;
      vistas.add(id);
      const referente = leerReferente(card);
      const nombre = referente.nombre || texto(card.title) || id;
      const imagenPropia = indiceLocal(referente);

      if (imagenPropia) {
        fuentes.push({ id, nombre, etiquetas: referente.etiquetas, imagen: { src: imagenPropia, nombre: nombre || id } });
        procedencia[id] = 'referente';
        continue;
      }

      const marcoId = marcoDe.get(id);
      if (marcoId) {
        const hijos = hijosPorMarco.get(marcoId) ?? new Set<string>();
        const candidatas = imagenes.filter((imagen) => hijos.has(imagen.id) || marcoDe.get(imagen.id) === marcoId);
        if (candidatas.length) {
          const usadas = usadasEnMarco.get(marcoId) ?? 0;
          const imagen = candidatas[usadas % candidatas.length];
          usadasEnMarco.set(marcoId, usadas + 1);
          fuentes.push({ id, nombre, etiquetas: referente.etiquetas, imagen: { src: imagen.src, nombre: imagen.nombre } });
          procedencia[id] = 'marco';
          continue;
        }
      }

      if (imagenes.length) {
        const imagen = imagenes[usadasEnTablero % imagenes.length];
        usadasEnTablero += 1;
        fuentes.push({ id, nombre, etiquetas: referente.etiquetas, imagen: { src: imagen.src, nombre: imagen.nombre } });
        procedencia[id] = 'tablero';
        continue;
      }

      fuentes.push({ id, nombre, etiquetas: referente.etiquetas });
      procedencia[id] = 'tipografico';
    }
  }

  return { fuentes, procedencia };
}
