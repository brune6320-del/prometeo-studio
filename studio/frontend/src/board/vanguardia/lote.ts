import type { HerramientaFuente } from './combinador';
import {
  nuevaSemilla,
  tirarEntropia,
  type EntropiaDatos,
  type FuenteEntropia,
} from './entropia';
import type { Gustos } from './gustos';
import type { TamanoLienzo } from './reglas';
import { generador } from './semilla';

/** Tope del lote: un muro de más de 200 collages deja de ser una noche y pasa a ser un archivo. */
export const MAX_LOTE = 200;

export interface LoteOpciones {
  semillaBase: string;
  n: number;
  fuentes: readonly FuenteEntropia[];
  herramientas: readonly HerramientaFuente[];
  tamano: TamanoLienzo;
  gustos?: Gustos;
  /** Fijo en tests para que la tirada completa sea comparable. */
  creado?: string;
}

export interface LoteItem {
  indice: number;
  datos: EntropiaDatos;
}

/** Semilla derivada y estable: el lote 2026 siempre produce las mismas 50 semillas. */
export function semillaDeLote(base: string, indice: number): string {
  return nuevaSemilla(generador(`${base}:${indice}`));
}

/**
 * Crea n tiradas con semillas derivadas de `semillaBase`. No usa azar del
 * sistema: mismas fuentes, mismas herramientas y mismo n dan el mismo lote.
 */
export function crearLote(opciones: LoteOpciones): LoteItem[] {
  const n = Math.trunc(opciones.n);
  if (!Number.isFinite(n) || n < 1) throw new Error('El lote necesita al menos 1 collage.');
  if (n > MAX_LOTE) throw new Error(`El lote admite como máximo ${MAX_LOTE} collages.`);
  if (!opciones.semillaBase.trim()) throw new Error('El lote necesita una semilla.');

  const usadas = new Set<string>();
  const items: LoteItem[] = [];
  for (let indice = 0; indice < n; indice += 1) {
    let semilla = semillaDeLote(opciones.semillaBase, indice);
    let extra = 0;
    while (usadas.has(semilla)) {
      semilla = nuevaSemilla(generador(`${opciones.semillaBase}:${indice}:${extra}`));
      extra += 1;
    }
    usadas.add(semilla);
    const datos = tirarEntropia({
      semilla,
      fuentes: opciones.fuentes,
      herramientas: opciones.herramientas,
      tamano: opciones.tamano,
      ...(opciones.gustos ? { gustos: opciones.gustos } : {}),
      ...(opciones.creado ? { creado: opciones.creado } : {}),
    });
    items.push({ indice: indice + 1, datos });
  }
  return items;
}

/** Recorta un título a seis palabras, sin comillas ni saltos de línea. */
export function tituloCorto(value: string, fallback = 'Collage sin título'): string {
  const limpio = String(value ?? '')
    .replace(/[\r\n\t]+/g, ' ')
    .replace(/^[\s"'«»“”`]+|[\s"'«»“”`]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim();
  const palabras = limpio.split(' ').filter(Boolean).slice(0, 6);
  const titulo = palabras.join(' ');
  if (titulo) return titulo;
  return String(fallback).split(/\s+/).filter(Boolean).slice(0, 6).join(' ') || 'Collage sin título';
}

/** Título determinista para cuando no se pidió DeepSeek o la llamada falló. */
export function tituloDeRespaldo(datos: EntropiaDatos): string {
  return tituloCorto(`${datos.reglaNombre || datos.regla} · ${datos.restriccion}`, 'Collage sin título');
}
