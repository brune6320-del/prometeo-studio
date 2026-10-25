import type { BoardCard } from './model';

/**
 * Metadatos públicos de una URL. Los obtiene el backend local (open graph),
 * así la clave y la red viven fuera del navegador y del tablero.
 */
export interface VistaPrevia {
  url: string;
  titulo: string;
  descripcion: string;
  imagen: string;
  sitio: string;
  obtenida: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function texto(value: unknown, max: number): string {
  return typeof value === 'string' ? value.slice(0, max).trim() : '';
}

function urlSegura(value: string): string {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' || url.protocol === 'http:' ? url.toString() : '';
  } catch {
    return '';
  }
}

export function normalizarVistaPrevia(value: unknown, url: string): VistaPrevia | undefined {
  if (!isRecord(value)) return undefined;
  const imagen = urlSegura(texto(value.imagen, 2048));
  const titulo = texto(value.titulo, 300);
  const descripcion = texto(value.descripcion, 600);
  if (!titulo && !descripcion && !imagen) return undefined;
  let sitio = '';
  try {
    sitio = new URL(url).hostname.replace(/^www\./, '');
  } catch {
    sitio = '';
  }
  return {
    url,
    titulo,
    descripcion,
    imagen,
    sitio,
    obtenida: new Date().toISOString(),
  };
}

export function leerVistaPrevia(card: BoardCard): VistaPrevia | undefined {
  const raw = isRecord(card.datos) ? card.datos : {};
  return normalizarVistaPrevia(raw.vistaPrevia, card.url ?? '');
}
